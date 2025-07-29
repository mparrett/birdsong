#!/usr/bin/env python3
"""
birdsong_sweeps_8sym.py - 8-Symbol Frequency Sweep Transmission

Extended tonal encoding system with 8 symbols (3 bits each) for 3x higher data rates:

3-Band System:
- Low band: 784-1046Hz
- Mid band: 1046-1568Hz  
- High band: 1568-2093Hz

8 Symbol Encoding (3 bits each):
- 000: Low Rising    (784Hz → 1046Hz)
- 001: Low Falling   (1046Hz → 784Hz)
- 010: Mid Rising    (1046Hz → 1568Hz)
- 011: Mid Falling   (1568Hz → 1046Hz)
- 100: High Rising   (1568Hz → 2093Hz)
- 101: High Falling  (2093Hz → 1568Hz)
- 110: Cross Rising  (784Hz → 1568Hz)   # Skip middle band
- 111: Cross Falling (1568Hz → 784Hz)   # Skip middle band

Data rate: 3 bits per symbol, 50 symbols/sec = 150 bits/s
"""

import numpy as np
import sys
import argparse
import sounddevice as sd
from scipy.io import wavfile
from dataclasses import dataclass


@dataclass
class SweepConfig8:
    """Configuration for 8-symbol frequency sweep transmission."""
    # Three frequency bands
    low_freq: float = 784.0      # G5
    mid_freq: float = 1046.5     # C6  
    high_freq: float = 1568.0    # G6
    top_freq: float = 2093.0     # C7
    
    # Timing
    symbol_duration: float = 0.020   # 20ms per symbol for 150 bits/s
    sample_rate: int = 44100
    
    @property
    def samples_per_symbol(self):
        return int(self.symbol_duration * self.sample_rate)


def text_to_symbols_3bit(text):
    """Convert text to 3-bit symbols (0-7)."""
    text_bytes = text.encode('utf-8')
    symbols = []
    
    # Convert each byte to bits, then group into 3-bit symbols
    all_bits = []
    for byte in text_bytes:
        for i in range(8):
            all_bits.append((byte >> (7 - i)) & 1)
    
    # Pad to multiple of 3
    while len(all_bits) % 3 != 0:
        all_bits.append(0)
    
    # Group into 3-bit symbols
    for i in range(0, len(all_bits), 3):
        symbol = (all_bits[i] << 2) | (all_bits[i+1] << 1) | all_bits[i+2]
        symbols.append(symbol)
    
    return symbols


def symbols_to_text_3bit(symbols):
    """Convert 3-bit symbols back to text."""
    # Convert symbols back to bits
    all_bits = []
    for symbol in symbols:
        for i in range(3):
            bit = (symbol >> (2 - i)) & 1
            all_bits.append(bit)
    
    # Group into bytes
    text_bytes = []
    for i in range(0, len(all_bits), 8):
        if i + 7 < len(all_bits):
            byte_value = 0
            for j in range(8):
                byte_value |= (all_bits[i + j] << (7 - j))
            
            if byte_value == 0:
                break
            text_bytes.append(byte_value)
    
    try:
        while text_bytes and text_bytes[-1] == 0:
            text_bytes.pop()
        return bytes(text_bytes).decode('utf-8')
    except UnicodeDecodeError:
        return f"<DECODE_ERROR: {text_bytes}>"


def generate_frequency_sweep(start_freq, end_freq, duration, sample_rate):
    """Generate smooth frequency sweep."""
    t = np.linspace(0, duration, int(duration * sample_rate), endpoint=False)
    freq_rate = (end_freq - start_freq) / duration
    phase = 2 * np.pi * (start_freq * t + 0.5 * freq_rate * t**2)
    return np.sin(phase)


def generate_symbol_audio_8(symbol, config):
    """
    Generate audio for 8-symbol system:
    0(000): Low↗    1(001): Low↘    2(010): Mid↗    3(011): Mid↘
    4(100): High↗   5(101): High↘   6(110): Cross↗  7(111): Cross↘
    """
    duration = config.symbol_duration
    
    if symbol == 0:    # 000: Low Rising
        return generate_frequency_sweep(config.low_freq, config.mid_freq, duration, config.sample_rate)
    elif symbol == 1:  # 001: Low Falling  
        return generate_frequency_sweep(config.mid_freq, config.low_freq, duration, config.sample_rate)
    elif symbol == 2:  # 010: Mid Rising
        return generate_frequency_sweep(config.mid_freq, config.high_freq, duration, config.sample_rate)
    elif symbol == 3:  # 011: Mid Falling
        return generate_frequency_sweep(config.high_freq, config.mid_freq, duration, config.sample_rate)
    elif symbol == 4:  # 100: High Rising
        return generate_frequency_sweep(config.high_freq, config.top_freq, duration, config.sample_rate)
    elif symbol == 5:  # 101: High Falling
        return generate_frequency_sweep(config.top_freq, config.high_freq, duration, config.sample_rate)
    elif symbol == 6:  # 110: Cross Rising (wide sweep)
        return generate_frequency_sweep(config.low_freq, config.high_freq, duration, config.sample_rate)
    elif symbol == 7:  # 111: Cross Falling (wide sweep)
        return generate_frequency_sweep(config.high_freq, config.low_freq, duration, config.sample_rate)
    else:
        raise ValueError(f"Invalid symbol: {symbol} (must be 0-7)")


def symbols_to_audio_8(symbols, config):
    """Convert symbols to audio with minimal gaps."""
    if not symbols:
        return np.array([])
    
    audio_segments = []
    for symbol in symbols:
        segment = generate_symbol_audio_8(symbol, config)
        audio_segments.append(segment)
    
    # Concatenate with small gaps to avoid interference
    gap_samples = int(0.002 * config.sample_rate)  # 2ms gap
    total_samples = len(symbols) * (config.samples_per_symbol + gap_samples)
    
    audio = np.zeros(total_samples)
    for i, segment in enumerate(audio_segments):
        start = i * (config.samples_per_symbol + gap_samples)
        end = start + len(segment)
        audio[start:end] = segment
    
    return audio


def detect_symbol_8(audio_segment, config):
    """Detect which of 8 symbols based on frequency analysis."""
    from scipy import signal
    
    # Compute spectrogram to find frequency trajectory
    f, t, Sxx = signal.spectrogram(audio_segment, config.sample_rate, 
                                  nperseg=min(256, len(audio_segment)//4), 
                                  noverlap=128)
    
    if Sxx.shape[1] < 2:
        return 0  # Can't analyze
    
    # Find dominant frequency at start and end
    start_spectrum = Sxx[:, 0]
    end_spectrum = Sxx[:, -1]
    
    start_freq = f[np.argmax(start_spectrum)]
    end_freq = f[np.argmax(end_spectrum)]
    
    # Classify based on start/end frequency patterns
    freqs = [config.low_freq, config.mid_freq, config.high_freq, config.top_freq]
    
    # Find closest frequency bands
    start_band = np.argmin([abs(start_freq - freq) for freq in freqs])
    end_band = np.argmin([abs(end_freq - freq) for freq in freqs])
    
    # Map frequency transitions to symbols
    if start_band == 0 and end_band == 1:    # Low→Mid
        return 0  # 000
    elif start_band == 1 and end_band == 0:  # Mid→Low
        return 1  # 001
    elif start_band == 1 and end_band == 2:  # Mid→High
        return 2  # 010
    elif start_band == 2 and end_band == 1:  # High→Mid
        return 3  # 011
    elif start_band == 2 and end_band == 3:  # High→Top
        return 4  # 100
    elif start_band == 3 and end_band == 2:  # Top→High
        return 5  # 101
    elif start_band == 0 and end_band == 2:  # Low→High (cross)
        return 6  # 110
    elif start_band == 2 and end_band == 0:  # High→Low (cross)
        return 7  # 111
    else:
        # Fallback: use direction within closest band pair
        if start_freq < end_freq:
            return 0  # Rising
        else:
            return 1  # Falling


def audio_to_symbols_8(audio, config):
    """Decode audio to 8-symbol system."""
    symbols = []
    gap_samples = int(0.002 * config.sample_rate)  # 2ms gap
    symbol_step = config.samples_per_symbol + gap_samples
    
    num_symbols = len(audio) // symbol_step
    
    for i in range(num_symbols):
        start = i * symbol_step
        end = start + config.samples_per_symbol
        
        if end <= len(audio):
            segment = audio[start:end]
            symbol = detect_symbol_8(segment, config)
            symbols.append(symbol)
    
    return symbols


def print_symbols_8(symbols, title="Symbols"):
    """Print 8-symbol representation."""
    print(f"\n{title} ({len(symbols)} symbols = {len(symbols)*3} bits):")
    
    symbol_names = ["Low↗", "Low↘", "Mid↗", "Mid↘", "High↗", "High↘", "Cross↗", "Cross↘"]
    for i, symbol in enumerate(symbols):
        if i % 8 == 0:
            print(f"\n  {i:2d}: ", end="")
        print(f"{symbol_names[symbol]:6s}", end=" ")
    print()


def send_sweeps_8(text="Hi", config=None, output_file=None, play_audio=True):
    """Send text using 8-symbol system."""
    symbols = text_to_symbols_3bit(text)
    print(f"Sending Text: '{text}' ({len(text.encode('utf-8'))} bytes → {len(symbols)} symbols)")
    print_symbols_8(symbols, "8-Symbol Sweeps")
    
    audio = symbols_to_audio_8(symbols, config)
    
    if output_file:
        max_val = np.max(np.abs(audio))
        if max_val > 0:
            audio_normalized = audio * 0.8 / max_val
        else:
            audio_normalized = audio
        
        wavfile.write(output_file, config.sample_rate, 
                     (audio_normalized * 32767).astype(np.int16))
        print(f"Saved audio to: {output_file}")
    
    if play_audio:
        print("Playing 8-symbol sweep audio...")
        sd.play(audio, config.sample_rate)
        sd.wait()
        print("Transmission complete.")


def receive_sweeps_8(config, input_file=None):
    """Receive and decode 8-symbol audio."""
    if input_file:
        sample_rate, audio = wavfile.read(input_file)
        audio = audio.astype(float) / 32767.0
        print(f"Loaded audio from: {input_file}")
    
    print("Decoding 8-symbol frequency sweeps...")
    decoded_symbols = audio_to_symbols_8(audio, config)
    print_symbols_8(decoded_symbols, "Received 8-Symbols")
    
    decoded_text = symbols_to_text_3bit(decoded_symbols)
    print(f"\n🎼 Decoded Text: '{decoded_text}'")
    
    return decoded_text


def main():
    parser = argparse.ArgumentParser(description="8-Symbol Frequency Sweep Transmission")
    parser.add_argument('mode', choices=['send', 'recv'])
    parser.add_argument('--text', '-t', default="Hi")
    parser.add_argument('--output', '-o')
    parser.add_argument('--input', '-i')
    parser.add_argument('--no-play', action='store_true')
    
    args = parser.parse_args()
    
    config = SweepConfig8()
    
    print(f"8-Symbol Sweep Configuration:")
    print(f"  Symbol duration: {config.symbol_duration:.3f}s")
    print(f"  Data rate: ~{3/config.symbol_duration:.0f} bits/s")
    print(f"  Frequency bands: {config.low_freq:.0f}-{config.mid_freq:.0f}-{config.high_freq:.0f}-{config.top_freq:.0f}Hz")
    
    if args.mode == 'send':
        send_sweeps_8(args.text, config, args.output, not args.no_play)
    else:
        receive_sweeps_8(config, args.input)


if __name__ == '__main__':
    main()