"""
Unit test suite untuk OpenRouter Model Rotation dan Fitur Cek Kuota.
Jalankan dengan: python -m unittest tests/test_openrouter_rotation.py
"""

import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.openrouter import (
    DEFAULT_OPENROUTER_MODELS,
    chat_openrouter,
    convert_gemini_tools_to_openai,
    get_model_list,
    get_openrouter_quota_info,
)
from src.tools import execute_check_quota


class TestOpenRouterRotation(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        os.environ["OPENROUTER_API_KEY"] = "sk-or-v1-mock-key-12345"
        os.environ["OPENROUTER_MODELS"] = "model1/test-a,model2/test-b,model3/test-c"

    def tearDown(self):
        os.environ.pop("OPENROUTER_MODELS", None)

    def test_get_model_list_custom_env(self):
        """Tes get_model_list mengambil daftar model dari OPENROUTER_MODELS."""
        models = get_model_list()
        self.assertEqual(models, ["model1/test-a", "model2/test-b", "model3/test-c"])

    def test_get_model_list_default_fallback(self):
        """Tes get_model_list fallback ke DEFAULT_OPENROUTER_MODELS jika env kosong."""
        os.environ["OPENROUTER_MODELS"] = ""
        models = get_model_list()
        self.assertEqual(models, DEFAULT_OPENROUTER_MODELS)

    def test_convert_gemini_tools_to_openai(self):
        """Tes konversi deklarasi tool Gemini ke format OpenAI/OpenRouter."""
        gemini_tools = [
            {
                "name": "get_weather_forecast",
                "description": "Cek cuaca",
                "parameters": {
                    "type": "object",
                    "properties": {"city": {"type": "string"}},
                    "required": ["city"],
                },
            }
        ]
        res = convert_gemini_tools_to_openai(gemini_tools)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["type"], "function")
        self.assertEqual(res[0]["function"]["name"], "get_weather_forecast")

    @patch("httpx.AsyncClient.post", new_callable=AsyncMock)
    async def test_openrouter_rotation_on_429_error(self, mock_post):
        """Tes rotasi model otomatis jika model pertama terkena HTTP 429 rate limit."""
        mock_resp_429 = MagicMock()
        mock_resp_429.status_code = 429
        mock_resp_429.text = "Rate limit exceeded"

        mock_resp_200 = MagicMock()
        mock_resp_200.status_code = 200
        mock_resp_200.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "Halo! Saya Oline dari model kedua.",
                        "tool_calls": None,
                    }
                }
            ]
        }

        # Panggilan pertama 429 (model1), panggilan kedua 200 (model2)
        mock_post.side_effect = [mock_resp_429, mock_resp_200]

        res = await chat_openrouter(
            system_prompt="System prompt test",
            history=[],
            user_message="Halo",
            chat_id=123,
        )

        self.assertEqual(res, "Halo! Saya Oline dari model kedua.")
        self.assertEqual(mock_post.call_count, 2)
        # Memastikan model kedua yang berhasil dipanggil
        called_model = mock_post.call_args_list[1][1]["json"]["model"]
        self.assertEqual(called_model, "model2/test-b")

    @patch("src.kv.get_cache", new_callable=AsyncMock)
    async def test_get_openrouter_quota_info(self, mock_get_cache):
        """Tes get_openrouter_quota_info mengembalikan model aktif dan daftar rotasi."""
        mock_get_cache.return_value = "5"
        info = await get_openrouter_quota_info(chat_id=123)

        self.assertEqual(info["active_model"], "model1/test-a")
        self.assertEqual(info["total_models"], 3)
        self.assertEqual(len(info["models_status"]), 3)
        self.assertEqual(info["models_status"][0]["model"], "model1/test-a")
        self.assertIn("Groq API", info["fallback_queue"][0])

    @patch("src.openrouter.get_openrouter_quota_info", new_callable=AsyncMock)
    @patch("src.tools.get_today_usage", new_callable=AsyncMock)
    @patch("src.tools.get_today_groq_usage", new_callable=AsyncMock)
    async def test_execute_check_quota_with_openrouter(self, mock_groq, mock_gemini, mock_openrouter):
        """Tes execute_check_quota menyertakan rincian OpenRouter active model dan fallback status."""
        mock_gemini.return_value = 100
        mock_groq.return_value = 200
        mock_openrouter.return_value = {
            "active_model": "poolside/laguna-s-2.1",
            "total_models": 5,
            "remaining_in_rotation": 5,
            "total_requests_today": 12,
            "models_status": [
                {"order": 1, "model": "poolside/laguna-s-2.1", "status": "Aktif (Primary)", "usage": 12},
                {"order": 2, "model": "thinkingmachines/inkling", "status": "Antrean ke-2", "usage": 0},
            ],
            "fallback_queue": ["Groq API", "Gemini API"],
        }

        res = await execute_check_quota(chat_id=999)
        self.assertIn("openrouter_summary", res)
        self.assertEqual(res["openrouter_active_model"], "poolside/laguna-s-2.1")
        self.assertEqual(res["openrouter_remaining_models_before_fallback"], 5)
        self.assertIn("poolside/laguna-s-2.1", res["openrouter_summary"])
        self.assertIn("Cadangan jika semua model OpenRouter limit", res["fallback_queue_info"])


if __name__ == "__main__":
    unittest.main()
