"""
Vercel Serverless Function – Entrypoint webhook untuk Oline Telegram Bot.

Menerima POST update dari Telegram webhook dan memprosesnya.
GET request digunakan sebagai health check sederhana.
"""

import asyncio
import json
import logging
import os
import sys

# Tambahkan root project ke path agar import src/ berfungsi
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from http.server import BaseHTTPRequestHandler

from telegram import Update

from src.bot import create_application

# Konfigurasi logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Webhook secret untuk validasi request dari Telegram
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")


class handler(BaseHTTPRequestHandler):
    """
    Vercel serverless handler.
    POST: Menerima Telegram webhook update.
    GET: Health check.
    """

    def do_GET(self):
        """Health check endpoint."""
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        response = json.dumps({
            "status": "ok",
            "bot": "Oline",
            "message": "Oline is running! 🤖",
        })
        self.wfile.write(response.encode("utf-8"))

    def do_POST(self):
        """Menerima dan memproses Telegram webhook update."""
        try:
            # Baca request body
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length == 0:
                self.send_response(400)
                self.end_headers()
                return

            body = self.rfile.read(content_length)

            # Validasi webhook secret jika dikonfigurasi
            if WEBHOOK_SECRET:
                secret_header = self.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
                if secret_header != WEBHOOK_SECRET:
                    logger.warning("Invalid webhook secret received")
                    self.send_response(403)
                    self.end_headers()
                    return

            # Parse update
            update_data = json.loads(body.decode("utf-8"))
            logger.info("Received update: %s", update_data.get("update_id", "unknown"))

            # Proses update secara async
            asyncio.run(self._process_update(update_data))

            # Respond OK ke Telegram
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok": true}')

        except json.JSONDecodeError:
            logger.error("Invalid JSON in request body")
            self.send_response(400)
            self.end_headers()
        except Exception as e:
            logger.error("Error processing update: %s", str(e))
            # Tetap return 200 ke Telegram agar tidak retry terus
            self.send_response(200)
            self.end_headers()

    async def _process_update(self, update_data: dict) -> None:
        """Proses Telegram update melalui bot application."""
        try:
            app = create_application()
            async with app:
                update = Update.de_json(update_data, app.bot)
                if update:
                    await app.process_update(update)
        except Exception as e:
            logger.error("Error in _process_update: %s", str(e))
