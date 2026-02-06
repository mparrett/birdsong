#!/usr/bin/env python3
"""
birdsong_sweeps.py - Frequency Sweep "Tonal" Transmission

Inspired by tonal languages and natural communication patterns where
frequency direction encodes meaning. Like Mandarin tones or bird song
patterns, we use continuous frequency changes rather than discrete tones.

Encoding System:
- Symbol 00: Low Rising   (784Hz → 1046Hz)   - like Mandarin tone 2
- Symbol 01: Low Falling  (1046Hz → 784Hz)   - like Mandarin tone 4
- Symbol 10: High Rising  (1568Hz → 2093Hz)  - like Mandarin tone 1
- Symbol 11: High Falling (2093Hz → 1568Hz)  - like Mandarin tone 3

Data rate: 2 bits per symbol, ~25 symbols/sec = 50 bits/s
Advantages: Natural patterns, no frequency interference, robust detection

Usage:
    python birdsong_sweeps.py send --text "Hi"
    python birdsong_sweeps.py recv
"""

import numpy as np
import argparse
import sounddevice as sd
from scipy.io import wavfile
from dataclasses import dataclass


@dataclass
class SweepConfig:
    """Configuration for frequency sweep transmission."""

    # Frequency ranges (inspired by our previous G-C harmonies)
    low_freq_start: float = 784.0  # G5
    low_freq_end: float = 1046.5  # C6
    high_freq_start: float = 1568.0  # G6
    high_freq_end: float = 2093.0  # C7

    # Timing
    symbol_duration: float = 0.040  # 40ms per symbol (was 50ms per slot)
    sample_rate: int = 44100

    # Sweep parameters
    overlap_factor: float = 0.1  # 10% overlap between symbols for smoothness

    @property
    def samples_per_symbol(self):
        """Number of audio samples per symbol."""
        return int(self.symbol_duration * self.sample_rate)

    @property
    def overlap_samples(self):
        """Number of samples for overlap between symbols."""
        return int(self.overlap_factor * self.samples_per_symbol)


def text_to_symbols(text):
    """
    Convert text to 2-bit symbols (00, 01, 10, 11).

    Args:
        text: String to encode

    Returns:
        List of integers 0-3 representing 2-bit symbols
    """
    text_bytes = text.encode("utf-8")
    symbols = []

    for byte in text_bytes:
        # Convert each byte to 4 symbols (2 bits each)
        for i in range(4):
            symbol = (byte >> (6 - i * 2)) & 0b11  # Extract 2 bits
            symbols.append(symbol)

    return symbols


def symbols_to_text(symbols):
    """
    Convert 2-bit symbols back to text.

    Args:
        symbols: List of integers 0-3

    Returns:
        Decoded text string
    """
    # Group symbols into bytes (4 symbols = 8 bits = 1 byte)
    text_bytes = []

    for i in range(0, len(symbols), 4):
        if i + 3 < len(symbols):
            # Reconstruct byte from 4 symbols
            byte_value = 0
            for j in range(4):
                symbol = symbols[i + j]
                byte_value |= symbol << (6 - j * 2)

            # Stop at null terminator
            if byte_value == 0:
                break
            text_bytes.append(byte_value)

    # Convert to text
    try:
        # Remove trailing nulls and decode
        while text_bytes and text_bytes[-1] == 0:
            text_bytes.pop()
        return bytes(text_bytes).decode("utf-8")
    except UnicodeDecodeError:
        return f"<DECODE_ERROR: {text_bytes}>"


def generate_frequency_sweep(
    start_freq, end_freq, duration, sample_rate, phase_offset=0
):
    """
    Generate a smooth frequency sweep from start_freq to end_freq.

    Uses quadratic phase for linear frequency change.
    """
    t = np.linspace(0, duration, int(duration * sample_rate), endpoint=False)

    # Linear frequency sweep: f(t) = start_freq + (end_freq - start_freq) * t / duration
    # Phase: φ(t) = ∫f(t)dt = start_freq*t + (end_freq - start_freq) * t²/(2*duration)
    freq_rate = (end_freq - start_freq) / duration
    phase = 2 * np.pi * (start_freq * t + 0.5 * freq_rate * t**2) + phase_offset

    return np.sin(phase)


def generate_symbol_audio(symbol, config, phase_offset=0):
    """
    Generate audio for a single symbol (0-3).

    Symbol encoding:
    0 (00): Low Rising   (784Hz → 1046Hz)
    1 (01): Low Falling  (1046Hz → 784Hz)
    2 (10): High Rising  (1568Hz → 2093Hz)
    3 (11): High Falling (2093Hz → 1568Hz)
    """
    duration = config.symbol_duration

    if symbol == 0:  # 00: Low Rising
        return generate_frequency_sweep(
            config.low_freq_start,
            config.low_freq_end,
            duration,
            config.sample_rate,
            phase_offset,
        )
    elif symbol == 1:  # 01: Low Falling
        return generate_frequency_sweep(
            config.low_freq_end,
            config.low_freq_start,
            duration,
            config.sample_rate,
            phase_offset,
        )
    elif symbol == 2:  # 10: High Rising
        return generate_frequency_sweep(
            config.high_freq_start,
            config.high_freq_end,
            duration,
            config.sample_rate,
            phase_offset,
        )
    elif symbol == 3:  # 11: High Falling
        return generate_frequency_sweep(
            config.high_freq_end,
            config.high_freq_start,
            duration,
            config.sample_rate,
            phase_offset,
        )
    else:
        raise ValueError(f"Invalid symbol: {symbol} (must be 0-3)")


def symbols_to_audio(symbols, config):
    """
    Convert list of symbols to audio with smooth transitions.

    Uses overlapping windows to ensure phase continuity between symbols.
    """
    if not symbols:
        return np.array([])

    symbol_samples = config.samples_per_symbol
    overlap_samples = config.overlap_samples
    effective_samples = symbol_samples - overlap_samples

    # Total audio length
    total_samples = len(symbols) * effective_samples + overlap_samples
    audio = np.zeros(total_samples)

    # Generate each symbol with overlap
    current_phase = 0
    for i, symbol in enumerate(symbols):
        start_sample = i * effective_samples
        end_sample = start_sample + symbol_samples

        # Generate symbol audio
        symbol_audio = generate_symbol_audio(symbol, config, current_phase)

        # Add to output with overlap handling
        if i == 0:
            # First symbol: full length
            audio[start_sample:end_sample] = symbol_audio
        else:
            # Overlapping symbols: crossfade
            overlap_start = start_sample
            overlap_end = start_sample + overlap_samples
            main_start = overlap_end
            main_end = end_sample

            # Crossfade weights
            fade_out = np.linspace(1, 0, overlap_samples)
            fade_in = np.linspace(0, 1, overlap_samples)

            # Apply crossfade
            audio[overlap_start:overlap_end] *= fade_out
            audio[overlap_start:overlap_end] += symbol_audio[:overlap_samples] * fade_in

            # Add main part of symbol
            if main_start < total_samples:
                main_samples = min(main_end - main_start, total_samples - main_start)
                audio[main_start : main_start + main_samples] = symbol_audio[
                    overlap_samples : overlap_samples + main_samples
                ]

        # Update phase for continuity (approximate)
        # For simple continuity, we'll estimate end phase
        if symbol in [0, 1]:  # Low band
            end_freq = config.low_freq_end if symbol == 0 else config.low_freq_start
        else:  # High band
            end_freq = config.high_freq_end if symbol == 2 else config.high_freq_start

        current_phase += 2 * np.pi * end_freq * config.symbol_duration
        current_phase = current_phase % (2 * np.pi)

    return audio


def detect_sweep_direction(audio_segment, config):
    """
    Detect if a frequency sweep is rising or falling.

    Uses spectrogram analysis to find frequency trend.
    """
    from scipy import signal

    # Compute spectrogram
    f, t, Sxx = signal.spectrogram(
        audio_segment, config.sample_rate, nperseg=256, noverlap=128
    )

    # Find the dominant frequency at each time
    dominant_freqs = []
    for time_idx in range(Sxx.shape[1]):
        power_spectrum = Sxx[:, time_idx]
        peak_freq_idx = np.argmax(power_spectrum)
        dominant_freqs.append(f[peak_freq_idx])

    if len(dominant_freqs) < 2:
        return 0  # Can't determine direction

    # Linear regression to find frequency trend
    time_points = np.arange(len(dominant_freqs))
    slope = np.polyfit(time_points, dominant_freqs, 1)[0]

    return 1 if slope > 0 else -1  # Rising vs Falling


def detect_frequency_band(audio_segment, config):
    """
    Detect if sweep is in low band (784-1046Hz) or high band (1568-2093Hz).
    """
    from scipy import signal

    # Compute average spectrum
    f, Pxx = signal.welch(audio_segment, config.sample_rate, nperseg=1024)

    # Energy in low band
    low_mask = (f >= config.low_freq_start) & (f <= config.low_freq_end)
    low_energy = np.sum(Pxx[low_mask])

    # Energy in high band
    high_mask = (f >= config.high_freq_start) & (f <= config.high_freq_end)
    high_energy = np.sum(Pxx[high_mask])

    return 0 if low_energy > high_energy else 1  # Low band vs High band


def audio_to_symbols(audio, config):
    """
    Decode audio back to symbols using sweep detection.
    """
    symbols = []
    symbol_samples = config.samples_per_symbol
    overlap_samples = config.overlap_samples
    effective_samples = symbol_samples - overlap_samples

    # Estimate number of symbols
    num_symbols = max(1, (len(audio) - overlap_samples) // effective_samples)

    for i in range(num_symbols):
        start_sample = i * effective_samples
        end_sample = start_sample + symbol_samples

        if end_sample <= len(audio):
            segment = audio[start_sample:end_sample]

            # Detect frequency band (0=low, 1=high)
            band = detect_frequency_band(segment, config)

            # Detect sweep direction (1=rising, -1=falling)
            direction = detect_sweep_direction(segment, config)

            # Map to symbol
            if band == 0:  # Low band
                symbol = 0 if direction > 0 else 1  # Rising=0, Falling=1
            else:  # High band
                symbol = 2 if direction > 0 else 3  # Rising=2, Falling=3

            symbols.append(symbol)

    return symbols


def print_symbols(symbols, title="Symbols"):
    """Print symbols in a human-readable format."""
    print(f"\n{title} ({len(symbols)} symbols = {len(symbols) * 2} bits):")

    symbol_names = ["LowRise", "LowFall", "HighRise", "HighFall"]
    for i, symbol in enumerate(symbols):
        if i % 8 == 0:
            print(f"\n  {i:2d}: ", end="")
        print(f"{symbol_names[symbol]:8s}", end=" ")
    print()


def send_sweeps(text=None, config=None, output_file=None, play_audio=True):
    """Generate and transmit frequency sweep audio."""
    if not text:
        text = "Hi"

    symbols = text_to_symbols(text)
    print(
        f"Sending Text: '{text}' ({len(text.encode('utf-8'))} bytes → {len(symbols)} symbols)"
    )
    print_symbols(symbols, "Sweep Symbols")

    # Convert to audio
    audio = symbols_to_audio(symbols, config)

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
        print("Playing sweep audio...")
        sd.play(audio, config.sample_rate)
        sd.wait()
        print("Transmission complete.")


def receive_sweeps(config, input_file=None, record_duration=None):
    """Receive and decode frequency sweep audio."""
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
            # Estimate duration needed
            estimated_symbols = 20  # Assume ~20 symbols for unknown text
            record_duration = estimated_symbols * config.symbol_duration + 0.5

        print(f"Recording for {record_duration:.1f} seconds...")
        audio = sd.rec(
            int(record_duration * config.sample_rate),
            samplerate=config.sample_rate,
            channels=1,
        )
        sd.wait()
        audio = audio.flatten()
        print("Recording complete.")

    # Decode symbols
    print("Decoding frequency sweeps...")
    decoded_symbols = audio_to_symbols(audio, config)
    print_symbols(decoded_symbols, "Received Symbols")

    # Convert to text
    decoded_text = symbols_to_text(decoded_symbols)
    print(f"\n🎵 Decoded Text: '{decoded_text}'")

    return decoded_text


def main():
    parser = argparse.ArgumentParser(description="Frequency Sweep 'Tonal' Transmission")
    parser.add_argument(
        "mode", choices=["send", "recv"], help="Send or receive sweep data"
    )

    # Send mode arguments
    parser.add_argument("--text", "-t", default="Hi", help="Text to send (default: Hi)")
    parser.add_argument("--output", "-o", help="Output WAV file for send mode")
    parser.add_argument(
        "--no-play", action="store_true", help="Do not play audio (send mode)"
    )

    # Receive mode arguments
    parser.add_argument("--input", "-i", help="Input WAV file for receive mode")
    parser.add_argument(
        "--duration", "-d", type=float, help="Recording duration for receive mode"
    )

    # Configuration
    parser.add_argument(
        "--symbol-duration",
        type=float,
        default=0.040,
        help="Duration per symbol in seconds (default: 0.040)",
    )

    args = parser.parse_args()

    # Create configuration
    config = SweepConfig(symbol_duration=args.symbol_duration)

    print("Sweep Configuration:")
    print(f"  Symbol duration: {config.symbol_duration:.3f}s")
    print(f"  Data rate: ~{2 / config.symbol_duration:.1f} bits/s")
    print(f"  Low band: {config.low_freq_start:.0f}-{config.low_freq_end:.0f}Hz")
    print(f"  High band: {config.high_freq_start:.0f}-{config.high_freq_end:.0f}Hz")

    if args.mode == "send":
        send_sweeps(args.text, config, args.output, not args.no_play)
    else:
        receive_sweeps(config, args.input, args.duration)


if __name__ == "__main__":
    main()
