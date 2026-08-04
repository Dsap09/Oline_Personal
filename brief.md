
## Brief Fitur: Integrasi Groq API untuk Fast Path (Hemat Kuota Gemini)

### 🎯 Tujuan
1. Menghemat kuota Gemini dengan memindahkan obrolan ringan (fast path) ke Groq.
2. Menambah total kuota harian bot secara signifikan (Groq: 14.400 req/hari, Gemini: 1.500 req/hari).
3. Membuat Oline lebih cepat merespons sapaan dan obrolan tanpa tools.
4. Menyediakan fallback otomatis: jika Groq error/limit, lempar ke Gemini.

### 🏗️ Arsitektur Dual API

| Jalur | API | Model | Tools? |
|-------|-----|-------|--------|
| **Fast Path** (sapaan, curhat, tanya umum) | **Groq** | `llama-3.1-8b-instant` | ❌ Tanpa tools |
| **Slow Path** (butuh tools: cuaca, saham, dll.) | **Gemini** | `gemini-1.5-flash` | ✅ Dengan tools |
| **Fallback** (jika Groq gagal) | **Gemini** | `gemini-1.5-flash` | ❌ Tanpa tools |

Alur:
```
Pesan masuk → Intent detection
├─ Fast Path (tanpa tools) → Groq → berhasil? → balas
│                                      └─ gagal? → Gemini (fallback)
└─ Slow Path (butuh tools) → Gemini + tools → balas
```

### 🛠️ Langkah Implementasi

#### 1. Dapatkan API Key Groq
- Daftar di [console.groq.com](https://console.groq.com).
- Buat API key, simpan sebagai environment variable di Vercel:
  - `GROQ_API_KEY` = `gsk_...`

#### 2. Tambahkan Dependensi
Di `requirements.txt`:
```
groq
```

#### 3. Buat File Baru `src/groq.py`
Fungsi untuk memanggil Groq dengan retry dan fallback:

```python
import os
from groq import Groq

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

GROQ_MODEL = "llama-3.1-8b-instant"

async def chat_groq(system_prompt: str, history: list, user_message: str) -> str:
    """Panggil Groq untuk fast path. Return teks respons atau raise exception."""
    messages = [{"role": "system", "content": system_prompt}]
    
    # Tambahkan riwayat (maks 5 pasang)
    for h in history[-10:]:
        messages.append(h)
    
    messages.append({"role": "user", "content": user_message})
    
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        temperature=0.9,
        max_tokens=1024
    )
    
    return response.choices[0].message.content
```

**Catatan:** Jika ingin retry logic, bisa ditambahkan di sini (exponential backoff).

#### 4. Modifikasi `handlers.py` — Pisah Jalur Fast & Slow

Di bagian handler pesan, setelah intent detection:

```python
from src.groq import chat_groq
from src.gemini import chat_with_oline  # yang sudah ada

# ... setelah dapat intent ...

if intent is None:  # Fast Path
    try:
        response = await chat_groq(SYSTEM_PROMPT, history, user_text)
    except Exception as e:
        log.warning(f"Groq failed: {e}, fallback to Gemini")
        response = await chat_with_oline(
            SYSTEM_PROMPT, history, user_text, tools=None  # Tanpa tools
        )
else:  # Slow Path
    tools = TOOLS_BY_INTENT.get(intent, [])
    response = await chat_with_oline(
        SYSTEM_PROMPT, history, user_text, tools=tools
    )
```

**Penting:** Pastikan `chat_with_oline` di `gemini.py` menerima parameter `tools=None` agar bisa dipanggil tanpa tools untuk fallback.

#### 5. Penanganan Rate Limit & Retry
- Groq: tambahkan retry dengan exponential backoff (1s, 2s, 4s) di `chat_groq`. Jika tetap gagal, lempar exception agar fallback ke Gemini.
- Gemini: sudah ada retry, pastikan tetap berfungsi.

#### 6. System Prompt yang Sama
Gunakan system prompt Oline yang sama persis (dari `personas.py`) untuk Groq dan Gemini, agar karakter Oline konsisten.

#### 7. (Opsional) Monitoring Kuota Groq
Header respons Groq mengandung `x-ratelimit-remaining-requests`. Bisa disimpan ke Vercel KV untuk fitur "cek kuota" nanti. Tapi ini bisa menyusul.

### 📁 File yang Perlu Diubah/Dibuat
| File | Aksi |
|------|------|
| `requirements.txt` | Tambahkan `groq` |
| `src/groq.py` | **Baru** — client Groq + fungsi `chat_groq` |
| `src/handlers.py` | Ubah — pisah fast path (Groq) dan slow path (Gemini), tambah fallback |
| `src/gemini.py` | Pastikan `chat_with_oline` bisa dipanggil dengan `tools=None` |
| Environment Vercel | Tambahkan `GROQ_API_KEY` |

### 🧪 Contoh Percakapan (Fast Path via Groq)
```
User: halo lin
Oline: (Groq) haii! tumben nongol, ada cerita apa hari ini? ✨

User: aku lagi bete nih
Oline: (Groq) lah kenapa bestie? spill dong, siapa tau aku bisa bantu~ 😔
```

### ⚠️ Catatan Penting
- **Model Groq:** `llama-3.1-8b-instant` dipilih karena gratis, cepat, dan kuota besar. Jangan gunakan model besar di fast path.
- **Function calling:** Tetap di Gemini. Groq tidak akan menerima tools di tahap ini.
- **Fallback:** Jika Groq down atau limit, Oline tetap bisa jawab lewat Gemini. User tidak akan merasakan perbedaan.
- **Biaya:** Tetap gratis. Groq free tier cukup untuk penggunaan pribadi.
