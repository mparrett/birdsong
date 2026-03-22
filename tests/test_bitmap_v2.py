import pathlib
import tempfile
import unittest

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "experiments" / "active"))

from birdsong_bitmap_v2 import (
    BitmapConfig,
    all_ones_pattern,
    all_zeros_pattern,
    bitmap_to_audio,
    bitmap_to_text,
    audio_to_bitmap,
    checkerboard_pattern,
    receive_bitmap,
    send_bitmap,
    text_to_bitmap,
)


class BitmapV2InMemoryTests(unittest.TestCase):
    def setUp(self):
        self.config = BitmapConfig()

    def test_all_ones_round_trip(self):
        bitmap = all_ones_pattern(self.config)
        audio = bitmap_to_audio(bitmap, self.config)
        result = audio_to_bitmap(audio, self.config)
        np.testing.assert_array_equal(bitmap, result)

    def test_all_zeros_round_trip(self):
        bitmap = all_zeros_pattern(self.config)
        audio = bitmap_to_audio(bitmap, self.config)
        result = audio_to_bitmap(audio, self.config)
        np.testing.assert_array_equal(bitmap, result)

    def test_checkerboard_round_trip(self):
        bitmap = checkerboard_pattern(self.config)
        audio = bitmap_to_audio(bitmap, self.config)
        result = audio_to_bitmap(audio, self.config)
        np.testing.assert_array_equal(bitmap, result)

    def test_text_hi_round_trip(self):
        bitmap = text_to_bitmap("hi", self.config)
        audio = bitmap_to_audio(bitmap, self.config)
        result = audio_to_bitmap(audio, self.config)
        decoded = bitmap_to_text(result, self.config)
        self.assertEqual("hi", decoded)

    def test_text_max_capacity_round_trip(self):
        max_bytes = self.config.max_payload_bytes
        text = "A" * max_bytes
        bitmap = text_to_bitmap(text, self.config)
        audio = bitmap_to_audio(bitmap, self.config)
        result = audio_to_bitmap(audio, self.config)
        decoded = bitmap_to_text(result, self.config)
        self.assertEqual(text, decoded)


class BitmapV2WAVTests(unittest.TestCase):
    def setUp(self):
        self.config = BitmapConfig()

    def test_pattern_wav_round_trip(self):
        bitmap = checkerboard_pattern(self.config)
        with tempfile.TemporaryDirectory() as tmpdir:
            wav_path = pathlib.Path(tmpdir) / "bitmap.wav"
            send_bitmap(bitmap, self.config, str(wav_path))
            result = receive_bitmap(str(wav_path), self.config)
        np.testing.assert_array_equal(bitmap, result)

    def test_text_wav_round_trip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wav_path = pathlib.Path(tmpdir) / "bitmap.wav"
            bitmap = text_to_bitmap("hi", self.config)
            send_bitmap(bitmap, self.config, str(wav_path))
            decoded = receive_bitmap(str(wav_path), self.config, decode_text=True)
        self.assertEqual("hi", decoded)


if __name__ == "__main__":
    unittest.main()
