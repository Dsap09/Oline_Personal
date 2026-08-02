
## Brief Fitur: Auto-Correct Typo Ringan Sebelum Pemrosesan Pesan

### 🎯 Tujuan
Bot Oline tetap bisa memahami maksud pengguna meskipun ada kesalahan ketik (typo) kecil, tanpa mengubah pengalaman ngobrol yang cepat.

### 🔧 Solusi
Gunakan library spell checker ringan berbahasa Indonesia `autocorrect` (gratis, tanpa API) untuk mengoreksi teks sebelum masuk ke pengecekan intent atau dikirim ke Gemini.

Contoh:
- Input: "cari tau siap ekin"
- Output setelah koreksi: "cari tau siapa ekin"

Library `autocorrect` mendukung bahasa Indonesia (`lang='id'`) dan cukup akurat untuk typo umum.

### 🛠️ Langkah Implementasi

#### 1. Tambahkan Dependensi
Di `requirements.txt`, tambahkan:
```
autocorrect
```

#### 2. Modifikasi Handler Pesan (`handlers.py`)
Pada bagian awal fungsi yang menerima teks dari pengguna, lakukan koreksi ejaan:

```python
from autocorrect import Speller

# Inisialisasi sekali di level modul (agar tidak dibuat ulang setiap request)
spell_id = Speller(lang='id')

# Di dalam fungsi handler:
original_text = update.message.text
corrected_text = spell_id(original_text)

# Opsional: log perbedaan agar bisa di-debug
if original_text != corrected_text:
    print(f"Typo corrected: '{original_text}' -> '{corrected_text}'")

# Gunakan corrected_text untuk keyword detection dan kirim ke Gemini
text_to_process = corrected_text
```

#### 3. Pastikan Nama Orang / Kata Khusus Tidak Terkoreksi Berlebihan
Kadang nama seperti "Ekin" bisa dikoreksi menjadi "ekin" (kata benda?). Tapi dalam kasus ini, "Ekin" adalah nama, jadi mungkin akan tetap dianggap tidak baku. Untuk sementara, biarkan dulu. Kalau ke depannya sering salah koreksi nama, kita bisa tambahkan daftar pengecualian (custom word list) di Speller.

#### 4. (Opsional) Fallback di System Prompt
Tambahkan instruksi di system prompt Oline: "Jika pengguna mengetik dengan sedikit typo, cobalah pahami maksud sebenarnya dan jangan langsung menyerah. Gunakan fungsi pencarian jika diperlukan dengan perkiraan kata yang benar."

### 📁 File yang Perlu Diubah/Dibuat
- `requirements.txt` – tambahkan `autocorrect`
- `src/handlers.py` – tambahkan inisialisasi Speller dan terapkan pada teks sebelum diproses

### 🧪 Skenario Uji
- Input: "cari tau siap ekin" → Oline akan mencari "siapa ekin" dan memberikan jawaban.
- Input: "rekomendasi flm horor" → dikoreksi jadi "rekomendasi film horor", lalu berfungsi normal.
- Input: "cuaca di jkarta" → dikoreksi jadi "cuaca di jakarta".
- Input normal tanpa typo tetap aman.

### ⚠️ Catatan
- Latensi tambahan sangat kecil (< 50ms) karena koreksi dilakukan lokal.
- Jika suatu kata tidak dikenal, Speller akan membiarkannya (tidak dipaksa berubah), jadi nama unik seperti "Ekin" tetap lolos.
- Solusi ini bekerja di sisi kode, tidak menambah biaya.
