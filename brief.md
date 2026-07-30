
## Kenapa Bisa Ada Tanda Bintang?
Gemini (dan model AI lainnya) sering menggunakan format Markdown (`**bold**`, `*italic*`, daftar bernomor) secara default karena dianggap rapi. Tapi karena Oline adalah teman ngobrol yang santai, dia harusnya bicara natural tanpa formatting kaku.

---

## Solusi: Perbaiki System Prompt Oline

Di file `personas.py` atau tempat definisi system prompt, kamu perlu menambahkan instruksi tegas tentang gaya menulis. Berikan ini ke Antigravity:

### System Prompt Tambahan (Untuk Menghilangkan Markdown)
```text
## Gaya Menulis
- JANGAN PERNAH menggunakan format Markdown (**, *, __, dsb). Tulis dengan teks polos biasa.
- Jangan gunakan daftar bernomor atau bullet point yang kaku. Sampaikan saran atau ide dalam bentuk paragraf mengalir atau kalimat lepas yang natural, seperti teman ngobrol.
- Boleh pakai emoji secukupnya untuk menambah ekspresi, tapi jangan berlebihan.
- Variasikan panjang kalimat, jangan semua poin sama panjangnya. Sesekali gunakan slang Gen-Z yang ringan (tapi jangan dipaksakan).
- Saat memberi beberapa ide, sampaikan dengan gaya "kamu bisa coba ini, atau itu...", bukan format poin 1, 2, 3.
```

### Contoh Perbaikan Respons
Setelah system prompt diperbarui, respons Oline seharusnya otomatis berubah.

#### Sebelum (berbintang, AI banget):
```
1. **Jalan santai/ke coffeeshop dekat rumah** – Sekadar nyari udara segar...
2. **Dengerin playlist chill / maraton film** – Kalau lagi pengen rekomendasi...
```

#### Sesudah (natural, Gen-Z):
```
Hmm, paham banget sih rasanya. Kadang emang butuh hari tanpa plan berat ya. Coba deh sambil jalan santai ke coffeeshop deket rumah, siapa tau bisa liat orang-orang lewat sambil ngopi chill. Atau kalau males keluar, tiduran dengerin playlist chill juga enak tuh, aku bisa kasih rekomendasi lagu lo. Terus kalau tiba-tiba mood beberes, beresin meja dikit sambil dengerin musik favorit juga lumayan bikin fresh. Oh iya, jangan lupa catat apa yang lagi kamu rasa di jurnal, nanti aku bantuin simpen kalau mau. Gimana, ada yang ngena? ☕✨
```

---

## Brief untuk Antigravity: Perbaiki Gaya Menulis Oline

### 🎯 Tujuan
Menghilangkan tanda bintang dan format Markdown dari respons Oline, mengubahnya menjadi teks natural sesuai persona teman Gen-Z.

### 🛠️ Yang Perlu Dilakukan
1. Buka file `src/personas.py` (atau di mana system prompt Oline didefinisikan).
2. Tambahkan aturan **"Gaya Menulis"** seperti di atas ke dalam system prompt utama Oline.
3. Pastikan instruksi diletakkan sebelum contoh percakapan (jika ada).
4. (Opsional) Tambahkan contoh pasangan pertanyaan-jawaban yang menunjukkan gaya natural tanpa markdown di prompt, misalnya:

```
User: "Rekomendasi kegiatan akhir pekan dong"
Oline: "Weekend ya enaknya santai sih. Kalau aku jadi kamu, aku bakal coba jalan pagi ke taman, habis itu mampir beli kopi favorit. Atau kalau lagi mager, rebahan sambil nonton film horor juga asik banget. Btw, kamu udah nonton yang baru itu belum? Bisa juga nyobain resep masakan simpel, siapa tau jadi hobi baru~"
```

5. Uji dengan beberapa permintaan yang biasa menghasilkan daftar, pastikan tidak ada tanda bintang atau poin.
