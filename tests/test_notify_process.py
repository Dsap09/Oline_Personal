"""
Unit test suite untuk helper notify_process dan notifikasi proses berjalan.
Jalankan dengan: python -m unittest tests/test_notify_process.py
"""

import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils import notify_process
from src.tools import execute_tool


class TestNotifyProcess(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        os.environ["TELEGRAM_BOT_TOKEN"] = "mock_bot_token_123"

    @patch("telegram.Bot.send_chat_action", new_callable=AsyncMock)
    @patch("telegram.Bot.send_message", new_callable=AsyncMock)
    async def test_notify_process_with_action_and_message(self, mock_send_message, mock_send_action):
        """Tes notify_process mengirim chat action dan pesan status."""
        await notify_process(chat_id=12345, action="typing", message="Proses deploy ya, bentar~ 🚀")
        mock_send_action.assert_called_once_with(chat_id=12345, action="typing")
        mock_send_message.assert_called_once_with(chat_id=12345, text="Proses deploy ya, bentar~ 🚀")

    @patch("telegram.Bot.send_chat_action", new_callable=AsyncMock)
    @patch("telegram.Bot.send_message", new_callable=AsyncMock)
    async def test_notify_process_action_only(self, mock_send_message, mock_send_action):
        """Tes notify_process mengirim chat action tanpa pesan teks."""
        await notify_process(chat_id=12345, action="typing", message=None)
        mock_send_action.assert_called_once_with(chat_id=12345, action="typing")
        mock_send_message.assert_not_called()

    async def test_notify_process_no_chat_id(self):
        """Tes notify_process mengabaikan panggila jika chat_id 0 atau None."""
        await notify_process(chat_id=0, action="typing", message="Hello")
        # Should complete gracefully without error

    @patch("src.utils.notify_process", new_callable=AsyncMock)
    @patch("src.tools.preview_with_codepen", new_callable=AsyncMock)
    async def test_execute_tool_triggers_notification(self, mock_preview, mock_notify):
        """Tes execute_tool memicu notify_process untuk heavy tool preview_with_codepen."""
        mock_preview.return_value = {"status": "success", "url": "https://jsfiddle.net/123/"}
        res = await execute_tool(
            "preview_with_codepen",
            {"title": "Test", "html": "<h1>test</h1>"},
            chat_id=999,
        )
        mock_notify.assert_called_once_with(chat_id=999, action="typing", message="Aku buatkan preview dulu~")
        self.assertEqual(res["status"], "success")


if __name__ == "__main__":
    unittest.main()
