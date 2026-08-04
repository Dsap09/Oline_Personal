"""
Unit dan Integration Test untuk Groq API Integration & Fallback ke Gemini.
Jalankan dengan: python tests/test_groq_integration.py
"""

import asyncio
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# Add root directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.bot import detect_intent
from src.gemini import chat_with_oline
from src.groq import GROQ_MODEL, chat_groq


class TestGroqIntegration(unittest.IsolatedAsyncioTestCase):

    async def test_groq_missing_api_key(self):
        """Tes error ketika GROQ_API_KEY tidak diset."""
        with patch.dict(os.environ, {"GROQ_API_KEY": ""}, clear=False):
            with self.assertRaises(ValueError) as ctx:
                await chat_groq("system prompt", [], "halo")
            self.assertIn("GROQ_API_KEY environment variable is not set", str(ctx.exception))

    @patch("groq.AsyncGroq")
    async def test_groq_successful_chat(self, mock_async_groq):
        """Tes respons sukses dari Groq API."""
        mock_client = MagicMock()
        mock_completion = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "Halo! Ada yang bisa aku bantu?"
        mock_completion.choices = [mock_choice]

        mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)
        mock_async_groq.return_value = mock_client

        with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_test123"}):
            response = await chat_groq(
                system_prompt="Kamu Oline",
                history=[{"role": "user", "text": "hai"}, {"role": "model", "text": "halo"}],
                user_message="apa kabar?",
            )
            self.assertEqual(response, "Halo! Ada yang bisa aku bantu?")

            # Pastikan create dipanggil dengan argument yang tepat
            mock_client.chat.completions.create.assert_called_once()
            call_kwargs = mock_client.chat.completions.create.call_args.kwargs
            self.assertEqual(call_kwargs["model"], GROQ_MODEL)
            self.assertEqual(len(call_kwargs["messages"]), 4)  # system + 2 history + 1 user
            self.assertEqual(call_kwargs["messages"][0]["role"], "system")
            self.assertEqual(call_kwargs["messages"][-1]["role"], "user")

    @patch("asyncio.sleep", new_callable=AsyncMock)
    @patch("groq.AsyncGroq")
    async def test_groq_retry_mechanism(self, mock_async_groq, mock_sleep):
        """Tes retry exponential backoff ketika Groq error beberapa kali lalu sukses."""
        mock_client = MagicMock()
        mock_completion = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "Respons setelah retry"
        mock_completion.choices = [mock_choice]

        # Simulasi: 2 kali gagal, ke-3 sukses
        mock_client.chat.completions.create = AsyncMock(
            side_effect=[
                RuntimeError("Rate limit 429"),
                RuntimeError("Service unavailable 503"),
                mock_completion,
            ]
        )
        mock_async_groq.return_value = mock_client

        with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_test123"}):
            response = await chat_groq("prompt", [], "tes", max_retries=3)
            self.assertEqual(response, "Respons setelah retry")
            self.assertEqual(mock_client.chat.completions.create.call_count, 3)
            self.assertEqual(mock_sleep.call_count, 2)  # backoff dipanggil 2 kali (1s, 2s)

    @patch("src.groq.chat_groq", new_callable=AsyncMock)
    @patch("src.gemini._generate_content_with_fallback", new_callable=AsyncMock)
    @patch("src.gemini.get_memory", new_callable=AsyncMock)
    @patch("src.gemini.get_history", new_callable=AsyncMock)
    @patch("src.gemini.save_history", new_callable=AsyncMock)
    async def test_chat_with_oline_groq_fallback_to_gemini(
        self,
        mock_save_hist,
        mock_get_hist,
        mock_get_mem,
        mock_gen_gemini,
        mock_chat_groq,
    ):
        """Tes jika Groq gagal (exception), chat_with_oline otomatis fallback ke Gemini."""
        mock_get_mem.return_value = ""
        mock_get_hist.return_value = []
        mock_chat_groq.side_effect = RuntimeError("Groq Rate Limit Exceeded")

        mock_gemini_resp = MagicMock()
        mock_gemini_resp.text = "Jawaban dari Gemini Fallback"
        mock_gen_gemini.return_value = (mock_gemini_resp, "gemini-2.0-flash", 120)

        with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_test123"}):
            response = await chat_with_oline(
                chat_id=888111,
                user_message="halo lin",
                user_name="Budi",
                intent=None,  # Fast path
            )

            # Pastikan chat_groq dipanggil & melempar exception
            mock_chat_groq.assert_called_once()
            # Pastikan Gemini fallback dipanggil
            mock_gen_gemini.assert_called_once()
            self.assertEqual(response, "Jawaban dari Gemini Fallback")

    @patch("src.groq.chat_groq", new_callable=AsyncMock)
    @patch("src.gemini._generate_content_with_fallback", new_callable=AsyncMock)
    @patch("src.gemini.get_memory", new_callable=AsyncMock)
    @patch("src.gemini.get_history", new_callable=AsyncMock)
    @patch("src.gemini.save_history", new_callable=AsyncMock)
    async def test_chat_with_oline_slow_path_skips_groq(
        self,
        mock_save_hist,
        mock_get_hist,
        mock_get_mem,
        mock_gen_gemini,
        mock_chat_groq,
    ):
        """Tes bahwa Slow Path (intent tidak None) langsung ke Gemini dan tidak memanggil Groq."""
        mock_get_mem.return_value = ""
        mock_get_hist.return_value = []

        mock_gemini_resp = MagicMock()
        mock_gemini_resp.text = "Hari ini cuaca di Jakarta cerah 28°C"
        mock_gen_gemini.return_value = (mock_gemini_resp, "gemini-2.0-flash", 200)

        with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_test123"}):
            response = await chat_with_oline(
                chat_id=888111,
                user_message="bagaimana cuaca di Jakarta?",
                user_name="Budi",
                intent="cuaca",  # Slow path
            )

            # Pastikan Groq TIDAK dipanggil
            mock_chat_groq.assert_not_called()
            # Pastikan Gemini dipanggil
            mock_gen_gemini.assert_called_once()
            self.assertEqual(response, "Hari ini cuaca di Jakarta cerah 28°C")


if __name__ == "__main__":
    unittest.main()
