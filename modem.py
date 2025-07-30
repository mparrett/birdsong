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

import sys
import argparse
import wave
import struct
import math
import subprocess
from dataclasses import dataclass
import io
import time
import numpy as np
from scipy import signal

# --- Configuration ---

@dataclass
class ModemConfig:
    """Configuration for the Spectrogram Bitmap Modem."""
    sample_rate: int = 44100
    # Grid dimensions
    freq_bands: int = 8      # Number of frequency bands (Y-axis)
    time_slots_data: int = 32 # Number of time slots for payload data
    slot_duration: float = 0.200  # 200ms per time slot (much slower for better reliability)
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

# --- Signal Processing Helpers ---

def correlate_2d(bitmap1: list, bitmap2: list):
    """2D correlation for preamble detection using scipy."""
    bitmap1_np = np.array(bitmap1, dtype=float)
    bitmap2_np = np.array(bitmap2, dtype=float)
    correlation = signal.correlate2d(bitmap1_np, bitmap2_np, mode='valid')
    # Return as 1D list of correlation scores across time slots
    return correlation.flatten().tolist()

# --- Protocol & Helpers ---

def create_preamble_bitmap(config: ModemConfig):
    """Creates a distinct, high-energy preamble pattern for synchronization."""
    preamble = [[0 for _ in range(config.preamble_slots)] for _ in range(config.freq_bands)]
    # Create a diagonal sweep pattern (chirp-like) for robust detection
    for i in range(config.preamble_slots):
        freq_idx = i % config.freq_bands
        preamble[freq_idx][i] = 1
    return preamble

def calculate_checksum(data_bytes: bytes) -> int:
    """Calculates a simple 8-bit checksum."""
    return sum(data_bytes) & 0xFF

def bits_to_bytes(bits: list) -> bytes:
    """Converts a list of bits into a bytes object efficiently."""
    if len(bits) % 8 != 0:
        # Pad with zeros to make it a multiple of 8
        bits = bits + [0] * (8 - len(bits) % 8)
    
    byte_array = bytearray()
    for i in range(0, len(bits), 8):
        byte = int("".join(map(str, bits[i:i+8])), 2)
        byte_array.append(byte)
    return bytes(byte_array)

def bits_to_bitmap(bits: list, bands: int, slots: int):
    """Converts a list of bits into a 2D bitmap."""
    total_cells = bands * slots
    if len(bits) > total_cells:
        raise ValueError(f"Too many bits ({len(bits)}) for the bitmap size ({total_cells}).")
    padded_bits = bits + [0] * (total_cells - len(bits))
    # Convert to 2D list: reshape and transpose
    bitmap = [[padded_bits[r * slots + c] for c in range(slots)] for r in range(bands)]
    return bitmap

def bitmap_to_bits(bitmap: list) -> list:
    """Converts a 2D bitmap back into a list of bits."""
    bits = []
    for row in range(len(bitmap)):
        for col in range(len(bitmap[0])):
            bits.append(bitmap[row][col])
    return bits

# --- Sender Logic ---

def bitmap_to_audio(bitmap: list, config: ModemConfig):
    """Converts a bitmap into an audio signal with phase continuity."""
    num_slots = len(bitmap[0])
    total_samples = num_slots * config.samples_per_slot
    audio = [0.0] * total_samples
    phase_states = [0.0] * config.freq_bands

    for t in range(num_slots):
        start_sample = t * config.samples_per_slot
        
        # Count active bands for amplitude scaling
        active_bands = sum(bitmap[f][t] for f in range(config.freq_bands))
        amplitude = 1.0 / math.sqrt(max(1, active_bands)) # Equal power distribution

        for sample_idx in range(config.samples_per_slot):
            sample_time = sample_idx / config.sample_rate
            sample_value = 0.0
            
            for f in range(config.freq_bands):
                if bitmap[f][t] == 1:
                    sine_val = math.sin(2 * math.pi * config.frequencies[f] * sample_time + phase_states[f])
                    sample_value += amplitude * sine_val
            
            audio[start_sample + sample_idx] = sample_value
        
        # Update phase for continuity
        for f in range(config.freq_bands):
            phase_states[f] = (phase_states[f] + 2 * math.pi * config.frequencies[f] * config.slot_duration) % (2 * math.pi)
    
    # Normalize final audio to prevent clipping
    max_val = max(abs(sample) for sample in audio) if audio else 1.0
    return [sample / max_val for sample in audio] if max_val > 0 else audio

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
    if verbose:
        print(f"Debug: Header bytes to send: {header_bytes + header_checksum}", file=sys.stderr)
        print(f"Debug: Header bits to send (first 32): {header_bits[:32]}", file=sys.stderr)
    header_map = bits_to_bitmap(header_bits, config.freq_bands, config.header_slots)

    # 3. Create Payload
    payload_checksum = calculate_checksum(payload_bytes).to_bytes(1, 'big')
    payload_bits = [int(b) for b in ''.join(f'{byte:08b}' for byte in payload_bytes + payload_checksum)]
    payload_map = bits_to_bitmap(payload_bits, config.freq_bands, config.time_slots_data)

    # 4. Combine into full transmission bitmap
    full_bitmap = []
    for f in range(config.freq_bands):
        row = preamble_map[f] + header_map[f] + payload_map[f]
        full_bitmap.append(row)
    
    if verbose:
        print(f"Sender: Transmitting {len(payload_bytes)} bytes.", file=sys.stderr)
        print(f"Debug: Payload bytes: {payload_bytes}", file=sys.stderr)
        print(f"Debug: Payload checksum: {payload_checksum[0]}", file=sys.stderr)
        print(f"Bitmap: {len(full_bitmap)} freqs x {len(full_bitmap[0])} slots", file=sys.stderr)

    # 5. Convert to audio
    audio_signal = bitmap_to_audio(full_bitmap, config)
    audio_int16 = [int(sample * 32767) for sample in audio_signal]

    # 6. Play or Save
    if output_file:
        # Create WAV file using wave module
        if output_file == "-":
            # Write to stdout
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, 'wb') as wav_file:
                wav_file.setnchannels(1)  # Mono
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(config.sample_rate)
                wav_data = struct.pack('<' + 'h' * len(audio_int16), *audio_int16)
                wav_file.writeframes(wav_data)
            sys.stdout.buffer.write(wav_buffer.getvalue())
        else:
            with wave.open(output_file, 'wb') as wav_file:
                wav_file.setnchannels(1)  # Mono
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(config.sample_rate)
                wav_data = struct.pack('<' + 'h' * len(audio_int16), *audio_int16)
                wav_file.writeframes(wav_data)
            print(f"Saved audio to {output_file}", file=sys.stderr)
    else:
        # Play using system command (afplay on macOS, aplay on Linux, etc.)
        print("Playing audio...", file=sys.stderr)
        # Create temporary WAV file
        temp_file = "/tmp/modem_temp.wav"
        with wave.open(temp_file, 'wb') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(config.sample_rate)
            wav_data = struct.pack('<' + 'h' * len(audio_int16), *audio_int16)
            wav_file.writeframes(wav_data)
        
        # Try to play using system commands
        try:
            subprocess.run(['afplay', temp_file], check=True)  # macOS
        except (subprocess.CalledProcessError, FileNotFoundError):
            try:
                subprocess.run(['aplay', temp_file], check=True)  # Linux
            except (subprocess.CalledProcessError, FileNotFoundError):
                print("Error: Could not play audio. Install afplay (macOS) or aplay (Linux).", file=sys.stderr)
        print("Playback complete.", file=sys.stderr)

# --- Receiver Logic ---

def audio_to_bitmap(audio: list, config: ModemConfig):
    """Converts audio into a bitmap using adaptive thresholding."""
    audio_np = np.array(audio, dtype=np.float32)
    num_slots = len(audio_np) // config.samples_per_slot
    bitmap = np.zeros((config.freq_bands, num_slots), dtype=int)
    energy_matrix = np.zeros((config.freq_bands, num_slots))
    
    # Pre-calculate FFT bin indices
    fft_freqs_template = np.fft.fftfreq(config.samples_per_slot, 1/config.sample_rate)
    target_bin_indices = [np.argmin(np.abs(fft_freqs_template - f)) for f in config.frequencies]
    
    # 1. Collect energy measurements for all cells
    for t in range(num_slots):
        segment = audio_np[t * config.samples_per_slot : (t + 1) * config.samples_per_slot]
        if len(segment) == 0: continue
        
        windowed_segment = segment * np.hanning(len(segment))
        fft_result = np.fft.fft(windowed_segment)
        
        for f_idx, bin_idx in enumerate(target_bin_indices):
            # Sum energy in a larger window around the target bin
            bin_range = 5
            energy = np.sum(np.abs(fft_result[bin_idx-bin_range : bin_idx+bin_range+1])**2)
            energy_matrix[f_idx, t] = energy
            
    # 2. Balance approach: fixed threshold but more sensitive
    if energy_matrix.size > 0:
        # Use a simple percentage of maximum energy
        max_energy = np.max(energy_matrix)
        threshold = max_energy * 0.05  # 5% of peak energy
        
        # Apply threshold to create bitmap
        bitmap[energy_matrix > threshold] = 1
    return bitmap.tolist()

def recv(config: ModemConfig, input_file: str, verbose: bool):
    """Receives audio, finds the preamble, and decodes the data."""
    if input_file:
        with wave.open(input_file, 'rb') as wav_file:
            sample_rate = wav_file.getframerate()
            if sample_rate != config.sample_rate:
                print(f"Warning: File sample rate ({sample_rate}) differs from config ({config.sample_rate}).", file=sys.stderr)
            
            frames = wav_file.readframes(wav_file.getnframes())
            audio_int16 = struct.unpack('<' + 'h' * (len(frames) // 2), frames)
    else:
        # For microphone input, use system recording tools
        duration = (config.time_slots_data + config.preamble_slots + config.header_slots) * config.slot_duration + 1.0
        print(f"Recording for {duration:.1f} seconds...", file=sys.stderr)
        temp_file = "/tmp/modem_record.wav"
        
        try:
            # Try rec (SoX) first
            subprocess.run(['rec', '-c', '1', '-r', str(config.sample_rate), '-b', '16', temp_file, 'trim', '0', str(duration)], check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("Error: Could not record audio. Install 'rec' (SoX) for microphone input.", file=sys.stderr)
            return
        
        with wave.open(temp_file, 'rb') as wav_file:
            frames = wav_file.readframes(wav_file.getnframes())
            audio_int16 = struct.unpack('<' + 'h' * (len(frames) // 2), frames)
        print("Recording complete.", file=sys.stderr)

    audio = [sample / 32767.0 for sample in audio_int16]
    
    if verbose:
        print(f"Audio length: {len(audio)} samples, duration: {len(audio)/config.sample_rate:.2f}s", file=sys.stderr)
    
    # 1. Convert entire audio stream to a bitmap
    received_map = audio_to_bitmap(audio, config)
    if verbose:
        print(f"Receiver: Decoded bitmap of size {len(received_map)}x{len(received_map[0])}", file=sys.stderr)

    # 2. Find preamble using 2D correlation
    preamble_map = create_preamble_bitmap(config)
    correlation = correlate_2d(received_map, preamble_map)
    
    if len(correlation) == 0:
        print("Error: Could not perform correlation. Signal too short?", file=sys.stderr)
        return

    # Enhanced synchronization with confidence checking
    peak_score = max(correlation)
    mean_score = sum(correlation) / len(correlation)
    sync_slot = correlation.index(max(correlation))
    
    # Add a confidence check - a good signal should have a peak several times the average
    confidence_ratio = peak_score / mean_score if mean_score > 0 else float('inf')
    min_confidence = 3.0  # Peak should be at least 3x the average
    min_absolute_score = 1e-6  # Avoid issues with pure silence
    
    if peak_score > min_confidence * mean_score and peak_score > min_absolute_score:
        if verbose:
            print(f"Sync point found at slot {sync_slot} (Score: {peak_score:.2f}, Confidence: {confidence_ratio:.1f}x)", file=sys.stderr)
    else:
        print(f"Error: Preamble not detected or signal too noisy. Score: {peak_score:.2f}, Confidence: {confidence_ratio:.1f}x", file=sys.stderr)
        return

    # 3. Extract and decode header
    start = sync_slot + config.preamble_slots
    end = start + config.header_slots
    header_map = [row[start:end] for row in received_map]
    header_bits = bitmap_to_bits(header_map)
    header_all_bytes = bits_to_bytes(header_bits)

    if verbose:
        print(f"Debug: Header bits (first 32): {header_bits[:32]}", file=sys.stderr)
        print(f"Debug: Header bytes: {header_all_bytes}", file=sys.stderr)
    
    payload_len = int.from_bytes(header_all_bytes[:2], 'big')
    header_checksum = header_all_bytes[2]
    calculated_header_checksum = calculate_checksum(header_all_bytes[:2])
    
    if verbose:
        print(f"Debug: Payload length from header: {payload_len}", file=sys.stderr)
        print(f"Debug: Header checksum calculated: {calculated_header_checksum}, received: {header_checksum}", file=sys.stderr)
    
    if calculated_header_checksum != header_checksum:
        print(f"Error: Invalid header checksum. Calculated: {calculated_header_checksum}, Received: {header_checksum}", file=sys.stderr)
        return
    if verbose:
        print(f"Header decoded: Payload length = {payload_len} bytes", file=sys.stderr)
        
    # 4. Extract and decode payload
    payload_bits_to_read = (payload_len + 1) * 8 # +1 for checksum
    payload_slots_to_read = (payload_bits_to_read + config.freq_bands - 1) // config.freq_bands
    
    start = end
    end = start + payload_slots_to_read
    payload_map = [row[start:end] for row in received_map]
    payload_bits = bitmap_to_bits(payload_map)[:payload_bits_to_read]
    payload_all_bytes = bits_to_bytes(payload_bits)

    payload_data = payload_all_bytes[:-1]
    payload_checksum = payload_all_bytes[-1]
    
    # 5. Verify payload and output
    calculated_checksum = calculate_checksum(payload_data)
    if verbose:
        print(f"Debug: Payload data ({len(payload_data)} bytes): {payload_data}", file=sys.stderr)
        print(f"Debug: Calculated checksum: {calculated_checksum}, Received checksum: {payload_checksum}", file=sys.stderr)
        print(f"Debug: Payload bits (first 32): {payload_bits[:32]}", file=sys.stderr)
    
    if calculated_checksum == payload_checksum:
        sys.stdout.buffer.write(payload_data)
        sys.stdout.buffer.flush()
        if verbose:
            print("\nChecksum valid. Data received successfully.", file=sys.stderr)
    else:
        print(f"Error: Invalid payload checksum. Calculated: {calculated_checksum}, Received: {payload_checksum}", file=sys.stderr)


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
