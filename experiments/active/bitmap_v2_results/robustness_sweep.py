#!/usr/bin/env python3
"""
bitmap_v2_robustness.py - Characterization sweep for bitmap v2 robustness

Injects calibrated noise and corruption into bitmap v2 audio to map the
robustness envelope: at what SNR / corruption level does each band fail,
and where does the overall system break down?

Corruption types:
  - White noise at varying SNR (dB)
  - Band-limited noise (low-pass filtered, simulates speaker rolloff)
  - Amplitude clipping (simulates saturation)
  - Sample offset jitter (tests sync preamble robustness)

Usage:
    uv run python3 experiments/active/bitmap_v2_results/robustness_sweep.py
    uv run python3 experiments/active/bitmap_v2_results/robustness_sweep.py --type white_noise
    uv run python3 experiments/active/bitmap_v2_results/robustness_sweep.py --type all --pattern all_ones
"""

import argparse
import sys
import pathlib

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from birdsong_bitmap_v2 import (
    BitmapConfig,
    FREQUENCIES,
    all_ones_pattern,
    all_zeros_pattern,
    bitmap_to_audio,
    audio_to_bitmap,
    checkerboard_pattern,
)


# --- Corruption functions ---


def add_white_noise(audio, snr_db):
    """Add white Gaussian noise at a given SNR (dB)."""
    signal_power = np.mean(audio ** 2)
    if signal_power == 0:
        return audio.copy()
    noise_power = signal_power / (10 ** (snr_db / 10))
    noise = np.random.normal(0, np.sqrt(noise_power), len(audio))
    return audio + noise


def add_bandlimited_noise(audio, snr_db, cutoff_hz, sample_rate):
    """Add low-pass filtered noise (simulates speaker/mic rolloff contamination)."""
    signal_power = np.mean(audio ** 2)
    if signal_power == 0:
        return audio.copy()
    noise_power = signal_power / (10 ** (snr_db / 10))
    noise = np.random.normal(0, np.sqrt(noise_power), len(audio))

    # Simple brick-wall low-pass in frequency domain
    fft_noise = np.fft.fft(noise)
    freqs = np.fft.fftfreq(len(noise), 1 / sample_rate)
    fft_noise[np.abs(freqs) > cutoff_hz] = 0
    filtered = np.real(np.fft.ifft(fft_noise))

    # Re-scale to target noise power
    filtered_power = np.mean(filtered ** 2)
    if filtered_power > 0:
        filtered *= np.sqrt(noise_power / filtered_power)

    return audio + filtered


def apply_clipping(audio, clip_fraction):
    """Clip audio at a fraction of peak amplitude (0.0-1.0).

    clip_fraction=0.5 means clip at 50% of peak, simulating heavy saturation.
    """
    peak = np.max(np.abs(audio))
    if peak == 0:
        return audio.copy()
    threshold = peak * clip_fraction
    return np.clip(audio, -threshold, threshold)


def apply_sample_offset(audio, offset_samples):
    """Shift audio by N samples (simulates timing misalignment)."""
    if offset_samples == 0:
        return audio.copy()
    if offset_samples > 0:
        return np.concatenate([np.zeros(offset_samples), audio])
    else:
        return audio[abs(offset_samples):]


def apply_highpass_rolloff(audio, rolloff_hz, sample_rate):
    """Attenuate frequencies below rolloff_hz (simulates small speaker response)."""
    fft_audio = np.fft.fft(audio)
    freqs = np.fft.fftfreq(len(audio), 1 / sample_rate)
    # Gentle rolloff: linear taper below cutoff
    gain = np.ones(len(freqs))
    below = np.abs(freqs) < rolloff_hz
    gain[below] = np.abs(freqs[below]) / rolloff_hz
    fft_audio *= gain
    return np.real(np.fft.ifft(fft_audio))


def apply_lowpass_rolloff(audio, rolloff_hz, sample_rate):
    """Attenuate frequencies above rolloff_hz (simulates mic bandwidth limit)."""
    fft_audio = np.fft.fft(audio)
    freqs = np.fft.fftfreq(len(audio), 1 / sample_rate)
    nyquist = sample_rate / 2
    gain = np.ones(len(freqs))
    above = np.abs(freqs) > rolloff_hz
    # Linear taper from rolloff to nyquist
    gain[above] = np.maximum(0, 1 - (np.abs(freqs[above]) - rolloff_hz) / (nyquist - rolloff_hz))
    fft_audio *= gain
    return np.real(np.fft.ifft(fft_audio))


# --- Measurement ---


def bit_error_rate(original, decoded):
    """Compute overall and per-band bit error rates."""
    if original.shape != decoded.shape:
        # Shape mismatch is total failure
        return 1.0, np.ones(original.shape[0])

    errors = original != decoded
    overall = np.mean(errors)
    per_band = np.mean(errors, axis=1)
    return overall, per_band


def run_trial(bitmap, config, corrupt_fn):
    """Run one encode → corrupt → decode trial, return BER."""
    audio = bitmap_to_audio(bitmap, config)
    corrupted = corrupt_fn(audio)
    try:
        decoded = audio_to_bitmap(corrupted, config)
    except Exception:
        return 1.0, np.ones(config.freq_bands)
    return bit_error_rate(bitmap, decoded)


# --- Sweep runners ---


def sweep_white_noise(bitmap, config, snr_range):
    print("\n=== White Noise Sweep ===")
    print(f"{'SNR (dB)':>10}  {'BER':>8}  Per-band BER")
    print("-" * 70)
    for snr in snr_range:
        bers = []
        band_bers = []
        for _ in range(5):  # average over trials
            overall, per_band = run_trial(
                bitmap, config, lambda a, s=snr: add_white_noise(a, s)
            )
            bers.append(overall)
            band_bers.append(per_band)
        avg_ber = np.mean(bers)
        avg_bands = np.mean(band_bers, axis=0)
        band_str = "  ".join(f"{b:.2f}" for b in avg_bands)
        marker = " <<<" if avg_ber > 0 and avg_ber < 1.0 else (" FAIL" if avg_ber >= 1.0 else "")
        print(f"{snr:>10.0f}  {avg_ber:>8.4f}  [{band_str}]{marker}")


def sweep_bandlimited_noise(bitmap, config, snr_range):
    print("\n=== Band-Limited Noise Sweep (cutoff=3000Hz) ===")
    print(f"{'SNR (dB)':>10}  {'BER':>8}  Per-band BER")
    print("-" * 70)
    for snr in snr_range:
        bers = []
        band_bers = []
        for _ in range(5):
            overall, per_band = run_trial(
                bitmap, config,
                lambda a, s=snr: add_bandlimited_noise(a, s, 3000, config.sample_rate),
            )
            bers.append(overall)
            band_bers.append(per_band)
        avg_ber = np.mean(bers)
        avg_bands = np.mean(band_bers, axis=0)
        band_str = "  ".join(f"{b:.2f}" for b in avg_bands)
        print(f"{snr:>10.0f}  {avg_ber:>8.4f}  [{band_str}]")


def sweep_clipping(bitmap, config, clip_levels):
    print("\n=== Clipping Sweep ===")
    print(f"{'Clip at':>10}  {'BER':>8}  Per-band BER")
    print("-" * 70)
    for clip in clip_levels:
        overall, per_band = run_trial(
            bitmap, config, lambda a, c=clip: apply_clipping(a, c)
        )
        band_str = "  ".join(f"{b:.2f}" for b in per_band)
        print(f"{clip:>9.0%}  {overall:>8.4f}  [{band_str}]")


def sweep_sample_offset(bitmap, config, offsets):
    sps = config.samples_per_slot
    print(f"\n=== Sample Offset Sweep (slot = {sps} samples) ===")
    print(f"{'Offset':>10}  {'% slot':>8}  {'BER':>8}  Per-band BER")
    print("-" * 70)
    for offset in offsets:
        overall, per_band = run_trial(
            bitmap, config, lambda a, o=offset: apply_sample_offset(a, o)
        )
        pct = offset / sps * 100
        band_str = "  ".join(f"{b:.2f}" for b in per_band)
        print(f"{offset:>10}  {pct:>7.1f}%  {overall:>8.4f}  [{band_str}]")


def sweep_highpass_rolloff(bitmap, config, rolloff_freqs):
    print("\n=== High-Pass Rolloff Sweep (small speaker sim) ===")
    print(f"{'Rolloff Hz':>10}  {'BER':>8}  Per-band BER")
    print("-" * 70)
    for freq in rolloff_freqs:
        overall, per_band = run_trial(
            bitmap, config,
            lambda a, f=freq: apply_highpass_rolloff(a, f, config.sample_rate),
        )
        band_str = "  ".join(f"{b:.2f}" for b in per_band)
        print(f"{freq:>10.0f}  {overall:>8.4f}  [{band_str}]")


def sweep_lowpass_rolloff(bitmap, config, rolloff_freqs):
    print("\n=== Low-Pass Rolloff Sweep (mic bandwidth sim) ===")
    print(f"{'Rolloff Hz':>10}  {'BER':>8}  Per-band BER")
    print("-" * 70)
    for freq in rolloff_freqs:
        overall, per_band = run_trial(
            bitmap, config,
            lambda a, f=freq: apply_lowpass_rolloff(a, f, config.sample_rate),
        )
        band_str = "  ".join(f"{b:.2f}" for b in per_band)
        print(f"{freq:>10.0f}  {overall:>8.4f}  [{band_str}]")


def sweep_combined(bitmap, config, snr_range):
    """White noise + high-pass at 500Hz + low-pass at 6000Hz (realistic channel)."""
    print("\n=== Combined Channel Sweep (HP=500Hz, LP=6000Hz + white noise) ===")
    print(f"{'SNR (dB)':>10}  {'BER':>8}  Per-band BER")
    print("-" * 70)

    def channel(audio, snr):
        a = apply_highpass_rolloff(audio, 500, config.sample_rate)
        a = apply_lowpass_rolloff(a, 6000, config.sample_rate)
        a = add_white_noise(a, snr)
        return a

    for snr in snr_range:
        bers = []
        band_bers = []
        for _ in range(5):
            overall, per_band = run_trial(
                bitmap, config, lambda a, s=snr: channel(a, s)
            )
            bers.append(overall)
            band_bers.append(per_band)
        avg_ber = np.mean(bers)
        avg_bands = np.mean(band_bers, axis=0)
        band_str = "  ".join(f"{b:.2f}" for b in avg_bands)
        print(f"{snr:>10.0f}  {avg_ber:>8.4f}  [{band_str}]")


# --- Main ---

SWEEPS = {
    "white_noise": lambda b, c: sweep_white_noise(b, c, [40, 30, 20, 15, 10, 5, 0, -5]),
    "bandlimited_noise": lambda b, c: sweep_bandlimited_noise(b, c, [30, 20, 15, 10, 5, 0]),
    "clipping": lambda b, c: sweep_clipping(b, c, [0.9, 0.7, 0.5, 0.3, 0.2, 0.1]),
    "sample_offset": lambda b, c: sweep_sample_offset(
        b, c, [0, 50, 100, 200, 500, 1000, 2000]
    ),
    "highpass": lambda b, c: sweep_highpass_rolloff(b, c, [200, 500, 800, 1000, 1500, 2000]),
    "lowpass": lambda b, c: sweep_lowpass_rolloff(b, c, [8000, 6000, 5000, 4000, 3000, 2000]),
    "combined": lambda b, c: sweep_combined(b, c, [40, 30, 20, 15, 10, 5, 0]),
}

PATTERNS = {
    "checkerboard": checkerboard_pattern,
    "all_ones": all_ones_pattern,
    "all_zeros": all_zeros_pattern,
}


def main():
    parser = argparse.ArgumentParser(description="Bitmap v2 robustness characterization")
    parser.add_argument(
        "--type", default="all",
        choices=list(SWEEPS.keys()) + ["all"],
        help="Corruption type to sweep (default: all)",
    )
    parser.add_argument(
        "--pattern", default="checkerboard",
        choices=list(PATTERNS.keys()),
        help="Test pattern (default: checkerboard)",
    )
    parser.add_argument("--seed", type=int, default=42, help="RNG seed")
    args = parser.parse_args()

    np.random.seed(args.seed)
    config = BitmapConfig()
    bitmap = PATTERNS[args.pattern](config)

    print(f"Bitmap v2 Robustness Characterization")
    print(f"Pattern: {args.pattern} ({config.freq_bands}x{config.data_columns})")
    print(f"Bands: {', '.join(f'{f:.0f}Hz' for f in FREQUENCIES)}")
    print(f"Band indices: {' '.join(f'  B{i}  ' for i in range(config.freq_bands))}")

    if args.type == "all":
        for name, sweep_fn in SWEEPS.items():
            sweep_fn(bitmap, config)
    else:
        SWEEPS[args.type](bitmap, config)

    print()


if __name__ == "__main__":
    main()
