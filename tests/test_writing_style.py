"""
Pengujian gaya penulisan Oline: memastikan tidak ada tanda bintang (*), markdown bold/italic, atau daftar bernomor.
Jalankan dengan: python tests/test_writing_style.py
"""

import asyncio
import os
import sys
import re

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.gemini import chat_with_oline


async def test_no_markdown_style():
    print("=== Testing Oline Writing Style (No Markdown / Asterisks) ===")

    queries = [
        "Rekomendasi kegiatan akhir pekan dong",
        "Kasih aku 3 ide buat sarapan simpel",
        "Ada saran lagu yang enak buat nemenin belajar?",
    ]

    for q in queries:
        print(f"\nUser Query: '{q}'")
        response = await chat_with_oline(
            chat_id=888888,
            user_message=q,
            user_name="Budi",
            intent=None
        )
        safe_resp = response.encode("ascii", "ignore").decode("ascii")
        print(f"Oline Response: {safe_resp}")

        # Assertions
        has_asterisks = "*" in response
        has_numbered_list = bool(re.search(r"^\s*\d+\.\s+", response, re.MULTILINE))

        print(f" - Contains asterisks (*): {has_asterisks}")
        print(f" - Contains numbered list (1. 2. 3.): {has_numbered_list}")

        if not has_asterisks and not has_numbered_list:
            print(" -> [SUCCESS] Plain text natural style!")
        else:
            print(" -> [WARNING] Response still contained markdown/formatting.")

    print("\n=== Test Writing Style Completed ===")


if __name__ == "__main__":
    asyncio.run(test_no_markdown_style())
