"""
Unit test untuk memverifikasi fitur Auto-Correct ejaan Bahasa Indonesia.
Jalankan dengan: python tests/test_autocorrect.py atau pytest tests/test_autocorrect.py
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.autocorrect_utils import correct_typo
from src.bot import detect_intent


class TestAutoCorrectFeature(unittest.TestCase):

    def test_speller_corrections(self):
        """Memastikan kata-kata typo umum dapat dikoreksi ke bentuk baku/benar."""
        test_cases = [
            ("rekomendasi flm horor", "film"),
            ("cuaca di jkarta", "jakarta"),
            ("catat jurnl hari ini", "jurnal"),
            ("cari tau siap ekin", "siapa"),
        ]

        for input_text, expected_word in test_cases:
            corrected = correct_typo(input_text)
            self.assertIn(
                expected_word,
                corrected.lower(),
                f"Koreksi '{input_text}' gagal. Hasil: '{corrected}'",
            )

    def test_intent_detection_after_correction(self):
        """Memastikan intent terdeteksi dengan tepat setelah typo dikoreksi."""
        typo_queries = [
            ("cuaca di jkarta", "cuaca"),
            ("rekomendasi flm horor", "rekomendasi"),
            ("cari berita trkini", "search"),
        ]

        for typo_text, expected_intent in typo_queries:
            corrected_text = correct_typo(typo_text)
            intent = detect_intent(corrected_text)
            self.assertEqual(
                intent,
                expected_intent,
                f"Intent untuk '{typo_text}' (dikoreksi: '{corrected_text}') harusnya '{expected_intent}', tapi terdeteksi '{intent}'",
            )

    def test_normal_text_preservation(self):
        """Memastikan teks tanpa typo dan nama diri seperti Ekin tidak rusak."""
        normal_text = "siapa presiden indonesia sekarang ekin"
        corrected = correct_typo(normal_text)
        self.assertIn("presiden", corrected.lower())
        self.assertIn("indonesia", corrected.lower())
        self.assertIn("ekin", corrected.lower())


if __name__ == "__main__":
    unittest.main()
