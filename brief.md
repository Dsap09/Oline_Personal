## Brief Fitur: Lokasi & Rekomendasi Tempat Terdekat (OpenStreetMap)

### 🎯 Tujuan
Oline mampu:
1. **Menyimpan lokasi terkini pengguna** (dikirim via Telegram).
2. **Memberikan rekomendasi tempat terdekat** (cafe, toko buku, restoran, dll.) berdasarkan lokasi tersimpan.
3. **Memberikan rekomendasi tempat berdasarkan kota/area** (misal: "toko buku di Surabaya").
4. **Mengirim titik lokasi** hasil rekomendasi ke Telegram (opsional).

Semua dilakukan dengan bahasa alami, tanpa perintah khusus.

### 🏗️ Arsitektur & Sumber Data (Gratis)

| Fungsi | Layanan | Keterangan |
|--------|---------|------------|
| Geocoding (kota → koordinat) | **Nominatim** (OpenStreetMap) | Tanpa API key, free, cukup untuk personal use |
| Pencarian tempat (POI) | **Overpass API** (OpenStreetMap) | Tanpa API key, bisa cari berdasarkan kategori & radius |
| Penyimpanan lokasi | **Vercel KV / Upstash** (existing) | Simpan koordinat per chat ID |
| Jarak | Perhitungan Haversine di kode | Tidak butuh library tambahan |

### 🛠️ Langkah Implementasi

#### 1. Tambahkan Dependensi
`requirements.txt`:
```
requests
```
`geopy` tidak diperlukan; kita hitung jarak manual.

#### 2. Simpan Lokasi Pengguna
**Handler Telegram:**
- Tangkap `update.message.location` (saat user mengirim lokasi).
- Simpan `latitude`, `longitude` ke Vercel KV:
  ```python
  set_kv(f"location:{chat_id}", json.dumps({"lat": lat, "lon": lon}))
  ```
- Balas: "Lokasi kamu udah aku simpan! Mau cari apa di sekitar sini? 📍"

#### 3. Definisikan Tools untuk Gemini
Dua tool baru:

**a. `get_nearby_places`**
```python
{
    "name": "get_nearby_places",
    "description": "Mencari tempat terdekat dari lokasi pengguna yang tersimpan, berdasarkan kategori (misal: cafe, toko buku, restoran).",
    "parameters": {
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "description": "Kategori tempat, misal 'cafe', 'restaurant', 'bookstore', 'mall'."
            },
            "radius_km": {
                "type": "number",
                "description": "Radius pencarian dalam kilometer. Default 2."
            }
        },
        "required": ["category"]
    }
}
```

**b. `search_places_by_city`**
```python
{
    "name": "search_places_by_city",
    "description": "Mencari tempat berdasarkan nama kota/area dan kategori. Menggunakan geocoding untuk mendapatkan koordinat kota.",
    "parameters": {
        "type": "object",
        "properties": {
            "city": {
                "type": "string",
                "description": "Nama kota atau area, misal 'Surabaya', 'Bandung', 'Jakarta Selatan'."
            },
            "category": {
                "type": "string",
                "description": "Kategori tempat, misal 'toko buku', 'cafe', 'mall'."
            }
        },
        "required": ["city", "category"]
    }
}
```

#### 4. Buat Handler Tools di `src/tools.py`

**Fungsi bantu:**
```python
import requests
import math

def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # km
    dLat = math.radians(lat2 - lat1)
    dLon = math.radians(lon2 - lon1)
    a = math.sin(dLat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dLon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def overpass_query(lat, lon, category, radius_m=2000):
    # Konversi kategori ke tag OSM (sederhana)
    tag_map = {
        "cafe": "amenity=cafe",
        "restaurant": "amenity=restaurant",
        "toko buku": "shop=books",
        "mall": "shop=mall",
        "bar": "amenity=bar",
        "minimarket": "shop=convenience"
    }
    tag = tag_map.get(category.lower(), "amenity=" + category.lower())
    query = f"""
    [out:json];
    node[{tag}](around:{radius_m},{lat},{lon});
    out body 5;
    """
    response = requests.post("https://overpass-api.de/api/interpreter", data={"data": query}, timeout=10)
    return response.json().get("elements", [])
```

**a. `get_nearby_places`**
```python
async def get_nearby_places(category: str, radius_km: float = 2.0) -> str:
    loc = json.loads(get_kv(f"location:{chat_id}") or "{}")
    if not loc:
        return "Lokasi belum disimpan. Minta pengguna kirim lokasi dulu."
    lat, lon = loc["lat"], loc["lon"]
    places = overpass_query(lat, lon, category, radius_m=int(radius_km*1000))
    if not places:
        return f"Tidak ada {category} dalam {radius_km} km."
    # Urutkan by jarak
    results = []
    for p in places:
        plat = p.get("lat", lat)
        plon = p.get("lon", lon)
        dist = haversine(lat, lon, plat, plon)
        name = p.get("tags", {}).get("name", "Tanpa nama")
        address = p.get("tags", {}).get("addr:street", "")
        results.append((name, address, dist, plat, plon))
    results.sort(key=lambda x: x[2])
    lines = []
    for name, address, dist, plat, plon in results[:5]:
        lines.append(f"{name} ({dist:.1f} km) {address}")
    return "\n".join(lines)
```

**b. `search_places_by_city`**
```python
async def search_places_by_city(city: str, category: str) -> str:
    # Geocode
    geo = requests.get("https://nominatim.openstreetmap.org/search", params={
        "q": city, "format": "json", "limit": 1
    }, headers={"User-Agent": "OlineBot/1.0"}, timeout=10).json()
    if not geo:
        return f"Kota/area '{city}' tidak ditemukan."
    lat = float(geo[0]["lat"])
    lon = float(geo[0]["lon"])
    # Search with large radius (misal 5 km)
    places = overpass_query(lat, lon, category, radius_m=5000)
    if not places:
        return f"Tidak ada {category} di {city}."
    lines = []
    for p in places[:5]:
        name = p.get("tags", {}).get("name", "Tanpa nama")
        address = p.get("tags", {}).get("addr:street", "")
        lines.append(f"{name} {address}")
    return "\n".join(lines)
```

**Daftarkan ke `TOOL_HANDLERS`:**
```python
TOOL_HANDLERS.update({
    "get_nearby_places": get_nearby_places,
    "search_places_by_city": search_places_by_city
})
```

#### 5. Integrasikan ke Intent Detection
Di `handlers.py`, tambahkan kategori lokasi:

```python
"lokasi": [
    "lokasi", "terdekat", "dekat", "cafe", "toko buku", "restoran", "mall",
    "tempat makan", "kedai", "coffee", "cari tempat", "cari cafe"
]
```
Dan tools mapping:
```python
TOOLS_BY_INTENT["lokasi"] = [get_nearby_places_tool, search_places_by_city_tool]
```

#### 6. Perbarui System Prompt
Di `personas.py`:
```text
- Jika pengguna meminta rekomendasi tempat (cafe, toko, restoran, dll.), gunakan fungsi get_nearby_places atau search_places_by_city.
- Selalu utamakan get_nearby_places jika pengguna menyebut "terdekat" atau "dekat sini".
- Jika belum ada lokasi tersimpan, minta pengguna untuk mengirim lokasi.
- Setelah mendapat hasil, sampaikan dengan gaya Oline yang santai. Boleh tambahkan emoji. Jangan format kaku.
```

#### 7. Kirim Titik Lokasi (Opsional)
Setelah Oline memberikan rekomendasi, pengguna bisa minta "kirim titik lokasinya". Handler bisa mengambil koordinat dari hasil sebelumnya (simpan di memori sementara atau state per chat), lalu kirim `context.bot.send_location(chat_id, lat, lon)`.  
Untuk tahap awal, cukup tampilkan teks alamat. Titik lokasi bisa menyusul.

### 📁 File yang Perlu Diubah/Dibuat
| File | Aksi |
|------|------|
| `requirements.txt` | Tambahkan `requests` (jika belum ada) |
| `src/tools.py` | Tambah handler geocoding & Overpass, daftarkan tools |
| `src/handlers.py` | Tangkap pesan lokasi, simpan ke KV; tambah intent lokasi |
| `src/personas.py` | Update system prompt |
| `src/kv.py` | Pastikan fungsi `get_kv`, `set_kv` berjalan baik |

### 🧪 Contoh Percakapan
```
User: (kirim lokasi)
Oline: "Lokasi kamu udah aku simpan! Sekarang bilang aja mau cari apa di sekitar sini. 📍"

User: cafe terdekat
Oline: "Di sekitar kamu ada 3 cafe:
☕ Kopi Nako (0,3 km) – Jl. Raya Darmo
☕ Cold Brew Co (0,7 km) – Jl. Untung Suropati
☕ Kafe Kita (1,2 km) – Jl. Mayjend Sungkono
Mau aku kirim titik lokasinya?"

User: toko buku di Surabaya
Oline: "Di Surabaya ada beberapa toko buku:
📚 Gramedia Basuki Rahmat – Jl. Basuki Rahmat 8
📚 Togamas Tunjungan – Jl. Tunjungan 55
📚 Toko Buku Pustaka – Jl. Diponegoro 12
Mau detail atau titik lokasi?"
```

### ⚠️ Catatan Penting
- **Rate Limit**: Overpass & Nominatim punya batas wajar. Tambahkan jeda 1 detik antar request. Untuk bot pribadi sangat aman.
- **Kategori mapping**: Perlu menyempurnakan `tag_map` untuk berbagai kategori (bisa diperluas).
- **Privasi**: Lokasi hanya disimpan untuk chat ID tertentu, tidak dibagikan.
- **Timeout**: Overpass kadang lambat; gunakan `timeout=10` dan siapkan fallback jika gagal.
- **Geocoding Nominatim**: Gunakan header `User-Agent` yang valid, jangan terlalu sering (maks 1 req/detik).
