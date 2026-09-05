"""
Unit test suite untuk fitur identify_image_subject (Identifikasi Objek/Subjek Universal).
Jalankan dengan: python -m unittest tests/test_identify_image.py
"""

import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.tools import identify_image_subject, execute_tool


class TestIdentifyImage(unittest.IsolatedAsyncioTestCase):

    @patch("src.tools.analyze_image", new_callable=AsyncMock)
    @patch("asyncio.to_thread", new_callable=AsyncMock)
    async def test_identify_image_subject_success(self, mock_to_thread, mock_analyze):
        """Tes identify_image_subject menggabungkan Moondream visual description & DDGS search."""
        mock_analyze.return_value = "A large stone monument with a gold flame on top located in a city park."
        mock_to_thread.return_value = [
            {"title": "Monas - Monumen Nasional Jakarta"},
            {"title": "Monumen Nasional - Wikipedia"},
        ]

        res = await identify_image_subject(b"fake_image_bytes", context_hint="ini apa")
        self.assertIn("Monas - Monumen Nasional Jakarta", res)
        self.assertIn("kemungkinan besar adalah", res)
        self.assertIn("stone monument", res)

    @patch("src.tools.analyze_image", new_callable=AsyncMock)
    @patch("asyncio.to_thread", new_callable=AsyncMock)
    async def test_identify_image_subject_no_ddgs_results(self, mock_to_thread, mock_analyze):
        """Tes identify_image_subject fallback ke deskripsi saat DDGS tidak merespons."""
        mock_analyze.return_value = "A rare species of blue bird sitting on a branch."
        mock_to_thread.return_value = []

        res = await identify_image_subject(b"fake_image_bytes", context_hint="burung apa ini")
        self.assertIn("Aku bisa lihat gambarnya", res)
        self.assertIn("rare species of blue bird", res)

    async def test_identify_image_subject_empty_bytes(self):
        """Tes identify_image_subject mengembalikan error saat data gambar kosong."""
        res = await identify_image_subject(b"", context_hint="ini apa")
        self.assertIn("gagal", res.lower())

    @patch("src.tools.analyze_image", new_callable=AsyncMock)
    @patch("asyncio.to_thread", new_callable=AsyncMock)
    async def test_execute_tool_identify_image_subject(self, mock_to_thread, mock_analyze):
        """Tes execute_tool memanggil identify_image_subject."""
        mock_analyze.return_value = "A large stone monument with a gold flame on top located in a city park."
        mock_to_thread.return_value = [{"title": "Monas - Monumen Nasional"}]
        res = await execute_tool(
            "identify_image_subject",
            {"image_bytes": b"fake_bytes", "context_hint": "ini apa"},
            chat_id=123,
        )
        self.assertIn("Monas - Monumen Nasional", res)


if __name__ == "__main__":
    unittest.main()
