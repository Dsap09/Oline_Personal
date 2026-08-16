"""
Unit test suite untuk fitur Lokasi & Rekomendasi Tempat Terdekat (OpenStreetMap).
Jalankan dengan: python -m unittest tests/test_location_tools.py
"""

import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# Add root directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.bot import detect_intent
from src.kv import get_user_location, save_user_location
from src.tools import (
    get_nearby_places,
    get_tools_for_intent,
    haversine,
    overpass_query,
    search_places_by_city,
)


class TestLocationTools(unittest.IsolatedAsyncioTestCase):

    def test_haversine_distance(self):
        """Tes perhitungan jarak lurus (haversine formula)."""
        # Monas Jakarta (-6.1754, 106.8272) ke Kota Tua Jakarta (-6.1352, 106.8133) ~ 4.7 km
        dist = haversine(-6.1754, 106.8272, -6.1352, 106.8133)
        self.assertAlmostEqual(dist, 4.75, delta=0.5)

    def test_detect_intent_lokasi(self):
        """Tes pendeteksi intent lokasi."""
        self.assertEqual(detect_intent("cafe terdekat"), "lokasi")
        self.assertEqual(detect_intent("toko buku di Surabaya"), "lokasi")
        self.assertEqual(detect_intent("cari tempat makan dekat sini"), "lokasi")
        self.assertEqual(detect_intent("spbu terdekat"), "lokasi")

    def test_get_tools_for_intent_lokasi(self):
        """Tes pengambilan deklarasi tool untuk intent lokasi."""
        tools = get_tools_for_intent("lokasi")
        tool_names = [t["name"] for t in tools]
        self.assertIn("get_nearby_places", tool_names)
        self.assertIn("search_places_by_city", tool_names)

    @patch("src.kv._kv_request", new_callable=AsyncMock)
    async def test_save_and_get_user_location(self, mock_kv):
        """Tes save_user_location dan get_user_location ke Vercel KV."""
        # 1. Save location
        mock_kv.return_value = {"result": "OK"}
        saved = await save_user_location(12345, -6.1754, 106.8272)
        self.assertTrue(saved)

        # 2. Get location
        mock_kv.return_value = {"result": '{"lat": -6.1754, "lon": 106.8272}'}
        loc = await get_user_location(12345)
        self.assertIsNotNone(loc)
        self.assertAlmostEqual(loc["lat"], -6.1754)
        self.assertAlmostEqual(loc["lon"], 106.8272)

    @patch("src.tools.get_user_location", new_callable=AsyncMock)
    async def test_get_nearby_places_no_location(self, mock_get_loc):
        """Tes get_nearby_places jika lokasi pengguna belum tersimpan."""
        mock_get_loc.return_value = None
        res = await get_nearby_places(chat_id=999, category="cafe")
        self.assertIn("error", res)
        self.assertIn("Lokasi belum disimpan", res["error"])

    @patch("src.tools.overpass_query")
    @patch("src.tools.get_user_location", new_callable=AsyncMock)
    async def test_get_nearby_places_success(self, mock_get_loc, mock_overpass):
        """Tes get_nearby_places jika lokasi pengguna ada dan Overpass mengembalikan POI."""
        mock_get_loc.return_value = {"lat": -6.1754, "lon": 106.8272}
        mock_overpass.return_value = [
            {
                "lat": -6.1760,
                "lon": 106.8280,
                "tags": {"name": "Kopi Nako", "addr:street": "Jl. Merdeka"},
            },
            {
                "lat": -6.1800,
                "lon": 106.8300,
                "tags": {"name": "Kafe Kita", "addr:street": "Jl. Thamrin"},
            },
        ]

        res = await get_nearby_places(chat_id=123, category="cafe", radius_km=2.0)
        self.assertEqual(res["category"], "cafe")
        self.assertEqual(res["total_found"], 2)
        self.assertEqual(res["places"][0]["name"], "Kopi Nako")

    @patch("requests.get")
    @patch("src.tools.overpass_query")
    async def test_search_places_by_city_success(self, mock_overpass, mock_requests_get):
        """Tes search_places_by_city via Nominatim Geocoding & Overpass."""
        mock_geo_resp = MagicMock()
        mock_geo_resp.json.return_value = [
            {"lat": "-7.2575", "lon": "112.7521", "display_name": "Surabaya, Jawa Timur"}
        ]
        mock_requests_get.return_value = mock_geo_resp

        mock_overpass.return_value = [
            {"tags": {"name": "Gramedia Basuki Rahmat", "addr:street": "Jl. Basuki Rahmat"}}
        ]

        res = await search_places_by_city(city="Surabaya", category="toko buku")
        self.assertEqual(res["city"], "Surabaya")
        self.assertEqual(res["total_found"], 1)
        self.assertEqual(res["places"][0]["name"], "Gramedia Basuki Rahmat")


if __name__ == "__main__":
    unittest.main()
