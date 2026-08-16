# Oline – Personal AI Telegram Bot 🤖

Oline adalah bot Telegram asisten pribadi berpersona Gen-Z yang cerdas, cepat, dan serba bisa. Dibangun menggunakan **Python 3.10+**, **Google Gemini AI**, **Groq API**, dan dideploy di **Vercel Serverless Functions**.

---

## ✨ Fitur Utama

- **⚡ Fast Path (Groq API)** — Respon kilat untuk obrolan santai, sapaan, dan pertanyaan ringan menggunakan model `openai/gpt-oss-20b`.
- **🛠️ Slow Path (Google Gemini API)** — Pemrosesan kecerdasan utama dengan rotasi model otomatis (`gemini-flash-lite-latest`, `gemini-2.5-flash`, `gemini-2.0-flash`) dan Function Calling untuk tugas kompleks.
- **🛡️ Groq Slow Path Fallback** — Jika Gemini down (kuota habis/429/timeout), Oline otomatis fallback ke Groq dengan dukungan *Function Calling* (2-stage OpenAI tool execution) agar fitur bot tidak pernah mati.
- **🎬 Rekomendasi Film** — Pencarian rekomendasi film berdasarkan genre, mood, atau kata kunci (via TMDb API).
- **🎵 Rekomendasi Lagu** — Pencarian rekomendasi musik berdasarkan artis, genre, atau kata kunci (via iTunes Search API).
- **🌤️ Cek Cuaca** — Informasi cuaca real-time dan prakiraan cuaca 5 hari ke depan untuk berbagai kota (via OpenWeatherMap API).
- **📈 Saham Indonesia & IHSG** — Cek harga saham 4 huruf (BBCA, BBRI, TLKM, BUMI, GOTO, dsb.), ringkasan pergerakan IHSG, serta Top Gainer & Loser (via `yfinance`).
- **🎙️ Pesan Suara (Voice Note)** — Oline bisa bernyanyi, menggombal, atau membaca puisi dalam bentuk Voice Note Telegram bersuara natural (via ElevenLabs TTS).
- **🔍 Search Internet Real-time** — Pencarian berita terkini, fakta terbaru, dan definisi di internet (via DuckDuckGo Search `ddgs`).
- **📂 Google Drive Integration (Database Oline)** — Manajemen folder, listing file, pencarian file, upload foto/dokumen dari Telegram ke Drive, dan download file dari Drive langsung ke Telegram (via Google Drive OAuth 2.0 API).
- **📔 Jurnal Harian** — Pencatatan jurnal harian dan rekap harian/mingguan (via Vercel KV / Upstash Redis).
- **📊 Cek Kuota & Pemakaian API** — Tool `check_quota` untuk memantau sisa kuota harian Groq (Fast Path) dan Gemini (Slow Path) secara transparan.
- **🚨 Smart Rate Limiting** — Pembatasan rate limit 25 req/menit per user dengan pengecekan TTL otomatis di Redis pipeline untuk mencegah kunci permanen.

---

## 🛠️ Tech Stack

| Komponen | Teknologi |
|----------|-----------|
| **Bahasa** | Python 3.10+ |
| **Hosting** | Vercel (Serverless Functions) |
| **Database / KV** | Vercel KV / Upstash Redis (REST API Pipeline) |
| **AI Primary Engine** | Google Gemini API (`google-genai` SDK) |
| **AI Fast Engine & Fallback** | Groq API (`openai/gpt-oss-20b`) |
| **TTS Voice Engine** | ElevenLabs API |
| **Cloud Storage** | Google Drive API (OAuth 2.0) |
| **Integrasi API** | TMDb, OpenWeatherMap, iTunes, yfinance, DuckDuckGo (`ddgs`) |
| **Telegram Framework** | `python-telegram-bot` v20+ (Webhook Mode) |
| **HTTP Client** | `httpx` (async) |

---

## 📁 Struktur Proyek

```
.
├── api/
│   └── index.py                    # Entrypoint serverless Vercel (webhook)
├── src/
│   ├── bot.py                      # Telegram Bot handlers & routing
│   ├── gemini.py                   # Gemini AI client, model rotation & tool execution
│   ├── groq.py                     # Groq Fast Path & Slow Path fallback (Function Calling)
│   ├── tools.py                    # Deklarasi tools, OpenAI format converter & executor
│   ├── drive.py                    # Google Drive API integration helper
│   ├── voice.py                    # ElevenLabs TTS & Telegram Voice Note helper
│   ├── kv.py                       # Vercel KV / Upstash Redis REST helper (pipeline, rate limit)
│   ├── autocorrect_utils.py        # Normalisasi kata & pembersihan typo
│   ├── personas.py                 # System prompt & kepribadian Gen-Z Oline
│   └── utils.py                    # Helper tanggal & format Indonesia
├── scripts/
│   └── set_webhook.py              # Script setup & inspeksi Webhook Telegram
├── tests/
│   ├── test_groq_integration.py    # Integration test Groq Fast Path
│   ├── test_groq_slowpath.py       # Integration test Groq Slow Path Fallback & Function Calling
│   ├── test_drive_integration.py   # Unit test Google Drive integration
│   ├── test_autocorrect.py         # Unit test autocorrect & normalisasi
│   ├── test_search.py              # Unit test DuckDuckGo search
│   └── test_local.py               # Unit test local flow
├── brief.md                        # Spesifikasi teknis fitur fallback
├── prd.md                          # Product Requirement Document
├── requirements.txt
├── vercel.json
├── .env.example
└── README.md
```

---

## 🚀 Setup & Deployment

### 1. Clone & Install Dependencies

```bash
git clone https://github.com/Dsap09/Oline_Personal.git
cd Oline_Personal
pip install -r requirements.txt
```

### 2. Konfigurasi Environment Variables

Salin file `.env.example` menjadi `.env` lalu lengkapi nilainya:

```bash
cp .env.example .env
```

Isi variabel utama:
- `TELEGRAM_BOT_TOKEN`: Dari [@BotFather](https://t.me/BotFather)
- `GEMINI_API_KEY`: Dari [Google AI Studio](https://aistudio.google.com/apikey)
- `GROQ_API_KEY`: Dari [Groq Console](https://console.groq.com/keys)
- `TMDB_API_KEY`: Dari [TMDb API](https://www.themoviedb.org/settings/api)
- `OPENWEATHER_API_KEY`: Dari [OpenWeatherMap](https://openweathermap.org/api)
- `KV_REST_API_URL` & `KV_REST_API_TOKEN`: Dari [Vercel KV / Upstash Redis](https://vercel.com/storage/kv)
- `ELEVENLABS_API_KEY` & `ELEVENLABS_VOICE_ID`: Dari [ElevenLabs](https://elevenlabs.io/)
- `GOOGLE_DRIVE_*`: Client ID, Client Secret, Refresh Token & Folder ID dari Google Cloud Console.

### 3. Deploy ke Vercel

```bash
# Install Vercel CLI
npm i -g vercel

# Deploy ke Vercel
vercel --prod
```

Pastikan semua variabel lingkungan dari `.env` diisi pada menu **Settings > Environment Variables** di Vercel Dashboard.

### 4. Set Webhook Telegram

Setelah aplikasi di-deploy ke Vercel, daftarkan Webhook Telegram:

```bash
python scripts/set_webhook.py https://your-project.vercel.app
```

Cek status webhook:
```bash
python scripts/set_webhook.py --info
```

### 5. Jalankan Unit Test (Opsional)

Untuk memverifikasi semua fungsi dan integrasi berjalan baik:

```bash
python -m unittest discover tests
```

---

## 💬 Contoh Penggunaan

```text
User: Hai Oline, apa kabar?
Oline: Haii! Aku baik nih, kamu gimana? Ada yang bisa Oline bantu hari ini? 😊

User: Cuaca besok di Bandung gimana?
Oline: 🌤️ Kondisi di Bandung besok diprediksi sedikit berawan
       🌡️ Suhu sekitar 25°C, adem dan nyaman banget
       💡 Pas buat jalan-jalan sore, tapi tetep bawa payung ya!

User: Cek saham BBCA dong
Oline: BBCA sekarang Rp 10,250 📈 (+150, +1.49%)

User: Cek kuota
Oline: ⚡ Groq API (Fast Path / Sapaan): 1,250 / 14,400,000 token (0.0%), sisa 14,398,750 token
       🛠️ Gemini API (Slow Path / Tools): 45,000 / 1,000,000 token (4.5%), sisa 955,000 token

User: Tolong simpan foto ini ke folder Foto Kuliah
Oline: File 'foto_123.jpg' berhasil tersimpan rapi di folder 'Foto Kuliah'! 📁✨
```

---

## 📝 Lisensi

Personal project oleh Doni.
