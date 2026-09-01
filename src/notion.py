"""
Notion API Integration untuk Oline Bot.
Menyimpan catatan ke database Notion menggunakan REST API.
"""

import logging
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

NOTION_API_URL = "https://api.notion.com/v1/pages"


def extract_database_id(raw_id: str) -> str:
    """
    Ekstrak 32-karakter ID database Notion dari ID mentah atau URL link Notion.
    Contoh: 'https://app.notion.com/p/3ceec30101df806fa6ddf65ab5aa6e40?v=...' -> '3ceec30101df806fa6ddf65ab5aa6e40'
    """
    if not raw_id:
        return ""

    raw_clean = raw_id.strip()

    # Jika mengandung URL, ekstrak bagian hex id 32 karakter
    match = re.search(r"([a-fA-F0-9]{32})", raw_clean)
    if match:
        return match.group(1)

    # Cek format UUID dengan strip tanda hubung
    cleaned_uuid = raw_clean.replace("-", "")
    if len(cleaned_uuid) == 32:
        return cleaned_uuid

    return raw_clean


async def save_note_to_notion(
    title: str, content: str, category: str = "Umum"
) -> dict[str, Any]:
    """
    Menyimpan catatan baru ke Notion database.
    Return dictionary berisi status dan pesan respons.
    """
    api_key = os.environ.get("NOTION_API_KEY", "").strip()
    raw_db_id = os.environ.get("NOTION_DATABASE_ID", "").strip()
    database_id = extract_database_id(raw_db_id)

    if not api_key:
        return {"error": "NOTION_API_KEY belum dikonfigurasi di environment variables."}

    if not database_id:
        return {"error": "NOTION_DATABASE_ID belum dikonfigurasi atau format ID tidak valid."}

    if not title or not title.strip():
        return {"error": "Judul catatan tidak boleh kosong."}

    if not content or not content.strip():
        return {"error": "Isi catatan tidak boleh kosong."}

    wib = timezone(timedelta(hours=7))
    now_iso = datetime.now(wib).isoformat()

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }

    payload = {
        "parent": {"database_id": database_id},
        "properties": {
            "Title": {
                "title": [{"text": {"content": title.strip()}}]
            },
            "Kategori": {
                "select": {"name": (category or "Umum").strip()}
            },
            "Tanggal": {
                "date": {"start": now_iso}
            },
        },
        "children": [
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": content.strip()}}]
                },
            }
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(NOTION_API_URL, json=payload, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                page_url = data.get("url", "")
                return {
                    "status": "success",
                    "title": title.strip(),
                    "category": category.strip() if category else "Umum",
                    "message": f"Catatan '{title.strip()}' berhasil disimpan ke Notion.",
                    "url": page_url,
                }
            else:
                err_body = resp.text[:200]
                logger.error("Notion API error (Status %d): %s", resp.status_code, err_body)
                return {
                    "error": f"Gagal menyimpan ke Notion (Status {resp.status_code}): {err_body}"
                }
    except httpx.TimeoutException:
        return {"error": "Koneksi ke Notion API mengalami timeout (10 detik). Coba lagi nanti ya."}
    except Exception as e:
        logger.error("Error saving note to Notion: %s", str(e))
        return {"error": f"Gagal menghubungi Notion API: {str(e)}"}
