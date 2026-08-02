"""
Script pengujian unit dan integrasi untuk fitur pencarian internet DuckDuckGo.
Jalankan dengan: python tests/test_search.py atau pytest tests/test_search.py
"""

import asyncio
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Set path agar src bisa diimport
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.bot import detect_intent
from src.tools import (
    TOOL_DECLARATIONS,
    TOOLS_BY_INTENT,
    get_tools_for_intent,
    search_internet,
)


class TestSearchFeature(unittest.TestCase):

    def test_detect_search_intent(self):
        """Memastikan kata kunci pencarian terdeteksi sebagai intent 'search'."""
        search_queries = [
            "siapa presiden indonesia sekarang",
            "apa itu quantum computing",
            "kapan pemilu 2024",
            "dimana lokasi konser coldplay",
            "cari berita terbaru hari ini",
            "definisi kecerdasan buatan",
            "pengertian machine learning",
        ]
        for query in search_queries:
            intent = detect_intent(query)
            self.assertEqual(intent, "search", f"Query '{query}' gagal terdeteksi sebagai intent 'search'")

    def test_search_tool_declaration(self):
        """Memastikan search_internet terdaftar di TOOL_DECLARATIONS dan TOOLS_BY_INTENT."""
        search_decl = [t for t in TOOL_DECLARATIONS if t["name"] == "search_internet"]
        self.assertEqual(len(search_decl), 1)
        self.assertIn("query", search_decl[0]["parameters"]["properties"])

        self.assertIn("search", TOOLS_BY_INTENT)
        self.assertIn("search_internet", TOOLS_BY_INTENT["search"])

        tools_for_intent = get_tools_for_intent("search")
        self.assertEqual(len(tools_for_intent), 1)
        self.assertEqual(tools_for_intent[0]["name"], "search_internet")

    @patch("src.tools.asyncio.to_thread")
    def test_search_internet_success(self, mock_to_thread):
        """Memastikan search_internet mengembalikan hasil snippet yang diformat dengan benar."""
        mock_to_thread.return_value = [
            {"title": "Judul 1", "body": "Ringkasan berita 1", "href": "https://example.com/1"},
            {"title": "Judul 2", "body": "Ringkasan berita 2", "href": "https://example.com/2"},
        ]

        async def _run():
            res = await search_internet("berita terkini")
            self.assertIn("results", res)
            self.assertIn("Judul 1: Ringkasan berita 1", res["results"])
            self.assertIn("Judul 2: Ringkasan berita 2", res["results"])

        asyncio.run(_run())

    @patch("src.tools.asyncio.to_thread")
    def test_search_internet_empty_results(self, mock_to_thread):
        """Memastikan search_internet menangani hasil kosong dengan pesan fallback."""
        mock_to_thread.return_value = []

        async def _run():
            res = await search_internet("xyzabc12345nonexistent")
            self.assertIn("message", res)

        asyncio.run(_run())

    @patch("src.tools.asyncio.to_thread")
    def test_search_internet_error_handling(self, mock_to_thread):
        """Memastikan search_internet menangani exception dengan respons error yang ramah."""
        mock_to_thread.side_effect = Exception("DDG Connection error")

        async def _run():
            res = await search_internet("query error")
            self.assertIn("error", res)

        asyncio.run(_run())


if __name__ == "__main__":
    unittest.main()
