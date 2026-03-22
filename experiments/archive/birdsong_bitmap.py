#!/usr/bin/env python3
"""
birdsong_bitmap.py - Spectrogram Bitmap Transmission

Revolutionary approach: Treat the spectrogram as a 2D canvas where data is "drawn"
as patterns of frequency-time blocks, then transmitted as audio that recreates
those visual patterns in the receiver's spectrogram.

Grid System:
- 8 frequency bands (G-C perfect fourth harmonies)
- 16 time slots (50ms each = 0.8s total transmission)
- 128 bits total capacity per transmission

Encoding: Each grid cell [freq][time] = 1 bit
- Bit 1: Generate sine wave at that frequency during that time slot
- Bit 0: Silence (no energy in that freq/time cell)

Usage:
    python birdsong_bitmap.py send --pattern checkerboard
    python birdsong_bitmap.py recv
"""

import numpy as np
import argparse
import sounddevice as sd
from scipy.io import wavfile
from dataclasses import dataclass


@dataclass
class BitmapConfig:
    """Configuration for spectrogram bitmap transmission."""

    # Grid dimensions
    freq_bands: int = 8  # Number of frequency bands (Y-axis)
    time_slots: int = 16  # Number of time slots (X-axis)

    # Timing
    slot_duration: float = 0.050  # 50ms per time slot
    sample_rate: int = 44100

    # Frequencies (G-C perfect fourth harmonies)
    frequencies: list = None

    def __post_init__(self):
        if self.frequencies is None:
            self.frequencies = [
                784.0,  # G5 - Octave
                1046.5,  # C6 - Perfect fourth above G5
                1568.0,  # G6 - Octave
                2093.0,  # C7 - Perfect fourth above G6
                2637.0,  # G7 - Octave (extrapolated)
                3520.0,  # C8 - Perfect fourth above G7 (extrapolated)
                4186.0,  # C8 (actual piano note)
                5274.0,  # C9 - One octave above C8
            ]

    @property
    def total_duration(self):
        """Total transmission duration in seconds."""
        return self.time_slots * self.slot_duration

    @property
    def samples_per_slot(self):
        """Number of audio samples per time slot."""
        return int(self.slot_duration * self.sample_rate)

    @property
    def total_bits(self):
        """Total bit capacity of the grid."""
        return self.freq_bands * self.time_slots


def text_to_bitmap(text, config):
    """
    Convert text string to bitmap representation.

    Args:
        text: String to encode
        config: BitmapConfig instance

    Returns:
        2D numpy array [freq_bands, time_slots] of 0s and 1s

    Raises:
        ValueError: If text is too long for current grid size
    """
    # Convert text to UTF-8 bytes, then to bit array
    text_bytes = text.encode("utf-8")
    bit_list = []

    for byte in text_bytes:
        # Convert each byte to 8 bits (MSB first)
        for i in range(8):
            bit_list.append((byte >> (7 - i)) & 1)

    # Check if text fits in our grid
    total_bits = config.total_bits
    if len(bit_list) > total_bits:
        raise ValueError(
            f"Text too long: {len(bit_list)} bits needed, {total_bits} available"
        )

    # Pad with zeros if needed
    while len(bit_list) < total_bits:
        bit_list.append(0)

    # Convert bit list to 2D bitmap
    bitmap = np.zeros((config.freq_bands, config.time_slots), dtype=int)
    bit_idx = 0

    # Fill bitmap row by row (frequency by frequency)
    for f in range(config.freq_bands):
        for t in range(config.time_slots):
            if bit_idx < len(bit_list):
                bitmap[f, t] = bit_list[bit_idx]
                bit_idx += 1

    return bitmap


def bitmap_to_text(bitmap, config):
    """
    Convert bitmap back to text string.

    Args:
        bitmap: 2D numpy array [freq_bands, time_slots] of 0s and 1s
        config: BitmapConfig instance

    Returns:
        Decoded text string
    """
    # Extract bits from bitmap (row by row)
    bit_list = []
    for f in range(config.freq_bands):
        for t in range(config.time_slots):
            bit_list.append(int(bitmap[f, t]))

    # Convert bits to bytes
    text_bytes = []
    for i in range(0, len(bit_list), 8):
        if i + 7 < len(bit_list):
            # Reconstruct byte from 8 bits (MSB first)
            byte_value = 0
            for j in range(8):
                byte_value |= bit_list[i + j] << (7 - j)

            # Stop at null terminator or non-printable characters at end
            if byte_value == 0:
                break
            text_bytes.append(byte_value)

    # Convert bytes to UTF-8 string, handle decode errors gracefully
    try:
        # Remove trailing null bytes and decode
        while text_bytes and text_bytes[-1] == 0:
            text_bytes.pop()
        return bytes(text_bytes).decode("utf-8")
    except UnicodeDecodeError:
        # Return raw bytes representation if UTF-8 decode fails
        return f"<DECODE_ERROR: {text_bytes}>"


def create_test_patterns():
    """Create various test patterns for bitmap transmission."""
    patterns = {}

    # Checkerboard pattern
    checkerboard = np.zeros((8, 16), dtype=int)
    for f in range(8):
        for t in range(16):
            checkerboard[f, t] = (f + t) % 2
    patterns["checkerboard"] = checkerboard

    # Horizontal stripes
    horizontal = np.zeros((8, 16), dtype=int)
    for f in range(8):
        horizontal[f, :] = f % 2
    patterns["horizontal"] = horizontal

    # Vertical stripes
    vertical = np.zeros((8, 16), dtype=int)
    for t in range(16):
        vertical[:, t] = t % 2
    patterns["vertical"] = vertical

    # Diagonal line
    diagonal = np.zeros((8, 16), dtype=int)
    for i in range(min(8, 16)):
        diagonal[i, i] = 1
        if i + 8 < 16:  # Second diagonal if space allows
            diagonal[i, i + 8] = 1
    patterns["diagonal"] = diagonal

    # Border frame
    border = np.zeros((8, 16), dtype=int)
    border[0, :] = 1  # Top
    border[-1, :] = 1  # Bottom
    border[:, 0] = 1  # Left
    border[:, -1] = 1  # Right
    patterns["border"] = border

    # All ones (stress test)
    patterns["all_ones"] = np.ones((8, 16), dtype=int)

    # All zeros (silence test)
    patterns["all_zeros"] = np.zeros((8, 16), dtype=int)

    return patterns


def bitmap_to_audio(bitmap, config):
    """
    Convert a 2D bitmap to audio signal with phase continuity.

    Args:
        bitmap: 2D numpy array [freq_bands, time_slots] of 0s and 1s
        config: BitmapConfig instance

    Returns:
        numpy array of audio samples
    """
    total_samples = int(config.total_duration * config.sample_rate)
    audio = np.zeros(total_samples)

    # Track phase for each frequency to maintain continuity
    phase_states = np.zeros(config.freq_bands)  # Accumulated phase for each frequency

    # Generate audio for each time slot
    for t in range(config.time_slots):
        start_sample = t * config.samples_per_slot
        end_sample = start_sample + config.samples_per_slot

        # Create time array for this slot
        slot_samples = end_sample - start_sample
        time_array = np.linspace(0, config.slot_duration, slot_samples, endpoint=False)

        # Sum all active frequencies for this time slot
        slot_signal = np.zeros(slot_samples)
        active_count = 0
        active_power = 0

        # First pass: calculate total power needed for equal power distribution
        for f in range(config.freq_bands):
            if bitmap[f, t] == 1:
                active_count += 1
                active_power += 1  # Each frequency gets equal power

        for f in range(config.freq_bands):
            frequency = config.frequencies[f]

            if bitmap[f, t] == 1:
                # Generate sine wave continuing from previous phase
                phase_offset = phase_states[f]
                sine_wave = np.sin(2 * np.pi * frequency * time_array + phase_offset)

                # Equal power distribution: each active frequency gets 1/sqrt(active_count) amplitude
                # This ensures total power is constant regardless of number of active frequencies
                amplitude = 1.0 / np.sqrt(active_count) if active_count > 0 else 0
                slot_signal += amplitude * sine_wave

            # Update phase state for this frequency (whether active or not)
            # This maintains phase continuity even across gaps
            phase_advance = 2 * np.pi * frequency * config.slot_duration
            phase_states[f] = (phase_states[f] + phase_advance) % (2 * np.pi)

        # Apply gentle fade in/out to prevent clicks (smaller fade since we have phase continuity)
        fade_samples = min(
            50, slot_samples // 20
        )  # Reduced fade since phase is continuous
        if fade_samples > 0:
            fade_in = np.linspace(0, 1, fade_samples)
            fade_out = np.linspace(1, 0, fade_samples)
            slot_signal[:fade_samples] *= fade_in
            slot_signal[-fade_samples:] *= fade_out

        audio[start_sample:end_sample] = slot_signal

    return audio


def audio_to_bitmap(audio, config):
    """
    Convert audio signal back to 2D bitmap using adaptive thresholding.

    Args:
        audio: numpy array of audio samples
        config: BitmapConfig instance

    Returns:
        2D numpy array [freq_bands, time_slots] of 0s and 1s
    """
    bitmap = np.zeros((config.freq_bands, config.time_slots), dtype=int)

    # Collect energy measurements for adaptive thresholding
    all_energies = []
    energy_matrix = np.zeros((config.freq_bands, config.time_slots))

    # First pass: collect all energy measurements
    for t in range(config.time_slots):
        start_sample = t * config.samples_per_slot
        end_sample = start_sample + config.samples_per_slot

        # Extract audio segment for this time slot
        if end_sample <= len(audio):
            segment = audio[start_sample:end_sample]

            # Apply windowing to reduce spectral leakage
            window = np.hanning(len(segment))
            windowed_segment = segment * window

            # Compute FFT
            fft = np.fft.fft(windowed_segment)
            freqs = np.fft.fftfreq(len(segment), 1 / config.sample_rate)

            # Measure energy at each target frequency
            for f in range(config.freq_bands):
                target_freq = config.frequencies[f]

                # Find the closest frequency bin
                freq_idx = np.argmin(np.abs(freqs - target_freq))

                # Measure energy around target frequency (sum nearby bins)
                bin_range = 3  # Check +/- 3 bins around target
                start_idx = max(0, freq_idx - bin_range)
                end_idx = min(len(fft), freq_idx + bin_range + 1)

                energy = np.sum(np.abs(fft[start_idx:end_idx]) ** 2)
                energy_matrix[f, t] = energy
                all_energies.append(energy)

    # Calculate adaptive threshold based on signal statistics
    if len(all_energies) > 0:
        all_energies = np.array(all_energies)

        # Global statistics for overall signal level
        np.mean(all_energies)
        global_std = np.std(all_energies)

        # Estimate noise floor (use lower percentile as background noise)
        noise_floor = np.percentile(all_energies, 25)  # Bottom 25% assumed to be noise

        # Calculate frequency-specific thresholds
        freq_thresholds = np.zeros(config.freq_bands)
        for f in range(config.freq_bands):
            freq_energies = energy_matrix[f, :]
            np.mean(freq_energies)
            freq_std = np.std(freq_energies)

            # Adaptive threshold: noise floor + margin based on frequency-specific statistics
            # Use the larger of: global threshold or frequency-specific threshold
            global_threshold = noise_floor + 2.0 * global_std
            freq_threshold = noise_floor + 1.5 * freq_std

            freq_thresholds[f] = max(global_threshold, freq_threshold)

            # Higher frequencies have less harmonic interference
            # Apply minimal conservative boost for text reliability
            freq_thresholds[f] *= 1.1  # Require 10% more energy for all frequencies
    else:
        # Fallback to fixed thresholds if no energy data
        freq_thresholds = np.full(config.freq_bands, 1000)

    # Second pass: apply adaptive thresholds
    for t in range(config.time_slots):
        for f in range(config.freq_bands):
            energy = energy_matrix[f, t]
            threshold = freq_thresholds[f]
            bitmap[f, t] = 1 if energy > threshold else 0

    return bitmap


def print_bitmap(bitmap, title="Bitmap", config=None):
    """Print a bitmap in a human-readable format."""
    print(f"\n{title} ({bitmap.shape[0]}×{bitmap.shape[1]}):")
    print("Freq\\Time", end="")
    for t in range(bitmap.shape[1]):
        print(f"{t:2d}", end="")
    print()

    for f in range(bitmap.shape[0]):
        print(f"  {f}     ", end="")
        for t in range(bitmap.shape[1]):
            symbol = "██" if bitmap[f, t] == 1 else "  "
            print(symbol, end="")
        if config and hasattr(config, "frequencies") and f < len(config.frequencies):
            print(f"  ({config.frequencies[f]:.0f}Hz)")
        else:
            print(f"  (freq{f})")


def send_bitmap(
    pattern_name=None, text=None, config=None, output_file=None, play_audio=True
):
    """Generate and transmit a bitmap pattern or text."""
    if text is not None:
        # Text mode
        try:
            bitmap = text_to_bitmap(text, config)
            print(f"Sending Text: '{text}' ({len(text.encode('utf-8')) * 8} bits)")
            print_bitmap(bitmap, "Text Bitmap", config)
        except ValueError as e:
            print(f"Error: {e}")
            return
    else:
        # Pattern mode
        patterns = create_test_patterns()

        if pattern_name not in patterns:
            print(f"Error: Unknown pattern '{pattern_name}'")
            print(f"Available patterns: {list(patterns.keys())}")
            return

        bitmap = patterns[pattern_name]
        print_bitmap(bitmap, f"Sending Pattern: {pattern_name}", config)

    # Convert bitmap to audio
    audio = bitmap_to_audio(bitmap, config)

    # Save to file if requested
    if output_file:
        # Normalize audio to prevent clipping
        max_val = np.max(np.abs(audio))
        if max_val > 0:
            audio_normalized = audio * 0.8 / max_val
        else:
            audio_normalized = audio

        wavfile.write(
            output_file, config.sample_rate, (audio_normalized * 32767).astype(np.int16)
        )
        print(f"Saved audio to: {output_file}")

    # Play audio if requested
    if play_audio:
        print("Playing bitmap audio...")
        sd.play(audio, config.sample_rate)
        sd.wait()  # Wait for completion
        print("Transmission complete.")


def receive_bitmap(config, input_file=None, record_duration=None, decode_as_text=False):
    """Receive and decode bitmap pattern or text."""
    if input_file:
        # Load from file
        sample_rate, audio = wavfile.read(input_file)
        if sample_rate != config.sample_rate:
            print(
                f"Warning: File sample rate {sample_rate} != config {config.sample_rate}"
            )
        audio = audio.astype(float) / 32767.0  # Normalize to [-1, 1]
        print(f"Loaded audio from: {input_file}")
    else:
        # Record from microphone
        if record_duration is None:
            record_duration = config.total_duration + 0.5  # Add buffer

        print(f"Recording for {record_duration:.1f} seconds...")
        audio = sd.rec(
            int(record_duration * config.sample_rate),
            samplerate=config.sample_rate,
            channels=1,
        )
        sd.wait()
        audio = audio.flatten()
        print("Recording complete.")

    # Decode bitmap
    print("Decoding bitmap...")
    decoded_bitmap = audio_to_bitmap(audio, config)
    print_bitmap(decoded_bitmap, "Received Bitmap", config)

    if decode_as_text:
        # Text mode - decode as text
        decoded_text = bitmap_to_text(decoded_bitmap, config)
        print(f"\n🎯 Decoded Text: '{decoded_text}'")
        return decoded_text
    else:
        # Pattern mode - try to match against known patterns
        patterns = create_test_patterns()
        best_match = None
        best_score = -1

        for name, pattern in patterns.items():
            # Calculate match score (percentage of correct bits)
            matches = np.sum(decoded_bitmap == pattern)
            total = pattern.size
            score = matches / total

            if score > best_score:
                best_score = score
                best_match = name

        print(f"\nBest pattern match: {best_match} ({best_score:.1%} accuracy)")
        if best_score < 1.0:
            print_bitmap(
                patterns[best_match], f"Expected Pattern: {best_match}", config
            )

        return best_match, best_score


def main():
    parser = argparse.ArgumentParser(description="Spectrogram Bitmap Transmission")
    parser.add_argument(
        "mode", choices=["send", "recv"], help="Send or receive bitmap data"
    )

    # Text vs Pattern mode
    text_group = parser.add_mutually_exclusive_group()
    text_group.add_argument(
        "--text", "-t", help="Text to send (alternative to --pattern)"
    )
    text_group.add_argument(
        "--pattern",
        default="checkerboard",
        help="Pattern to send (default: checkerboard)",
    )

    # Send mode arguments
    parser.add_argument("--output", "-o", help="Output WAV file for send mode")
    parser.add_argument(
        "--no-play", action="store_true", help="Do not play audio (send mode)"
    )

    # Receive mode arguments
    parser.add_argument("--input", "-i", help="Input WAV file for receive mode")
    parser.add_argument(
        "--duration", "-d", type=float, help="Recording duration for receive mode"
    )
    parser.add_argument(
        "--decode-text",
        action="store_true",
        help="Decode received data as text (receive mode)",
    )

    # Configuration
    parser.add_argument(
        "--time-slots", type=int, default=16, help="Number of time slots (default: 16)"
    )
    parser.add_argument(
        "--slot-duration",
        type=float,
        default=0.050,
        help="Duration per time slot in seconds (default: 0.050)",
    )

    args = parser.parse_args()

    # Create configuration
    config = BitmapConfig(time_slots=args.time_slots, slot_duration=args.slot_duration)

    print("Bitmap Configuration:")
    print(f"  Grid: {config.freq_bands}×{config.time_slots} = {config.total_bits} bits")
    print(f"  Duration: {config.total_duration:.2f}s")
    print(f"  Data rate: {config.total_bits / config.total_duration:.1f} bits/s")
    print(f"  Max text length: ~{config.total_bits // 8} characters")

    if args.mode == "send":
        if args.text:
            send_bitmap(
                text=args.text,
                config=config,
                output_file=args.output,
                play_audio=not args.no_play,
            )
        else:
            send_bitmap(
                pattern_name=args.pattern,
                config=config,
                output_file=args.output,
                play_audio=not args.no_play,
            )
    else:
        receive_bitmap(config, args.input, args.duration, args.decode_text)


if __name__ == "__main__":
    main()
