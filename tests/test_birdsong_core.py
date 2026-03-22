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
        self.assertTrue(
            math.isclose(
                birdsong.get_frequency("Bb4"),
                birdsong.get_frequency("A#4"),
                rel_tol=1e-9,
            )
        )

    def test_normalize_audio_samples_downmixes_and_normalizes_int16(self):
        stereo = np.array([[32767, -32767], [16384, 16384]], dtype=np.int16)
        normalized = birdsong.normalize_audio_samples(stereo)

        self.assertEqual(np.float32, normalized.dtype)
        self.assertEqual((2,), normalized.shape)
        self.assertAlmostEqual(0.0, float(normalized[0]), places=4)
        self.assertAlmostEqual(16384 / 32768, float(normalized[1]), places=4)

    def test_normalize_audio_samples_supports_uint8(self):
        samples = np.array([0, 128, 255], dtype=np.uint8)
        normalized = birdsong.normalize_audio_samples(samples)

        self.assertEqual(np.float32, normalized.dtype)
        self.assertAlmostEqual(-1.0, float(normalized[0]), places=4)
        self.assertAlmostEqual(0.0, float(normalized[1]), places=2)
        self.assertGreater(float(normalized[2]), 0.99)

    def test_generate_tone_is_float32_and_windowed(self):
        tone = birdsong.generate_tone(440.0, 0.05, birdsong.SAMPLE_RATE)

        self.assertEqual(np.float32, tone.dtype)
        self.assertAlmostEqual(0.0, float(tone[0]), places=6)
        self.assertAlmostEqual(0.0, float(tone[-1]), places=6)
        self.assertGreater(float(np.max(np.abs(tone))), 0.5)


if __name__ == "__main__":
    unittest.main()
