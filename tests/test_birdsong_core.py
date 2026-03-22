import importlib
import math
import pathlib
import sys
import unittest

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
birdsong = importlib.import_module("birdsong")


class BirdsongCoreTests(unittest.TestCase):
    def test_bytes_to_bits_round_trip(self):
        payload = b"\x00\xa5\xff"
        bits = birdsong.bytes_to_bits(payload)
        self.assertEqual(payload, birdsong.bits_to_bytes(bits))

    def test_checksum_matches_sum_mod_256(self):
        self.assertEqual(0x38, birdsong.calculate_checksum(b"Birdsong"))

    def test_get_frequency_parses_musical_notes(self):
        self.assertTrue(math.isclose(birdsong.get_frequency("A4"), 440.0, rel_tol=1e-9))
        self.assertTrue(
            math.isclose(birdsong.get_frequency("C8"), 4186.009044809578, rel_tol=1e-9)
        )

    def test_generate_tone_is_float32_and_windowed(self):
        tone = birdsong.generate_tone(440.0, 0.05, birdsong.SAMPLE_RATE)

        self.assertEqual(np.float32, tone.dtype)
        self.assertAlmostEqual(0.0, float(tone[0]), places=6)
        self.assertAlmostEqual(0.0, float(tone[-1]), places=6)
        self.assertGreater(float(np.max(np.abs(tone))), 0.5)


if __name__ == "__main__":
    unittest.main()
