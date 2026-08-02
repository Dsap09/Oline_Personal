
## Brief Fitur: Oline Bisa Cari Info di Internet (DuckDuckGo)

### 🎯 Tujuan
Oline mampu mencari informasi terkini dari internet saat pengguna bertanya hal di luar pengetahuan Gemini (berita, fakta terbaru, definisi, dll.), lalu menyampaikannya dengan gaya natural Oline.

### 💰 Opsi Teknis
Pakai **DuckDuckGo Instant Answer** via library `duckduckgo_search` (gratis, tanpa API key, tanpa batas harian resmi). Ini aman untuk penggunaan personal dengan rate limiting wajar.

### 🛠️ Langkah Implementasi

#### 1. Tambahkan Dependensi
- Di `requirements.txt`, tambahkan: `duckduckgo-search`

#### 2. Tambahkan Tool Baru di Function Calling
Di file `src/tools.py` (atau tempat mendefinisikan tools), tambahkan definisi fungsi:

```python
search_tool = {
    "name": "search_internet",
    "description": "Cari informasi terkini di internet. Gunakan saat pengguna bertanya hal yang memerlukan data real-time atau di luar pengetahuan umum yang kamu miliki.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Kata kunci pencarian yang ingin dicari di internet."
            }
        },
        "required": ["query"]
    }
}
```

- Pastikan `search_tool` dimasukkan ke dalam daftar tools yang tersedia untuk intent pencarian. (Bisa ditambahkan ke `TOOLS_BY_INTENT` di handler fast path nanti).

#### 3. Buat Handler untuk Tool
Di file yang sama (`tools.py`), implementasikan fungsi pemanggil DuckDuckGo:

```python
from duckduckgo_search import DDGS

def search_internet(query: str) -> str:
    try:
        with DDGS() as ddgs:
            results = ddgs.text(query, max_results=3)
            if not results:
                return "Oline gak nemu info yang cocok nih, bestie."
            # Gabungkan judul dan body untuk konteks Gemini
            snippets = []
            for r in results:
                snippets.append(f"{r['title']}: {r['body']}")
            return "\n".join(snippets)
    except Exception as e:
        # Fallback jika DDG error
        return "Aduh, Oline lagi gak bisa akses internet nih. Coba lagi nanti ya~"
```

**Catatan:** Karena Gemini nanti yang akan merangkum, kita berikan data mentah. Jangan lupa return teks yang cukup informatif.

#### 4. Daftarkan Handler di `gemini.py` (atau handler utama)
- Tambahkan fungsi `search_internet` ke mapping pemanggilan tools.  
- Jika pakai dictionary tool handler seperti `TOOL_HANDLERS = {"search_internet": search_internet}`, pastikan terdaftar.

#### 5. Integrasikan ke Fast Path / Intent Detection
Di `handlers.py`, tambahkan intent “search” ke dalam `HEAVY_KEYWORDS`:

```python
"search": ["cari", "search", "apa itu", "siapa", "kapan", "dimana", "berita", "definisi", "pengertian"]
```

Dan pastikan tools search ditambahkan ke `TOOLS_BY_INTENT["search"] = [search_tool]`.

Atau bisa juga, tanpa intent spesifik: biarkan Gemini yang memutuskan kapan memanggil search. Tapi agar tetap cepat, lebih baik search di-trigger oleh kata kunci tertentu (slow path), tidak di-fast-path.

#### 6. Perbarui System Prompt Oline
Di `personas.py`, tambahkan instruksi agar Oline tahu kapan harus menggunakan search:

```text
## Pengetahuan dan Pencarian Internet
- Pengetahuan dasarmu hanya sampai pertengahan 2024. Jika pengguna bertanya tentang hal yang terjadi setelahnya atau memerlukan data terkini, WAJIB gunakan fungsi search_internet.
- Setelah mendapatkan hasil pencarian, olah kembali menjadi jawaban yang natural ala Oline. Jangan hanya copy-paste mentah.
- Sebut sumber singkat jika relevan (misal "kata Detik.com sih...") tapi jangan berlebihan.
```

#### 7. Penanganan Rate Limiting (Opsional, tapi disarankan)
- Beri jeda 2 detik setelah setiap panggilan DDG (gunakan `time.sleep(2)` di handler) untuk menghindari IP diblokir.
- Karena bot pribadi, ini sangat jarang terjadi, tapi lebih aman.

#### 8. Chat Action
- Saat search dipanggil, kirim `sendChatAction` dengan `action="typing"` (atau "find_location" untuk variasi) supaya pengguna tahu Oline sedang mencari.

### 📁 File yang Perlu Diubah/Dibuat
- `requirements.txt` – tambahkan `duckduckgo-search`
- `src/tools.py` – tambahkan `search_tool` dan handler `search_internet`
- `src/gemini.py` – daftarkan tool handler baru
- `src/handlers.py` – tambahkan intent "search" ke keyword dan mapping tools
- `src/personas.py` – update system prompt

### 🧪 Contoh Percakapan
```
User: Olin, siapa presiden Indonesia sekarang?
Oline: (search otomatis)
Bentar ya, Oline cek dulu~
Presiden Indonesia sekarang adalah Prabowo Subianto, bestie. Dilantik 20 Oktober 2024 kemarin. Jadi udah ganti nih dari Pak Jokowi.

User: Berapa harga emas hari ini?
Oline: (search)
Harga emas Antam hari ini di kisaran Rp 1.450.000 per gram, naik dikit dari kemarin. Mau investasi atau sekadar pantau aja nih? 💸
```

### ⚠️ Catatan
- Hindari pencarian berulang untuk pertanyaan yang mirip dalam waktu singkat; manfaatkan memori percakapan agar tidak boros.
- Jika DDG down, Oline akan memberikan fallback yang lucu tanpa error mentah.
- Fitur ini tetap gratis, tidak ada biaya tambahan.
