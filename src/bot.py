"""
Telegram Bot setup dan handler untuk Oline.
Mengelola penerimaan pesan dan routing ke Gemini pipeline.
"""

import logging
import os
import re

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from src.gemini import chat_with_oline
from src.kv import check_rate_limit, save_journal

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")


def create_application() -> Application:
    """
    Membuat dan mengkonfigurasi Application python-telegram-bot.
    Untuk mode webhook (stateless per-request di Vercel).
    """
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError(
            "TELEGRAM_BOT_TOKEN environment variable is not set. "
            "Cannot initialize Telegram bot."
        )

    application = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .updater(None)  # Tidak pakai polling, hanya webhook
        .build()
    )

    # Register handlers
    application.add_handler(CommandHandler("start", handle_start))
    application.add_handler(CommandHandler("help", handle_help))
    application.add_handler(CommandHandler("jurnal", handle_jurnal_command))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    return application


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler untuk command /start."""
    if not update.effective_chat:
        return

    welcome_text = (
        "haii! aku Oline 👋\n\n"
        "aku teman virtual kamu yang bisa bantu banyak hal:\n"
        "💬 ngobrol santai tentang apa aja\n"
        "🎬 rekomendasi film & lagu\n"
        "🌤️ cek cuaca\n"
        "📔 catat jurnal harian\n\n"
        "langsung aja chat aku, gak perlu command khusus! "
        "kecuali kalau mau cepet nulis jurnal, bisa pakai /jurnal.\n\n"
        "btw, siapa namamu? biar aku bisa ingat 😊"
    )
    await update.effective_chat.send_message(welcome_text)


async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler untuk command /help."""
    if not update.effective_chat:
        return

    help_text = (
        "ini yang bisa aku bantu:\n\n"
        "💬 *Ngobrol* — langsung chat aja\n"
        "🎬 *Rekomendasi Film* — \"rekomendasiin film horor\"\n"
        "🎵 *Rekomendasi Lagu* — \"cari lagu chill indonesia\"\n"
        "🌤️ *Cek Cuaca* — \"cuaca besok di Bandung\"\n"
        "📔 *Jurnal* — /jurnal [catatan] atau \"catat jurnal hari ini: ...\"\n"
        "📋 *Rekap Jurnal* — \"rekap jurnal minggu ini\"\n\n"
        "semua bisa pakai bahasa biasa, aku otomatis ngerti kok 😌"
    )
    await update.effective_chat.send_message(help_text, parse_mode="Markdown")


async def handle_jurnal_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Handler untuk command /jurnal <teks>.
    Shortcut langsung simpan jurnal tanpa lewat Gemini.
    """
    if not update.effective_chat or not update.message:
        return

    chat_id = update.effective_chat.id

    # Rate limiting
    if not await check_rate_limit(chat_id):
        await update.effective_chat.send_message(
            "sabar ya, kamu udah kebanyakan chat 😅 tunggu sebentar lagi."
        )
        return

    # Ambil teks setelah /jurnal
    text = ""
    if update.message.text:
        text = update.message.text.replace("/jurnal", "", 1).strip()

    if not text:
        await update.effective_chat.send_message(
            "tulis jurnalmu setelah /jurnal ya!\n"
            "contoh: `/jurnal hari ini seru banget, ketemu teman lama`"
        )
        return

    # Simpan langsung ke KV
    success = await save_journal(chat_id, text)
    if success:
        await update.effective_chat.send_message(
            "catatan kamu tersimpan rapi! 📖✨\n"
            "kalau pengen liat rekap, tinggal bilang \"rekap jurnal minggu ini\" aja ya~"
        )
    else:
        await update.effective_chat.send_message(
            "aduh, gagal nyimpen jurnal 😢 coba lagi nanti ya."
        )


async def handle_message(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Handler utama untuk semua pesan teks biasa.
    Meneruskan pesan ke Gemini pipeline untuk diproses.
    """
    if not update.effective_chat or not update.message or not update.message.text:
        return

    chat_id = update.effective_chat.id
    user_message = update.message.text.strip()

    if not user_message:
        return

    # Rate limiting
    if not await check_rate_limit(chat_id):
        await update.effective_chat.send_message(
            "sabar ya, kamu udah kebanyakan chat 😅 tunggu sebentar lagi."
        )
        return

    # Kirim "typing" action
    await update.effective_chat.send_action("typing")

    # Ambil nama pengguna dari Telegram
    user_name = "Teman"
    if update.effective_user and update.effective_user.first_name:
        user_name = update.effective_user.first_name

    # Proses lewat Gemini
    response = await chat_with_oline(chat_id, user_message, user_name=user_name)

    # Kirim respons (split jika terlalu panjang)
    if len(response) > 4096:
        # Telegram max 4096 chars per pesan
        for i in range(0, len(response), 4096):
            chunk = response[i : i + 4096]
            await update.effective_chat.send_message(chunk)
    else:
        await update.effective_chat.send_message(response)
