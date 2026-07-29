"""
Script untuk mengatur webhook Telegram Bot ke URL Vercel.

Penggunaan:
    python scripts/set_webhook.py <VERCEL_URL>

Contoh:
    python scripts/set_webhook.py https://oline-bot.vercel.app

Environment variables yang dibutuhkan:
    - TELEGRAM_BOT_TOKEN: Token bot Telegram
    - WEBHOOK_SECRET (opsional): Secret token untuk validasi webhook
"""

import os
import sys

import httpx
from dotenv import load_dotenv

# Load .env jika ada (untuk development lokal)
load_dotenv()


def set_webhook(vercel_url: str) -> None:
    """Set webhook Telegram Bot ke URL Vercel."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("Error: TELEGRAM_BOT_TOKEN environment variable is not set.")
        sys.exit(1)

    webhook_url = f"{vercel_url.rstrip('/')}/api/index"
    api_url = f"https://api.telegram.org/bot{token}/setWebhook"

    params = {"url": webhook_url}

    # Tambahkan secret token jika ada
    secret = os.environ.get("WEBHOOK_SECRET")
    if secret:
        params["secret_token"] = secret
        print(f"Using webhook secret token for validation.")

    print(f"Setting webhook to: {webhook_url}")

    response = httpx.post(api_url, json=params, timeout=30.0)
    result = response.json()

    if result.get("ok"):
        print("Webhook berhasil diatur! [SUCCESS]")
        print(f"Response: {result.get('description', '')}")
    else:
        print(f"Gagal mengatur webhook [FAIL]")
        print(f"Error: {result.get('description', 'Unknown error')}")
        sys.exit(1)


def get_webhook_info() -> None:
    """Tampilkan info webhook saat ini."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("Error: TELEGRAM_BOT_TOKEN environment variable is not set.")
        sys.exit(1)

    api_url = f"https://api.telegram.org/bot{token}/getWebhookInfo"
    response = httpx.get(api_url, timeout=30.0)
    result = response.json()

    if result.get("ok"):
        info = result.get("result", {})
        print("Webhook Info:")
        print(f"  URL: {info.get('url', '(not set)')}")
        print(f"  Pending updates: {info.get('pending_update_count', 0)}")
        print(f"  Last error: {info.get('last_error_message', '(none)')}")
    else:
        print(f"Gagal mengambil info webhook: {result}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/set_webhook.py <VERCEL_URL>")
        print("       python scripts/set_webhook.py --info")
        sys.exit(1)

    if sys.argv[1] == "--info":
        get_webhook_info()
    else:
        set_webhook(sys.argv[1])
