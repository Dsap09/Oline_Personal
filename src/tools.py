"""
Tool definitions dan executor functions untuk Gemini Function Calling.
Mencakup: rekomendasi film (TMDb), rekomendasi musik (iTunes),
cuaca (OpenWeatherMap), dan jurnal harian (Vercel KV).
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Any, Optional

import httpx

from src.kv import (
    get_journal_entries,
    get_monthly_tts_usage,
    get_today_usage,
    save_journal,
    save_tts_usage,
)
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
            "Mengecek sisa kuota token Gemini API hari ini. "
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
]

TOOLS_BY_INTENT = {
    "cuaca": ["get_weather_forecast"],
    "rekomendasi": ["get_movie_recommendation", "get_music_recommendation"],
    "suara": ["send_voice_message"],
    "jurnal": ["save_journal_entry", "get_journal_recap"],
    "kuota": ["check_quota"],
    "search": ["search_internet"],
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
    Mengecek pemakaian token Gemini API hari ini dan menghitung sisa kuota.
    Kuota harian free tier: 1.000.000 token.
    """
    DAILY_TOKEN_LIMIT = 1_000_000

    tokens_used = await get_today_usage(chat_id)
    tokens_remaining = max(0, DAILY_TOKEN_LIMIT - tokens_used)
    usage_percent = round((tokens_used / DAILY_TOKEN_LIMIT) * 100, 1)

    return {
        "date": format_date_indonesian(datetime.now().strftime("%Y-%m-%d")),
        "tokens_used": tokens_used,
        "tokens_remaining": tokens_remaining,
        "daily_limit": DAILY_TOKEN_LIMIT,
        "usage_percent": usage_percent,
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
}
