"""
Groq API client untuk Oline bot (Fast Path).
Mengelola percakapan cepat (sapaan, obrolan umum) menggunakan model Groq llama-3.1-8b-instant.
Dilengkapi retry mechanism (exponential backoff) dan fallback exception.
"""

import asyncio
import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")


async def chat_groq(
    system_prompt: str,
    history: list[dict[str, Any]],
    user_message: str,
    max_retries: int = 3,
) -> str:
    """
    Panggil Groq API untuk Fast Path.
    Return teks respons atau raise exception jika terjadi kesalahan/rate limit.
    """
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        raise ValueError("GROQ_API_KEY environment variable is not set.")

    try:
        from groq import AsyncGroq
    except ImportError:
        raise ImportError(
            "Package 'groq' belum terinstall. Jalankan 'pip install groq'."
        )

    client = AsyncGroq(api_key=api_key)

    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]

    # Format riwayat percakapan (dibatasi 10 pesan terakhir / 5 putaran)
    if history:
        for h in history[-10:]:
            role = h.get("role", "user")
            groq_role = "assistant" if role in ("model", "assistant") else "user"
            text = h.get("text", "") or h.get("content", "")
            if text and text.strip():
                messages.append({"role": groq_role, "content": text.strip()})

    messages.append({"role": "user", "content": user_message})

    last_exception = None
    for attempt in range(max_retries):
        try:
            response = await client.chat.completions.create(
                model=GROQ_MODEL,
                messages=messages,
                temperature=0.9,
                max_tokens=1024,
            )

            if response.choices and len(response.choices) > 0:
                content = response.choices[0].message.content
                if content and content.strip():
                    logger.info("Successfully received response from Groq (%s)", GROQ_MODEL)
                    return content.strip()

            raise ValueError("Groq returned empty response choices.")

        except Exception as e:
            last_exception = e
            logger.warning(
                "Groq API call attempt %d/%d failed: %s",
                attempt + 1,
                max_retries,
                str(e),
            )
            if attempt < max_retries - 1:
                backoff = 2**attempt  # 1s, 2s, 4s
                await asyncio.sleep(backoff)

    if last_exception:
        raise last_exception
    raise RuntimeError("Groq API request failed after retries.")
