

## Brief Fitur: Kirim Pesan Suara dengan ElevenLabs TTS (Suara Karakter Oline)

### 🎯 Tujuan
Oline bisa mengirim **voice note** di Telegram saat diminta, misalnya:
- “Oline, nyanyi sebaris dong.”
- “Bacain puisi pendek tentang senja.”
- “Ngegombal pake suara ya, Oline.”

Suara yang digunakan adalah suara natural dari ElevenLabs (pre-made voice, bukan hasil cloning), dipilih yang paling cocok dengan persona Oline: **perempuan muda, kalem, cool, tapi bisa lucu dan gemes**.

---

### 🛠️ Arsitektur (Gratis, dalam batas free tier)
| Komponen | Teknologi |
|----------|-----------|
| Bot Telegram | Python, Vercel (existing) |
| TTS Engine | **ElevenLabs API** (free tier 10.000 karakter/bulan) |
| Intent Detection | Gemini function calling (sudah ada) |

Alur:  
`User minta suara → Gemini deteksi intent → Bot panggil ElevenLabs API → Dapat audio MP3/OGG → Kirim voice note ke Telegram`

---

### 📦 Langkah Implementasi

#### 1. Dapatkan ElevenLabs API Key & Pilih Voice
- Daftar di [elevenlabs.io](https://elevenlabs.io) (paket gratis).
- Buka **Profile → API Key**, salin key-nya.
- Buka [Voice Library](https://elevenlabs.io/voice-library), cari suara perempuan natural yang cocok dengan karakter Oline.  
  Beberapa rekomendasi (bisa dicek dulu):
  - `Rachel` – suara perempuan muda, tenang, ramah.
  - `Bella` – agak ceria tapi tetap kalem.
  - `Grace` – lembut dan cool.
- Catat **Voice ID** dari suara yang dipilih (ada di URL atau detail voice).

#### 2. Simpan di Environment Variables Vercel
Tambahkan dua variabel baru:
- `ELEVENLABS_API_KEY` = (API key tadi)
- `ELEVENLABS_VOICE_ID` = (Voice ID pilihan)

#### 3. Tambahkan Function di Gemini Tools
Definisikan fungsi baru dalam daftar tools yang dikirim ke Gemini:

```python
{
    "name": "send_voice_message",
    "description": "Mengirim pesan suara ketika pengguna meminta Oline bernyanyi, membaca puisi, menggombal, atau mengucapkan sesuatu dengan suara.",
    "parameters": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "Teks yang akan diucapkan Oline dengan suara."
            }
        },
        "required": ["text"]
    }
}
```

#### 4. Handler untuk `send_voice_message`
Saat fungsi dipanggil, bot akan:
1. Kirim `sendChatAction` dengan `action: "record_voice"` agar user tahu Oline sedang “merekam”.
2. Panggil ElevenLabs API:

```python
import requests

url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
headers = {
    "Accept": "audio/mpeg",
    "Content-Type": "application/json",
    "xi-api-key": ELEVENLABS_API_KEY
}
data = {
    "text": text,
    "model_id": "eleven_multilingual_v2",  # model standar gratis yang mendukung bahasa Indonesia
    "voice_settings": {
        "stability": 0.5,
        "similarity_boost": 0.5
    }
}
response = requests.post(url, json=data, headers=headers)
audio_bytes = response.content  # ini MP3
```

3. Konversi MP3 ke OGG (format voice note Telegram) menggunakan `ffmpeg` atau library `pydub`.  
   Karena Vercel tidak bisa menjalankan ffmpeg binary, lebih baik gunakan **pydub** (pure Python, tidak butuh binary eksternal):

```python
from pydub import AudioSegment
import io

audio_mp3 = io.BytesIO(audio_bytes)
sound = AudioSegment.from_file(audio_mp3, format="mp3")
ogg_buffer = io.BytesIO()
sound.export(ogg_buffer, format="ogg", codec="libopus")
ogg_buffer.seek(0)
```

4. Kirim voice note ke Telegram:

```python
await context.bot.send_voice(
    chat_id=update.effective_chat.id,
    voice=ogg_buffer,
    caption="🎙️ dari Oline, spesial buat kamu~"
)
```

#### 5. Penanganan Batas Free Tier
Free tier ElevenLabs hanya 10.000 karakter per bulan.  
Agar tidak kehabisan, bisa ditambahkan **pengecekan sederhana**:
- Hitung total karakter yang sudah dipakai bulan ini, simpan di Vercel KV (key: `tts_usage:<chat_id>:YYYY-MM`).
- Sebelum generate, cek apakah `total_karakter + len(text) > 10000`. Jika ya, Oline balas dengan gaya gemes:  
  “Aduh, suara Oline bulan ini udah abis, bestie. Tunggu bulan depan ya, atau kita ngobrol teks aja dulu~ 😘”
- Jika masih cukup, lanjutkan dan tambahkan `len(text)` ke KV.

---

### 🧪 Contoh Interaksi
```
User: Oline, baca puisi pendek dong.
Oline: (mengirim chat action "recording...")
Oline: (mengirim voice note berisi suara perempuan muda membaca puisi)
```

---

### 📁 File yang Perlu Diubah/Dibuat
- `src/tools.py` atau `src/voice.py` (baru) – handler `send_voice_message`, pemanggilan ElevenLabs, konversi audio.
- `src/gemini.py` – tambahkan definisi fungsi `send_voice_message` ke daftar tools.
- `src/kv.py` – tambahkan helper untuk simpan/baca pemakaian karakter TTS (opsional).
- `requirements.txt` – tambahkan `pydub` dan `requests`.

---

### ⚠️ Catatan
- **Waktu proses**: Pembuatan TTS ElevenLabs biasanya 1–3 detik. Dengan network latency, total bisa 3–5 detik. Masih dalam batas 10 detik Vercel (Hobby).
- **Kualitas suara**: Model `eleven_monolingual_v1` gratis, hasilnya cukup natural. Jika suatu saat upgrade, bisa pakai model `eleven_turbo_v2` (lebih cepat, tapi butuh paket Starter).
- **Privasi**: Suara ini bukan tiruan Oline JKT48, jadi aman secara etika.

