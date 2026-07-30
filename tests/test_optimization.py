"""
Pengujian otomatis untuk Fast Path, Intent Detection, Tool Filtering, dan chat_with_oline.
Jalankan dengan: python tests/test_optimization.py
"""

import asyncio
import os
import sys
import time

from dotenv import load_dotenv

load_dotenv()

# Add root directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.bot import detect_intent
from src.tools import get_tools_for_intent
from src.gemini import chat_with_oline


async def test_optimization():
    print("=== 1. Testing Intent Detection ===")
    test_cases = [
        ("halo lin, lagi apa?", None),
        ("apa kabar kamu hari ini?", None),
        ("rekomendasi film horor dong", "rekomendasi"),
        ("bagaimana cuaca di Jakarta besok?", "cuaca"),
        ("bacain puisi singkat pakai suara", "suara"),
        ("catat jurnal hari ini: makan enak", "jurnal"),
        ("sisa kuota token berapa ya?", "kuota"),
    ]

    passed_intents = 0
    for text, expected in test_cases:
        res = detect_intent(text)
        status = "PASSED" if res == expected else f"FAILED (Got {res}, expected {expected})"
        print(f" - Text: '{text}' -> Intent: {res} [{status}]")
        if res == expected:
            passed_intents += 1

    print(f"Intent Detection Result: {passed_intents}/{len(test_cases)} passed.")

    print("\n=== 2. Testing Tool Filtering ===")
    fast_path_tools = get_tools_for_intent(None)
    weather_tools = get_tools_for_intent("cuaca")
    reco_tools = get_tools_for_intent("rekomendasi")

    print(f" - Fast Path Tools Count: {len(fast_path_tools)} (Expected: 0)")
    print(f" - Weather Tools: {[t['name'] for t in weather_tools]} (Expected: 1 tool)")
    print(f" - Reco Tools: {[t['name'] for t in reco_tools]} (Expected: 2 tools)")

    assert len(fast_path_tools) == 0
    assert len(weather_tools) == 1 and weather_tools[0]["name"] == "get_weather_forecast"
    assert len(reco_tools) == 2

    print("\n=== 3. Testing Fast Path Chat Latency ===")
    start_time = time.time()
    response_fast = await chat_with_oline(chat_id=999999, user_message="halo lin, selamat pagi!", user_name="Budi", intent=None)
    elapsed_fast = time.time() - start_time
    print(f" - Fast Path Response: '{response_fast[:60].encode('ascii', 'ignore').decode('ascii')}...'")
    print(f" - Latency: {elapsed_fast:.2f} detik (Target <3s)")

    print("\n=== 4. Testing Slow Path Chat (Cuaca) ===")
    start_time = time.time()
    response_slow = await chat_with_oline(chat_id=999999, user_message="bagaimana cuaca di Bandung hari ini?", user_name="Budi", intent="cuaca")
    elapsed_slow = time.time() - start_time
    print(f" - Slow Path Response: '{response_slow[:80].encode('ascii', 'ignore').decode('ascii')}...'")
    print(f" - Latency: {elapsed_slow:.2f} detik (Target <6s)")

    print("\n=== All Optimization Tests Completed Successfully! ===")



if __name__ == "__main__":
    asyncio.run(test_optimization())
