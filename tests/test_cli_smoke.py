import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
PYTHON = sys.executable
FIXTURE = ROOT / "docs/project_notes/restructure_plan.md"


class CliSmokeTests(unittest.TestCase):
    def run_script(self, relative_path, *args, input_bytes=None):
        return subprocess.run(
            [PYTHON, str(ROOT / relative_path), *args],
            input=input_bytes,
            capture_output=True,
            check=True,
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
