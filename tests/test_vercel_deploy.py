"""
Unit test suite untuk fitur Code Generation & Auto Deploy ke Vercel.
Jalankan dengan: python -m unittest tests/test_vercel_deploy.py
"""

import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# Add root directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.bot import detect_intent
from src.tools import deploy_to_vercel, get_tools_for_intent


class TestVercelDeploy(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        os.environ["VERCEL_API_TOKEN"] = "vcp_mock_token_12345"

    def test_detect_intent_deploy(self):
        """Tes pendeteksi intent deploy pada bot.py."""
        self.assertEqual(detect_intent("buatkan landing page dan deploy ke vercel"), "deploy")
        self.assertEqual(detect_intent("onlinekan website ini"), "deploy")
        self.assertEqual(detect_intent("hosting ke vercel"), "deploy")

    def test_get_tools_for_intent_deploy(self):
        """Tes pengambilan deklarasi tool untuk intent deploy."""
        tools = get_tools_for_intent("deploy")
        tool_names = [t["name"] for t in tools]
        self.assertIn("deploy_to_vercel", tool_names)

    @patch("httpx.AsyncClient.post", new_callable=AsyncMock)
    async def test_deploy_to_vercel_success(self, mock_post):
        """Tes deploy_to_vercel mengembalikan status success dan live URL saat status 200."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "dpl_12345",
            "url": "minuman-kekinian-12345.vercel.app",
        }
        mock_post.return_value = mock_response

        files = [
            {"filename": "index.html", "content": "<h1>Minuman Kekinian</h1>"},
            {"filename": "style.css", "content": "h1 { color: red; }"},
        ]

        res = await deploy_to_vercel(project_name="minuman kekinian", files=files)
        self.assertIn("status", res)
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["url"], "https://minuman-kekinian-12345.vercel.app")
        self.assertIn("Deployment berhasil", res["message"])

    @patch("httpx.AsyncClient.post", new_callable=AsyncMock)
    async def test_deploy_to_vercel_error(self, mock_post):
        """Tes deploy_to_vercel mengembalikan error saat status != 200."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_post.return_value = mock_response

        files = [{"filename": "index.html", "content": "<h1>Test</h1>"}]

        res = await deploy_to_vercel(project_name="test-app", files=files)
        self.assertIn("error", res)
        self.assertIn("Status 401", res["error"])


if __name__ == "__main__":
    unittest.main()
