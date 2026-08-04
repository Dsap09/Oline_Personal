"""
Helper untuk akses Vercel KV (Redis REST API) via httpx.
Menyediakan fungsi untuk memori percakapan dan penyimpanan jurnal harian.
"""

import base64
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Optional


import httpx

logger = logging.getLogger(__name__)

# Prefix keys
MEMORY_PREFIX = "memory"
JOURNAL_PREFIX = "jurnal"
HISTORY_PREFIX = "history"
RATE_PREFIX = "rate"
USAGE_PREFIX = "gemini_usage"
GROQ_USAGE_PREFIX = "groq_usage"
TTS_PREFIX = "tts_usage"
PENDING_FILE_PREFIX = "pending_file"




def _get_kv_credentials() -> tuple[str, str]:
    """Mengambil credentials Upstash Redis / Vercel KV dari environment variables."""
    raw_url = os.environ.get("KV_REST_API_URL") or os.environ.get("UPSTASH_REDIS_REST_URL", "")
    raw_token = os.environ.get("KV_REST_API_TOKEN") or os.environ.get("UPSTASH_REDIS_REST_TOKEN", "")
    url = raw_url.strip().rstrip("/")
    token = raw_token.strip()
    return url, token


async def _kv_request(command: list[str]) -> dict | None:
    """
    Mengirim command Redis ke Vercel KV / Upstash Redis REST API.
    Menggunakan pipeline endpoint untuk single command.
    """
    kv_url, kv_token = _get_kv_credentials()
    if not kv_url or not kv_token:
        logger.warning("Vercel KV / Upstash Redis credentials not configured. Skipping KV operation.")
        return None

    url = f"{kv_url}/pipeline"
    headers = {
        "Authorization": f"Bearer {kv_token}",
        "Content-Type": "application/json",
    }
    payload = [command]

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            result = response.json()
            # Pipeline returns array of results
            if isinstance(result, list) and len(result) > 0:
                return result[0]
            return result
    except Exception as e:
        logger.error("KV operation error: %s", str(e))
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


# --- Groq Usage Tracking ---

async def save_groq_usage(chat_id: int, tokens: int) -> bool:
    """
    Menambahkan jumlah token terpakai hari ini untuk Groq API ke Vercel KV.
    Key format: groq_usage:<chat_id>:YYYY-MM-DD
    TTL 48 jam (172800 detik).
    """
    if tokens <= 0:
        return True

    date_str = datetime.now().strftime("%Y-%m-%d")
    key = f"{GROQ_USAGE_PREFIX}:{chat_id}:{date_str}"

    result = await _kv_request(["INCRBY", key, str(tokens)])
    if result is not None:
        await _kv_request(["EXPIRE", key, "172800"])
        return True
    return False


async def get_today_groq_usage(chat_id: int) -> int:
    """
    Mengambil total token Groq yang terpakai hari ini untuk chat_id tertentu.
    """
    date_str = datetime.now().strftime("%Y-%m-%d")
    key = f"{GROQ_USAGE_PREFIX}:{chat_id}:{date_str}"

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


async def check_rate_limit(chat_id: int, max_requests: int = 25) -> bool:
    """
    Rate limiting: maks `max_requests` pesan per menit per chat_id.
    Returns True jika masih dalam batas, False jika melebihi.
    """
    key = f"{RATE_PREFIX}:{chat_id}"

    result = await _kv_request(["INCR", key])
    if not result or "result" not in result:
        return True

    try:
        current_count = int(result["result"])
    except (ValueError, TypeError):
        return True

    # Jika pesan pertama di window ini, set TTL 60 detik
    if current_count == 1:
        await _kv_request(["EXPIRE", key, "60"])

    if current_count > max_requests:
        return False

    return True


# --- Pending File Cache for Telegram Uploads ---

async def save_pending_file(
    chat_id: int, file_name: str, file_bytes: bytes, mime_type: str
) -> bool:
    """
    Menyimpan file sementara yang baru diunggah pengguna ke KV.
    TTL 10 menit (600 detik).
    """
    key = f"{PENDING_FILE_PREFIX}:{chat_id}"
    b64_str = base64.b64encode(file_bytes).decode("utf-8")
    payload = json.dumps({
        "file_name": file_name,
        "mime_type": mime_type,
        "file_bytes": b64_str,
    })
    result = await _kv_request(["SET", key, payload, "EX", "600"])
    return result is not None


async def get_pending_file(chat_id: int) -> Optional[dict]:
    """
    Mengambil file sementara pengguna dari KV.
    """
    key = f"{PENDING_FILE_PREFIX}:{chat_id}"
    result = await _kv_request(["GET", key])
    if result and result.get("result"):
        try:
            data = json.loads(result["result"])
            data["file_bytes"] = base64.b64decode(data["file_bytes"])
            return data
        except Exception as e:
            logger.warning("Error reading pending file from KV: %s", str(e))
    return None


async def clear_pending_file(chat_id: int) -> bool:
    """
    Menghapus file sementara pengguna setelah diunggah ke Drive.
    """
    key = f"{PENDING_FILE_PREFIX}:{chat_id}"
    result = await _kv_request(["DEL", key])
    return result is not None


