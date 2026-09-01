 Menyambungkan ke Oline ke notion
1. Tambahkan Environment Variables di Vercel
NOTION_API_KEY = token dari Tahap 1 langkah 6

NOTION_DATABASE_ID = ID dari Tahap 1 langkah 4

2. Tambahkan Dependensi
requirements.txt:

text
requests
3. Buat File Baru src/notion.py
python
import os
import requests
from datetime import datetime, timezone, timedelta

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

HEADERS = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

async def save_note_to_notion(title: str, content: str, category: str = "Umum") -> str:
    wib = timezone(timedelta(hours=7))
    now = datetime.now(wib).isoformat()
    payload = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": {
            "Title": {
                "title": [{"text": {"content": title}}]
            },
            "Kategori": {
                "select": {"name": category}
            },
            "Tanggal": {
                "date": {"start": now}
            }
        },
        "children": [
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": content}}]
                }
            }
        ]
    }
    resp = requests.post(
        "https://api.notion.com/v1/pages",
        json=payload,
        headers=HEADERS,
        timeout=10
    )
    if resp.status_code == 200:
        return f"Catatan '{title}' berhasil disimpan ke Notion."
    else:
        return f"Gagal menyimpan ke Notion: {resp.text[:200]}"
4. Tambahkan Tool di src/tools.py
python
save_notion_tool = {
    "name": "save_note_to_notion",
    "description": "Menyimpan catatan ke Notion.",
    "parameters": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Judul catatan"},
            "content": {"type": "string", "description": "Isi catatan"},
            "category": {"type": "string", "description": "Kategori catatan, default: Umum"}
        },
        "required": ["title", "content"]
    }
}
Daftarkan ke TOOL_HANDLERS:

python
from src.notion import save_note_to_notion
TOOL_HANDLERS["save_note_to_notion"] = save_note_to_notion
5. Tambahkan Intent
Di handlers.py:

python
"notion": ["notion", "catat ke notion", "simpan ke notion", "buat catatan", "catat", "notes"]
Mapping:

python
TOOLS_BY_INTENT["notion"] = [save_notion_tool]
6. Update System Prompt
Di personas.py:

text
- Jika pengguna meminta untuk menyimpan catatan ke Notion, gunakan tool save_note_to_notion.
- Konfirmasi judul dan isi hanya jika pengguna belum menyebutkannya dengan jelas.
- Setelah berhasil, balas dengan gaya Oline yang santai.
Tahap 3: Uji Coba
Percakapan yang diharapkan:

text
User: Olin, catat ke Notion: "Ide riset AI agent" isinya "Membahas autonomous agent untuk skripsi."
Oline: "Siap! Catatan 'Ide riset AI agent' udah masuk Notion, kategori Umum~ 📝"
Cek di Notion: akan muncul halaman baru di database "Catatan" dengan judul, tanggal, dan isi.

⚠️ Catatan Penting
Nama property di Notion harus sama persis dengan yang di kode (Title, Kategori, Tanggal). Jika beda, sesuaikan.

Limit Notion API: gratis, ada rate limit wajar (3 request/detik). Aman untuk bot pribadi.

Keamanan: token Notion bersifat rahasia. Simpan hanya di Vercel environment variable.

Error handling: Antigravity sudah menyiapkan fallback jika API gagal.

