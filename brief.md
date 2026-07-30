
## Brief Fitur: Pelacakan Kuota Gemini Otomatis & Perintah “Cek Kuota”

### 🎯 Tujuan
Pengguna dapat menanyakan sisa kuota harian Gemini API yang sudah terpakai oleh Oline, cukup dengan bahasa alami (misal “Oline, cek kuota”). Semua pelacakan terjadi otomatis di balik layar.

### ⚙️ Mekanisme Otomatis
1. **Setiap kali Gemini mengembalikan respons sukses** (entah itu obrolan biasa atau function call), ambil `usage_metadata` dari objek respons (`response.usage_metadata`).
2. Simpan **total_token_count** ke Vercel KV dengan struktur:
   - Key: `gemini_usage:<chat_id>:YYYY-MM-DD`
   - Value: integer (ditambahkan terus, jadi jika sudah ada key, tambahkan nilainya).
3. Gunakan operasi **INCR** jika tersedia, atau GET → tambah → SET (dengan hati-hati agar tidak race condition, tapi karena bot satu pengguna tidak masalah).

### 📊 Kuota Acuan (Free Tier)
- **Model yang digunakan**: `gemini-1.5-flash` (setelah migrasi).
- Kuota gratis per hari: **1.500 permintaan** dan **1.000.000 token**.
- Untuk kesederhanaan, kita tampilkan kuota token saja (atau bisa dua-duanya nanti).

### 💬 Intent “Cek Kuota”
1. Tambahkan ke sistem **function calling** sebuah function baru, misal `check_quota`.
2. Pemicu: frasa seperti “cek kuota”, “sisa token”, “kuota Gemini”, dsb.
3. Saat terpicu, function akan:
   - Baca semua key dengan pola `gemini_usage:<chat_id>:*` untuk hari ini (atau bisa juga baca yang hari ini saja).
   - Hitung total token terpakai hari ini.
   - Hitung sisa token: `1_000_000 - total`.
   - Kembalikan hasilnya agar Gemini merangkai respons dengan gaya Oline.
4. Jika belum ada data (misal belum ada pemakaian), Oline akan bilang belum ada catatan hari ini.

### 📁 File yang Perlu Diubah/Ditambah
- `src/gemini.py`:
  - Setelah panggil `model.generate_content`, ambil `usage_metadata` dan panggil fungsi baru `save_usage(chat_id, total_tokens)`.
  - Tambahkan definisi function `check_quota` ke daftar tools yang dikirim ke Gemini.
- `src/kv.py`:
  - Tambahkan fungsi `save_usage(chat_id, tokens)`.
  - Tambahkan fungsi `get_today_usage(chat_id)`.
- `src/tools.py` (atau di file terpisah):
  - Implementasikan handler untuk `check_quota` yang membaca KV dan mengembalikan hasil.
- `src/personas.py` (opsional):
  - Tambahkan contoh respons Oline saat ditanya kuota, agar tetap gemes.

### 🧪 Contoh Interaksi
```
User: Oline, cek kuota dong
Oline: Hari ini Oline udah pakai 124.500 token dari 1.000.000 token gratis.
       Masih aman banget, bestie! Mau ngobrol apa lagi nih? ✨
```

### ⚠️ Catatan Penting
- Pastikan Vercel KV sudah terkonfigurasi (environment variables `KV_REST_API_URL` dan `KV_REST_API_TOKEN` sudah di-set).
- Fitur ini tidak menambah biaya, tetap dalam batas gratis.
- Pelacakan hanya untuk pemakaian lewat bot (cukup akurat untuk personal use).
