#!/usr/bin/env python3
"""
frequency_analysis.py - Diagnostic tools for measuring harmonic interference

Tools to understand what's actually happening in our frequency domain:
1. Single frequency test - see harmonics from individual tones
2. Cross-talk measurement - measure interference between frequency pairs
3. Spectrogram visualization - see actual patterns vs expected
4. Energy distribution analysis - quantify where energy is leaking
"""

import numpy as np
import matplotlib.pyplot as plt
from scipy.io import wavfile
from scipy import signal
import argparse
import sys


def generate_single_tone(frequency, duration, sample_rate):
    """Generate a pure sine wave for testing."""
    t = np.linspace(0, duration, int(duration * sample_rate), endpoint=False)
    return np.sin(2 * np.pi * frequency * t)


def measure_harmonic_spread(frequency, duration=0.1, sample_rate=44100):
    """
    Measure harmonic content of a single frequency.
    
    Returns:
        frequencies, magnitudes of FFT
    """
    audio = generate_single_tone(frequency, duration, sample_rate)
    
    # Apply window to reduce spectral leakage
    window = np.hanning(len(audio))
    windowed_audio = audio * window
    
    # Compute FFT
    fft = np.fft.fft(windowed_audio)
    freqs = np.fft.fftfreq(len(audio), 1/sample_rate)
    
    # Only positive frequencies
    positive_mask = freqs >= 0
    freqs = freqs[positive_mask]
    magnitudes = np.abs(fft[positive_mask])
    
    return freqs, magnitudes


def test_frequency_isolation():
    """Test each of our target frequencies in isolation."""
    our_frequencies = [784.0, 1046.5, 1568.0, 2093.0, 2637.0, 3520.0, 4186.0, 5274.0]
    
    print("=== Single Frequency Harmonic Analysis ===")
    
    for i, freq in enumerate(our_frequencies):
        print(f"\nTesting {freq:.1f}Hz (band {i}):")
        
        freqs, mags = measure_harmonic_spread(freq)
        
        # Find peaks in the spectrum
        peaks, _ = signal.find_peaks(mags, height=np.max(mags) * 0.1)  # 10% of max
        
        print(f"  Primary: {freq:.1f}Hz")
        print("  Detected peaks:")
        for peak_idx in peaks[:5]:  # Top 5 peaks
            peak_freq = freqs[peak_idx]
            peak_mag = mags[peak_idx]
            if peak_freq > 10:  # Ignore DC
                print(f"    {peak_freq:.1f}Hz: {20*np.log10(peak_mag/np.max(mags)):.1f}dB")


def measure_cross_talk(freq1, freq2, duration=0.1, sample_rate=44100):
    """
    Measure interference between two frequencies.
    
    Test what happens when we play freq1 and try to detect freq2.
    """
    # Generate audio with freq1
    audio = generate_single_tone(freq1, duration, sample_rate)
    
    # Apply window
    window = np.hanning(len(audio))
    windowed_audio = audio * window
    
    # Compute FFT
    fft = np.fft.fft(windowed_audio)
    freqs = np.fft.fftfreq(len(audio), 1/sample_rate)
    
    # Find energy near freq2
    freq2_idx = np.argmin(np.abs(freqs - freq2))
    bin_range = 3  # ±3 bins like our decoder
    start_idx = max(0, freq2_idx - bin_range)
    end_idx = min(len(fft), freq2_idx + bin_range + 1)
    
    # Energy at freq2 location when playing freq1
    cross_talk_energy = np.sum(np.abs(fft[start_idx:end_idx])**2)
    
    # Energy at freq1 location for reference
    freq1_idx = np.argmin(np.abs(freqs - freq1))
    freq1_start = max(0, freq1_idx - bin_range)
    freq1_end = min(len(fft), freq1_idx + bin_range + 1)
    primary_energy = np.sum(np.abs(fft[freq1_start:freq1_end])**2)
    
    # Cross-talk ratio
    ratio = cross_talk_energy / primary_energy if primary_energy > 0 else 0
    
    return ratio, cross_talk_energy, primary_energy


def test_cross_talk_matrix():
    """Test cross-talk between all pairs of our frequencies."""
    our_frequencies = [784.0, 1046.5, 1568.0, 2093.0, 2637.0, 3520.0, 4186.0, 5274.0]
    
    print("\n=== Cross-talk Matrix ===")
    print("Playing freq (rows) → Detected at freq (cols)")
    print("Values show cross-talk ratio (lower is better)")
    
    # Header
    print("        ", end="")
    for freq in our_frequencies:
        print(f"{freq:>8.0f}", end="")
    print()
    
    # Cross-talk matrix
    for i, freq1 in enumerate(our_frequencies):
        print(f"{freq1:>6.0f}Hz", end="")
        for j, freq2 in enumerate(our_frequencies):
            if i == j:
                print(f"{'1.000':>8}", end="")  # Self-detection should be 1.0
            else:
                ratio, _, _ = measure_cross_talk(freq1, freq2)
                print(f"{ratio:>8.3f}", end="")
        print()


def analyze_bitmap_audio(wav_file):
    """Analyze the spectrum of actual bitmap audio."""
    sample_rate, audio = wavfile.read(wav_file)
    audio = audio.astype(float) / 32767.0  # Normalize
    
    print(f"\n=== Bitmap Audio Analysis: {wav_file} ===")
    
    # Compute spectrogram
    f, t, Sxx = signal.spectrogram(audio, sample_rate, nperseg=1024)
    
    # Show peak frequencies
    # Average power across time
    avg_power = np.mean(Sxx, axis=1)
    peak_indices = signal.find_peaks(avg_power, height=np.max(avg_power) * 0.1)[0]
    
    print("Detected frequency peaks:")
    for idx in peak_indices:
        freq = f[idx]
        power = avg_power[idx]
        print(f"  {freq:.1f}Hz: {10*np.log10(power):.1f}dB")
    
    # Compare to expected frequencies
    our_frequencies = [784.0, 1046.5, 1568.0, 2093.0, 2637.0, 3520.0, 4186.0, 5274.0]
    print("\nExpected vs Detected:")
    for expected in our_frequencies:
        closest_idx = np.argmin(np.abs(f - expected))
        closest_freq = f[closest_idx]
        closest_power = avg_power[closest_idx]
        print(f"  Expected {expected:.1f}Hz → Found {closest_freq:.1f}Hz ({10*np.log10(closest_power):.1f}dB)")


def test_natural_patterns():
    """Test patterns inspired by nature."""
    print("\n=== Natural Pattern Ideas ===")
    
    # Frequency sweep (like bird song)
    print("1. Frequency Sweeps:")
    print("   - Instead of discrete tones, use frequency ramps")
    print("   - Each 'bit' could be an up-sweep vs down-sweep")
    print("   - Natural and less harmonic interference")
    
    # Chirps (like insects)
    print("\n2. Chirp Patterns:")
    print("   - Short pulses at different frequencies")
    print("   - Timing gaps reduce interference")
    print("   - Each frequency gets its own time slot")
    
    # Harmonic series (like whale songs)
    print("\n3. Harmonic Series:")
    print("   - Use intentional harmonics as features")
    print("   - Encode data in harmonic relationships")
    print("   - Work with harmonics instead of against them")


def main():
    parser = argparse.ArgumentParser(description="Frequency Analysis Tools")
    parser.add_argument('command', choices=['harmonics', 'crosstalk', 'analyze', 'natural'],
                       help='Analysis to perform')
    parser.add_argument('--file', '-f', help='WAV file to analyze')
    
    args = parser.parse_args()
    
    if args.command == 'harmonics':
        test_frequency_isolation()
    elif args.command == 'crosstalk':
        test_cross_talk_matrix()
    elif args.command == 'analyze':
        if not args.file:
            print("Error: --file required for analyze command")
            sys.exit(1)
        analyze_bitmap_audio(args.file)
    elif args.command == 'natural':
        test_natural_patterns()


if __name__ == '__main__':
    main()