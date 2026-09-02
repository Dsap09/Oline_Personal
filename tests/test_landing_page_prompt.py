"""
Unit test suite untuk memastikan prompt Panduan Landing Page Anti AI-Slop terpasang dengan benar di OLINE_SYSTEM_PROMPT.
Jalankan dengan: python -m unittest tests/test_landing_page_prompt.py
"""

import os
import sys
import unittest

# Add root directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.personas import OLINE_SYSTEM_PROMPT


class TestLandingPagePrompt(unittest.TestCase):

    def test_anti_ai_slop_section_exists(self):
        """Memastikan judul dan section Panduan Landing Page Anti AI-Slop ada dalam prompt."""
        self.assertIn("Panduan Membuat Landing Page (Anti AI Slop)", OLINE_SYSTEM_PROMPT)
        self.assertIn("Struktur & Layout", OLINE_SYSTEM_PROMPT)
        self.assertIn("Copywriting", OLINE_SYSTEM_PROMPT)

    def test_design_styles_exist(self):
        """Memastikan 3 gaya desain default (Editorial, Brutalist, Soft UI) tercantum."""
        self.assertIn("Editorial", OLINE_SYSTEM_PROMPT)
        self.assertIn("Brutalist", OLINE_SYSTEM_PROMPT)
        self.assertIn("Soft UI", OLINE_SYSTEM_PROMPT)

    def test_typography_recommendations_exist(self):
        """Memastikan font berkarakter dari Google Fonts direkomendasikan."""
        fonts = ["Space Grotesk", "Fraunces", "Manrope", "Playfair Display", "DM Mono"]
        for font in fonts:
            self.assertIn(font, OLINE_SYSTEM_PROMPT)

    def test_revision_process_guideline_exists(self):
        """Memastikan instruksi penanganan revisi landing page tercantum."""
        self.assertIn("Proses Revisi Landing Page", OLINE_SYSTEM_PROMPT)
        self.assertIn("Ubah kode yang relevan, lalu deploy ulang", OLINE_SYSTEM_PROMPT)


if __name__ == "__main__":
    unittest.main()
