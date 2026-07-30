"""
Module untuk mengelola Text-to-Speech (TTS) menggunakan ElevenLabs API
dan mengirimkan pesan suara / voice note ke Telegram.
"""

import io
import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
# Default voice ID: Rachel (21m00Tcm4TlvDq8ikWAM)
ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")

ELEVENLABS_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech"
TELEGRAM_API_URL = "https://api.telegram.org"


async def send_chat_action_record_voice(chat_id: int) -> bool:
    """Mengirim Telegram chat action 'record_voice'."""
    if not TELEGRAM_BOT_TOKEN:
        return False

    url = f"{TELEGRAM_API_URL}/bot{TELEGRAM_BOT_TOKEN}/sendChatAction"
    payload = {"chat_id": chat_id, "action": "record_voice"}

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            res = await client.post(url, json=payload)
            return res.status_code == 200
    except Exception as e:
        logger.warning("Failed to send record_voice action: %s", str(e))
        return False


async def generate_elevenlabs_tts(text: str) -> bytes:
    """
    Mengubah teks menjadi audio menggunakan ElevenLabs Text-to-Speech API.
    Returns: byte audio (MP3).
    """
    if not ELEVENLABS_API_KEY:
        raise ValueError(
            "ELEVENLABS_API_KEY tidak dikonfigurasi. Mohon isi di environment variables."
        )

    voice_id = ELEVENLABS_VOICE_ID or "21m00Tcm4TlvDq8ikWAM"
    url = f"{ELEVENLABS_TTS_URL}/{voice_id}"

    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": ELEVENLABS_API_KEY,
    }

    model_id = os.environ.get("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")

    payload = {
        "text": text,
        "model_id": model_id,
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.5,
        },
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(url, headers=headers, json=payload)
        if response.status_code != 200:
            logger.error(
                "ElevenLabs API error (Status %d): %s",
                response.status_code,
                response.text,
            )
            raise RuntimeError(
                f"Gagal menghasilkan suara dari ElevenLabs API (Status {response.status_code})."
            )
        return response.content


async def send_voice_note_to_telegram(
    chat_id: int, audio_bytes: bytes, caption: str = "🎙️ dari Oline, spesial buat kamu~"
) -> bool:
    """
    Mengirim audio bytes sebagai Voice Note di Telegram.
    Menggunakan endpoint sendVoice dengan fallback ke sendAudio jika gagal.
    """
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not configured.")
        return False

    base_url = f"{TELEGRAM_API_URL}/bot{TELEGRAM_BOT_TOKEN}"

    # Coba pydub konversi ke OGG Opus jika pydub & ffmpeg tersedia, jika tidak kirim MP3 langsung
    ogg_bytes: Optional[bytes] = None
    try:
        from pydub import AudioSegment
        sound = AudioSegment.from_file(io.BytesIO(audio_bytes), format="mp3")
        ogg_buf = io.BytesIO()
        sound.export(ogg_buf, format="ogg", codec="libopus")
        ogg_bytes = ogg_buf.getvalue()
    except Exception:
        logger.info("pydub/ffmpeg conversion skipped or unavailable. Sending direct MP3 bytes.")

    payload = {
        "chat_id": str(chat_id),
        "caption": caption,
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        # 1. Coba sendVoice dengan OGG atau MP3
        try:
            files_voice = {
                "voice": ("voice.ogg" if ogg_bytes else "voice.mp3", ogg_bytes or audio_bytes, "audio/ogg" if ogg_bytes else "audio/mpeg")
            }
            res = await client.post(f"{base_url}/sendVoice", data=payload, files=files_voice)
            if res.status_code == 200:
                return True
            logger.warning("sendVoice status %d: %s. Trying sendAudio fallback...", res.status_code, res.text)
        except Exception as e:
            logger.warning("sendVoice request exception: %s. Trying sendAudio fallback...", str(e))

        # 2. Fallback to sendAudio
        try:
            files_audio = {
                "audio": ("voice.mp3", audio_bytes, "audio/mpeg")
            }
            res_audio = await client.post(f"{base_url}/sendAudio", data=payload, files=files_audio)
            return res_audio.status_code == 200
        except Exception as e:
            logger.error("sendAudio request exception: %s", str(e))
            return False
