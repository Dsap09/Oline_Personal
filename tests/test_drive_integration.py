"""
Unit dan Integration Test untuk Google Drive Integration.
Jalankan dengan: python tests/test_drive_integration.py
"""

import asyncio
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# Add root directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.bot import detect_intent
from src.tools import (
    execute_create_drive_folder,
    execute_list_drive_files,
    execute_search_drive_files,
    get_tools_for_intent,
)


class TestDriveIntegration(unittest.IsolatedAsyncioTestCase):

    def test_drive_intent_detection(self):
        """Tes deteksi intent 'drive' dari teks pengguna."""
        drive_queries = [
            "Olin, buat folder Skripsi di database",
            "simpan file ini ke folder tugas",
            "tampilkan isi folder dokumen",
            "cari file laporan keuangan",
            "kirim file Kucing.jpg",
        ]
        for query in drive_queries:
            intent = detect_intent(query)
            self.assertEqual(intent, "drive", f"Failed for query: '{query}'")

    def test_drive_tool_filtering(self):
        """Tes ketersediaan tools saat intent='drive'."""
        drive_tools = get_tools_for_intent("drive")
        tool_names = [t["name"] for t in drive_tools]

        self.assertIn("create_drive_folder", tool_names)
        self.assertIn("list_drive_files", tool_names)
        self.assertIn("search_drive_files", tool_names)
        self.assertIn("upload_to_drive", tool_names)
        self.assertIn("download_from_drive", tool_names)
        self.assertEqual(len(drive_tools), 5)

    @patch("src.drive.get_drive_service")
    async def test_execute_create_drive_folder(self, mock_get_service):
        """Tes pembuatan folder baru di Drive."""
        mock_service = MagicMock()
        mock_get_service.return_value = mock_service

        with patch("src.drive.create_folder", return_value=("folder_123", True)):
            res = await execute_create_drive_folder("Skripsi")
            self.assertEqual(res["status"], "success")
            self.assertIn("Folder 'Skripsi' berhasil dibuat", res["message"])

    @patch("src.drive.get_drive_service")
    async def test_execute_list_drive_files(self, mock_get_service):
        """Tes melihat daftar file di Drive."""
        mock_service = MagicMock()
        mock_get_service.return_value = mock_service

        mock_items = [
            {"id": "1", "name": "Skripsi", "mimeType": "application/vnd.google-apps.folder", "is_folder": True},
            {"id": "2", "name": "Draft_Bab1.pdf", "mimeType": "application/pdf", "is_folder": False},
        ]

        with patch("src.drive.list_files", return_value=mock_items):
            res = await execute_list_drive_files("Skripsi")
            self.assertEqual(res["total_items"], 2)
            self.assertIn("📂 Skripsi", res["items"])
            self.assertIn("📄 Draft_Bab1.pdf", res["items"])

    @patch("src.drive.get_drive_service")
    async def test_execute_search_drive_files(self, mock_get_service):
        """Tes pencarian file di Drive."""
        mock_service = MagicMock()
        mock_get_service.return_value = mock_service

        mock_items = [
            {"id": "2", "name": "Draft_Bab1.pdf", "mimeType": "application/pdf", "is_folder": False},
        ]

        with patch("src.drive.search_files", return_value=mock_items):
            res = await execute_search_drive_files("Bab1")
            self.assertEqual(res["total_found"], 1)
            self.assertIn("📄 Draft_Bab1.pdf", res["results"])


if __name__ == "__main__":
    unittest.main()
