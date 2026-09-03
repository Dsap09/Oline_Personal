"""
Vercel Serverless Function — Endpoint ringan untuk keep-alive (warm-up).
Tidak import library berat apapun. Dilindungi secret header.
"""

import json
import os
from datetime import datetime


def app(environ, start_response):
    """
    WSGI Application handler untuk keep-alive endpoint.
    Hanya merespons GET. Dilindungi header x-keepalive-secret.
    """
    method = environ.get("REQUEST_METHOD", "GET").upper()

    # Hanya izinkan GET
    if method != "GET":
        start_response("405 Method Not Allowed", [("Content-Type", "text/plain")])
        return [b"Method Not Allowed"]

    # Validasi secret header
    expected_secret = os.environ.get("KEEPALIVE_SECRET", "").strip()
    provided_secret = environ.get("HTTP_X_KEEPALIVE_SECRET", "")

    if expected_secret:
        if provided_secret != expected_secret:
            start_response("403 Forbidden", [("Content-Type", "text/plain")])
            return [b"Forbidden"]

    # Respons ringan
    body = json.dumps({
        "status": "ok",
        "bot": "Oline",
        "endpoint": "keepalive",
        "time": datetime.now().isoformat(),
    }).encode("utf-8")

    start_response("200 OK", [
        ("Content-Type", "application/json"),
        ("Cache-Control", "no-store"),
    ])
    return [body]
