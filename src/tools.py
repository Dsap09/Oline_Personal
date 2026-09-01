"""
Tool definitions dan executor functions untuk Gemini Function Calling.
Mencakup: rekomendasi film (TMDb), rekomendasi musik (iTunes),
cuaca (OpenWeatherMap), dan jurnal harian (Vercel KV).
"""

import asyncio
import logging
import math
import os
from datetime import datetime
from typing import Any, Optional

import httpx
import requests

from src.kv import (
    get_journal_entries,
    get_monthly_tts_usage,
    get_today_groq_usage,
    get_today_usage,
    get_user_location,
    save_journal,
    save_tts_usage,
    save_user_location,
)


from src.notion import save_note_to_notion
from src.utils import format_date_indonesian, parse_relative_date
from src.voice import (
    generate_elevenlabs_tts,
    send_chat_action_record_voice,
    send_voice_note_to_telegram,
)

logger = logging.getLogger(__name__)

# API Keys dari environment
TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "")
OPENWEATHER_API_KEY = os.environ.get("OPENWEATHER_API_KEY", "")

# Base URLs
TMDB_BASE_URL = "https://api.themoviedb.org/3"
ITUNES_BASE_URL = "https://itunes.apple.com"
OPENWEATHER_BASE_URL = "https://api.openweathermap.org/data/2.5"
PISTON_EXECUTE_URL = "https://emkc.org/api/v2/piston/execute"


# ============================================================
# Gemini Function/Tool Declarations (untuk dikirim ke Gemini API)
# ============================================================

TOOL_DECLARATIONS = [
    {
        "name": "get_movie_recommendation",
        "description": (
            "Mencari dan merekomendasikan film berdasarkan genre, mood, "
            "atau kata kunci pencarian. Gunakan saat pengguna meminta "
            "rekomendasi film."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Kata kunci pencarian film (misal: 'horror indonesia', 'komedi romantis').",
                },
                "genre": {
                    "type": "string",
                    "description": "Genre film (misal: 'horror', 'comedy', 'action', 'drama'). Opsional.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_music_recommendation",
        "description": (
            "Mencari dan merekomendasikan lagu/musik berdasarkan genre, "
            "artis, atau kata kunci. Gunakan saat pengguna meminta "
            "rekomendasi lagu atau musik."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Kata kunci pencarian musik (misal: 'pop indonesia', 'lagu chill').",
                },
                "artist": {
                    "type": "string",
                    "description": "Nama artis spesifik (opsional).",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_weather_forecast",
        "description": (
            "Mengecek cuaca saat ini atau forecast untuk kota tertentu. "
            "Gunakan saat pengguna menanyakan kondisi cuaca."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "Nama kota (misal: 'Bandung', 'Jakarta', 'Yogyakarta').",
                },
                "date": {
                    "type": "string",
                    "description": (
                        "Tanggal cuaca yang ingin dicek dalam format YYYY-MM-DD. "
                        "Jika tidak disebutkan, gunakan hari ini."
                    ),
                },
            },
            "required": ["city"],
        },
    },
    {
        "name": "save_journal_entry",
        "description": (
            "Menyimpan catatan jurnal harian pengguna. Gunakan saat pengguna "
            "ingin mencatat jurnal, diary, atau hal yang ingin diingat hari ini."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Isi catatan jurnal yang ingin disimpan.",
                },
                "date": {
                    "type": "string",
                    "description": "Tanggal jurnal (format YYYY-MM-DD). Default hari ini jika tidak disebutkan.",
                },
            },
            "required": ["text"],
        },
    },
    {
        "name": "get_journal_recap",
        "description": (
            "Mengambil rekap atau catatan jurnal sebelumnya. Gunakan saat "
            "pengguna meminta rekap jurnal, melihat catatan sebelumnya, "
            "atau bertanya apa yang ditulis pada tanggal tertentu."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "start_date": {
                    "type": "string",
                    "description": "Tanggal awal rentang (YYYY-MM-DD). Default 7 hari lalu.",
                },
                "end_date": {
                    "type": "string",
                    "description": "Tanggal akhir rentang (YYYY-MM-DD). Default hari ini.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "check_quota",
        "description": (
            "Mengecek sisa kuota token dan pemakaian API hari ini (Gemini API & Groq API). "
            "Gunakan saat pengguna bertanya tentang kuota, sisa token, "
            "pemakaian API, atau berapa banyak token yang sudah terpakai hari ini."
        ),

        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "send_voice_message",
        "description": (
            "Mengirim pesan suara (voice note) ketika pengguna meminta Oline "
            "bernyanyi, membaca puisi, menggombal dengan suara, atau mengucapkan sesuatu dengan suara."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Teks kalimat, lirik, atau puisi yang akan diucapkan Oline dengan suara.",
                },
            },
            "required": ["text"],
        },
    },
    {
        "name": "search_internet",
        "description": (
            "Cari informasi terkini di internet. Gunakan saat pengguna bertanya "
            "hal yang memerlukan data real-time, berita, fakta terbaru, definisi, "
            "atau informasi di luar pengetahuan umum yang kamu miliki."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Kata kunci pencarian yang ingin dicari di internet.",
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_stock_price",
        "description": (
            "Ambil harga terkini dan perubahan harian suatu saham Indonesia. "
            "Kode saham 4 huruf (contoh: BBCA, BBRI, TLKM)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Kode saham 4 huruf, tanpa .JK (misal: BBCA, TLKM, BBRI).",
                }
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "create_drive_folder",
        "description": (
            "Membuat folder baru di Google Drive (Database Oline). "
            "Gunakan saat pengguna meminta membuat folder baru di drive/database."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "folder_name": {
                    "type": "string",
                    "description": "Nama folder baru yang ingin dibuat.",
                }
            },
            "required": ["folder_name"],
        },
    },
    {
        "name": "list_drive_files",
        "description": (
            "Melihat daftar isi file dan folder di Google Drive (Database Oline). "
            "Gunakan saat pengguna meminta tampilkan isi folder, lihat daftar file, atau isi database."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "folder_name": {
                    "type": "string",
                    "description": "Nama subfolder yang ingin dilihat isinya (opsional). Jika kosong, tampilkan root database.",
                }
            },
            "required": [],
        },
    },
    {
        "name": "search_drive_files",
        "description": (
            "Mencari file berdasarkan nama di Google Drive (Database Oline). "
            "Gunakan saat pengguna mencari file spesifik."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Kata kunci atau nama file yang dicari.",
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": "upload_to_drive",
        "description": (
            "Menyimpan file/dokumen/foto yang baru diterima dari pengguna ke Google Drive. "
            "Gunakan saat pengguna meminta menyimpan file/foto ke folder atau database."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "folder_name": {
                    "type": "string",
                    "description": "Nama subfolder tempat menyimpan file (opsional).",
                }
            },
            "required": [],
        },
    },
    {
        "name": "download_from_drive",
        "description": (
            "Mengambil dan mengirimkan file/foto dari Google Drive kembali ke pengguna di Telegram. "
            "Gunakan saat pengguna meminta kirim file, minta foto, atau download dari drive."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "file_name": {
                    "type": "string",
                    "description": "Nama file atau foto yang ingin dikirimkan.",
                },
                "folder_name": {
                    "type": "string",
                    "description": "Nama subfolder tempat file tersimpan (opsional).",
                },
            },
            "required": ["file_name"],
        },
    },
    {
        "name": "get_nearby_places",
        "description": (
            "Mencari tempat terdekat dari lokasi pengguna yang tersimpan, "
            "berdasarkan kategori (misal: cafe, toko buku, restoran, mall)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Kategori tempat, misal 'cafe', 'restaurant', 'bookstore', 'mall', 'toko buku'.",
                },
                "radius_km": {
                    "type": "number",
                    "description": "Radius pencarian dalam kilometer. Default 2.0.",
                },
            },
            "required": ["category"],
        },
    },
    {
        "name": "search_places_by_city",
        "description": (
            "Mencari tempat berdasarkan nama kota/area dan kategori. "
            "Menggunakan geocoding untuk mendapatkan koordinat kota."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "Nama kota atau area (misal: 'Surabaya', 'Bandung', 'Jakarta Selatan').",
                },
                "category": {
                    "type": "string",
                    "description": "Kategori tempat, misal 'toko buku', 'cafe', 'restoran', 'mall'.",
                },
            },
            "required": ["city", "category"],
        },
    },
    {
        "name": "execute_code",
        "description": (
            "Jalankan potongan kode menggunakan Piston API. Dukung banyak bahasa. "
            "Gunakan saat pengguna meminta mengeksekusi atau menjalankan kode."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "language": {
                    "type": "string",
                    "description": "Bahasa pemrograman, misal: python, javascript, cpp, java, dll.",
                },
                "code": {
                    "type": "string",
                    "description": "Kode sumber yang akan dijalankan.",
                },
            },
            "required": ["language", "code"],
        },
    },
    {
        "name": "save_note_to_notion",
        "description": "Menyimpan catatan ke Notion database.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Judul catatan.",
                },
                "content": {
                    "type": "string",
                    "description": "Isi catatan.",
                },
                "category": {
                    "type": "string",
                    "description": "Kategori catatan (opsional, misal: 'Umum', 'Skripsi', 'Riset', 'Pribadi'). Default: Umum.",
                },
            },
            "required": ["title", "content"],
        },
    },
]

TOOLS_BY_INTENT = {
    "cuaca": ["get_weather_forecast"],
    "rekomendasi": ["get_movie_recommendation", "get_music_recommendation"],
    "suara": ["send_voice_message"],
    "jurnal": ["save_journal_entry", "get_journal_recap"],
    "kuota": ["check_quota"],
    "search": ["search_internet"],
    "saham": ["get_stock_price", "get_market_summary"],
    "drive": [
        "create_drive_folder",
        "list_drive_files",
        "search_drive_files",
        "upload_to_drive",
        "download_from_drive",
    ],
    "lokasi": ["get_nearby_places", "search_places_by_city"],
    "coding": ["execute_code"],
    "notion": ["save_note_to_notion"],
}




def get_tools_for_intent(intent: Optional[str]) -> list[dict]:
    """
    Mengembalikan deklarasi tool yang terfilter sesuai intent pengguna.
    Jika intent None (Fast Path), mengembalikan list kosong [].
    """
    if not intent:
        return []

    allowed_names = set(TOOLS_BY_INTENT.get(intent, []))
    if not allowed_names:
        return []

    return [decl for decl in TOOL_DECLARATIONS if decl["name"] in allowed_names]


# ============================================================
# Tool Executor Functions
# ============================================================



async def get_movie_recommendation(
    query: str, genre: Optional[str] = None
) -> dict[str, Any]:
    """Mencari film di TMDb API berdasarkan query dan genre."""
    if not TMDB_API_KEY:
        return {"error": "TMDb API key tidak dikonfigurasi."}

    # Genre mapping TMDb
    genre_map = {
        "action": 28, "adventure": 12, "animation": 16, "comedy": 35,
        "crime": 80, "documentary": 99, "drama": 18, "family": 10751,
        "fantasy": 14, "history": 36, "horror": 27, "music": 10402,
        "mystery": 9648, "romance": 10749, "sci-fi": 878, "thriller": 53,
        "war": 10752, "western": 37, "komedi": 35, "horor": 27,
        "aksi": 28, "petualangan": 12, "animasi": 16, "dokumenter": 99,
        "keluarga": 10751, "fantasi": 14, "sejarah": 36, "misteri": 9648,
        "romantis": 10749, "perang": 10752,
    }

    params: dict[str, Any] = {
        "api_key": TMDB_API_KEY,
        "language": "id-ID",
        "query": query,
        "page": 1,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Coba search dulu
            response = await client.get(
                f"{TMDB_BASE_URL}/search/movie", params=params
            )
            response.raise_for_status()
            data = response.json()

            results = data.get("results", [])

            # Coba deteksi genre dari query jika genre belum diisi
            target_genre = genre
            if not target_genre:
                for g_name in genre_map:
                    if g_name in query.lower():
                        target_genre = g_name
                        break

            # Jika search kosong, coba discover berdasarkan genre
            if not results and target_genre:
                genre_id = genre_map.get(target_genre.lower())
                if genre_id:
                    discover_params: dict[str, Any] = {
                        "api_key": TMDB_API_KEY,
                        "language": "id-ID",
                        "with_genres": genre_id,
                        "sort_by": "popularity.desc",
                        "page": 1,
                    }
                    response = await client.get(
                        f"{TMDB_BASE_URL}/discover/movie", params=discover_params
                    )
                    response.raise_for_status()
                    data = response.json()
                    results = data.get("results", [])

            # Ambil top 5
            movies = []
            for movie in results[:5]:
                movies.append({
                    "title": movie.get("title", "Unknown"),
                    "original_title": movie.get("original_title", ""),
                    "year": movie.get("release_date", "")[:4],
                    "rating": movie.get("vote_average", 0),
                    "overview": movie.get("overview", "")[:200],
                })

            if not movies:
                return {"message": "Tidak ditemukan film yang cocok dengan pencarian."}

            return {"movies": movies, "total_results": data.get("total_results", 0)}

    except httpx.HTTPStatusError as e:
        logger.error("TMDb HTTP error: %s", e.response.status_code)
        if e.response.status_code == 401:
            return {"error": "TMDb API key tidak valid atau belum diaktifkan."}
        return {"error": f"Gagal mengakses TMDb API (Status {e.response.status_code})."}
    except httpx.RequestError as e:
        logger.error("TMDb API error: %s", str(e))
        return {"error": f"Gagal mengakses TMDb API: {str(e)}"}


async def get_music_recommendation(
    query: str, artist: Optional[str] = None
) -> dict[str, Any]:
    """Mencari lagu di iTunes Search API berdasarkan query dan artis."""
    search_term = query
    if artist:
        search_term = f"{artist} {query}"

    params = {
        "term": search_term,
        "media": "music",
        "entity": "song",
        "limit": 5,
        "country": "ID",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{ITUNES_BASE_URL}/search", params=params)
            response.raise_for_status()
            data = response.json()

            results = data.get("results", [])
            songs = []
            for track in results:
                songs.append({
                    "title": track.get("trackName", "Unknown"),
                    "artist": track.get("artistName", "Unknown"),
                    "album": track.get("collectionName", ""),
                    "genre": track.get("primaryGenreName", ""),
                    "preview_url": track.get("previewUrl", ""),
                    "track_url": track.get("trackViewUrl", ""),
                })

            if not songs:
                return {"message": "Tidak ditemukan lagu yang cocok dengan pencarian."}

            return {"songs": songs}

    except httpx.RequestError as e:
        logger.error("iTunes API error: %s", str(e))
        return {"error": f"Gagal mengakses iTunes API: {str(e)}"}


async def get_weather_forecast(
    city: str, date: Optional[str] = None
) -> dict[str, Any]:
    """
    Mengecek cuaca untuk kota tertentu via OpenWeatherMap API.
    Mendukung cuaca saat ini dan forecast hingga 5 hari ke depan.
    """
    if not OPENWEATHER_API_KEY:
        return {"error": "OpenWeatherMap API key tidak dikonfigurasi."}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Ambil forecast 5 hari
            params: dict[str, Any] = {
                "q": city,
                "appid": OPENWEATHER_API_KEY,
                "units": "metric",
                "lang": "id",
            }

            # Jika tanggal hari ini atau tidak disebut, gunakan current weather
            target_date = date or datetime.now().strftime("%Y-%m-%d")
            today_str = datetime.now().strftime("%Y-%m-%d")

            if target_date == today_str:
                response = await client.get(
                    f"{OPENWEATHER_BASE_URL}/weather", params=params
                )
                response.raise_for_status()
                data = response.json()

                return {
                    "city": data.get("name", city),
                    "date": format_date_indonesian(today_str),
                    "temp": data["main"]["temp"],
                    "temp_min": data["main"]["temp_min"],
                    "temp_max": data["main"]["temp_max"],
                    "humidity": data["main"]["humidity"],
                    "condition": data["weather"][0]["description"],
                    "wind_speed": data["wind"]["speed"],
                }
            else:
                # Gunakan forecast
                response = await client.get(
                    f"{OPENWEATHER_BASE_URL}/forecast", params=params
                )
                response.raise_for_status()
                data = response.json()

                # Cari forecast untuk tanggal target
                target_forecasts = []
                for item in data.get("list", []):
                    item_date = item["dt_txt"][:10]
                    if item_date == target_date:
                        target_forecasts.append(item)

                if not target_forecasts:
                    return {
                        "error": (
                            f"Data cuaca untuk tanggal {format_date_indonesian(target_date)} "
                            "belum tersedia. Forecast hanya tersedia hingga 5 hari ke depan."
                        )
                    }

                # Ambil rata-rata dari forecasts hari itu
                temps = [f["main"]["temp"] for f in target_forecasts]
                humidity = [f["main"]["humidity"] for f in target_forecasts]
                conditions = [f["weather"][0]["description"] for f in target_forecasts]
                winds = [f["wind"]["speed"] for f in target_forecasts]

                # Kondisi cuaca paling sering muncul
                most_common_condition = max(set(conditions), key=conditions.count)

                return {
                    "city": data.get("city", {}).get("name", city),
                    "date": format_date_indonesian(target_date),
                    "temp": round(sum(temps) / len(temps), 1),
                    "temp_min": round(min(temps), 1),
                    "temp_max": round(max(temps), 1),
                    "humidity": round(sum(humidity) / len(humidity)),
                    "condition": most_common_condition,
                    "wind_speed": round(sum(winds) / len(winds), 1),
                }

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return {"error": f"Kota '{city}' tidak ditemukan. Coba nama kota lain ya."}
        logger.error("OpenWeatherMap HTTP error: %s", e.response.status_code)
        return {"error": "Gagal mengakses data cuaca."}
    except httpx.RequestError as e:
        logger.error("OpenWeatherMap request error: %s", str(e))
        return {"error": f"Gagal mengakses OpenWeatherMap API: {str(e)}"}


async def execute_save_journal(chat_id: int, text: str, date: Optional[str] = None) -> dict[str, Any]:
    """Menyimpan entri jurnal harian ke Vercel KV."""
    journal_date = date or datetime.now().strftime("%Y-%m-%d")
    success = await save_journal(chat_id, text, journal_date)

    if success:
        return {
            "status": "saved",
            "date": format_date_indonesian(journal_date),
            "message": "Jurnal berhasil disimpan.",
        }
    else:
        return {"error": "Gagal menyimpan jurnal. Coba lagi nanti ya."}


async def execute_get_journal_recap(
    chat_id: int,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> dict[str, Any]:
    """Mengambil rekap jurnal dari Vercel KV."""
    entries = await get_journal_entries(chat_id, start_date, end_date)

    if not entries:
        return {"message": "Belum ada catatan jurnal di rentang tanggal tersebut."}

    formatted = {}
    for date_key, text in entries.items():
        formatted[format_date_indonesian(date_key)] = text

    return {"entries": formatted, "total_entries": len(formatted)}


async def execute_check_quota(chat_id: int) -> dict[str, Any]:
    """
    Mengecek pemakaian token API (Gemini & Groq) hari ini dan menghitung sisa kuota.
    Gemini daily limit: 1.000.000 token (1.500 req/hari).
    Groq daily limit: 14.400.000 token (14.400 req/hari).
    """
    GEMINI_LIMIT = 1_000_000
    GROQ_LIMIT = 14_400_000

    gemini_used = await get_today_usage(chat_id)
    groq_used = await get_today_groq_usage(chat_id)

    gemini_remaining = max(0, GEMINI_LIMIT - gemini_used)
    groq_remaining = max(0, GROQ_LIMIT - groq_used)

    return {
        "date": format_date_indonesian(datetime.now().strftime("%Y-%m-%d")),
        "groq_fast_path": (
            f"⚡ Groq API (Fast Path / Sapaan): {groq_used:,} / {GROQ_LIMIT:,} token "
            f"({round((groq_used / GROQ_LIMIT) * 100, 1)}%), sisa {groq_remaining:,} token"
        ),
        "gemini_slow_path": (
            f"🛠️ Gemini API (Slow Path / Tools): {gemini_used:,} / {GEMINI_LIMIT:,} token "
            f"({round((gemini_used / GEMINI_LIMIT) * 100, 1)}%), sisa {gemini_remaining:,} token"
        ),
        "groq_tokens_used": groq_used,
        "groq_tokens_remaining": groq_remaining,
        "groq_daily_limit": GROQ_LIMIT,
        "gemini_tokens_used": gemini_used,
        "gemini_tokens_remaining": gemini_remaining,
        "gemini_daily_limit": GEMINI_LIMIT,
        "total_tokens_used_today": gemini_used + groq_used,
        "note": "WAJIB tampilkan sisa kuota kedua API (Groq Fast Path dan Gemini Slow Path) secara terpisah di baris berbeda.",
    }




async def execute_send_voice_message(chat_id: int, text: str) -> dict[str, Any]:
    """
    Mengirim pesan suara (voice note) dengan suara ElevenLabs TTS.
    Memeriksa kuota gratis bulanan (10.000 karakter/bulan).
    """
    MONTHLY_CHAR_LIMIT = 10_000

    if not text or not text.strip():
        return {"error": "Teks untuk voice message kosong."}

    char_count = len(text)

    # 1. Cek kuota bulanan
    used_chars = await get_monthly_tts_usage(chat_id)
    if used_chars + char_count > MONTHLY_CHAR_LIMIT:
        return {
            "quota_exceeded": True,
            "message": (
                "Aduh, suara Oline bulan ini udah abis, bestie. "
                "Tunggu bulan depan ya, atau kita ngobrol teks aja dulu~ 😘"
            ),
        }

    # 2. Kirim chat action "record_voice" agar Telegram menampilkan indikator merekam
    await send_chat_action_record_voice(chat_id)

    # 3. Generate audio via ElevenLabs
    try:
        audio_bytes = await generate_elevenlabs_tts(text)
    except Exception as e:
        logger.error("Failed to generate TTS: %s", str(e))
        return {
            "error": "Failed to generate TTS audio",
            "message": f"Aduh, maaf ya, Oline lagi gagu nih 😅 Gagal bikin suaranya ({str(e)}).",
        }

    # 4. Simpan pemakaian karakter ke KV
    await save_tts_usage(chat_id, char_count)

    # 5. Kirim voice note ke Telegram
    sent = await send_voice_note_to_telegram(
        chat_id=chat_id,
        audio_bytes=audio_bytes,
        caption="🎙️ dari Oline, spesial buat kamu~",
    )

    if sent:
        return {
            "status": "success",
            "text": text,
            "message": "Voice note berhasil dikirim langsung ke chat Telegram pengguna.",
        }
    else:
        return {
            "error": "Failed to send voice to Telegram",
            "message": "Gagal mengirimkan voice note ke Telegram 😢 Coba lagi nanti ya.",
        }


async def search_internet(query: str) -> dict[str, Any]:
    """
    Mencari informasi terkini di internet menggunakan DDGS (DuckDuckGo Search).
    """
    try:
        def _do_search():
            try:
                from ddgs import DDGS
            except ImportError:
                from duckduckgo_search import DDGS

            with DDGS() as ddgs:
                return list(ddgs.text(query, max_results=5))

        results = await asyncio.to_thread(_do_search)
        await asyncio.sleep(2)

        if not results:
            return {"message": "Oline gak nemu info yang cocok nih, bestie."}

        snippets = []
        for r in results:
            title = r.get("title", "")
            body = r.get("body", "")
            href = r.get("href", "")
            if title and body:
                snippets.append(f"{title}: {body} (Sumber: {href})")
            elif title or body:
                snippets.append(f"{title or body} (Sumber: {href})")

        return {"results": "\n".join(snippets)}
    except Exception as e:
        logger.error("DuckDuckGo search error: %s", str(e))
        return {"error": "Aduh, Oline lagi gak bisa akses internet nih. Coba lagi nanti ya~"}


def _get_top_movers(is_gainer: bool = True, limit: int = 3) -> str:
    """Ambil top gainer atau loser dari saham populer IHSG, dengan fallback."""
    import yfinance as yf
    try:
        tickers = ['BBCA', 'BBRI', 'TLKM', 'ASII', 'UNVR', 'ADRO', 'ANTM', 'ICBP']
        movers = []
        for t in tickers:
            stock = yf.Ticker(t + '.JK')
            data = stock.history(period='1d')
            if not data.empty:
                close = float(data['Close'].iloc[-1])
                prev = float(stock.info.get('previousClose', close))
                pct = ((close - prev) / prev) * 100 if prev else 0.0
                movers.append((t, pct))
        movers.sort(key=lambda x: x[1], reverse=is_gainer)
        return ", ".join([f"{m[0]} ({'+' if m[1]>=0 else ''}{m[1]:.1f}%)" for m in movers[:limit]])
    except Exception as e:
        logger.warning("Error fetching top movers: %s", str(e))
        return ""


async def get_stock_price(ticker: str) -> dict[str, Any]:
    """
    Mengecek harga terkini dan perubahan harian suatu saham Indonesia via yfinance.
    """
    import yfinance as yf
    import time

    ticker_clean = ticker.upper().strip()
    full_ticker = ticker_clean
    if not full_ticker.endswith('.JK') and full_ticker.isalpha() and len(full_ticker) == 4:
        full_ticker += '.JK'

    def _fetch():
        time.sleep(0.5)
        stock = yf.Ticker(full_ticker)
        data = stock.history(period='1d')
        if data.empty:
            return {"error": f"Data {ticker_clean} kosong. Mungkin kode salah atau market lagi tutup ya~"}

        latest = float(data['Close'].iloc[-1])
        prev_close = float(stock.info.get('previousClose', latest))
        change = latest - prev_close
        change_pct = (change / prev_close) * 100 if prev_close else 0.0

        formatted = (
            f"{ticker_clean} sekarang Rp {latest:,.0f} "
            f"({'📈 +' if change >= 0 else '📉 '}{change:,.0f}, "
            f"{'+' if change >= 0 else ''}{change_pct:.2f}%)"
        )
        return {
            "ticker": ticker_clean,
            "latest_price": latest,
            "prev_close": prev_close,
            "change": change,
            "change_pct": change_pct,
            "formatted_result": formatted,
        }

    try:
        return await asyncio.to_thread(_fetch)
    except Exception as e:
        logger.error("Error getting stock price for %s: %s", ticker, str(e))
        return {"error": f"Gagal ambil data {ticker_clean}: {str(e)}"}


async def get_market_summary() -> dict[str, Any]:
    """
    Mengecek ringkasan pergerakan IHSG hari ini dan top movers via yfinance.
    """
    import yfinance as yf
    import time

    def _fetch():
        time.sleep(0.5)
        ihsg = yf.Ticker('^JKSE')
        data = ihsg.history(period='1d')
        if data.empty:
            return {"error": "Data IHSG belum tersedia hari ini."}

        latest = float(data['Close'].iloc[-1])
        prev_close = float(ihsg.info.get('previousClose', latest))
        change = latest - prev_close
        change_pct = (change / prev_close) * 100 if prev_close else 0.0

        lines = [
            f"IHSG: Rp {latest:,.0f} "
            f"({'📈 +' if change >= 0 else '📉 '}{change:,.0f}, "
            f"{'+' if change >= 0 else ''}{change_pct:.2f}%)"
        ]

        top_gainer = _get_top_movers(is_gainer=True)
        top_loser = _get_top_movers(is_gainer=False)
        if top_gainer:
            lines.append(f"Top Gainer: {top_gainer}")
        if top_loser:
            lines.append(f"Top Loser: {top_loser}")

        return {
            "index_name": "IHSG",
            "latest_price": latest,
            "change": change,
            "change_pct": change_pct,
            "top_gainer": top_gainer,
            "top_loser": top_loser,
            "formatted_summary": "\n".join(lines),
        }

    try:
        return await asyncio.to_thread(_fetch)
    except Exception as e:
        logger.error("Error getting market summary: %s", str(e))
        return {"error": f"Gagal ambil data IHSG: {str(e)}"}


async def execute_create_drive_folder(folder_name: str) -> dict[str, Any]:
    """Membuat folder baru di Google Drive (Database Oline)."""
    try:
        from src.drive import create_folder, get_drive_service
        service = get_drive_service()
        folder_id, is_new = await asyncio.to_thread(create_folder, service, folder_name)
        if is_new:
            return {
                "status": "success",
                "folder_name": folder_name,
                "message": f"Folder '{folder_name}' berhasil dibuat di Database Oline! 📂",
            }
        else:
            return {
                "status": "exists",
                "folder_name": folder_name,
                "message": f"Folder '{folder_name}' sudah ada di Database Oline.",
            }
    except Exception as e:
        logger.error("Error in create_drive_folder: %s", str(e))
        return {"error": f"Gagal membuat folder '{folder_name}': {str(e)}"}


async def execute_list_drive_files(folder_name: Optional[str] = None) -> dict[str, Any]:
    """Melihat daftar isi file & folder di Google Drive."""
    try:
        from src.drive import get_drive_service, list_files
        service = get_drive_service()
        items = await asyncio.to_thread(list_files, service, folder_name)
        if not items:
            loc = f"folder '{folder_name}'" if folder_name else "Database Oline"
            return {"message": f"Belum ada file di {loc} nih."}

        formatted_items = []
        for item in items:
            icon = "📂" if item["is_folder"] else "📄"
            formatted_items.append(f"{icon} {item['name']}")

        return {
            "location": folder_name or "Root Database",
            "total_items": len(items),
            "items": formatted_items,
        }
    except Exception as e:
        logger.error("Error in list_drive_files: %s", str(e))
        return {"error": f"Gagal mengambil daftar file: {str(e)}"}


async def execute_search_drive_files(query: str) -> dict[str, Any]:
    """Mencari file di Google Drive berdasarkan nama."""
    try:
        from src.drive import get_drive_service, search_files
        service = get_drive_service()
        items = await asyncio.to_thread(search_files, service, query)
        if not items:
            return {"message": f"Gak ketemu file yang cocok dengan nama '{query}' nih."}

        formatted_items = []
        for item in items:
            icon = "📂" if item["is_folder"] else "📄"
            formatted_items.append(f"{icon} {item['name']}")

        return {"query": query, "total_found": len(items), "results": formatted_items}
    except Exception as e:
        logger.error("Error in search_drive_files: %s", str(e))
        return {"error": f"Gagal mencari file: {str(e)}"}


async def execute_upload_to_drive(
    chat_id: int = 0, folder_name: Optional[str] = None
) -> dict[str, Any]:
    """Menyimpan file yang baru dikirim pengguna ke Google Drive."""
    try:
        from src.drive import get_drive_service, upload_file
        from src.kv import clear_pending_file, get_pending_file

        pending = await get_pending_file(chat_id)
        if not pending:
            return {
                "error": "File tidak ditemukan",
                "message": (
                    "Oline gak nemu file yang baru kamu kirim nih. "
                    "Coba kirim ulang file atau fotonya ya!"
                ),
            }

        service = get_drive_service()
        result = await asyncio.to_thread(
            upload_file,
            service,
            pending["file_name"],
            pending["file_bytes"],
            pending["mime_type"],
            folder_name,
        )

        await clear_pending_file(chat_id)

        target_dest = f"folder '{folder_name}'" if folder_name else "Database Oline"
        return {
            "status": "success",
            "file_name": result["name"],
            "destination": target_dest,
            "web_link": result.get("web_link", ""),
            "message": f"File '{result['name']}' berhasil tersimpan rapi di {target_dest}! 📁✨",
        }
    except Exception as e:
        logger.error("Error in upload_to_drive: %s", str(e))
        return {"error": f"Gagal mengunggah file ke Google Drive: {str(e)}"}


async def execute_download_from_drive(
    chat_id: int = 0, file_name: str = "", folder_name: Optional[str] = None
) -> dict[str, Any]:
    """Mendownload file dari Google Drive dan mengirimkannya ke Telegram."""
    try:
        from src.drive import download_file, get_drive_service, list_files, search_files

        service = get_drive_service()

        matching_files = (
            await asyncio.to_thread(list_files, service, folder_name)
            if folder_name
            else await asyncio.to_thread(search_files, service, file_name)
        )

        target_file = None
        for item in matching_files:
            if not item["is_folder"] and file_name.lower() in item["name"].lower():
                target_file = item
                break

        if not target_file and matching_files:
            for item in matching_files:
                if not item["is_folder"]:
                    target_file = item
                    break

        if not target_file:
            return {"error": f"File '{file_name}' tidak ditemukan di Drive 😢"}

        file_bytes, real_name, mime_type = await asyncio.to_thread(
            download_file, service, target_file["id"]
        )

        from src.bot import send_drive_file_to_telegram

        sent = await send_drive_file_to_telegram(
            chat_id=chat_id, file_bytes=file_bytes, file_name=real_name, mime_type=mime_type
        )

        if sent:
            return {
                "status": "success",
                "file_name": real_name,
                "message": f"File '{real_name}' udah Oline kirim langsung ke chat ini yaa! 📄✨",
            }
        else:
            return {"error": f"Gagal mengirimkan file '{real_name}' ke Telegram."}

    except Exception as e:
        logger.error("Error in download_from_drive: %s", str(e))
        return {"error": f"Gagal mengambil file dari Google Drive: {str(e)}"}


# ============================================================
# Location & OpenStreetMap Helper Functions
# ============================================================


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Menghitung jarak garis lurus (Haversine formula) dalam km antar 2 titik koordinat."""
    R = 6371.0  # km
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def overpass_query(lat: float, lon: float, category: str, radius_m: int = 2000) -> list[dict]:
    """Melakukan query ke Overpass API (OpenStreetMap) untuk mencari node POI."""
    tag_map = {
        "cafe": "amenity=cafe",
        "kafe": "amenity=cafe",
        "restaurant": "amenity=restaurant",
        "restoran": "amenity=restaurant",
        "toko buku": "shop=books",
        "bookstore": "shop=books",
        "mall": "shop=mall",
        "bar": "amenity=bar",
        "minimarket": "shop=convenience",
        "supermarket": "shop=supermarket",
        "spbu": "amenity=fuel",
        "pom bensin": "amenity=fuel",
        "apotek": "amenity=pharmacy",
        "rumah sakit": "amenity=hospital",
        "bank": "amenity=bank",
        "atm": "amenity=atm",
    }
    cat_lower = category.lower().strip()
    tag = tag_map.get(cat_lower, f"amenity={cat_lower}")

    query = f"""
    [out:json][timeout:10];
    node[{tag}](around:{radius_m},{lat},{lon});
    out body 10;
    """
    try:
        response = requests.post(
            "https://overpass-api.de/api/interpreter",
            data={"data": query},
            headers={"User-Agent": "OlineBot/1.0"},
            timeout=10.0,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("elements", [])
    except Exception as e:
        logger.error("Overpass API query error: %s", str(e))
        return []


async def get_nearby_places(
    chat_id: int = 0, category: str = "", radius_km: float = 2.0
) -> dict[str, Any]:
    """Mencari tempat terdekat dari lokasi pengguna yang tersimpan."""
    if not category:
        return {"error": "Kategori tempat harus diisi (misal: 'cafe', 'toko buku', 'restoran')."}

    loc = await get_user_location(chat_id)
    if not loc:
        return {
            "error": "Lokasi belum disimpan",
            "message": (
                "Oline belum tahu lokasi kamu nih! "
                "Coba kirim titik lokasi kamu via Telegram dulu ya (tombol jepit kertas > Lokasi) 📍"
            ),
        }

    lat, lon = loc["lat"], loc["lon"]
    radius_m = int(radius_km * 1000)

    elements = await asyncio.to_thread(overpass_query, lat, lon, category, radius_m)
    if not elements:
        return {
            "message": f"Tidak ditemukan {category} dalam radius {radius_km} km dari lokasi kamu."
        }

    results = []
    for p in elements:
        plat = p.get("lat", lat)
        plon = p.get("lon", lon)
        dist = haversine(lat, lon, plat, plon)
        tags = p.get("tags", {})
        name = tags.get("name") or tags.get("brand") or "Tanpa Nama"
        street = tags.get("addr:street", "")
        city_tag = tags.get("addr:city", "")
        address = ", ".join(filter(None, [street, city_tag])) or "Alamat tidak spesifik"
        results.append({
            "name": name,
            "distance_km": round(dist, 2),
            "address": address,
            "lat": plat,
            "lon": plon,
        })

    results.sort(key=lambda x: x["distance_km"])
    return {
        "category": category,
        "total_found": len(results),
        "places": results[:5],
    }


async def search_places_by_city(city: str, category: str) -> dict[str, Any]:
    """Mencari tempat berdasarkan nama kota/area dan kategori via Nominatim & Overpass API."""
    def _geocode_and_search():
        try:
            geo_resp = requests.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": city, "format": "json", "limit": 1},
                headers={"User-Agent": "OlineBot/1.0"},
                timeout=10.0,
            )
            geo_resp.raise_for_status()
            geo_data = geo_resp.json()
            if not geo_data:
                return {"error": f"Kota/area '{city}' tidak ditemukan."}

            lat = float(geo_data[0]["lat"])
            lon = float(geo_data[0]["lon"])
            display_name = geo_data[0].get("display_name", city)

            elements = overpass_query(lat, lon, category, radius_m=5000)
            if not elements:
                return {"message": f"Tidak ditemukan {category} di area {city}."}

            results = []
            for p in elements[:5]:
                tags = p.get("tags", {})
                name = tags.get("name") or tags.get("brand") or "Tanpa Nama"
                street = tags.get("addr:street", "")
                address = street if street else "Alamat tidak spesifik"
                results.append({
                    "name": name,
                    "address": address,
                })

            return {
                "city": city,
                "display_name": display_name,
                "category": category,
                "total_found": len(results),
                "places": results,
            }
        except Exception as e:
            logger.error("Error in search_places_by_city: %s", str(e))
            return {"error": f"Gagal mencari tempat di {city}: {str(e)}"}

    return await asyncio.to_thread(_geocode_and_search)


async def execute_code(language: str, code: str) -> dict[str, Any]:
    """
    Eksekusi kode via Piston API.
    Return output atau error dalam format dictionary.
    """
    if not language or not code:
        return {"error": "Bahasa dan kode harus diisi."}

    payload = {
        "language": language.lower(),
        "version": "*",
        "files": [{"content": code}],
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(PISTON_EXECUTE_URL, json=payload)
            if resp.status_code != 200:
                return {
                    "error": f"Piston API error: {resp.status_code} {resp.text[:200]}"
                }

            data = resp.json()
            run = data.get("run", {})
            stdout = (run.get("stdout") or "").strip()
            stderr = (run.get("stderr") or "").strip()
            output = (run.get("output") or "").strip()

            MAX_LEN = 1500
            if len(stdout) > MAX_LEN:
                stdout = stdout[:MAX_LEN] + "\n...(output dipotong)"
            if len(stderr) > MAX_LEN:
                stderr = stderr[:MAX_LEN] + "\n...(error dipotong)"
            if len(output) > MAX_LEN:
                output = output[:MAX_LEN] + "\n...(output dipotong)"

            return {
                "language": language,
                "stdout": stdout,
                "stderr": stderr,
                "output": output or stdout,
                "exit_code": run.get("code", 0),
            }
    except httpx.TimeoutException:
        return {
            "error": "Wah eksekusinya kelamaan (timeout 15 detik), coba kode yang lebih pendek ya~"
        }
    except Exception as e:
        logger.error("Gagal menghubungi Piston API: %s", str(e))
        return {"error": f"Gagal menghubungi Piston API: {str(e)}"}


# Map nama tool ke executor function
TOOL_EXECUTORS = {
    "get_movie_recommendation": get_movie_recommendation,
    "get_music_recommendation": get_music_recommendation,
    "get_weather_forecast": get_weather_forecast,
    "save_journal_entry": execute_save_journal,
    "get_journal_recap": execute_get_journal_recap,
    "check_quota": execute_check_quota,
    "send_voice_message": execute_send_voice_message,
    "search_internet": search_internet,
    "get_stock_price": get_stock_price,
    "get_market_summary": get_market_summary,
    "create_drive_folder": execute_create_drive_folder,
    "list_drive_files": execute_list_drive_files,
    "search_drive_files": execute_search_drive_files,
    "upload_to_drive": execute_upload_to_drive,
    "download_from_drive": execute_download_from_drive,
    "get_nearby_places": get_nearby_places,
    "search_places_by_city": search_places_by_city,
    "execute_code": execute_code,
    "save_note_to_notion": save_note_to_notion,
}

TOOL_HANDLERS = TOOL_EXECUTORS


def convert_tools_to_openai_format(tool_declarations: list[dict]) -> list[dict]:
    """
    Mengonversi deklarasi tools (format Gemini / dict biasa) ke format OpenAI/Groq function calling.
    """
    if not tool_declarations:
        return []

    openai_tools = []
    for decl in tool_declarations:
        if "type" in decl and "function" in decl:
            openai_tools.append(decl)
        else:
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": decl.get("name"),
                    "description": decl.get("description", ""),
                    "parameters": decl.get("parameters", {"type": "object", "properties": {}}),
                },
            })
    return openai_tools


async def execute_tool(
    func_name: str, func_args: dict, chat_id: int = 0
) -> dict[str, Any]:
    """
    Menjalankan fungsi tool berdasarkan nama dan mengembalikan hasilnya.
    Mendukung penyuntikan parameter otomatis (seperti chat_id).
    """
    logger.info("Executing function call: %s with args: %s", func_name, func_args)

    executor = TOOL_EXECUTORS.get(func_name)
    if not executor:
        return {"error": f"Unknown function: {func_name}"}

    args = dict(func_args) if func_args else {}

    if func_name in ("save_journal_entry", "get_journal_recap"):
        args["chat_id"] = chat_id
        if func_name == "save_journal_entry":
            return await executor(
                chat_id=chat_id,
                text=args.get("text", ""),
                date=args.get("date"),
            )
        else:
            return await executor(
                chat_id=chat_id,
                start_date=args.get("start_date"),
                end_date=args.get("end_date"),
            )
    elif func_name == "check_quota":
        return await executor(chat_id=chat_id)
    elif func_name == "send_voice_message":
        return await executor(chat_id=chat_id, text=args.get("text", ""))
    elif func_name == "get_nearby_places":
        return await executor(chat_id=chat_id, **args)
    elif func_name in ("upload_to_drive", "download_from_drive"):
        return await executor(chat_id=chat_id, **args)
    else:
        return await executor(**args)



