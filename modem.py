#!/usr/bin/env python3
"""
Spectrogram Bitmap Modem - A Unified High-Performance Acoustic Modem

This script combines the most innovative concepts from the repository into a single,
robust, and high-throughput acoustic modem.

Core Technology: Spectrogram Bitmap Transmission
- Data is "drawn" onto a time-frequency grid (a bitmap).
- This bitmap is converted into an audio signal.
- The receiver regenerates the bitmap from the audio to decode the data.

Key Features Integrated:
1.  High Data Rate: Uses 8 parallel frequency bands to transmit 8 bits (1 byte)
    per time slot, inspired by the multi-band and bitmap scripts.
2.  Robust Protocol: Implements a formal preamble for synchronization, a header
    with payload length, and a checksum for data integrity.
3.  Advanced Synchronization: The receiver uses 2D correlation to precisely
    locate the preamble pattern in the received spectrogram, making it highly
    resilient to timing offsets.
4.  Adaptive Receiver: Employs adaptive thresholding based on the received
    signal's statistics (noise floor, standard deviation) to reliably distinguish
    signal from noise, making it robust to volume changes.
5.  Musical Harmonics: Frequencies are based on a G-C perfect fourth harmony
    stack, making the signal more pleasant and reducing inharmonic distortion.

Usage:
  # Send text from stdin
  echo "Hello, this is a test!" | python modem.py send

  # Save to a file instead of playing
  echo "Save me" | python modem.py send -o message.wav

  # Receive from microphone
  python modem.py recv

  # Receive from a file
  python modem.py recv -i message.wav
"""

import numpy as np
import sys
import argparse
import sounddevice as sd
from scipy.io import wavfile
from scipy import signal
from dataclasses import dataclass
import io
import time

# --- Configuration ---

@dataclass
class ModemConfig:
    """Configuration for the Spectrogram Bitmap Modem."""
    sample_rate: int = 44100
    # Grid dimensions
    freq_bands: int = 8      # Number of frequency bands (Y-axis)
    time_slots_data: int = 32 # Number of time slots for payload data
    slot_duration: float = 0.040  # 40ms per time slot
    # Protocol
    preamble_slots: int = 8  # Preamble duration in time slots
    header_slots: int = 4    # Header duration (2 bytes length + 1 byte checksum)
    # Frequencies (G-C perfect fourth harmonies)
    frequencies: list = None

    def __post_init__(self):
        if self.frequencies is None:
            self.frequencies = [
                784.0, 1046.5, 1568.0, 2093.0, 2637.0, 3520.0, 4186.0, 5274.0
            ]
    @property
    def samples_per_slot(self):
        return int(self.slot_duration * self.sample_rate)
    @property
    def max_payload_bytes(self):
        return (self.freq_bands * self.time_slots_data) // 8

# --- Protocol & Helpers ---

def create_preamble_bitmap(config: ModemConfig):
    """Creates a distinct, high-energy preamble pattern for synchronization."""
    preamble = np.zeros((config.freq_bands, config.preamble_slots), dtype=int)
    # Create a diagonal sweep pattern (chirp-like) for robust detection
    for i in range(config.preamble_slots):
        freq_idx = i % config.freq_bands
        preamble[freq_idx, i] = 1
    return preamble

def calculate_checksum(data_bytes: bytes) -> int:
    """Calculates a simple 8-bit checksum."""
    return sum(data_bytes) & 0xFF

def bits_to_bitmap(bits: list, bands: int, slots: int):
    """Converts a list of bits into a 2D bitmap."""
    total_cells = bands * slots
    if len(bits) > total_cells:
        raise ValueError(f"Too many bits ({len(bits)}) for the bitmap size ({total_cells}).")
    padded_bits = bits + [0] * (total_cells - len(bits))
    return np.array(padded_bits).reshape((slots, bands)).T

def bitmap_to_bits(bitmap: np.ndarray) -> list:
    """Converts a 2D bitmap back into a list of bits."""
    return bitmap.T.flatten().tolist()

# --- Sender Logic ---

def bitmap_to_audio(bitmap: np.ndarray, config: ModemConfig):
    """Converts a bitmap into an audio signal with phase continuity."""
    num_slots = bitmap.shape[1]
    total_samples = num_slots * config.samples_per_slot
    audio = np.zeros(total_samples, dtype=np.float32)
    phase_states = np.zeros(config.freq_bands)

    for t in range(num_slots):
        start_sample = t * config.samples_per_slot
        time_array = np.linspace(0, config.slot_duration, config.samples_per_slot, endpoint=False)
        slot_signal = np.zeros(config.samples_per_slot, dtype=np.float32)
        
        active_bands = np.sum(bitmap[:, t])
        amplitude = 1.0 / np.sqrt(max(1, active_bands)) # Equal power distribution

        for f in range(config.freq_bands):
            if bitmap[f, t] == 1:
                sine_wave = np.sin(2 * np.pi * config.frequencies[f] * time_array + phase_states[f])
                slot_signal += amplitude * sine_wave
            
            # Update phase for continuity, even on silent cells
            phase_states[f] = (phase_states[f] + 2 * np.pi * config.frequencies[f] * config.slot_duration) % (2 * np.pi)
        
        audio[start_sample : start_sample + config.samples_per_slot] = slot_signal
    
    # Normalize final audio to prevent clipping
    max_val = np.max(np.abs(audio))
    return audio / max_val if max_val > 0 else audio

def send(config: ModemConfig, output_file: str, verbose: bool):
    """Reads data from stdin, builds a framed bitmap, and transmits it as audio."""
    payload_bytes = sys.stdin.buffer.read()
    if not payload_bytes:
        print("Sender: No input data from stdin.", file=sys.stderr)
        return

    if len(payload_bytes) > config.max_payload_bytes:
        print(f"Error: Payload too large ({len(payload_bytes)} bytes). Max is {config.max_payload_bytes}.", file=sys.stderr)
        return

    # 1. Create Preamble
    preamble_map = create_preamble_bitmap(config)

    # 2. Create Header (2 bytes for length, 1 for checksum)
    header_bytes = len(payload_bytes).to_bytes(2, 'big')
    header_checksum = calculate_checksum(header_bytes).to_bytes(1, 'big')
    header_bits = [int(b) for b in ''.join(f'{byte:08b}' for byte in header_bytes + header_checksum)]
    header_map = bits_to_bitmap(header_bits, config.freq_bands, config.header_slots)

    # 3. Create Payload
    payload_checksum = calculate_checksum(payload_bytes).to_bytes(1, 'big')
    payload_bits = [int(b) for b in ''.join(f'{byte:08b}' for byte in payload_bytes + payload_checksum)]
    payload_map = bits_to_bitmap(payload_bits, config.freq_bands, config.time_slots_data)

    # 4. Combine into full transmission bitmap
    full_bitmap = np.hstack([preamble_map, header_map, payload_map])
    
    if verbose:
        print(f"Sender: Transmitting {len(payload_bytes)} bytes.", file=sys.stderr)
        print(f"Bitmap: {full_bitmap.shape[0]} freqs x {full_bitmap.shape[1]} slots", file=sys.stderr)

    # 5. Convert to audio
    audio_signal = bitmap_to_audio(full_bitmap, config)
    audio_int16 = (audio_signal * 32767).astype(np.int16)

    # 6. Play or Save
    if output_file:
        wav_buffer = io.BytesIO()
        wavfile.write(wav_buffer, config.sample_rate, audio_int16)
        if output_file == "-":
            sys.stdout.buffer.write(wav_buffer.getvalue())
        else:
            with open(output_file, "wb") as f:
                f.write(wav_buffer.getvalue())
            print(f"Saved audio to {output_file}", file=sys.stderr)
    else:
        print("Playing audio...", file=sys.stderr)
        sd.play(audio_int16, config.sample_rate)
        sd.wait()
        print("Playback complete.", file=sys.stderr)

# --- Receiver Logic ---

def audio_to_bitmap(audio: np.ndarray, config: ModemConfig):
    """Converts audio into a bitmap using adaptive thresholding."""
    num_slots = len(audio) // config.samples_per_slot
    bitmap = np.zeros((config.freq_bands, num_slots), dtype=int)
    energy_matrix = np.zeros((config.freq_bands, num_slots))
    
    # 1. Collect energy measurements for all cells
    for t in range(num_slots):
        segment = audio[t * config.samples_per_slot : (t + 1) * config.samples_per_slot]
        if len(segment) == 0: continue
        
        windowed_segment = segment * np.hanning(len(segment))
        fft_result = np.fft.fft(windowed_segment)
        fft_freqs = np.fft.fftfreq(len(segment), 1/config.sample_rate)
        
        for f in range(config.freq_bands):
            target_freq = config.frequencies[f]
            freq_idx = np.argmin(np.abs(fft_freqs - target_freq))
            # Sum energy in a small window around the target bin
            bin_range = 3
            energy = np.sum(np.abs(fft_result[freq_idx-bin_range : freq_idx+bin_range+1])**2)
            energy_matrix[f, t] = energy
            
    # 2. Calculate adaptive threshold
    if energy_matrix.size > 0:
        # A robust threshold is slightly above the median energy, plus a factor of the standard deviation
        # This separates signal peaks from the noise floor.
        median_energy = np.median(energy_matrix)
        std_dev_energy = np.std(energy_matrix[energy_matrix > 0]) # Std dev of non-zero energy
        threshold = median_energy + 1.5 * std_dev_energy
        threshold = max(threshold, 1e-6) # Ensure threshold is not zero
    else:
        return bitmap

    # 3. Apply threshold to create bitmap
    bitmap[energy_matrix > threshold] = 1
    return bitmap

def recv(config: ModemConfig, input_file: str, verbose: bool):
    """Receives audio, finds the preamble, and decodes the data."""
    if input_file:
        sample_rate, audio_int16 = wavfile.read(input_file)
        if sample_rate != config.sample_rate:
            print(f"Warning: File sample rate ({sample_rate}) differs from config ({config.sample_rate}).", file=sys.stderr)
    else:
        duration = (config.time_slots_data + config.preamble_slots + config.header_slots) * config.slot_duration + 1.0
        print(f"Recording for {duration:.1f} seconds...", file=sys.stderr)
        audio_int16 = sd.rec(int(duration * config.sample_rate), samplerate=config.sample_rate, channels=1, dtype='int16')
        sd.wait()
        print("Recording complete.", file=sys.stderr)

    audio = audio_int16.flatten().astype(np.float32) / 32767.0
    
    # 1. Convert entire audio stream to a bitmap
    received_map = audio_to_bitmap(audio, config)
    if verbose:
        print(f"Receiver: Decoded bitmap of size {received_map.shape}", file=sys.stderr)

    # 2. Find preamble using 2D correlation
    preamble_map = create_preamble_bitmap(config)
    correlation = signal.correlate2d(received_map.astype(float), preamble_map.astype(float), mode='valid')
    
    if correlation.size == 0:
        print("Error: Could not perform correlation. Signal too short?", file=sys.stderr)
        return

    sync_slot = np.argmax(correlation)
    if verbose:
        print(f"Sync point found at time slot: {sync_slot} (Score: {correlation[0, sync_slot]:.2f})", file=sys.stderr)

    # 3. Extract and decode header
    start = sync_slot + config.preamble_slots
    end = start + config.header_slots
    header_map = received_map[:, start:end]
    header_bits = bitmap_to_bits(header_map)
    header_all_bytes = int("".join(map(str, header_bits)), 2).to_bytes(len(header_bits)//8, 'big')

    payload_len = int.from_bytes(header_all_bytes[:2], 'big')
    header_checksum = header_all_bytes[2]
    
    if calculate_checksum(header_all_bytes[:2]) != header_checksum:
        print("Error: Invalid header checksum. Aborting.", file=sys.stderr)
        return
    if verbose:
        print(f"Header decoded: Payload length = {payload_len} bytes", file=sys.stderr)
        
    # 4. Extract and decode payload
    payload_bits_to_read = (payload_len + 1) * 8 # +1 for checksum
    payload_slots_to_read = (payload_bits_to_read + config.freq_bands - 1) // config.freq_bands
    
    start = end
    end = start + payload_slots_to_read
    payload_map = received_map[:, start:end]
    payload_bits = bitmap_to_bits(payload_map)[:payload_bits_to_read]
    payload_all_bytes = int("".join(map(str, payload_bits)), 2).to_bytes(len(payload_bits)//8, 'big')

    payload_data = payload_all_bytes[:-1]
    payload_checksum = payload_all_bytes[-1]
    
    # 5. Verify payload and output
    if calculate_checksum(payload_data) == payload_checksum:
        sys.stdout.buffer.write(payload_data)
        sys.stdout.buffer.flush()
        if verbose:
            print("\nChecksum valid. Data received successfully.", file=sys.stderr)
    else:
        print("Error: Invalid payload checksum. Data may be corrupt.", file=sys.stderr)


# --- Main Execution ---

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="High-performance Spectrogram Bitmap Modem",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest='command', required=True)
    
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose status messages.")

    # Sender command
    parser_send = subparsers.add_parser('send', help='Transmit data from stdin.', parents=[parent_parser])
    parser_send.add_argument("-o", "--output", help="Write audio to a WAV file. Use '-' for stdout.")
    
    # Receiver command
    parser_recv = subparsers.add_parser('recv', help='Receive data from microphone or file.', parents=[parent_parser])
    parser_recv.add_argument("-i", "--input", help="Read audio from a WAV file.")
    
    args = parser.parse_args()
    config = ModemConfig()
    
    try:
        if args.command == "send":
            send(config, args.output, args.verbose)
        elif args.command == "recv":
            recv(config, args.input, args.verbose)
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)
