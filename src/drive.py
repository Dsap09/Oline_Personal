"""
Google Drive API helper untuk Oline bot.
Mengelola autentikasi Service Account, pembuat folder, upload file/foto,
list file, pencarian, dan download file.
"""

import io
import json
import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]


def get_drive_folder_id() -> str:
    """Mengembalikan root folder ID Oline di Google Drive."""
    folder_id = os.environ.get("GOOGLE_DRIVE_FOLDER_ID", "").strip()
    return folder_id


def get_drive_service():
    """
    Inisialisasi dan mengembalikan service Google Drive v3.
    Mendukung JSON dari environment variable GOOGLE_DRIVE_CREDENTIALS
    atau fallback ke file JSON lokal di folder api/ jika ada.
    """
    creds_json = os.environ.get("GOOGLE_DRIVE_CREDENTIALS", "").strip()
    creds_dict = None

    if creds_json:
        try:
            creds_dict = json.loads(creds_json)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse GOOGLE_DRIVE_CREDENTIALS JSON: %s", str(e))

    if not creds_dict:
        # Fallback ke file JSON lokal di directory api/ jika ada
        api_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "api")
        if os.path.exists(api_dir):
            for file in os.listdir(api_dir):
                if file.endswith(".json") and "serviceaccount" in file.lower() or "project" in file.lower():
                    json_path = os.path.join(api_dir, file)
                    try:
                        with open(json_path, "r", encoding="utf-8") as f:
                            creds_dict = json.load(f)
                            logger.info("Loaded Google Drive service account from local file: %s", file)
                            break
                    except Exception as fe:
                        logger.warning("Could not read local JSON file %s: %s", file, str(fe))

    if not creds_dict:
        raise ValueError(
            "GOOGLE_DRIVE_CREDENTIALS environment variable is not configured "
            "and no valid local service account JSON file was found."
        )

    try:
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build

        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        return build("drive", "v3", credentials=creds)
    except Exception as e:
        logger.error("Failed to initialize Google Drive service: %s", str(e))
        raise RuntimeError(f"Gagal menginisialisasi Google Drive API: {str(e)}")


def find_folder(service, folder_name: str, parent_id: Optional[str] = None) -> Optional[str]:
    """
    Mencari folder berdasarkan nama persis di bawah parent_id (default GOOGLE_DRIVE_FOLDER_ID).
    Returns folder_id atau None jika tidak ditemukan.
    """
    root_id = parent_id or get_drive_folder_id()
    folder_name_clean = folder_name.replace("'", "\\'")

    query = (
        f"mimeType='application/vnd.google-apps.folder' "
        f"and name='{folder_name_clean}' "
        f"and trashed=false"
    )
    if root_id:
        query += f" and '{root_id}' in parents"

    results = service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get("files", [])
    if files:
        return files[0]["id"]
    return None


def create_folder(service, folder_name: str, parent_id: Optional[str] = None) -> tuple[str, bool]:
    """
    Membuat folder baru di bawah parent_id.
    Returns tuple: (folder_id, is_newly_created).
    """
    root_id = parent_id or get_drive_folder_id()

    existing_id = find_folder(service, folder_name, root_id)
    if existing_id:
        return existing_id, False

    metadata: dict[str, Any] = {
        "name": folder_name,
        "mimeType": "application/vnd.google-apps.folder",
    }
    if root_id:
        metadata["parents"] = [root_id]

    folder = service.files().create(body=metadata, fields="id, name").execute()
    return folder.get("id"), True


def upload_file(
    service,
    file_name: str,
    file_bytes: bytes,
    mime_type: str = "application/octet-stream",
    folder_name: Optional[str] = None,
) -> dict[str, Any]:
    """
    Upload file/dokumen/foto ke Google Drive.
    Jika folder_name diisi, file dimasukkan ke subfolder tersebut.
    """
    from googleapiclient.http import MediaIoBaseUpload

    clean_name = os.path.basename(file_name) or "file_oline"
    root_id = get_drive_folder_id()
    target_parent_id = root_id

    if folder_name:
        folder_id, _ = create_folder(service, folder_name, root_id)
        target_parent_id = folder_id

    file_metadata: dict[str, Any] = {"name": clean_name}
    if target_parent_id:
        file_metadata["parents"] = [target_parent_id]

    media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mime_type, resumable=False)
    uploaded = service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id, name, webViewLink, mimeType, size",
    ).execute()

    return {
        "id": uploaded.get("id"),
        "name": uploaded.get("name"),
        "web_link": uploaded.get("webViewLink", ""),
        "mimeType": uploaded.get("mimeType", mime_type),
        "size": uploaded.get("size", len(file_bytes)),
    }


def list_files(service, folder_name: Optional[str] = None) -> list[dict[str, Any]]:
    """
    Mengambil daftar file dan folder di dalam folder_name (atau root folder ID).
    """
    root_id = get_drive_folder_id()
    target_id = root_id

    if folder_name:
        found_id = find_folder(service, folder_name, root_id)
        if not found_id:
            return []
        target_id = found_id

    query = "trashed=false"
    if target_id:
        query += f" and '{target_id}' in parents"

    results = service.files().list(
        q=query,
        fields="files(id, name, mimeType, size, webViewLink)",
        orderBy="folder, name",
    ).execute()

    items = results.get("files", [])
    output = []
    for item in items:
        is_dir = item.get("mimeType") == "application/vnd.google-apps.folder"
        output.append({
            "id": item.get("id"),
            "name": item.get("name"),
            "mimeType": item.get("mimeType"),
            "is_folder": is_dir,
            "size": item.get("size", 0),
            "web_link": item.get("webViewLink", ""),
        })
    return output


def search_files(service, query_name: str) -> list[dict[str, Any]]:
    """
    Mencari file berdasarkan substring nama file.
    """
    clean_query = query_name.replace("'", "\\'")
    query = f"name contains '{clean_query}' and trashed=false"
    root_id = get_drive_folder_id()
    if root_id:
        query += f" and '{root_id}' in parents"

    results = service.files().list(
        q=query,
        fields="files(id, name, mimeType, size, webViewLink)",
    ).execute()

    items = results.get("files", [])
    output = []
    for item in items:
        is_dir = item.get("mimeType") == "application/vnd.google-apps.folder"
        output.append({
            "id": item.get("id"),
            "name": item.get("name"),
            "mimeType": item.get("mimeType"),
            "is_folder": is_dir,
            "size": item.get("size", 0),
            "web_link": item.get("webViewLink", ""),
        })
    return output


def download_file(service, file_id: str) -> tuple[bytes, str, str]:
    """
    Mendownload file dari Google Drive berdasarkan file_id.
    Returns tuple: (file_bytes, file_name, mime_type).
    """
    from googleapiclient.http import MediaIoBaseDownload

    meta = service.files().get(fileId=file_id, fields="name, mimeType").execute()
    file_name = meta.get("name", "file_oline")
    mime_type = meta.get("mimeType", "application/octet-stream")

    request = service.files().get_media(fileId=file_id)
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)

    done = False
    while not done:
        _, done = downloader.next_chunk()

    buffer.seek(0)
    return buffer.getvalue(), file_name, mime_type
