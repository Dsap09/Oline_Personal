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

from src.kv import check_rate_limit, get_history, save_journal

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
        MessageHandler(filters.LOCATION, handle_location_message)
    )
    application.add_handler(
        MessageHandler(filters.Document.ALL | filters.PHOTO, handle_file_message)
    )
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
        "📈 *Saham & IHSG* — \"cek saham BBCA\" / \"IHSG hari ini gimana\"\n"
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


POPULAR_STOCK_TICKERS = [
    "bbca", "bbri", "bmri", "bbni", "tlkm", "asii", "unvr", "adro", "antm", "icbp",
    "indf", "bumi", "pgas", "wskt", "sido", "myrx", "goto", "buka", "ptba", "medc",
    "emtk", "brpt", "tpia", "inkp", "tkim", "doid", "mbma", "mka", "hrum", "essa",
    "aces", "bsde", "ctra", "smra", "pwon", "eraa", "cpin", "jpfa", "smgr", "intp",
    "bren", "ammn", "cuan", "dewa", "film", "klbf", "mcap"
]

HEAVY_KEYWORDS = {
    "notion": [
        "notion", "catat ke notion", "simpan ke notion", "notes notion", "catatan notion",
        "tambah kolom", "buat kolom", "edit kolom", "tambah properti", "buat properti",
        "kolom file", "kolom notion", "tambah atribut",
    ],
    "cuaca": ["cuaca", "hujan", "panas", "suhu", "cerah"],
    "rekomendasi": ["rekomendasi", "film", "lagu", "seri", "anime"],
    "suara": ["suara", "nyanyi", "gombal", "puisi", "bacain", "baca"],
    "jurnal": ["jurnal", "catat", "rekap jurnal"],
    "kuota": ["kuota", "token", "quota"],
    "drive": [
        "drive", "database", "folder", "simpan file", "buat folder",
        "cari file", "tampilkan isi", "kirim file", "upload", "download", "file",
    ],
    "lokasi": [
        "terdekat", "dekat", "toko buku", "cafe", "kafe", "restoran", "restaurant",
        "mall", "tempat makan", "kedai", "coffee", "cari tempat", "cari cafe", "spbu",
        "pom bensin", "apotek", "rumah sakit", "bank", "atm", "lokasi terdekat", "lokasi saya",
    ],
    "search": ["search", "apa itu", "siapa", "kapan", "dimana", "berita", "definisi", "pengertian", "cari berita", "cari info"],
    "saham": [
        "saham", "ihsg", "indeks", "index", "market", "bursa", "gainer", "loser",
    ] + POPULAR_STOCK_TICKERS,
    "coding": [
        "jalankan", "eksekusi", "run code", "jalankan kode", "execute",
        "kode python", "kode javascript", "script", "debug", "coding",
        "contoh kode", "print", "buat fungsi", "buat script",
    ],
    "deploy": [
        "deploy", "vercel", "onlinekan", "live", "hosting", "buatkan website",
        "buatkan landing page", "deploy ke vercel", "publikasikan website",
        "list landing page", "daftar landing page", "hapus landing page",
        "hapus deployment", "list deployment", "daftar deployment", "delete deployment",
    ],
    "gambar": [
        "gambar", "foto", "image", "kirim gambar", "cari gambar", "cari foto",
        "tampilkan gambar", "kirimi gambar", "cariin gambar", "minta foto", "minta gambar",
    ],
}




def detect_intent(text: str) -> str | None:
    """
    Mendeteksi apakah pesan pengguna membutuhkan tools (heavy intent).
    Jika tidak ada kata kunci yang cocok, mengembalikan None (Fast Path).
    """
    text_lower = text.lower().strip()
    words = text_lower.split()

    # 1. Cek kata kunci persis/substring
    for intent, keywords in HEAVY_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            return intent

    # 2. Deteksi otomatis kode saham 4 huruf standalone (misal: "BUMI", "BBCA")
    if len(words) == 1 and len(words[0]) == 4 and words[0].isalpha():
        return "saham"

    return None


async def detect_intent_async(text: str, chat_id: int | None = None) -> str | None:
    """
    Mendeteksi intent dengan konteks percakapan sebelumnya.
    """
    intent = detect_intent(text)
    if intent:
        return intent

    # Jika pengguna mengirim pesan pendek (misal: 1-3 kata seperti "bumi", "bagaimana bumi"),
    # dan percakapan sebelumnya membahas saham, klasifikasikan sebagai intent 'saham'.
    if chat_id:
        try:
            words = text.strip().split()
            if len(words) <= 3:
                history = await get_history(chat_id)
                if history:
                    recent_texts = " ".join([m.get("text", "") for m in history[-3:]]).lower()
                    if any(kw in recent_texts for kw in HEAVY_KEYWORDS["saham"]):
                        return "saham"
        except Exception as e:
            logger.warning("Error checking history for intent context: %s", str(e))

    return None


RULE_KEYWORDS = [
    "jangan panggil", "mulai sekarang", "kedepannya", "ke depannya",
    "selalu", "ingat", "jangan lupa", "kalo aku minta", "setiap kali",
    "panggil aku", "panggil saya", "ingat ya", "catat ya",
]


def generate_memory_title(rule_text: str) -> str:
    """
    Menghasilkan judul singkat (maksimal 50-80 karakter) dari kalimat aturan/preferensi.
    Mencari keyword yang muncul paling awal dalam teks.
    """
    if not rule_text:
        return "Aturan Memori"

    rule_clean = rule_text.strip()
    rule_lower = rule_clean.lower()
    keywords = ["panggil", "jangan", "selalu", "setiap", "kalo", "kalau", "jika", "mulai sekarang", "kedepannya", "ke depannya", "deploy"]

    earliest_idx = -1
    for kw in keywords:
        idx = rule_lower.find(kw)
        if idx != -1:
            if earliest_idx == -1 or idx < earliest_idx:
                earliest_idx = idx

    if earliest_idx != -1:
        extracted = rule_clean[earliest_idx:].strip()
        if len(extracted) > 5:
            res_title = extracted[:60].strip()
            if len(extracted) > 60:
                res_title += "..."
            return res_title

    res_title = rule_clean[:60].strip()
    if len(rule_clean) > 60:
        res_title += "..."
    return res_title


def is_rule_message(text: str) -> bool:
    """
    Mendeteksi apakah pesan pengguna berisi instruksi aturan/preferensi baru.
    """
    if not text:
        return False
    text_lower = text.lower().strip()
    return any(kw in text_lower for kw in RULE_KEYWORDS)


async def handle_message(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Handler utama untuk semua pesan teks biasa.
    Meneruskan pesan ke Gemini pipeline untuk diproses (Fast Path vs Slow Path).
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

    # Ambil nama pengguna dari Telegram
    user_name = "Teman"
    if update.effective_user and update.effective_user.first_name:
        user_name = update.effective_user.first_name

    # Deteksi jika pesan berisi aturan/preferensi baru untuk disimpan ke Notion
    if is_rule_message(user_message):
        try:
            from src.notion import save_memory_to_notion
            rule_title = generate_memory_title(user_message)
            await save_memory_to_notion(title=rule_title, content=user_message, memory_type="Aturan")
        except Exception as rule_err:
            logger.warning("Gagal menyimpan aturan ke Notion: %s", str(rule_err))

    # Deteksi intent untuk menentukan Fast Path / Slow Path (dengan dukungan konteks percakapan)
    intent = await detect_intent_async(user_message, chat_id)

    # Kirim "typing" action HANYA untuk Slow Path (fitur berat) untuk memangkas latensi Fast Path
    if intent is not None:
        await update.effective_chat.send_action("typing")

    # Proses lewat Gemini (Fast Path tanpa tools jika intent=None)
    response = await chat_with_oline(chat_id, user_message, user_name=user_name, intent=intent)

    # Kirim respons (split jika terlalu panjang)
    if len(response) > 4096:
        # Telegram max 4096 chars per pesan
        for i in range(0, len(response), 4096):
            chunk = response[i : i + 4096]
            await update.effective_chat.send_message(chunk)
    else:
        await update.effective_chat.send_message(response)


async def handle_file_message(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Handler untuk pesan dokumen dan foto yang diunggah pengguna ke Telegram.
    Mendownload file bytes, menyimpan ke KV cache sementara, dan memproses caption jika ada.
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

    file_obj = None
    file_name = "file_oline"
    mime_type = "application/octet-stream"

    if update.message.document:
        doc = update.message.document
        file_name = doc.file_name or "dokumen_oline"
        mime_type = doc.mime_type or "application/octet-stream"
        file_obj = await context.bot.get_file(doc.file_id)
    elif update.message.photo:
        photo = update.message.photo[-1]
        file_name = f"foto_{photo.file_unique_id}.jpg"
        mime_type = "image/jpeg"
        file_obj = await context.bot.get_file(photo.file_id)

    if not file_obj:
        return

    file_bytes = bytes(await file_obj.download_as_bytearray())

    from src.kv import save_pending_file
    await save_pending_file(chat_id, file_name, file_bytes, mime_type)

    caption = (update.message.caption or "").strip()

    user_name = "Teman"
    if update.effective_user and update.effective_user.first_name:
        user_name = update.effective_user.first_name

    if caption:
        await update.effective_chat.send_action("typing")
        response = await chat_with_oline(
            chat_id, caption, user_name=user_name, intent="drive"
        )
        await update.effective_chat.send_message(response)
    else:
        await update.effective_chat.send_message(
            f"File/Foto '{file_name}' udah Oline terima nih! 📄✨\n\n"
            "Mau Oline simpan ke folder mana di database? "
            "(misal: \"simpan ke folder Skripsi\" atau \"simpan file ini\")"
        )


async def handle_location_message(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Handler untuk pesan lokasi Telegram (latitude & longitude).
    Menyimpan koordinat lokasi pengguna ke Vercel KV.
    """
    if not update.effective_chat or not update.message or not update.message.location:
        return

    chat_id = update.effective_chat.id

    if not await check_rate_limit(chat_id):
        await update.effective_chat.send_message(
            "sabar ya, kamu udah kebanyakan chat 😅 tunggu sebentar lagi."
        )
        return

    location = update.message.location
    lat = location.latitude
    lon = location.longitude

    from src.kv import save_user_location
    success = await save_user_location(chat_id, lat, lon)

    if success:
        await update.effective_chat.send_message(
            "Lokasi kamu udah aku simpan! 📍✨\n"
            "Sekarang tinggal bilang aja mau cari apa di sekitar sini "
            "(misal: \"cafe terdekat\" atau \"toko buku terdekat\")~"
        )
    else:
        await update.effective_chat.send_message(
            "aduh, gagal nyimpen lokasi kamu 😢 coba kirim ulang ya."
        )


async def send_drive_file_to_telegram(
    chat_id: int, file_bytes: bytes, file_name: str, mime_type: str
) -> bool:
    """
    Mengirimkan file atau foto dari Google Drive kembali ke chat Telegram pengguna.
    """
    if not TELEGRAM_BOT_TOKEN:
        return False

    try:
        from telegram import Bot

        bot = Bot(token=TELEGRAM_BOT_TOKEN)

        if "image" in mime_type.lower() or file_name.lower().endswith(
            (".jpg", ".jpeg", ".png", ".webp", ".gif")
        ):
            await bot.send_photo(
                chat_id=chat_id,
                photo=file_bytes,
                caption=f"📷 {file_name} dari Database Oline",
            )
        else:
            await bot.send_document(
                chat_id=chat_id,
                document=file_bytes,
                filename=file_name,
                caption=f"📄 {file_name} dari Database Oline",
            )
        return True
    except Exception as e:
        logger.error("Failed to send Drive file to Telegram: %s", str(e))
        return False



