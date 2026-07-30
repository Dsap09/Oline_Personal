"""
Helper untuk akses Vercel KV (Redis REST API) via httpx.
Menyediakan fungsi untuk memori percakapan dan penyimpanan jurnal harian.
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# Vercel KV REST API credentials dari environment variables
KV_REST_API_URL = os.environ.get("KV_REST_API_URL", "")
KV_REST_API_TOKEN = os.environ.get("KV_REST_API_TOKEN", "")

# Prefix keys
MEMORY_PREFIX = "memory"
JOURNAL_PREFIX = "jurnal"
HISTORY_PREFIX = "history"
RATE_PREFIX = "rate"
USAGE_PREFIX = "gemini_usage"
TTS_PREFIX = "tts_usage"


async def _kv_request(command: list[str]) -> dict | None:
    """
    Mengirim command Redis ke Vercel KV REST API.
    Menggunakan pipeline endpoint untuk single command.
    """
    if not KV_REST_API_URL or not KV_REST_API_TOKEN:
        logger.warning("Vercel KV credentials not configured. Skipping KV operation.")
        return None

    url = f"{KV_REST_API_URL}/pipeline"
    headers = {
        "Authorization": f"Bearer {KV_REST_API_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = [command]

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            result = response.json()
            # Pipeline returns array of results
            if isinstance(result, list) and len(result) > 0:
                return result[0]
            return result
    except httpx.HTTPStatusError as e:
        logger.error("KV HTTP error: %s", e.response.status_code)
        return None
    except httpx.RequestError as e:
        logger.error("KV request error: %s", str(e))
        return None


# --- Memory Functions ---

async def get_memory(chat_id: int) -> str:
    """Mengambil ringkasan memori percakapan untuk chat_id tertentu."""
    key = f"{MEMORY_PREFIX}:{chat_id}"
    result = await _kv_request(["GET", key])
    if result and result.get("result"):
        return str(result["result"])
    return ""


async def save_memory(chat_id: int, memory_summary: str) -> bool:
    """
    Menyimpan ringkasan memori percakapan.
    Memori di-overwrite setiap kali diperbarui (ringkasan terbaru).
    TTL 30 hari (2592000 detik).
    """
    key = f"{MEMORY_PREFIX}:{chat_id}"
    result = await _kv_request(["SET", key, memory_summary, "EX", "2592000"])
    return result is not None


# --- Conversation History Functions ---

async def get_history(chat_id: int) -> list[dict]:
    """
    Mengambil riwayat percakapan terakhir (maks 15 pesan).
    Disimpan sebagai JSON string di KV.
    """
    key = f"{HISTORY_PREFIX}:{chat_id}"
    result = await _kv_request(["GET", key])
    if result and result.get("result"):
        try:
            data = result["result"]
            if isinstance(data, str):
                return json.loads(data)
            return data
        except (json.JSONDecodeError, TypeError):
            return []
    return []


async def save_history(chat_id: int, history: list[dict]) -> bool:
    """
    Menyimpan riwayat percakapan (maks 15 pesan terakhir).
    TTL 24 jam (86400 detik).
    """
    # Potong hanya 15 pesan terakhir
    trimmed = history[-15:]
    key = f"{HISTORY_PREFIX}:{chat_id}"
    result = await _kv_request(
        ["SET", key, json.dumps(trimmed, ensure_ascii=False), "EX", "86400"]
    )
    return result is not None


# --- Journal Functions ---

async def save_journal(chat_id: int, text: str, date_str: Optional[str] = None) -> bool:
    """
    Menyimpan entri jurnal harian.
    Key format: jurnal:<chat_id>:YYYY-MM-DD
    Jika sudah ada entri di hari yang sama, teks di-append.
    TTL 90 hari (7776000 detik).
    """
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")

    key = f"{JOURNAL_PREFIX}:{chat_id}:{date_str}"

    # Cek apakah sudah ada entri hari ini
    existing = await _kv_request(["GET", key])
    if existing and existing.get("result"):
        existing_text = str(existing["result"])
        text = existing_text + "\n---\n" + text

    result = await _kv_request(["SET", key, text, "EX", "7776000"])
    return result is not None


async def get_journal_entries(
    chat_id: int,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> dict[str, str]:
    """
    Mengambil entri jurnal dalam rentang tanggal.
    Default: 7 hari terakhir.
    Returns dict {tanggal: teks_jurnal}.
    """
    if end_date is None:
        end_dt = datetime.now()
    else:
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")

    if start_date is None:
        start_dt = end_dt - timedelta(days=6)
    else:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")

    entries: dict[str, str] = {}
    current = start_dt

    while current <= end_dt:
        date_key = current.strftime("%Y-%m-%d")
        key = f"{JOURNAL_PREFIX}:{chat_id}:{date_key}"
        result = await _kv_request(["GET", key])
        if result and result.get("result"):
            entries[date_key] = str(result["result"])
        current += timedelta(days=1)

    return entries


# --- Gemini Usage Tracking ---

async def save_usage(chat_id: int, tokens: int) -> bool:
    """
    Menambahkan jumlah token terpakai hari ini ke Vercel KV.
    Key format: gemini_usage:<chat_id>:YYYY-MM-DD
    Menggunakan INCRBY untuk operasi atomik.
    TTL 48 jam (172800 detik) agar key otomatis expired keesokan harinya.
    """
    if tokens <= 0:
        return True

    date_str = datetime.now().strftime("%Y-%m-%d")
    key = f"{USAGE_PREFIX}:{chat_id}:{date_str}"

    # INCRBY secara atomik menambahkan nilai (membuat key jika belum ada)
    result = await _kv_request(["INCRBY", key, str(tokens)])
    if result is not None:
        # Set TTL agar key auto-expire (tidak menumpuk selamanya)
        await _kv_request(["EXPIRE", key, "172800"])
        return True
    return False


async def get_today_usage(chat_id: int) -> int:
    """
    Mengambil total token yang terpakai hari ini untuk chat_id tertentu.
    Returns 0 jika belum ada data.
    """
    date_str = datetime.now().strftime("%Y-%m-%d")
    key = f"{USAGE_PREFIX}:{chat_id}:{date_str}"

    result = await _kv_request(["GET", key])
    if result and result.get("result"):
        try:
            return int(result["result"])
        except (ValueError, TypeError):
            return 0
    return 0


# --- ElevenLabs TTS Usage Tracking ---

async def save_tts_usage(chat_id: int, char_count: int) -> bool:
    """
    Menambahkan jumlah karakter TTS terpakai bulan ini ke Vercel KV.
    Key format: tts_usage:<chat_id>:YYYY-MM
    TTL 60 hari (5184000 detik).
    """
    if char_count <= 0:
        return True

    month_str = datetime.now().strftime("%Y-%m")
    key = f"{TTS_PREFIX}:{chat_id}:{month_str}"

    result = await _kv_request(["INCRBY", key, str(char_count)])
    if result is not None:
        await _kv_request(["EXPIRE", key, "5184000"])
        return True
    return False


async def get_monthly_tts_usage(chat_id: int) -> int:
    """
    Mengambil total karakter TTS terpakai bulan ini untuk chat_id tertentu.
    """
    month_str = datetime.now().strftime("%Y-%m")
    key = f"{TTS_PREFIX}:{chat_id}:{month_str}"

    result = await _kv_request(["GET", key])
    if result and result.get("result"):
        try:
            return int(result["result"])
        except (ValueError, TypeError):
            return 0
    return 0


# --- Rate Limiting ---

async def check_rate_limit(chat_id: int, max_requests: int = 15) -> bool:
    """
    Rate limiting sederhana: maks `max_requests` pesan per menit per chat_id.
    Returns True jika masih dalam batas, False jika melebihi.
    """
    key = f"{RATE_PREFIX}:{chat_id}"
    result = await _kv_request(["GET", key])

    current_count = 0
    if result and result.get("result"):
        try:
            current_count = int(result["result"])
        except (ValueError, TypeError):
            current_count = 0

    if current_count >= max_requests:
        return False

    # Increment counter dengan TTL 60 detik
    await _kv_request(["SET", key, str(current_count + 1), "EX", "60", "NX"])
    await _kv_request(["INCR", key])

    return True
