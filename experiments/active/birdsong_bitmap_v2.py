#!/usr/bin/env python3
"""
birdsong_bitmap_v2.py - Spectrogram bitmap modem with sync and framing

Encodes data as a 2D grid of frequency/time cells visible in spectrograms.
Fixes v1's failures: adds sync preamble, calibration-based thresholds,
length/checksum framing, and removes fade-in/out windowing.

Transmission format:
  [2 sync columns] [1 length column] [N data columns] [1 checksum column]
   all-bands-on     8 bits = count    payload bits      8 bits

Grid: 8 freq bands, 50ms per slot

Usage:
    uv run python3 experiments/active/birdsong_bitmap_v2.py send --pattern checkerboard -o out.wav
    uv run python3 experiments/active/birdsong_bitmap_v2.py recv -i out.wav
    uv run python3 experiments/active/birdsong_bitmap_v2.py send --text "hi" -o out.wav
    uv run python3 experiments/active/birdsong_bitmap_v2.py recv -i out.wav --decode-text
"""

import argparse
import sys

import numpy as np
from dataclasses import dataclass, field
from scipy.io import wavfile

SAMPLE_RATE = 44100
SLOT_DURATION = 0.050  # 50ms per time slot
FREQ_BANDS = 8
DATA_COLUMNS = 16  # fixed payload columns
SYNC_COLUMNS = 2
OVERHEAD_COLUMNS = 4  # 2 sync + 1 length + 1 checksum

FREQUENCIES = [
    784.0,   # G5
    1046.5,  # C6
    1568.0,  # G6
    2093.0,  # C7
    2637.0,  # G7 (extrapolated)
    3520.0,  # C8 (extrapolated)
    4186.0,  # C8
    5274.0,  # C9
]

CALIBRATION_FACTOR = 0.3


@dataclass
class BitmapConfig:
    freq_bands: int = FREQ_BANDS
    data_columns: int = DATA_COLUMNS
    slot_duration: float = SLOT_DURATION
    sample_rate: int = SAMPLE_RATE
    frequencies: list = field(default_factory=lambda: list(FREQUENCIES))

    @property
    def samples_per_slot(self):
        return int(self.slot_duration * self.sample_rate)

    @property
    def total_columns(self):
        return SYNC_COLUMNS + 1 + self.data_columns + 1  # sync + length + data + checksum

    @property
    def total_duration(self):
        return self.total_columns * self.slot_duration

    @property
    def max_payload_bytes(self):
        return (self.data_columns * self.freq_bands) // 8


# --- Test patterns ---

def all_ones_pattern(config=None):
    cols = (config or BitmapConfig()).data_columns
    return np.ones((FREQ_BANDS, cols), dtype=int)


def all_zeros_pattern(config=None):
    cols = (config or BitmapConfig()).data_columns
    return np.zeros((FREQ_BANDS, cols), dtype=int)


def checkerboard_pattern(config=None):
    cols = (config or BitmapConfig()).data_columns
    bitmap = np.zeros((FREQ_BANDS, cols), dtype=int)
    for f in range(FREQ_BANDS):
        for t in range(cols):
            bitmap[f, t] = (f + t) % 2
    return bitmap


def create_test_patterns(config=None):
    return {
        "all_ones": all_ones_pattern(config),
        "all_zeros": all_zeros_pattern(config),
        "checkerboard": checkerboard_pattern(config),
    }


# --- Text encoding ---

def text_to_bitmap(text, config):
    text_bytes = text.encode("utf-8")
    max_bytes = config.max_payload_bytes
    if len(text_bytes) > max_bytes:
        raise ValueError(
            f"Text too long: {len(text_bytes)} bytes, max {max_bytes}"
        )

    bits = []
    for byte in text_bytes:
        for i in range(7, -1, -1):
            bits.append((byte >> i) & 1)

    total_bits = config.freq_bands * config.data_columns
    while len(bits) < total_bits:
        bits.append(0)

    bitmap = np.zeros((config.freq_bands, config.data_columns), dtype=int)
    idx = 0
    for f in range(config.freq_bands):
        for t in range(config.data_columns):
            bitmap[f, t] = bits[idx]
            idx += 1
    return bitmap


def bitmap_to_text(bitmap, config):
    bits = []
    for f in range(config.freq_bands):
        for t in range(bitmap.shape[1]):
            bits.append(int(bitmap[f, t]))

    byte_list = []
    for i in range(0, len(bits), 8):
        if i + 8 > len(bits):
            break
        val = 0
        for j in range(8):
            val = (val << 1) | bits[i + j]
        if val == 0:
            break
        byte_list.append(val)

    return bytes(byte_list).decode("utf-8")


# --- Core encode/decode ---

def bitmap_to_audio(bitmap, config):
    """Encode a data bitmap into audio with sync preamble and framing.

    Transmission: [2 sync cols (all on)] [1 length col] [N data cols] [1 checksum col]
    """
    n_data_cols = bitmap.shape[1]

    # Build the full transmission grid
    total_cols = SYNC_COLUMNS + 1 + n_data_cols + 1
    grid = np.zeros((config.freq_bands, total_cols), dtype=int)

    # Sync columns: all bands on
    grid[:, 0:SYNC_COLUMNS] = 1

    # Length column: encode n_data_cols as 8 bits (MSB at band 0)
    for i in range(8):
        grid[i, SYNC_COLUMNS] = (n_data_cols >> (7 - i)) & 1

    # Data columns
    grid[:, SYNC_COLUMNS + 1 : SYNC_COLUMNS + 1 + n_data_cols] = bitmap

    # Checksum column: sum of all data column bytes mod 256
    data_bits = []
    for f in range(config.freq_bands):
        for t in range(n_data_cols):
            data_bits.append(int(bitmap[f, t]))
    data_bytes = _bits_to_bytes(data_bits)
    checksum = sum(data_bytes) % 256
    for i in range(8):
        grid[i, SYNC_COLUMNS + 1 + n_data_cols] = (checksum >> (7 - i)) & 1

    # Synthesize audio
    return _grid_to_audio(grid, config)


def _grid_to_audio(grid, config):
    """Phase-continuous multi-tone synthesis for a full transmission grid."""
    n_cols = grid.shape[1]
    total_samples = n_cols * config.samples_per_slot
    audio = np.zeros(total_samples)
    phase_states = np.zeros(config.freq_bands)

    for t in range(n_cols):
        start = t * config.samples_per_slot
        end = start + config.samples_per_slot
        slot_len = end - start
        time_array = np.arange(slot_len) / config.sample_rate

        slot_signal = np.zeros(slot_len)
        active_count = sum(1 for f in range(config.freq_bands) if grid[f, t] == 1)

        for f in range(config.freq_bands):
            freq = config.frequencies[f]
            if grid[f, t] == 1:
                amplitude = 1.0 / np.sqrt(active_count) if active_count > 0 else 0
                slot_signal += amplitude * np.sin(
                    2 * np.pi * freq * time_array + phase_states[f]
                )
            # Always advance phase for continuity
            phase_states[f] = (
                phase_states[f] + 2 * np.pi * freq * slot_len / config.sample_rate
            ) % (2 * np.pi)

        audio[start:end] = slot_signal

    return audio


def audio_to_bitmap(audio, config):
    """Decode audio back to data bitmap using sync-based calibration."""
    energy_matrix, n_cols = _measure_energies(audio, config)

    if n_cols < OVERHEAD_COLUMNS:
        raise ValueError(f"Audio too short: {n_cols} columns, need at least {OVERHEAD_COLUMNS}")

    # Use sync columns for per-band calibration
    cal_energies = np.zeros(config.freq_bands)
    for f in range(config.freq_bands):
        cal_energies[f] = np.mean(energy_matrix[f, 0:SYNC_COLUMNS])

    thresholds = cal_energies * CALIBRATION_FACTOR

    # Decode length column
    length_col_idx = SYNC_COLUMNS
    n_data_cols = 0
    for i in range(8):
        energy = energy_matrix[i, length_col_idx]
        bit = 1 if energy > thresholds[i] else 0
        n_data_cols = (n_data_cols << 1) | bit

    # Bounds check
    available = n_cols - OVERHEAD_COLUMNS
    if n_data_cols > available:
        n_data_cols = available

    # Decode data columns
    data_start = SYNC_COLUMNS + 1
    bitmap = np.zeros((config.freq_bands, n_data_cols), dtype=int)
    for f in range(config.freq_bands):
        for t in range(n_data_cols):
            col = data_start + t
            if col < n_cols:
                bitmap[f, t] = 1 if energy_matrix[f, col] > thresholds[f] else 0

    # Decode and verify checksum
    checksum_col = data_start + n_data_cols
    if checksum_col < n_cols:
        received_checksum = 0
        for i in range(8):
            bit = 1 if energy_matrix[i, checksum_col] > thresholds[i] else 0
            received_checksum = (received_checksum << 1) | bit

        data_bits = []
        for f in range(config.freq_bands):
            for t in range(n_data_cols):
                data_bits.append(int(bitmap[f, t]))
        data_bytes = _bits_to_bytes(data_bits)
        expected_checksum = sum(data_bytes) % 256

        if received_checksum != expected_checksum:
            print(
                f"Warning: checksum mismatch (got {received_checksum}, "
                f"expected {expected_checksum})",
                file=sys.stderr,
            )

    return bitmap


def _measure_energies(audio, config):
    """Measure per-band energy for each time slot using FFT."""
    sps = config.samples_per_slot
    n_cols = len(audio) // sps
    energy_matrix = np.zeros((config.freq_bands, n_cols))

    for t in range(n_cols):
        start = t * sps
        end = start + sps
        segment = audio[start:end]

        window = np.hanning(len(segment))
        windowed = segment * window

        fft = np.fft.fft(windowed)
        freqs = np.fft.fftfreq(len(segment), 1 / config.sample_rate)

        for f in range(config.freq_bands):
            target = config.frequencies[f]
            freq_idx = np.argmin(np.abs(freqs - target))
            bin_range = 3
            lo = max(0, freq_idx - bin_range)
            hi = min(len(fft), freq_idx + bin_range + 1)
            energy_matrix[f, t] = np.sum(np.abs(fft[lo:hi]) ** 2)

    return energy_matrix, n_cols


def _bits_to_bytes(bits):
    result = []
    for i in range(0, len(bits), 8):
        chunk = bits[i : i + 8]
        if len(chunk) < 8:
            chunk = chunk + [0] * (8 - len(chunk))
        val = 0
        for b in chunk:
            val = (val << 1) | b
        result.append(val)
    return bytes(result)


# --- WAV I/O ---

def send_bitmap(bitmap, config, output_file):
    audio = bitmap_to_audio(bitmap, config)
    max_val = np.max(np.abs(audio))
    if max_val > 0:
        audio = audio * 0.8 / max_val
    wavfile.write(output_file, config.sample_rate, (audio * 32767).astype(np.int16))


def receive_bitmap(input_file, config, decode_text=False):
    sr, raw = wavfile.read(input_file)
    if sr != config.sample_rate:
        raise ValueError(f"Expected sample rate {config.sample_rate}, got {sr}")
    audio = raw.astype(np.float64)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    audio = audio / 32768.0

    bitmap = audio_to_bitmap(audio, config)
    if decode_text:
        return bitmap_to_text(bitmap, config)
    return bitmap


# --- Printing ---

def print_bitmap(bitmap, title="Bitmap"):
    print(f"\n{title} ({bitmap.shape[0]}x{bitmap.shape[1]}):")
    for f in range(bitmap.shape[0]):
        row = ""
        for t in range(bitmap.shape[1]):
            row += "##" if bitmap[f, t] == 1 else ".."
        print(f"  {f} {row}  ({FREQUENCIES[f]:.0f}Hz)")


# --- CLI ---

def main():
    parser = argparse.ArgumentParser(description="Bitmap v2 spectrogram modem")
    parser.add_argument("mode", choices=["send", "recv"])

    text_group = parser.add_mutually_exclusive_group()
    text_group.add_argument("--text", "-t")
    text_group.add_argument(
        "--pattern", default="checkerboard",
        help="Pattern: all_ones, all_zeros, checkerboard",
    )

    parser.add_argument("--output", "-o")
    parser.add_argument("--input", "-i")
    parser.add_argument("--decode-text", action="store_true")

    args = parser.parse_args()
    config = BitmapConfig()

    if args.mode == "send":
        if args.text:
            bitmap = text_to_bitmap(args.text, config)
            print(f"Encoding text: '{args.text}'")
        else:
            patterns = create_test_patterns(config)
            if args.pattern not in patterns:
                print(f"Unknown pattern '{args.pattern}'. Available: {list(patterns.keys())}", file=sys.stderr)
                sys.exit(1)
            bitmap = patterns[args.pattern]
            print(f"Encoding pattern: {args.pattern}")

        print_bitmap(bitmap, "Data bitmap")

        if args.output:
            send_bitmap(bitmap, config, args.output)
            print(f"Saved to {args.output}")
        else:
            audio = bitmap_to_audio(bitmap, config)
            print(f"Generated {len(audio)} samples ({len(audio)/config.sample_rate:.2f}s)")

    elif args.mode == "recv":
        if not args.input:
            print("Error: --input/-i required for recv mode", file=sys.stderr)
            sys.exit(1)

        result = receive_bitmap(args.input, config, decode_text=args.decode_text)
        if args.decode_text:
            print(f"Decoded text: '{result}'")
        else:
            print_bitmap(result, "Decoded bitmap")


if __name__ == "__main__":
    main()
