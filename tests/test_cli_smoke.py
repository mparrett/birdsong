import pathlib
import subprocess
import sys
import tempfile
import unittest

import numpy as np
from scipy.io import wavfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
PYTHON = sys.executable
FIXTURE = ROOT / "docs/project_notes/restructure_plan.md"


class CliSmokeTests(unittest.TestCase):
    def run_script(self, relative_path, *args, input_bytes=None, check=True):
        return subprocess.run(
            [PYTHON, str(ROOT / relative_path), *args],
            input=input_bytes,
            capture_output=True,
            check=check,
            cwd=ROOT,
        )

    def test_birdsong_file_round_trip(self):
        payload = FIXTURE.read_bytes()
        with tempfile.TemporaryDirectory() as tmpdir:
            wav_path = pathlib.Path(tmpdir) / "birdsong.wav"
            self.run_script("birdsong.py", "send", "-o", str(wav_path), input_bytes=payload)
            received = self.run_script("birdsong.py", "recv", "-i", str(wav_path))
        self.assertEqual(payload, received.stdout)

    def test_birdsong_pipe_round_trip(self):
        payload = b"pipe loopback\n"
        sent = self.run_script("birdsong.py", "send", "-o", "-", input_bytes=payload)
        received = self.run_script("birdsong.py", "recv", "-i", "-", input_bytes=sent.stdout)
        self.assertEqual(payload, received.stdout)

    def test_birdsong_recv_handles_stereo_wav(self):
        payload = b"stereo wav\n"
        with tempfile.TemporaryDirectory() as tmpdir:
            mono_path = pathlib.Path(tmpdir) / "mono.wav"
            stereo_path = pathlib.Path(tmpdir) / "stereo.wav"
            self.run_script("birdsong.py", "send", "-o", str(mono_path), input_bytes=payload)

            sample_rate, samples = wavfile.read(mono_path)
            stereo_samples = np.column_stack([samples, samples])
            wavfile.write(stereo_path, sample_rate, stereo_samples)

            received = self.run_script("birdsong.py", "recv", "-i", str(stereo_path))

        self.assertEqual(payload, received.stdout)

    def test_birdsong_send_rejects_empty_input(self):
        result = self.run_script(
            "birdsong.py",
            "send",
            "-o",
            "-",
            input_bytes=b"",
            check=False,
        )

        self.assertNotEqual(0, result.returncode)
        self.assertIn(b"No input data received", result.stderr)

    def test_birdsong_rejects_too_small_bit_duration(self):
        result = self.run_script(
            "birdsong.py",
            "send",
            "--bit-duration",
            "1e-9",
            "-o",
            "-",
            input_bytes=b"hi",
            check=False,
        )

        self.assertNotEqual(0, result.returncode)
        self.assertIn(b"too small", result.stderr)

    def test_birdsong_recv_rejects_wrong_sample_rate(self):
        payload = b"wrong rate\n"
        with tempfile.TemporaryDirectory() as tmpdir:
            valid_path = pathlib.Path(tmpdir) / "valid.wav"
            wrong_rate_path = pathlib.Path(tmpdir) / "wrong-rate.wav"
            self.run_script("birdsong.py", "send", "-o", str(valid_path), input_bytes=payload)

            sample_rate, samples = wavfile.read(valid_path)
            wavfile.write(wrong_rate_path, sample_rate // 2, samples)

            result = self.run_script(
                "birdsong.py",
                "recv",
                "-i",
                str(wrong_rate_path),
                check=False,
            )

        self.assertNotEqual(0, result.returncode)
        self.assertIn(b"sample rate", result.stderr)

    def test_fsk_sweeps_file_round_trip(self):
        payload = b"abc"
        with tempfile.TemporaryDirectory() as tmpdir:
            wav_path = pathlib.Path(tmpdir) / "fsk-sweeps.wav"
            self.run_script(
                "experiments/active/birdsong_fsk_sweeps.py",
                "send",
                "-o",
                str(wav_path),
                input_bytes=payload,
            )
            received = self.run_script(
                "experiments/active/birdsong_fsk_sweeps.py",
                "recv",
                "-i",
                str(wav_path),
            )
        self.assertEqual(payload, received.stdout)

    def test_multiband_file_round_trip(self):
        payload = b"abc"
        with tempfile.TemporaryDirectory() as tmpdir:
            wav_path = pathlib.Path(tmpdir) / "multiband.wav"
            self.run_script(
                "experiments/active/birdsong_8band.py",
                "send",
                "-o",
                str(wav_path),
                input_bytes=payload,
            )
            received = self.run_script(
                "experiments/active/birdsong_8band.py",
                "recv",
                "-i",
                str(wav_path),
            )
        self.assertEqual(payload, received.stdout)


if __name__ == "__main__":
    unittest.main()
