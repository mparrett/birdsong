#!/usr/bin/env python3
"""Acoustic modem implementation using FSK modulation with musical frequencies.

This modem transmits data over audio channels using frequencies based on musical
notes (G3=196Hz for '0', A6=1760Hz for '1', C8=4186Hz for handshake).
Adapted from our beloved birdsong.py for acoustic modem challenge.
"""

import argparse
import struct
import wave
import numpy as np
import scipy.signal
import sys
from typing import Optional


class AcousticModem:
    def __init__(self, speed_multiplier: float = 1.0):
        # Challenge specifies 48kHz as recommended
        self.sample_rate = 48000
        self.base_bit_duration = 0.05  # 50ms base duration from birdsong.py
        self.speed_multiplier = speed_multiplier
        self.bit_duration = self.base_bit_duration / speed_multiplier
        
        # FSK frequencies from our beloved birdsong.py - musical notes for better acoustics
        self.freq0 = 196.00      # G3 - frequency for bit '0'
        self.freq1 = 1760.00     # A6 - frequency for bit '1' 
        self.freq_start = 4186.01 # C8 - handshake frequency
        
        # Detection parameters from birdsong.py experience
        self.amplitude_threshold = 2.0
        self.handshake_min_detections = 2
        self.silence_timeout_chunks = 20

    def generate_tone(self, frequency: float, duration: float) -> np.ndarray:
        """Generate pure sine wave tone with fade-in/out (from birdsong.py)."""
        num_samples = int(self.sample_rate * duration)
        t = np.linspace(0, duration, num_samples, False)
        tone = np.sin(frequency * t * 2 * np.pi).astype(np.float32)
        
        # Apply fade-in/out to prevent audio clicks (birdsong.py technique)
        fade_len = int(num_samples * 0.10)
        if fade_len > 0:
            fade_in = np.linspace(0, 1, fade_len)
            fade_out = np.linspace(1, 0, fade_len)
            tone[:fade_len] *= fade_in
            tone[-fade_len:] *= fade_out
        
        return tone

    def bytes_to_bits(self, byte_data: bytes) -> list:
        """Convert bytes to list of bits (from birdsong.py)."""
        bits = []
        for byte in byte_data:
            for i in range(7, -1, -1):
                bits.append((byte >> i) & 1)
        return bits

    def bits_to_bytes(self, bits: list) -> bytes:
        """Convert list of bits back to bytes (from birdsong.py)."""
        byte_list = []
        for i in range(0, len(bits), 8):
            byte_chunk = bits[i:i + 8]
            if len(byte_chunk) < 8:
                continue
            byte_val = 0
            for bit in byte_chunk:
                byte_val = (byte_val << 1) | bit
            byte_list.append(byte_val)
        return bytes(byte_list)

    def calculate_checksum(self, byte_data: bytes) -> int:
        """Calculate simple 8-bit checksum (from birdsong.py)."""
        return sum(byte_data) % 256

    def send(self, message: str, output_file: str):
        """Send message as FSK-modulated audio (adapted from birdsong.py)."""
        if not message:
            print("Error: No message provided", file=sys.stderr)
            return
        
        # Convert message to bytes
        payload_bytes = message.encode('utf-8')
        
        # Create frame: handshake + payload + checksum (birdsong.py protocol)
        handshake_bits = [2, 2]  # Two handshake tones
        payload_bits = self.bytes_to_bits(payload_bytes) 
        checksum_val = self.calculate_checksum(payload_bytes)
        checksum_bits = self.bytes_to_bits(bytes([checksum_val]))
        
        # Combine all bits
        bits_to_transmit = handshake_bits + payload_bits + checksum_bits
        
        # Generate audio signal (birdsong.py approach)
        signal_parts = []
        for bit in bits_to_transmit:
            if bit == 0:
                freq = self.freq0
            elif bit == 1:
                freq = self.freq1
            else:  # bit == 2 (handshake)
                freq = self.freq_start
            
            signal_parts.append(self.generate_tone(freq, self.bit_duration))
        
        full_signal = np.concatenate(signal_parts)
        
        # Write to WAV file using wave module (challenge constraint)
        try:
            with wave.open(output_file, 'wb') as wav_file:
                wav_file.setnchannels(1)  # Mono
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(self.sample_rate)
                
                # Convert to 16-bit integers
                audio_int16 = (full_signal * 32767).astype(np.int16)
                wav_file.writeframes(audio_int16.tobytes())
                
        except Exception as e:
            print(f"Error writing audio file: {e}", file=sys.stderr)
            sys.exit(1)

    def find_dominant_bit(self, data: np.ndarray) -> Optional[int]:
        """Analyze audio chunk to find dominant frequency/bit (from birdsong.py)."""
        if len(data) == 0:
            return None
            
        # FFT analysis (birdsong.py technique)
        fft_result = np.fft.rfft(data)
        fft_magnitude = np.abs(fft_result)
        fft_freqs = np.fft.rfftfreq(len(data), 1.0 / self.sample_rate)
        
        # Find frequency bin indices
        freq0_idx = np.argmin(np.abs(fft_freqs - self.freq0))
        freq1_idx = np.argmin(np.abs(fft_freqs - self.freq1))
        freq_start_idx = np.argmin(np.abs(fft_freqs - self.freq_start))
        
        # Get magnitudes at our frequencies
        mag0 = fft_magnitude[freq0_idx]
        mag1 = fft_magnitude[freq1_idx]
        mag_start = fft_magnitude[freq_start_idx]
        
        # Determine dominant frequency (birdsong.py logic)
        if mag_start > self.amplitude_threshold and mag_start > mag1 and mag_start > mag0:
            return 2  # Handshake
        elif mag1 > self.amplitude_threshold and mag1 > mag0:
            return 1  # Bit '1'
        elif mag0 > self.amplitude_threshold:
            return 0  # Bit '0'
        else:
            return None  # Silence/noise

    def recv(self, input_file: str):
        """Receive and decode FSK-modulated audio (adapted from birdsong.py)."""
        try:
            # Read WAV file using wave module (challenge constraint)
            with wave.open(input_file, 'rb') as wav_file:
                sample_rate = wav_file.getframerate()
                if sample_rate != self.sample_rate:
                    print(f"Error: Expected sample rate {self.sample_rate}, got {sample_rate}", file=sys.stderr)
                    sys.exit(1)
                
                frames = wav_file.readframes(wav_file.getnframes())
                # Convert to numpy array
                audio_int16 = np.frombuffer(frames, dtype=np.int16)
                data = audio_int16.astype(np.float32) / 32767.0
            
        except Exception as e:
            print(f"Error reading audio file: {e}", file=sys.stderr)
            sys.exit(1)
        
        # Process audio in chunks (birdsong.py approach)
        chunk_size = int(self.sample_rate * self.bit_duration)
        
        # State machine for receiver (from birdsong.py)
        state = "WAITING_FOR_HANDSHAKE"
        all_bits = []
        handshake_counter = 0
        silence_counter = 0
        
        # Process each chunk
        num_samples = len(data)
        for i in range(0, num_samples, chunk_size):
            chunk = data[i:i + chunk_size]
            if len(chunk) < chunk_size:
                # Pad last chunk if needed
                chunk = np.pad(chunk, (0, chunk_size - len(chunk)), 'constant')
            
            bit = self.find_dominant_bit(chunk)
            
            if state == "WAITING_FOR_HANDSHAKE":
                if bit == 2:  # Handshake detected
                    handshake_counter += 1
                    if handshake_counter >= self.handshake_min_detections:
                        state = "RECEIVING_DATA"
                else:
                    handshake_counter = 0
                    
            elif state == "RECEIVING_DATA":
                if bit == 0 or bit == 1:
                    all_bits.append(bit)
                    silence_counter = 0
                else:
                    # Silence or noise
                    silence_counter += 1
                    if silence_counter > self.silence_timeout_chunks:
                        break  # End of transmission
        
        # Process received bits (birdsong.py protocol)
        if not all_bits or len(all_bits) < 8:
            print("Error: No data payload found", file=sys.stderr)
            sys.exit(1)
        
        # Split payload and checksum
        payload_bits = all_bits[:-8]
        checksum_bits = all_bits[-8:]
        
        # Convert to bytes
        received_bytes = self.bits_to_bytes(payload_bits)
        received_checksum = self.bits_to_bytes(checksum_bits)[0]
        expected_checksum = self.calculate_checksum(received_bytes)
        
        # Verify checksum (birdsong.py validation)
        if received_checksum != expected_checksum:
            print(f"Error: Checksum mismatch! Expected {expected_checksum}, got {received_checksum}", file=sys.stderr)
            sys.exit(1)
        
        # Output decoded message
        try:
            message = received_bytes.decode('utf-8')
            print(message)
        except UnicodeDecodeError:
            print("Error: Received data is not valid UTF-8", file=sys.stderr)
            sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Acoustic modem using FSK modulation with musical frequencies",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest='command', required=True, help='Command to run')
    
    # Send command (exact challenge interface)
    parser_send = subparsers.add_parser('send', help='Send message as audio')
    parser_send.add_argument('-o', '--output', required=True, help='Output WAV file')
    parser_send.add_argument('-m', '--message', required=True, help='Message to send')
    parser_send.add_argument('-s', '--speed', type=float, default=1.0, help='Speed multiplier')
    
    # Receive command (exact challenge interface)
    parser_recv = subparsers.add_parser('recv', help='Receive message from audio')
    parser_recv.add_argument('-i', '--input', required=True, help='Input WAV file')
    parser_recv.add_argument('-s', '--speed', type=float, default=1.0, help='Speed multiplier')
    
    args = parser.parse_args()
    
    # Validate speed parameter
    if args.speed <= 0:
        print(f"Error: Speed multiplier must be positive, got {args.speed}", file=sys.stderr)
        sys.exit(1)
    
    # Create modem instance
    modem = AcousticModem(speed_multiplier=args.speed)
    
    # Execute command
    if args.command == 'send':
        modem.send(args.message, args.output)
    elif args.command == 'recv':
        modem.recv(args.input)


if __name__ == "__main__":
    main()