"""
Unit test suite untuk verifikasi Persona Oline sebagai AI Agent Profesional.
Jalankan dengan: python -m unittest tests/test_professional_persona.py
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.personas import OLINE_SYSTEM_PROMPT


class TestProfessionalPersona(unittest.TestCase):

    def test_persona_identity_is_professional_ai_agent(self):
        """Memastikan deskripsi persona menetapkan Oline sebagai AI Agent profesional."""
        self.assertIn("AI Agent profesional", OLINE_SYSTEM_PROMPT)
        self.assertIn("efisien, akurat, dan dapat diandalkan", OLINE_SYSTEM_PROMPT)

    def test_no_gen_z_slang_in_system_prompt(self):
        """Memastikan kata kunci slang Gen-Z lama tidak ada di system prompt."""
        forbidden_terms = [
            "Gen-Z berusia 19 tahun",
            "perempuan Gen-Z",
            "lucu dan gemes",
            "seperti teman dekat, bukan customer service",
            "Aku bantu cek cuaca",
        ]
        for term in forbidden_terms:
            self.assertNotIn(term, OLINE_SYSTEM_PROMPT)

    def test_professional_phrasing_guidelines_exist(self):
        """Memastikan panduan kalimat khas profesional tercantum."""
        self.assertIn("Baik, saya proses.", OLINE_SYSTEM_PROMPT)
        self.assertIn("Permintaan Anda sedang dikerjakan.", OLINE_SYSTEM_PROMPT)
        self.assertIn("Apakah ada lagi yang bisa saya bantu?", OLINE_SYSTEM_PROMPT)


if __name__ == "__main__":
    unittest.main()
