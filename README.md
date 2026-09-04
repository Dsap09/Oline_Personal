# Oline – Personal AI Telegram Bot 🤖

Oline adalah bot Telegram asisten pribadi berpersona Gen-Z yang cerdas, cepat, dan serba bisa. Dibangun menggunakan **Python 3.10+**, **Google Gemini AI**, **Groq API**, **Neo4j AuraDB**, **Moondream VLM**, **Notion API**, dan dideploy di **Vercel Serverless Functions**.

---

## ✨ Fitur Utama

- **⚡ Fast Path (Groq API)** — Respon kilat untuk obrolan santai, sapaan, dan pertanyaan ringan menggunakan model `openai/gpt-oss-20b`.
- **🛠️ Slow Path (Google Gemini API)** — Pemrosesan kecerdasan utama dengan rotasi model otomatis (`gemini-flash-lite-latest`, `gemini-2.5-flash`, `gemini-2.0-flash`) dan Function Calling untuk tugas kompleks.
- **🛡️ Groq Slow Path Fallback** — Jika Gemini down (kuota habis/429/timeout), Oline otomatis fallback ke Groq dengan dukungan *Function Calling* (2-stage OpenAI tool execution) agar fitur bot tidak pernah mati.
- **🖼️ Analisis Gambar (Moondream VLM)** — Analisis dan deskripsi foto/gambar otomatis dari chat Telegram menggunakan **Moondream3** (`merve/moondream3`) dan **Moondream2** (`vikhyatk/moondream2`) dengan penerjemahan & penggubahan ulang (*auto-translation & rephrasing*) ke Bahasa Indonesia khas Gen-Z oleh Oline.
- **🎨 Search & Inspeksi Referensi Desain Website** — Mencari website referensi di internet (DuckDuckGo) dan menginspeksi elemen desainnya (font, warna hex dominan, struktur layout, hero text `<h1>`) via `BeautifulSoup` & `lxml` sebagai inspirasi landing page.
- **🚀 Landing Page Preview & Vercel Deploy** — Pembuatan landing page modern anti-AI-slop dengan preview otomatis di CodePen (`preview_with_codepen`) dan deployment langsung ke Vercel (`deploy_to_vercel`).
- **🔗 Activity Graph Log (Neo4j AuraDB)** — Penyimpanan & pencarian riwayat aktivitas pengguna dalam bentuk graph (`User` -[`:MELAKUKAN`]-> `Aktivitas`) dengan perekaman otomatis (*auto-log*) pada setiap aksi penting.
- **💻 Eksekusi Kode (Piston API)** — Jalankan potongan kode cepat (Python, JavaScript, C++, Java, dll.) langsung dari chat dengan pemotongan output otomatis max 1500 karakter dan timeout 15 detik.
- **📓 Integrasi Notion Database** — Simpan catatan (judul, isi, kategori, dan tanggal WIB) serta tambah/edit kolom database Notion secara otomatis (via Notion API).
- **⏰ Akurasi Waktu Real-Time (WIB)** — Penyuntikan otomatis hari, tanggal, bulan, tahun, dan jam WIB (UTC+7) ke system prompt di semua jalur AI agar jawaban waktu selalu akurat.
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
| **Graph Database** | Neo4j AuraDB (`neo4j` official driver) |
| **Vision Language Model** | Moondream3 (`merve/moondream3`) + Moondream2 (`vikhyatk/moondream2`) |
| **HTML Parsing & Inspection** | `beautifulsoup4` & `lxml` |
| **AI Primary Engine** | Google Gemini API (`google-genai` SDK) |
| **AI Fast Engine & Fallback** | Groq API (`openai/gpt-oss-20b`) |
| **AI Landing Page Generator** | DeepInfra API (`DeepSeek-V4-Flash-0731`) |
| **Catatan / Productivity** | Notion API (`https://api.notion.com`) |
| **Eksekusi Kode** | Piston API (`https://emkc.org/api/v2/piston/execute`) |
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
│   ├── bot.py                      # Telegram Bot handlers & intent routing
│   ├── gemini.py                   # Gemini AI client, model rotation & system prompt context
│   ├── groq.py                     # Groq Fast Path & Slow Path fallback (Function Calling)
│   ├── tools.py                    # Deklarasi tools, OpenAI format converter & executor registry
│   ├── neo4j_client.py             # Neo4j AuraDB graph database client (simpan/cari aktivitas)
│   ├── notion.py                   # Notion REST API helper (save notes, properties & database ID)
│   ├── drive.py                    # Google Drive API integration helper
│   ├── voice.py                    # ElevenLabs TTS & Telegram Voice Note helper
│   ├── kv.py                       # Vercel KV / Upstash Redis REST helper (pipeline, rate limit)
│   ├── autocorrect_utils.py        # Normalisasi kata & pembersihan typo
│   ├── personas.py                 # System prompt & kepribadian Gen-Z Oline
│   └── utils.py                    # Helper tanggal, waktu WIB real-time & format Indonesia
├── scripts/
│   └── set_webhook.py              # Script setup & inspeksi Webhook Telegram
├── tests/
│   ├── test_code_execution.py      # Unit test Piston API code execution
│   ├── test_notion.py              # Unit test Notion integration & ID extractor
│   ├── test_time_context.py        # Unit test WIB time context & prompt injection
│   ├── test_groq_integration.py    # Integration test Groq Fast Path
│   ├── test_groq_slowpath.py       # Integration test Groq Slow Path Fallback & Function Calling
│   ├── test_drive_integration.py   # Unit test Google Drive integration
│   ├── test_autocorrect.py         # Unit test autocorrect & normalisasi
│   ├── test_search.py              # Unit test DuckDuckGo search
│   └── test_local.py               # Unit test local flow
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
- `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`: Dari [Neo4j AuraDB Console](https://console.neo4j.io/)
- `MOONDREAM_SPACE_1` & `MOONDREAM_SPACE_2`: Space Moondream utama (`merve/moondream3`) dan fallback (`vikhyatk/moondream2`)
- `DEEPINFRA_API_KEY` & `DEEPINFRA_MODEL`: Dari [DeepInfra Console](https://deepinfra.com/)
- `NOTION_API_KEY` & `NOTION_DATABASE_ID`: Dari [Notion Integrations](https://www.notion.so/my-integrations)
- `VERCEL_API_TOKEN`: Dari [Vercel Tokens](https://vercel.com/account/tokens)
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
python -m unittest discover -s tests -p "test_*.py"
```

---

## 💬 Contoh Penggunaan

```text
User: Hai Oline, apa kabar?
Oline: Haii! Aku baik nih, kamu gimana? Ada yang bisa Oline bantu hari ini? 😊

User: (Kirim foto bus kuning)
Oline: Gambar ini menunjukkan sebuah bus sekolah berwarna kuning sedang melaju di jalan raya dengan suasana siang hari yang cerah~ 🚌☀️

User: Buat landing page gym, referensinya dari website gym terkenal
Oline: 🎨 Oline udah cari dan analisis beberapa referensi website gym nih! Ini link preview landing page baru yang udah Oline siapin: https://codepen.io/pen/define/xxx

User: Simpan aktivitas: Doni minta landing page gym
Oline: 🔗 Aktivitas 'Doni minta landing page gym' berhasil disimpan ke Neo4j Graph!

User: Tampilkan aktivitas terakhirku
Oline: 🔗 [2026-09-04 20:30:00] deploy -> landing-page-gym
       🔗 [2026-09-04 20:25:00] preview -> GYM MANIA
       🔗 [2026-09-04 20:20:00] simpan catatan -> Ide Riset AI

User: Catat ke Notion: "Ide riset AI agent" isinya "Membahas autonomous agent untuk skripsi."
Oline: 📝 Siap! Catatan 'Ide riset AI agent' udah masuk Notion, kategori Umum~

User: Cuaca besok di Bandung gimana?
Oline: 🌤️ Kondisi di Bandung besok diprediksi sedikit berawan
       🌡️ Suhu sekitar 25°C, adem dan nyaman banget
       💡 Pas buat jalan-jalan sore, tapi tetep bawa payung ya!

User: Cek saham BBCA dong
Oline: BBCA sekarang Rp 10,250 📈 (+150, +1.49%)
```

---

## 📝 Lisensi

Personal project oleh Doni.
