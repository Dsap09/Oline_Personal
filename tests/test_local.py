"""
Script pengujian lokal untuk memverifikasi API keys dan fungsi tools.
Jalankan dengan: python tests/test_local.py
"""

import asyncio
import os
import sys

from dotenv import load_dotenv

# Load .env
load_dotenv()

# Add root directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.tools import (
    get_movie_recommendation,
    get_music_recommendation,
    get_weather_forecast,
)


async def main():
    print("=== Testing Oline Tools & API Keys ===")

    # 1. iTunes API Test (No key required)
    print("\n1. Testing iTunes Search API (Music)...")
    music_res = await get_music_recommendation("chill indonesia")
    if "songs" in music_res:
        print(f"   [SUCCESS] Found {len(music_res['songs'])} songs:")
        for s in music_res["songs"][:2]:
            print(f"   - {s['title']} by {s['artist']}")
    else:
        print(f"   [FAIL] {music_res}")

    # 2. OpenWeatherMap API Test
    print("\n2. Testing OpenWeatherMap API (Weather)...")
    weather_res = await get_weather_forecast("Bandung")
    if "temp" in weather_res:
        print(f"   [SUCCESS] Weather in {weather_res['city']}:")
        print(f"   - Temp: {weather_res['temp']}°C, Condition: {weather_res['condition']}")
    else:
        print(f"   [FAIL] {weather_res}")

    # 3. TMDb API Test
    print("\n3. Testing TMDb API (Movies)...")
    movie_res = await get_movie_recommendation("horror indonesia")
    if "movies" in movie_res:
        print(f"   [SUCCESS] Found {len(movie_res['movies'])} movies:")
        for m in movie_res["movies"][:2]:
            print(f"   - {m['title']} ({m['year']}) - Rating: {m['rating']}")
    else:
        print(f"   [FAIL] {movie_res}")

    print("\n=== Test Completed ===")


if __name__ == "__main__":
    asyncio.run(main())
