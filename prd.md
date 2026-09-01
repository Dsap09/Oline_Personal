
```markdown
# Product Requirement Document (PRD) – Oline, Personal AI Telegram Bot

**Versi:** 1.0  
**Tanggal:** 29 Juli 2026  
**Pemilik:** [ Doni]  
**Tujuan:** Membangun asisten pribadi berbasis Telegram yang bernama Oline, berpersona Gen-Z, untuk membantu kehidupan sehari-hari lewat percakapan alami.

---

## 1. Gambaran Produk

Oline adalah bot Telegram yang berperilaku layaknya seorang teman perempuan Gen-Z berusia 19 tahun. Ia memiliki kepribadian kalem, cool, namun bisa lucu dan gemes. Bot dirancang untuk membantu penggunanya dengan empat fitur utama yang seluruhnya diakses tanpa perintah khusus berbasis `/` (kecuali untuk jurnal harian). Semua interaksi dideteksi maksudnya secara otomatis menggunakan kemampuan pemahaman bahasa alami Gemini.

Produk ini sepenuhnya gratis dalam operasionalnya dengan memanfaatkan layanan serverless (Vercel) dan API publik yang memiliki free tier mencukupi.

---

## 2. Persona Bot (Oline)

- **Nama:** Oline
- **Usia:** 19 tahun
- **Kepribadian:** Kalem, santai, humoris dengan sentuhan gemas, bukan yang hiperaktif. Menggunakan gaya bahasa campuran Indonesia informal dan sedikit slang Gen-Z (seperti “sip”, “okei”, “gemes”, “btw”). Tidak menggunakan kata kasar. Kadang menambahkan stiker atau emoji jika cocok.
- **Konteks:** Oline mengingat percakapan sebelumnya (memanfaatkan memori sederhana) sehingga bisa menyapa pengguna dengan lebih personal.

---

## 3. Fitur Utama

### 3.1 Tanya AI Personal
- **Deskripsi:** Pengguna bisa mengobrol bebas dengan Oline tentang apa saja. Oline akan menjawab sesuai personanya.
- **Pemicu:** Semua teks yang bukan permintaan spesifik (rekomendasi, cuaca, jurnal) akan dianggap sebagai obrolan umum.
- **Memori:** Bot menyimpan ringkasan percakapan penting di Vercel KV agar Oline bisa merujuk ke obrolan sebelumnya (misal nama pengguna, hobi, kejadian yang pernah diceritakan).
- **Konteks:** Maksimal 10–15 pesan terakhir disertakan dalam prompt untuk menjaga performa, ditambah ringkasan memori.
- **Teknis:** Menggunakan Gemini API (model `gemini-1.5-flash` atau yang paling efisien) dengan **function calling** untuk membedakan intent rekomendasi/cuaca/jurnal dari obrolan biasa.

### 3.2 Rekomendasi Acak
- **Deskripsi:** Pengguna bisa meminta rekomendasi film, lagu, atau buku. Oline akan mengambil data dari API publik dan menyajikan hasil dengan gaya personal.
- **Pemicu:** Frasa seperti “rekomendasiin film horor”, “cari lagu chill indonesia 90an”, “kasih rekomendasi buku fiksi”. Bisa disertai filter (genre, tahun, mood).
- **Kategori:**
  - Film: Gunakan TMDb API (search & discover).
  - Lagu: Gunakan iTunes Search API (berdasarkan genre, artis, atau kata kunci).
- **Perilaku:** Tidak mencampur kategori; hanya satu jenis per permintaan.
- **Format hasil:** Oline akan menjawab dengan judul, tahun, dan alasan singkat mengapa merekomendasikan itu (dihasilkan oleh Gemini dengan memanfaatkan data API). Untuk lagu, bisa cantumkan nama artis dan link preview (jika ada).

### 3.3 Cek Cuaca
- **Deskripsi:** Pengguna dapat menanyakan cuaca saat ini atau pada tanggal tertentu (maksimal 5 hari ke depan) dengan menyebutkan nama kota.
- **Pemicu:** “Cuaca hari ini di Bandung”, “Besok di Malang cerah gak?”, “Tanggal 3 Agustus cuacanya gimana di Jakarta?”.
- **Data:** Suhu, kondisi (cerah/hujan), kelembapan, kecepatan angin.
- **API:** OpenWeatherMap 5 Day Forecast (gratis). Panggil API untuk data saat ini atau forecast harian.
- **Keterbatasan:** Jika tanggal di luar jangkauan forecast, Oline memberitahu dengan ramah bahwa data belum tersedia.

### 3.4 Jurnal Harian
- **Deskripsi:** Pengguna bisa mencatat jurnal harian dan meminta rekap mingguan.
- **Pemicu:**
  - **Menulis:** `/jurnal` diikuti teks (satu-satunya command eksplisit). Atau secara alami: “Catat jurnal hari ini: tadi lihat kucing lucu di kampus.” (Didukung function calling). Jadi `/jurnal` adalah shortcut opsional.
  - **Membaca rekap:** “Rekap jurnal minggu ini dong” atau “Apa yang kutulis tanggal 15 Juli?”.
- **Penyimpanan:** Setiap entri disimpan di Vercel KV dengan key `jurnal:<chat_id>:YYYY-MM-DD`. Untuk beberapa entri di hari yang sama, teks di-append dengan pemisah baris baru.
- **Rekap:** Mengambil semua key yang sesuai dengan rentang tanggal, lalu meringkas menggunakan Gemini agar sesuai dengan gaya Oline (misal menyoroti momen lucu, mood, dsb).
- **Keamanan:** Data hanya bisa diakses oleh chat ID yang bersangkutan.

---

## 4. Arsitektur & Teknologi

### 4.1 Stack Teknologi
- **Bahasa:** Python 3.11+
- **Hosting:** Vercel (Serverless Functions)
- **Database:** Vercel KV (key-value store, gratis 256 MB)
- **AI/ML:** Google Gemini API (free tier, 1.500 request/hari)
- **Webhook Bot:** `python-telegram-bot` (versi 20+, dengan webhook integration)
- **Integrasi Eksternal:**
  - TMDb API (film)
  - iTunes Search API (lagu)
  - OpenWeatherMap API (cuaca)

### 4.2 Struktur Proyek (Rencana)
```
/ (root)
├── api/
│   └── index.py          # Entrypoint serverless Vercel (webhook)
├── src/
│   ├── bot.py            # Inisialisasi Application
│   ├── handlers.py       # Message handlers (text, voice, dll)
│   ├── gemini.py         # Klien Gemini + function calling
│   ├── tools.py          # Definisi tool/function untuk Gemini (rekomendasi, cuaca, jurnal)
│   ├── kv.py             # Helper untuk akses Vercel KV
│   ├── personas.py       # System prompt Oline
│   └── utils.py          # Fungsi utility
├── requirements.txt
├── vercel.json
└── README.md
```

### 4.3 Alur Kerja Utama
1. Pengguna mengirim pesan teks (atau voice, opsional) ke bot.
2. Telegram mengirim update ke webhook Vercel (`/api/index`).
3. Handler menerima pesan, meneruskan ke Gemini API.
4. Gemini memproses dengan system prompt Oline + riwayat percakapan + memori.
5. Jika Gemini mendeteksi maksud khusus (function call), maka tool terkait dijalankan (misal panggil API cuaca, ambil rekomendasi, simpan jurnal). Hasil tool dikembalikan ke Gemini untuk menghasilkan respons akhir.
6. Bot membalas ke Telegram.

### 4.4 Keamanan & Rate Limiting
- Token bot dan API key disimpan di environment variables Vercel.
- Rate limiting sederhana: per chat_id dibatasi 15 pesan/menit untuk menghindari penyalahgunaan (cukup untuk penggunaan pribadi).
- Tidak ada endpoint publik selain webhook Telegram.

---

## 5. Contoh Percakapan

```
User: Hai Oline, lagi bosen nih.
Oline: haii! bosen tuh musuh utama Gen-Z. butuh rekomendasi film atau lagu? atau mau curhat aja? 😌

User: Rekomendasi film horor indonesia yang seru
Oline: okeh! dari list gue, ada "Pengabdi Setan 2" yang lumayan bikin deg-degan tapi bagus sinematografinya. Selain itu "Qorin" juga rame tuh. Mo tau lebih detail? 🎬

User: Cuaca besok di Yogyakarta gimana?
Oline: besok (30 Juli) di Jogja diprediksi hujan ringan, suhu 24-29°C. Jangan lupa payung ya, bestie! ☔

User: /jurnal Hari ini aku selesai baca novel bagus banget, jadi termotivasi.
Oline: (menyimpan) catatan kamu tersimpan rapi. nanti kalau pengen liat rekap, tinggal bilang "rekap jurnal minggu ini" aja ya! 📖✨

User: Rekap jurnal minggu ini dong.
Oline: Minggu ini kayaknya mood kamu lumayan bagus! Kamu selesai baca novel, terus sempat nemu kafe lucu, dan juga mulai belajar masak. Gemes deh, produktif banget. 😆
```

---

## 6. Kebutuhan Non-Fungsional
- **Waktu respons:** < 3 detik untuk obrolan biasa, < 5 detik jika memanggil API eksternal.
- **Uptime:** Bergantung pada Vercel (99.9%).
- **Skalabilitas:** Cukup untuk pengguna tunggal atau beberapa pengguna terbatas (tidak untuk publik luas).
- **Biaya:** 0 rupiah, seluruhnya menggunakan free tier layanan.

---

## 7. Referensi Repositori GitHub

Berikut beberapa repo yang bisa dijadikan acuan, terutama untuk setup bot Telegram di Vercel dengan Gemini:

1. **Telegram Bot + Vercel + python-telegram-bot**  
   [https://github.com/michaelkro/simple-telegram-bot-vercel](https://github.com/michaelkro/simple-telegram-bot-vercel)  
   Struktur dasar webhook bot di Vercel.

2. **Gemini + python-telegram-bot (Function Calling)**  
   [https://github.com/anant/dev-gemini-bot](https://github.com/anant/dev-gemini-bot)  
   Contoh penggunaan Gemini dengan tools/function calling di bot Telegram.

3. **OpenAI Function Calling di Telegram (bisa diadaptasi)**  
   [https://github.com/karfly/chatgpt-telegram-bot](https://github.com/karfly/chatgpt-telegram-bot)  
   Arsitektur handler dan percakapan bisa dipelajari, lalu ganti dengan Gemini.

4. **Vercel KV + Python Quickstart**  
   [https://github.com/vercel/storage/tree/main/examples/kv-python](https://github.com/vercel/storage/tree/main/examples/kv-python)  
   Contoh kode akses Vercel KV dari Python (menggunakan `@vercel/kv` via HTTP).

5. **Bot Telegram Rekomendasi Film (TMDb)**  
   [https://github.com/malik45/tmdb-telegram-bot](https://github.com/malik45/tmdb-telegram-bot)  
   Bisa diambil bagian pencarian filmnya.

**Catatan:** Karena proyek ini menggabungkan banyak komponen, tidak ada satu repo yang persis sama. Kamu bisa gunakan repo di atas sebagai modul, lalu rangkai sesuai arsitektur yang sudah ditentukan.

---

## 8. Milestone & Next Steps
1. Siapkan semua API key (Telegram, Gemini, TMDb, OpenWeather, Vercel).
2. Buat proyek Vercel, hubungkan dengan Vercel KV.
3. Kembangkan handler dasar dan percakapan sederhana dengan Gemini (tanpa function calling).
4. Tambahkan function calling untuk rekomendasi, cuaca, jurnal.
5. Implementasi memori dengan Vercel KV.
6. Uji coba percakapan dan perbaiki persona.
7. (Opsional) Tambahkan dukungan voice note.
