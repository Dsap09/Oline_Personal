"""
Unit test suite untuk fitur Integrasi Notion (Simpan Catatan).
Jalankan dengan: python -m unittest tests/test_notion.py
"""

import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# Add root directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.bot import detect_intent
from src.notion import add_notion_property, extract_database_id, save_note_to_notion
from src.tools import get_tools_for_intent


class TestNotionIntegration(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        os.environ["NOTION_API_KEY"] = "ntn_mock_token_12345"
        os.environ["NOTION_DATABASE_ID"] = "3ceec30101df806fa6ddf65ab5aa6e40"

    def test_extract_database_id(self):
        """Tes fungsi extract_database_id dari berbagai format input Notion."""
        # 1. Full Notion URL
        url = "https://app.notion.com/p/3ceec30101df806fa6ddf65ab5aa6e40?v=3ceec30101df80a7be75000cbcebfb19&source=copy_link"
        self.assertEqual(extract_database_id(url), "3ceec30101df806fa6ddf65ab5aa6e40")

        # 2. Raw 32-char hex string
        raw_hex = "3ceec30101df806fa6ddf65ab5aa6e40"
        self.assertEqual(extract_database_id(raw_hex), "3ceec30101df806fa6ddf65ab5aa6e40")

        # 3. UUID string with hyphens
        uuid_str = "3ceec301-01df-806f-a6dd-f65ab5aa6e40"
        self.assertEqual(extract_database_id(uuid_str), "3ceec30101df806fa6ddf65ab5aa6e40")

    def test_detect_intent_notion(self):
        """Tes pendeteksi intent notion pada bot.py."""
        self.assertEqual(detect_intent("catat ke notion ide riset"), "notion")
        self.assertEqual(detect_intent("simpan ke notion: halo"), "notion")
        self.assertEqual(detect_intent("buat catatan di notion"), "notion")
        self.assertEqual(detect_intent("tambah kolom file di notion"), "notion")

    def test_get_tools_for_intent_notion(self):
        """Tes pengambilan deklarasi tool untuk intent notion."""
        tools = get_tools_for_intent("notion")
        tool_names = [t["name"] for t in tools]
        self.assertIn("save_note_to_notion", tool_names)
        self.assertIn("add_notion_property", tool_names)

    @patch("httpx.AsyncClient.patch", new_callable=AsyncMock)
    async def test_add_notion_property_success(self, mock_patch):
        """Tes add_notion_property berhasil menambahkan kolom ke Notion database."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_patch.return_value = mock_resp

        res = await add_notion_property(name="File", property_type="files")
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["property_name"], "File")
        self.assertIn("berhasil ditambahkan", res["message"])

    @patch("httpx.AsyncClient.get", new_callable=AsyncMock)
    @patch("httpx.AsyncClient.post", new_callable=AsyncMock)
    async def test_save_note_to_notion_success(self, mock_post, mock_get):
        """Tes save_note_to_notion mengembalikan status success saat status 200."""
        mock_get_resp = MagicMock()
        mock_get_resp.status_code = 200
        mock_get_resp.json.return_value = {
            "properties": {
                "Title": {"type": "title"},
                "Kategori": {"type": "select"},
                "Tanggal ": {"type": "date"},
            }
        }
        mock_get.return_value = mock_get_resp

        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 200
        mock_post_resp.json.return_value = {
            "id": "page-12345",
            "url": "https://www.notion.so/Ide-riset-AI-agent-3ceec30101df806fa6ddf65ab5aa6e40",
        }
        mock_post.return_value = mock_post_resp

        res = await save_note_to_notion(
            title="Ide riset AI agent",
            content="Membahas autonomous agent untuk skripsi.",
            category="Riset",
        )
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["title"], "Ide riset AI agent")
        self.assertEqual(res["category"], "Riset")
        self.assertIn("berhasil disimpan", res["message"])

    @patch("httpx.AsyncClient.get", new_callable=AsyncMock)
    @patch("httpx.AsyncClient.post", new_callable=AsyncMock)
    async def test_save_note_to_notion_api_error(self, mock_post, mock_get):
        """Tes save_note_to_notion mengembalikan error saat status != 200."""
        mock_get_resp = MagicMock()
        mock_get_resp.status_code = 404
        mock_get.return_value = mock_get_resp

        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 400
        mock_post_resp.text = "Invalid database ID"
        mock_post.return_value = mock_post_resp

        res = await save_note_to_notion(
            title="Catatan Error",
            content="Isi catatan test error",
        )
        self.assertIn("error", res)
        self.assertIn("Status 400", res["error"])


if __name__ == "__main__":
    unittest.main()
