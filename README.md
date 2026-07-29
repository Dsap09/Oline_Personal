# Oline – Personal AI Telegram Bot 🤖

Oline adalah bot Telegram asisten pribadi berpersona Gen-Z, dibangun dengan Python, Google Gemini AI, dan Vercel Serverless.

## ✨ Fitur

- **💬 Tanya AI Personal** — Ngobrol bebas dengan Oline tentang apa saja
- **🎬 Rekomendasi Film** — Cari film berdasarkan genre, mood, kata kunci (via TMDb)
- **🎵 Rekomendasi Lagu** — Cari lagu berdasarkan genre, artis, kata kunci (via iTunes)
- **🌤️ Cek Cuaca** — Info cuaca saat ini dan forecast 5 hari (via OpenWeatherMap)
- **📔 Jurnal Harian** — Catat dan rekap jurnal harian

Semua fitur dideteksi otomatis dari percakapan natural, tanpa perlu command khusus!

## 🛠️ Tech Stack

| Komponen | Teknologi |
|----------|-----------|
| Bahasa | Python 3.11+ |
| Hosting | Vercel (Serverless Functions) |
| Database | Vercel KV (Redis REST API) |
| AI/ML | Google Gemini API (Function Calling) |
| Telegram | python-telegram-bot v20+ |
| HTTP Client | httpx (async) |

## 📁 Struktur Proyek

```
├── api/
│   └── index.py          # Entrypoint serverless Vercel (webhook)
├── src/
│   ├── bot.py            # Telegram Bot handlers
│   ├── gemini.py         # Gemini AI client + function calling
│   ├── tools.py          # Tool definitions & API executors
│   ├── kv.py             # Vercel KV helper
│   ├── personas.py       # System prompt Oline
│   └── utils.py          # Utility functions
├── scripts/
│   └── set_webhook.py    # Script setup webhook Telegram
├── requirements.txt
├── vercel.json
├── .env.example
└── README.md
```

## 🚀 Setup & Deployment

### 1. Clone & Install Dependencies

```bash
git clone <repo-url>
cd oline-bot
pip install -r requirements.txt
```

### 2. Siapkan API Keys

Salin `.env.example` ke `.env` dan isi semua nilai:

```bash
cp .env.example .env
```

API keys yang dibutuhkan:
- **Telegram Bot Token**: Dari [@BotFather](https://t.me/BotFather)
- **Gemini API Key**: Dari [Google AI Studio](https://aistudio.google.com/apikey)
- **TMDb API Key**: Dari [TMDb](https://www.themoviedb.org/settings/api)
- **OpenWeatherMap API Key**: Dari [OpenWeatherMap](https://openweathermap.org/api)
- **Vercel KV**: Buat KV store di [Vercel Dashboard](https://vercel.com/dashboard)

### 3. Deploy ke Vercel

```bash
# Install Vercel CLI
npm i -g vercel

# Deploy
vercel

# Set environment variables di Vercel Dashboard
# atau via CLI:
vercel env add TELEGRAM_BOT_TOKEN
vercel env add GEMINI_API_KEY
vercel env add TMDB_API_KEY
vercel env add OPENWEATHER_API_KEY
vercel env add KV_REST_API_URL
vercel env add KV_REST_API_TOKEN
```

### 4. Set Webhook Telegram

```bash
python scripts/set_webhook.py https://your-project.vercel.app
```

Cek status webhook:
```bash
python scripts/set_webhook.py --info
```

## 💬 Contoh Percakapan

```
User: Hai Oline, lagi bosen nih.
Oline: haii! bosen tuh musuh utama Gen-Z. butuh rekomendasi film atau lagu?
       atau mau curhat aja? 😌

User: Rekomendasi film horor indonesia yang seru
Oline: okeh! dari list yang ada, "Pengabdi Setan 2" lumayan bikin deg-degan
       tapi sinematografinya bagus. Selain itu "Qorin" juga rame tuh.
       Mo tau lebih detail? 🎬

User: Cuaca besok di Yogyakarta gimana?
Oline: besok (30 Juli) di Jogja diprediksi hujan ringan, suhu 24-29°C.
       Jangan lupa payung ya, bestie! ☔

User: /jurnal Hari ini aku selesai baca novel bagus banget
Oline: catatan kamu tersimpan rapi! 📖✨
       nanti kalau pengen liat rekap, tinggal bilang aja ya~
```

## 📝 Lisensi

Personal project oleh Doni.
