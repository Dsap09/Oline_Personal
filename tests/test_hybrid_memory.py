"""
Unit test suite untuk fitur Memori Hybrid Oline (Vercel KV + Notion).
Jalankan dengan: python -m unittest tests/test_hybrid_memory.py
"""

import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# Add root directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.bot import is_rule_message
from src.gemini import _build_system_prompt_async, save_daily_summary
from src.kv import del_cache, get_cache, log_error, set_cache
from src.notion import (
    clear_memory_cache,
    read_memory_from_notion,
    save_memory_to_notion,
)


class TestHybridMemory(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        os.environ["NOTION_API_KEY"] = "secret_mock_notion_token_123"
        os.environ["NOTION_MEMORY_DATABASE_ID"] = "3ceec30101df806fa6ddf65ab5aa6e40"

    def test_is_rule_message(self):
        """Tes pendeteksian instruksi aturan dari pesan pengguna."""
        self.assertTrue(is_rule_message("mulai sekarang panggil aku Aga"))
        self.assertTrue(is_rule_message("jangan panggil aku bestie ya"))
        self.assertTrue(is_rule_message("ingat ya kalau aku minta kopi"))
        self.assertFalse(is_rule_message("cuaca di Bandung hari ini gimana?"))
        self.assertFalse(is_rule_message("rekomendasi film horor dong"))

    @patch("src.kv._kv_request", new_callable=AsyncMock)
    async def test_kv_generic_cache(self, mock_kv_request):
        """Tes fungsi cache generik KV (get_cache, set_cache, del_cache)."""
        mock_kv_request.return_value = {"result": "cached_val_123"}
        val = await get_cache("cache:test")
        self.assertEqual(val, "cached_val_123")

        mock_kv_request.return_value = {"result": "OK"}
        set_res = await set_cache("cache:test", "new_val", 600)
        self.assertTrue(set_res)

        del_res = await del_cache("cache:test")
        self.assertTrue(del_res)

    @patch("src.kv._kv_request", new_callable=AsyncMock)
    async def test_log_error(self, mock_kv_request):
        """Tes penyimpanan log error teknis ke KV."""
        mock_kv_request.return_value = {"result": "OK"}
        res = await log_error("Database timeout 504")
        self.assertTrue(res)

    @patch("httpx.AsyncClient.post", new_callable=AsyncMock)
    @patch("src.kv._kv_request", new_callable=AsyncMock)
    async def test_save_memory_to_notion(self, mock_kv, mock_post):
        """Tes menyimpan memori baru ke Notion."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": "page_12345"}
        mock_post.return_value = mock_resp
        mock_kv.return_value = {"result": "OK"}

        res = await save_memory_to_notion(
            title="Aturan dari Aga", content="Panggil aku Aga", memory_type="Aturan"
        )
        self.assertEqual(res, "Memori berhasil disimpan.")

    @patch("httpx.AsyncClient.post", new_callable=AsyncMock)
    @patch("src.kv._kv_request", new_callable=AsyncMock)
    async def test_read_memory_from_notion(self, mock_kv, mock_post):
        """Tes membaca memori dari Notion (dengan cache KV)."""
        # Scenario 1: Cache Miss -> Fetch dari Notion API
        mock_kv.return_value = {"result": None}
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "results": [
                {
                    "properties": {
                        "Title": {"title": [{"text": {"content": "Jangan panggil bestie"}}]}
                    }
                }
            ]
        }
        mock_post.return_value = mock_resp

        memory_text = await read_memory_from_notion("Aturan")
        self.assertIn("Jangan panggil bestie", memory_text)

    @patch("src.notion.read_memory_from_notion", new_callable=AsyncMock)
    async def test_build_system_prompt_async(self, mock_read_memory):
        """Tes penyuntikan memori Notion ke System Prompt."""
        mock_read_memory.side_effect = lambda m_type: (
            "- Panggil aku Aga" if m_type == "Aturan" else ""
        )

        prompt = await _build_system_prompt_async(memory="", user_name="Aga")
        self.assertIn("Memori Aturan & Preferensi dari Notion", prompt)
        self.assertIn("Panggil aku Aga", prompt)

    @patch("src.notion.save_memory_to_notion", new_callable=AsyncMock)
    @patch("src.gemini.get_history", new_callable=AsyncMock)
    @patch("src.gemini._get_client")
    async def test_save_daily_summary(self, mock_client, mock_history, mock_save_memory):
        """Tes pembuatan ringkasan harian dan penyimpanan ke Notion."""
        mock_history.return_value = [
            {"role": "user", "text": "Halo Oline"},
            {"role": "model", "text": "Halo Aga!"},
        ]
        mock_gen_resp = MagicMock()
        mock_gen_resp.text = "Hari ini membahas sapaan dan setup nama."
        mock_client.return_value.models.generate_content.return_value = mock_gen_resp

        mock_save_memory.return_value = "Memori berhasil disimpan."

        res = await save_daily_summary(99999)
        self.assertIn("Ringkasan percakapan hari ini berhasil disimpan ke Notion", res)
        self.assertIn("Hari ini membahas sapaan dan setup nama.", res)


if __name__ == "__main__":
    unittest.main()
