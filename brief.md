
## Brief Fitur: Fallback Cerdas Groq untuk Semua Fungsi (Slow Path)

### 🎯 Tujuan
1. Memastikan **semua fitur Oline tetap berjalan** meskipun API Gemini sedang error (kuota habis, timeout, 404, dll.).
2. Memanfaatkan **kuota Groq yang besar** (14.400 req/hari) sebagai pengganti otomatis untuk menjalankan *tools*.
3. Menghilangkan pengalaman "bot error" saat Gemini down, diganti dengan respons yang tetap informatif (meskipun mungkin sedikit kurang akurat).

### 🏗️ Arsitektur Baru (Slow Path dengan Fallback)
```
Permintaan pengguna (butuh tools)
        │
        ▼
Coba Gemini + tools
        │
        ├── Berhasil ──▶ Respons Gemini
        │
        └── Gagal (exception / timeout)
                │
                ▼
        Coba Groq + tools (fallback)
                │
                ├── Berhasil ──▶ Respons Groq (dengan catatan opsional)
                │
                └── Gagal ──▶ Pesan lucu Oline (error handling akhir)
```

**Catatan:**  
- Fallback Groq hanya akan dijalankan untuk permintaan **Slow Path** (yang membutuhkan tools). Fast Path sudah menggunakan Groq secara default, jadi tidak terpengaruh.
- Jika Groq juga gagal (jarang terjadi), Oline akan memberikan pesan ramah, bukan error mentah.

### 🛠️ Langkah Implementasi

#### 1. Tingkatkan Kemampuan `src/groq.py` – Dukungan Function Calling
Saat ini `chat_groq` hanya menerima pesan teks biasa. Kita perlu fungsi baru yang bisa menerima **tools** dan mengeksekusi *function calling*.

**Buat fungsi `chat_groq_with_tools`:**
```python
import json
from groq import Groq

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
GROQ_MODEL = "llama-3.1-8b-instant"

# Import handler tools (dari tools.py)
from src.tools import TOOL_HANDLERS

async def chat_groq_with_tools(system_prompt: str, history: list, user_message: str, tools: list) -> str:
    """
    Panggil Groq dengan function calling.
    Jika Groq memutuskan memanggil fungsi, eksekusi, lalu kirim ulang hasilnya ke Groq.
    """
    messages = [{"role": "system", "content": system_prompt}]
    for h in history[-10:]:
        messages.append(h)
    messages.append({"role": "user", "content": user_message})
    
    # Panggil pertama: Groq menentukan apakah perlu tool
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        tools=tools,  # Tools dalam format OpenAI
        tool_choice="auto",
        temperature=0.9,
        max_tokens=1024
    )
    
    response_message = response.choices[0].message
    
    # Cek apakah Groq ingin memanggil fungsi
    tool_calls = response_message.tool_calls
    if not tool_calls:
        # Tidak ada tool call, langsung kembalikan teks
        return response_message.content or ""
    
    # Ada tool call → eksekusi
    messages.append(response_message)  # simpan respons Groq yang berisi tool call
    
    for tool_call in tool_calls:
        function_name = tool_call.function.name
        function_args = json.loads(tool_call.function.arguments)
        
        # Panggil handler yang sesuai (dari TOOL_HANDLERS)
        if function_name in TOOL_HANDLERS:
            try:
                function_result = await TOOL_HANDLERS[function_name](**function_args)
            except Exception as e:
                function_result = f"Error saat menjalankan fungsi: {e}"
        else:
            function_result = f"Fungsi {function_name} tidak dikenal."
        
        # Tambahkan hasil tool ke pesan
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": str(function_result)
        })
    
    # Panggil kedua: Groq merangkai respons akhir berdasarkan hasil tool
    final_response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        temperature=0.9,
        max_tokens=1024
    )
    
    return final_response.choices[0].message.content or ""
```

**Penting:** Format tools yang dikirim harus kompatibel dengan OpenAI. Gemini tools yang sudah ada mungkin perlu dikonversi (biasanya sudah mirip). Antigravity bisa menyesuaikan jika diperlukan.

#### 2. Pastikan `TOOL_HANDLERS` Tersedia
Di `src/tools.py`, pastikan ada dictionary yang memetakan nama fungsi ke handler-nya, contoh:
```python
TOOL_HANDLERS = {
    "get_stock_price": get_stock_price,
    "get_market_summary": get_market_summary,
    "search_internet": search_internet,
    "get_weather": get_weather,
    # ... dan seterusnya
}
```
Jika belum ada, buat dictionary ini.

#### 3. Modifikasi `handlers.py` – Fallback di Slow Path
Di bagian handler yang menangani Slow Path, bungkus pemanggilan Gemini dengan `try-except`. Jika gagal, panggil `chat_groq_with_tools`.

```python
from src.gemini import chat_with_oline  # Gemini
from src.groq import chat_groq_with_tools  # Groq fallback

# Di dalam fungsi handler setelah intent terdeteksi:
if intent is not None:
    tools = TOOLS_BY_INTENT.get(intent, [])
    try:
        # Coba Gemini dulu
        response = await chat_with_oline(
            system_prompt=SYSTEM_PROMPT,
            history=history,
            user_message=user_text,
            tools=tools
        )
    except Exception as e:
        log.warning(f"Gemini gagal, mencoba fallback ke Groq. Error: {e}")
        try:
            # Fallback ke Groq dengan tools yang sama
            response = await chat_groq_with_tools(
                system_prompt=SYSTEM_PROMPT,
                history=history,
                user_message=user_text,
                tools=tools
            )
            # Tambahkan catatan kecil di respons agar user tahu (opsional)
            response += "\n\n(⚠️ Oline pakai otak cadangan nih, Gemini lagi istirahat~)"
        except Exception as e2:
            log.error(f"Groq fallback juga gagal: {e2}")
            response = "Aduh, Oline lagi error dua-duanya nih. Coba lagi nanti ya, bestie~ 😢"
```

#### 4. Konversi Tools Gemini ke Format OpenAI (Jika Diperlukan)
Gemini menggunakan format tools yang berbeda (biasanya dictionary dengan key `function_declarations`). Groq (OpenAI format) membutuhkan format berbeda. Antigravity bisa membuat fungsi kecil untuk mengonversi, atau menyimpan tools dalam format yang kompatibel dengan keduanya.  
Contoh sederhana: pastikan tools yang dikirim ke `chat_groq_with_tools` sudah dalam format:
```python
{
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "...",
        "parameters": { ... }
    }
}
```

#### 5. Penanganan Timeout
- Timeout Gemini sudah ada (8 detik). Jika timeout, exception akan dilempar dan langsung ditangkap untuk fallback ke Groq.
- Timeout Groq bisa diatur lebih longgar (10 detik) untuk memberi kesempatan function calling selesai.

### 📁 File yang Perlu Diubah/Dibuat
| File | Aksi |
|------|------|
| `src/groq.py` | Tambah fungsi `chat_groq_with_tools` |
| `src/tools.py` | Pastikan ada `TOOL_HANDLERS` mapping |
| `src/handlers.py` | Modifikasi slow path: try Gemini, except Groq fallback |
| `src/gemini.py` | Pastikan `chat_with_oline` bisa melempar exception yang jelas |

### 🧪 Contoh Percakapan (Saat Gemini Kuota Habis)
```
User: Cuaca di Tuban gimana?
(Proses: Gemini gagal karena kuota habis)
(Fallback: Groq dipanggil dengan tools cuaca)
(Groq berhasil ambil data dari OpenWeather, lalu merangkai respons)
Oline: "Otak utama lagi capek, tapi aku cek pakai cadangan ya~ Cuaca di Tuban sekarang berawan, 26°C. Jangan lupa bawa payung! ☁️"
```

### ⚠️ Catatan Penting
- **Akurasi Groq**: Model `llama-3.1-8b-instant` mungkin kurang akurat dalam memilih tools atau mengekstrak argumen dibanding Gemini. Namun untuk fallback, ini sudah cukup. Jika hasilnya kurang tepat, user bisa mencoba lagi nanti.
- **Kuota Groq**: Tetap gratis 14.400 req/hari. Pemakaian function calling akan sedikit lebih boros karena dua panggilan (pertama untuk tool choice, kedua untuk final). Tapi masih sangat aman untuk penggunaan pribadi.
- **Konsistensi Persona**: System prompt yang sama dipakai untuk Groq dan Gemini, sehingga Oline tetap berkepribadian sama.
- **Logging**: Pastikan setiap fallback tercatat di log Vercel untuk pemantauan.
