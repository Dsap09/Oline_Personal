"""
Unit test suite untuk fitur Eksekusi Kode (Piston API).
Jalankan dengan: python -m unittest tests/test_code_execution.py
"""

import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# Add root directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.bot import detect_intent
from src.tools import execute_code, get_tools_for_intent


class TestCodeExecution(unittest.IsolatedAsyncioTestCase):

    def test_detect_intent_coding(self):
        """Tes pendeteksi intent coding."""
        self.assertEqual(detect_intent("jalankan kode python print('halo')"), "coding")
        self.assertEqual(detect_intent("eksekusi script javascript"), "coding")
        self.assertEqual(detect_intent("run code python"), "coding")
        self.assertEqual(detect_intent("debug fungsi ini"), "coding")

    def test_get_tools_for_intent_coding(self):
        """Tes pengambilan deklarasi tool untuk intent coding."""
        tools = get_tools_for_intent("coding")
        tool_names = [t["name"] for t in tools]
        self.assertIn("execute_code", tool_names)

    @patch("httpx.AsyncClient.post", new_callable=AsyncMock)
    async def test_execute_code_success(self, mock_post):
        """Tes eksekusi kode sukses mengembalikan stdout."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "language": "python",
            "version": "3.10.0",
            "run": {
                "stdout": "halo dunia\n",
                "stderr": "",
                "code": 0,
                "output": "halo dunia\n",
            },
        }
        mock_post.return_value = mock_response

        res = await execute_code(language="python", code="print('halo dunia')")
        self.assertEqual(res["language"], "python")
        self.assertEqual(res["stdout"], "halo dunia")
        self.assertEqual(res["stderr"], "")
        self.assertEqual(res["exit_code"], 0)

    @patch("httpx.AsyncClient.post", new_callable=AsyncMock)
    async def test_execute_code_error_output(self, mock_post):
        """Tes eksekusi kode yang menghasilkan stderr."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "language": "python",
            "version": "3.10.0",
            "run": {
                "stdout": "",
                "stderr": "NameError: name 'x' is not defined\n",
                "code": 1,
                "output": "NameError: name 'x' is not defined\n",
            },
        }
        mock_post.return_value = mock_response

        res = await execute_code(language="python", code="print(x)")
        self.assertEqual(res["stderr"], "NameError: name 'x' is not defined")
        self.assertEqual(res["exit_code"], 1)

    @patch("httpx.AsyncClient.post", new_callable=AsyncMock)
    async def test_execute_code_truncation(self, mock_post):
        """Tes pemotongan output jika melebihi 1500 karakter."""
        long_output = "a" * 2000
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "language": "python",
            "version": "3.10.0",
            "run": {
                "stdout": long_output,
                "stderr": "",
                "code": 0,
                "output": long_output,
            },
        }
        mock_post.return_value = mock_response

        res = await execute_code(language="python", code="print('a'*2000)")
        self.assertTrue(res["stdout"].endswith("...(output dipotong)"))
        self.assertLess(len(res["stdout"]), 1600)

    @patch("httpx.AsyncClient.post", new_callable=AsyncMock)
    async def test_execute_code_timeout(self, mock_post):
        """Tes penanganan timeout pada Piston API."""
        import httpx

        mock_post.side_effect = httpx.TimeoutException("Timeout")

        res = await execute_code(language="python", code="while True: pass")
        self.assertIn("error", res)
        self.assertIn("kelamaan", res["error"])


if __name__ == "__main__":
    unittest.main()
