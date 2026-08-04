
## Brief Fitur: Google Drive Pribadi Oline (Kelola Folder, Dokumen & Foto)

### 🎯 Tujuan
Oline bisa mengelola folder khusus di Google Drive pemilik bot, seolah-olah itu adalah "database file pribadi". Kemampuan yang diinginkan:
1. **Membuat folder** di dalam folder khusus yang sudah diizinkan.
2. **Menyimpan file** (dokumen PDF/Word/foto) yang dikirim pengguna ke folder yang ditentukan.
3. **Melihat daftar isi** folder tertentu.
4. **Mencari file** berdasarkan nama di seluruh folder khusus.
5. **Mengirim kembali file/foto** dari Drive ke pengguna melalui Telegram.
6. **Menghapus file** (opsional, bisa ditambahkan nanti).

Semua interaksi dilakukan dengan bahasa alami, seperti:
- "Olin, buat folder Skripsi di database."
- "Simpan file ini ke folder Skripsi."
- "Tampilkan isi folder Skripsi."
- "Kirim foto sunset yang di Bali itu dong."

### 🏗️ Arsitektur
| Komponen | Teknologi |
|----------|-----------|
| Bot Telegram | Python, Vercel (existing) |
| Google Drive API | `google-api-python-client` |
| Autentikasi | Google Service Account (gratis) |
| Intent Detection | Gemini function calling (slow path) |

**Keamanan:** Service account hanya diberi izin akses ke **satu folder khusus** (misal: "Database Oline") di Google Drive pemilik bot. Folder di luar itu tidak bisa diakses.

### 🛠️ Langkah Implementasi

#### 1. Setup Google Cloud & Service Account
**Dilakukan oleh pemilik bot (Kak Aga), dibantu Antigravity untuk instruksi:**
1. Buka [Google Cloud Console](https://console.cloud.google.com).
2. Buat project baru (atau pakai existing).
3. Aktifkan **Google Drive API**.
4. Buat **Service Account**: IAM & Admin → Service Accounts → Create.
5. Simpan file JSON kredensial yang diunduh.
6. Di Google Drive, buat folder (misal: "Database Oline").
7. Klik kanan folder → **Bagikan** → masukkan email service account (ada di file JSON) dengan izin **Editor** atau **Content Manager**.
8. Salin **Folder ID** dari URL Drive: `https://drive.google.com/drive/folders/<FOLDER_ID>`.

#### 2. Simpan Environment Variables di Vercel
- `GOOGLE_DRIVE_CREDENTIALS` — isi dengan **seluruh teks JSON** dari file kredensial service account (bisa di-minify jadi satu baris).
- `GOOGLE_DRIVE_FOLDER_ID` — ID folder "Database Oline".

#### 3. Tambahkan Dependensi
Di `requirements.txt`:
```
google-api-python-client
google-auth
```

#### 4. Buat File Baru `src/drive.py`
Berisi semua fungsi untuk berinteraksi dengan Google Drive.

**a. Inisialisasi Service:**
```python
import json
import os
import io
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload

SCOPES = ['https://www.googleapis.com/auth/drive.file']
FOLDER_ID = os.getenv('GOOGLE_DRIVE_FOLDER_ID')

def get_drive_service():
    creds_dict = json.loads(os.getenv('GOOGLE_DRIVE_CREDENTIALS'))
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return build('drive', 'v3', credentials=creds)
```

**b. Cari Folder Berdasarkan Nama:**
```python
def find_folder(service, folder_name, parent_id=None):
    query = f"mimeType='application/vnd.google-apps.folder' and name='{folder_name}' and trashed=false"
    if parent_id:
        query += f" and '{parent_id}' in parents"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    folders = results.get('files', [])
    return folders[0]['id'] if folders else None
```

**c. Buat Folder Baru:**
```python
def create_folder(service, folder_name, parent_id=FOLDER_ID):
    existing = find_folder(service, folder_name, parent_id)
    if existing:
        return existing, False  # Sudah ada
    file_metadata = {
        'name': folder_name,
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': [parent_id]
    }
    folder = service.files().create(body=file_metadata, fields='id').execute()
    return folder['id'], True
```

**d. Upload File:**
```python
def upload_file(service, file_name, file_data, mime_type, folder_name=None):
    parent_id = FOLDER_ID
    if folder_name:
        found = find_folder(service, folder_name, FOLDER_ID)
        if not found:
            # Folder tidak ada → buat dulu
            found, _ = create_folder(service, folder_name)
        parent_id = found

    media = MediaIoBaseUpload(io.BytesIO(file_data), mimetype=mime_type, resumable=False)
    file_metadata = {
        'name': file_name,
        'parents': [parent_id]
    }
    uploaded = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    return uploaded['id']
```

**e. List File dalam Folder:**
```python
def list_files(service, folder_name=None):
    parent_id = FOLDER_ID
    if folder_name:
        found = find_folder(service, folder_name, FOLDER_ID)
        if not found:
            return []
        parent_id = found
    
    query = f"'{parent_id}' in parents and trashed=false"
    results = service.files().list(q=query, fields="files(id, name, mimeType, size)").execute()
    return results.get('files', [])
```

**f. Cari File Berdasarkan Nama:**
```python
def search_files(service, file_name):
    query = f"name contains '{file_name}' and '{FOLDER_ID}' in parents and trashed=false"
    results = service.files().list(q=query, fields="files(id, name, mimeType)").execute()
    return results.get('files', [])
```

**g. Download File:**
```python
def download_file(service, file_id):
    request = service.files().get_media(fileId=file_id)
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    buffer.seek(0)
    return buffer
```

#### 5. Definisikan Tools Gemini
Tambahkan tools berikut:

**a. `create_drive_folder`** — Buat folder baru di Database Oline.
**b. `upload_to_drive`** — Simpan file yang baru diterima ke folder tertentu.
**c. `list_drive_files`** — Lihat isi folder.
**d. `search_drive_files`** — Cari file berdasarkan nama.
**e. `download_from_drive`** — Kirim file dari Drive ke Telegram.

#### 6. Handler untuk File yang Diterima
Di `handlers.py`, tangkap pesan dengan dokumen/foto:
```python
if update.message.document:
    file = await context.bot.get_file(update.message.document.file_id)
    file_data = await file.download_as_bytearray()
    # Simpan sementara di memori, tunggu konfirmasi user (misal "simpan ke folder skripsi")
    # Lalu panggil upload_to_drive handler
```

#### 7. Integrasikan ke Intent Detection
Tambahkan keyword:
```python
"drive": ["drive", "database", "folder", "simpan file", "buat folder", "cari file", "tampilkan isi", "kirim file"]
```
Masukkan tools drive ke `TOOLS_BY_INTENT["drive"]`.

#### 8. Kirim Foto sebagai Gambar (Bukan Dokumen)
Saat mendownload foto dari Drive, jika mime type adalah `image/jpeg` atau `image/png`, gunakan `context.bot.send_photo()` agar pengguna bisa melihat preview langsung.

```python
if 'image' in mime_type:
    await context.bot.send_photo(chat_id=update.effective_chat.id, photo=buffer)
else:
    await context.bot.send_document(chat_id=update.effective_chat.id, document=buffer)
```

#### 9. Chat Action
Kirim `sendChatAction` dengan `action="typing"` atau `"upload_document"` saat memproses Drive.

### 📁 File yang Perlu Diubah/Dibuat
| File | Aksi |
|------|------|
| `requirements.txt` | Tambahkan `google-api-python-client`, `google-auth` |
| `src/drive.py` | **Baru** — semua fungsi Drive |
| `src/tools.py` | Tambahkan definisi & handler tools Drive |
| `src/handlers.py` | Tambahkan intent "drive", tangkap dokumen/foto |
| Environment Vercel | Tambahkan `GOOGLE_DRIVE_CREDENTIALS`, `GOOGLE_DRIVE_FOLDER_ID` |

### 🧪 Contoh Percakapan
```
User: Olin, buat folder Skripsi.
Oline: Sip! Folder Skripsi udah dibuat di Database Oline. 📂

User: (upload Draft_Bab1.pdf)
User: Simpan file ini ke folder Skripsi.
Oline: Beres! Draft_Bab1.pdf udah masuk ke folder Skripsi.

User: Tampilkan isi folder Skripsi.
Oline: Isi folder Skripsi: Draft_Bab1.pdf. Mau dikirim?

User: Kirim file Draft_Bab1.pdf yang di folder Skripsi.
Oline: (mengirim file)

User: (kirim foto Kucing.jpg)
User: Simpan ke folder Foto Hewan.
Oline: Kucing.jpg udah aman di folder Foto Hewan. Lucu banget sih~ 🐱
```

### ⚠️ Catatan Penting
- **Timeout Vercel**: Operasi Drive biasanya < 3 detik untuk file < 10 MB. Untuk file besar (15–20 MB), bisa mendekati 8–10 detik. Pantau log.
- **Kuota API**: Google Drive API gratis untuk operasi wajar. Upload/download file kecil tidak akan kena limit.
- **Keamanan**: Service account hanya bisa mengakses folder dengan ID `GOOGLE_DRIVE_FOLDER_ID`. Pastikan tidak ada file sensitif di folder tersebut.
- **Folder Duplikat**: Handler `create_folder` sudah mengecek apakah folder dengan nama sama sudah ada sebelum membuat.