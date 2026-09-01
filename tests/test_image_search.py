"""
Unit test suite untuk fitur Search & Send Image (Kirim Gambar via Oline).
Jalankan dengan: python -m unittest tests/test_image_search.py
"""

import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# Add root directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.bot import detect_intent
from src.tools import get_tools_for_intent, search_and_send_image


class TestImageSearch(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        os.environ["TELEGRAM_BOT_TOKEN"] = "123456789:ABCDEF_mock_token"

    def test_detect_intent_gambar(self):
        """Tes pendeteksi intent gambar pada bot.py."""
        self.assertEqual(detect_intent("kirim gambar ayam"), "gambar")
        self.assertEqual(detect_intent("cari foto pemandangan"), "gambar")
        self.assertEqual(detect_intent("tampilkan gambar kucing"), "gambar")

    def test_get_tools_for_intent_gambar(self):
        """Tes pengambilan deklarasi tool untuk intent gambar."""
        tools = get_tools_for_intent("gambar")
        tool_names = [t["name"] for t in tools]
        self.assertIn("search_and_send_image", tool_names)

    @patch("telegram.Bot.send_photo", new_callable=AsyncMock)
    @patch("httpx.AsyncClient.get", new_callable=AsyncMock)
    @patch("src.tools.asyncio.to_thread", new_callable=AsyncMock)
    async def test_search_and_send_image_success(self, mock_to_thread, mock_http_get, mock_send_photo):
        """Tes search_and_send_image berhasil mengunduh & mengirim foto ke Telegram."""
        mock_to_thread.return_value = [
            {"image": "https://example.com/ayam.jpg", "title": "Ayam Goreng"}
        ]

        mock_http_resp = MagicMock()
        mock_http_resp.status_code = 200
        mock_http_resp.content = b"fake_image_bytes"
        mock_http_get.return_value = mock_http_resp

        mock_send_photo.return_value = True

        res = await search_and_send_image(chat_id=12345, query="ayam", max_results=1)
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["query"], "ayam")
        self.assertIn("berhasil dikirim", res["message"])

    @patch("src.tools.asyncio.to_thread", new_callable=AsyncMock)
    async def test_search_and_send_image_empty(self, mock_to_thread):
        """Tes search_and_send_image ketika pencarian DDGS tidak menemukan hasil."""
        mock_to_thread.return_value = []

        res = await search_and_send_image(chat_id=12345, query="xyzxyznonexistent")
        self.assertIn("message", res)
        self.assertIn("Tidak ditemukan", res["message"])


if __name__ == "__main__":
    unittest.main()
