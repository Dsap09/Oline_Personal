
## Brief Fitur: Cek Saham & Pergerakan Market Harian (yfinance)

### 🎯 Tujuan
Oline bisa menjawab pertanyaan seputar pergerakan pasar saham Indonesia hari itu, seperti:
- "Olin, IHSG hari ini gimana?"
- "Cek saham BBCA dong."
- "Saham apa yang paling naik hari ini?"

Data diambil secara *real-time* dari Yahoo Finance, disampaikan dengan gaya natural Oline.

### 💰 Biaya
- Library `yfinance` gratis, tanpa API key.
- Tidak ada tambahan biaya operasional.

### 🛠️ Langkah Implementasi

#### 1. Tambahkan Dependensi
Di `requirements.txt`:
```
yfinance>=0.2.54
pandas
```

#### 2. Definisikan Tools untuk Gemini
Tambahkan dua tools baru di file tempat definisi tools disimpan:

**a. `get_stock_price`** — Cek satu saham spesifik.
```python
{
    "name": "get_stock_price",
    "description": "Ambil harga terkini dan perubahan harian suatu saham Indonesia. Kode saham 4 huruf (contoh: BBCA, BBRI).",
    "parameters": {
        "type": "object",
        "properties": {
            "ticker": {
                "type": "string",
                "description": "Kode saham 4 huruf, tanpa .JK (misal: BBCA, TLKM, BBRI)"
            }
        },
        "required": ["ticker"]
    }
}
```

**b. `get_market_summary`** — Ringkasan IHSG dan top movers.
```python
{
    "name": "get_market_summary",
    "description": "Ambil ringkasan pergerakan IHSG hari ini: nilai indeks, perubahan, dan saham top gainer/loser.",
    "parameters": {
        "type": "object",
        "properties": {},
        "required": []
    }
}
```

#### 3. Buat Handler di `tools.py`

```python
import yfinance as yf
import pandas as pd
import time

def get_stock_price(ticker: str) -> str:
    ticker = ticker.upper().strip()
    if not ticker.endswith('.JK') and ticker.isalpha() and len(ticker) == 4:
        ticker += '.JK'
    
    time.sleep(0.5)  # Jeda kecil
    
    try:
        stock = yf.Ticker(ticker)
        data = stock.history(period='1d')
        if data.empty:
            return f"Data {ticker} kosong. Mungkin kode salah atau market lagi tutup ya~"
        
        latest = data['Close'].iloc[-1]
        prev_close = stock.info.get('previousClose', latest)
        change = latest - prev_close
        change_pct = (change / prev_close) * 100
        
        return (
            f"{ticker.replace('.JK','')} sekarang Rp {latest:,.0f} "
            f"({'📈 +' if change >= 0 else '📉 '}{change:,.0f}, "
            f"{'+' if change >= 0 else ''}{change_pct:.2f}%)"
        )
    except Exception as e:
        return f"Gagal ambil data {ticker}: {e}"


def get_market_summary() -> str:
    time.sleep(0.5)
    
    try:
        ihsg = yf.Ticker('^JKSE')
        data = ihsg.history(period='1d')
        if data.empty:
            return "Data IHSG belum tersedia hari ini."
        
        latest = data['Close'].iloc[-1]
        prev_close = ihsg.info.get('previousClose', latest)
        change = latest - prev_close
        change_pct = (change / prev_close) * 100
        
        lines = [
            f"IHSG: Rp {latest:,.0f} "
            f"({'📈 +' if change >= 0 else '📉 '}{change:,.0f}, "
            f"{'+' if change >= 0 else ''}{change_pct:.2f}%)"
        ]
        
        # Top gainer/loser (optional)
        top_gainer = get_top_movers(True)
        top_loser = get_top_movers(False)
        if top_gainer:
            lines.append(f"Top Gainer: {top_gainer}")
        if top_loser:
            lines.append(f"Top Loser: {top_loser}")
        
        return "\n".join(lines)
    except Exception as e:
        return f"Gagal ambil data IHSG: {e}"


def get_top_movers(is_gainer=True, limit=3):
    """Ambil top gainer atau loser dari IHSG, dengan fallback."""
    try:
        tickers = ['BBCA', 'BBRI', 'TLKM', 'ASII', 'UNVR', 'ADRO', 'ANTM', 'ICBP']
        movers = []
        for t in tickers:
            stock = yf.Ticker(t + '.JK')
            data = stock.history(period='1d')
            if not data.empty:
                close = data['Close'].iloc[-1]
                prev = stock.info.get('previousClose', close)
                pct = ((close - prev) / prev) * 100
                movers.append((t, pct))
        movers.sort(key=lambda x: x[1], reverse=is_gainer)
        return ", ".join([f"{m[0]} ({'+' if m[1]>=0 else ''}{m[1]:.1f}%)" for m in movers[:limit]])
    except:
        return ""
```

**Catatan:** `get_top_movers` menggunakan daftar saham populer karena Yahoo Finance tidak menyediakan endpoint top mover resmi untuk IHSG. Bisa diperluas daftarnya nanti.

#### 4. Integrasikan ke Fast Path
Di `handlers.py`, tambahkan intent "saham" ke `HEAVY_KEYWORDS`:
```python
"saham": ["saham", "ihsg", "bbc", "bbri", "tlkm", "asii", "unvr", "adro", "index", "market", "gainer", "loser"]
```
Dan mapping tools:
```python
TOOLS_BY_INTENT["saham"] = [get_stock_price_tool, get_market_summary_tool]
```

#### 5. Perbarui System Prompt
Di `personas.py`, tambahkan:
```
- Jika pengguna bertanya tentang saham, IHSG, atau pergerakan market, gunakan tool get_stock_price atau get_market_summary.
- Sampaikan dengan gaya Oline yang santai. Jangan pakai format laporan kaku.
- Jika market sedang tutup (akhir pekan/libur), beri tahu dengan ramah.
```

#### 6. Chat Action
Kirim `sendChatAction` dengan `action="typing"` saat mengeksekusi tools saham, agar user tahu Oline sedang mengecek.

### 🧪 Contoh Percakapan
```
User: Olin, IHSG hari ini gimana?
Oline: IHSG hari ini di 7.250, naik 45 poin (+0,62%) 📈
       Top gainer: BBCA (+2.1%), TLKM (+1.8%), ASII (+1.2%)
       Lumayan hijau ya bestie~

User: Cek saham BBRI dong
Oline: BBRI sekarang Rp 5.800, turun 25 poin (-0,43%) 📉
       Masih mending sih, gak nyungsep banget~
```

### 📁 File yang Perlu Diubah/Dibuat
- `requirements.txt` — tambahkan `yfinance`, `pandas`
- `src/tools.py` — tambahkan handler saham
- `src/gemini.py` atau file tools definition — daftarkan tool baru
- `src/handlers.py` — tambahkan intent dan mapping tools
- `src/personas.py` — update system prompt

### ⚠️ Catatan
- **Rate Limit**: Sudah diberi jeda 0,5 detik per panggilan. Aman untuk pemakaian pribadi.
- **Market Tutup**: yfinance tetap bisa mengembalikan data terakhir. Oline bisa bilang "Ini data terakhir sebelum tutup ya~"
- **Saham tidak dikenal**: Fallback error akan dikembalikan dengan ramah.
- **Tetap gratis**: Tidak ada biaya tambahan.
