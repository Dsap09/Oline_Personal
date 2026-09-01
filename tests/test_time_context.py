"""
Unit test suite untuk perbaikan akurasi waktu (Hari/Tanggal/Jam WIB).
Jalankan dengan: python -m unittest tests/test_time_context.py
"""

import os
import sys
import unittest

# Add root directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.gemini import _build_system_prompt
from src.utils import get_current_time_context


class TestTimeContext(unittest.TestCase):

    def test_get_current_time_context_format(self):
        """Tes fungsi get_current_time_context mengembalikan string berformat WIB."""
        ctx = get_current_time_context()
        self.assertTrue(ctx.startswith("Sekarang adalah hari "))
        self.assertIn("WIB.", ctx)
        self.assertIn("pukul ", ctx)

        # Cek salah satu nama hari Indonesia ada dalam string
        hari_names = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
        has_hari = any(f"hari {h}" in ctx for h in hari_names)
        self.assertTrue(has_hari, f"Hasil '{ctx}' tidak memuat nama hari Indonesia yang valid")

    def test_build_system_prompt_injects_time(self):
        """Tes _build_system_prompt memasukkan konteks waktu WIB ke system prompt."""
        prompt = _build_system_prompt(memory="", user_name="Budi")
        self.assertIn("Budi", prompt)
        self.assertIn("Tanggal & Waktu Saat Ini:", prompt)
        self.assertIn("WIB.", prompt)


if __name__ == "__main__":
    unittest.main()
