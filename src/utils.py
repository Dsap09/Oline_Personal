"""
Utility functions untuk Oline bot.
Berisi parser tanggal Indonesia dan helper umum.
"""

import re
from datetime import datetime, timedelta
from typing import Optional


def parse_relative_date(text: str) -> Optional[str]:
    """
    Parse referensi tanggal relatif dalam bahasa Indonesia.
    Returns tanggal dalam format YYYY-MM-DD, atau None jika tidak ditemukan.
    """
    text_lower = text.lower().strip()
    today = datetime.now()

    # Hari ini
    if any(word in text_lower for word in ["hari ini", "sekarang", "saat ini"]):
        return today.strftime("%Y-%m-%d")

    # Kemarin
    if "kemarin" in text_lower or "kemaren" in text_lower:
        return (today - timedelta(days=1)).strftime("%Y-%m-%d")

    # Besok
    if "besok" in text_lower or "besuk" in text_lower:
        return (today + timedelta(days=1)).strftime("%Y-%m-%d")

    # Lusa
    if "lusa" in text_lower:
        return (today + timedelta(days=2)).strftime("%Y-%m-%d")

    # Mapping hari Indonesia ke index (Senin=0, Minggu=6)
    hari_map = {
        "senin": 0, "selasa": 1, "rabu": 2, "kamis": 3,
        "jumat": 4, "sabtu": 5, "minggu": 6,
    }

    for hari, target_day in hari_map.items():
        if hari in text_lower:
            current_day = today.weekday()
            days_ahead = target_day - current_day
            if days_ahead <= 0:
                days_ahead += 7
            return (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

    # Tanggal eksplisit: "tanggal 3 Agustus", "3 agustus 2026", dll
    bulan_map = {
        "januari": 1, "februari": 2, "maret": 3, "april": 4,
        "mei": 5, "juni": 6, "juli": 7, "agustus": 8,
        "september": 9, "oktober": 10, "november": 11, "desember": 12,
    }

    # Pattern: tanggal <angka> <bulan> [tahun]
    date_pattern = re.compile(
        r"(?:tanggal\s+)?(\d{1,2})\s+("
        + "|".join(bulan_map.keys())
        + r")(?:\s+(\d{4}))?",
        re.IGNORECASE,
    )
    match = date_pattern.search(text_lower)
    if match:
        day = int(match.group(1))
        month = bulan_map.get(match.group(2).lower(), 1)
        year = int(match.group(3)) if match.group(3) else today.year
        try:
            return datetime(year, month, day).strftime("%Y-%m-%d")
        except ValueError:
            return None

    return None


def format_date_indonesian(date_str: str) -> str:
    """
    Format tanggal YYYY-MM-DD ke format Indonesia readable.
    Contoh: "2026-07-29" -> "29 Juli 2026"
    """
    bulan_names = [
        "", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
        "Juli", "Agustus", "September", "Oktober", "November", "Desember",
    ]
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return f"{dt.day} {bulan_names[dt.month]} {dt.year}"
    except ValueError:
        return date_str


def truncate_text(text: str, max_length: int = 500) -> str:
    """Truncate text dengan ellipsis jika terlalu panjang."""
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."
