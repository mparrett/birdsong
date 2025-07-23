#!/usr/bin/env python3
"""
Minimal acoustic modem using only Python standard library (Corrected)
Usage: 
  echo "hello world" | python modem.py send > out.wav
  cat out.wav | python modem.py recv
"""

import sys
import math
import wave
import struct
from io import BytesIO

# Modem parameters
SAMPLE_RATE = 44100
FREQ_0 = 1200  # Frequency for bit 0
FREQ_1 = 2200  # Frequency for bit 1  
BIT_DURATION = 0.1  # 100ms per bit -> 10 bits/sec
PREAMBLE = "10101010"  # Sync pattern
POSTAMBLE = "01010101"  # End pattern
SIGNAL_THRESHOLD = 0.01 # Threshold to distinguish signal from noise

def generate_tone(frequency, duration, amplitude=0.5):
    """Generate a sine wave tone"""
    samples = int(SAMPLE_RATE * duration)
    frames = []
    for i in range(samples):
        sample = amplitude * math.sin(2 * math.pi * frequency * i / SAMPLE_RATE)
        frames.append(struct.pack('<h', int(sample * 32767)))
    return b''.join(frames)

def get_freq_magnitude(audio_data, target_freq):
    """Calculates magnitude of a frequency component, insensitive to phase."""
    num_samples = len(audio_data) // 2
    if num_samples == 0:
        return 0.0
    
    samples = struct.unpack('<' + 'h' * num_samples, audio_data)
    
    in_phase = 0.0
    quadrature = 0.0
    for i in range(num_samples):
        angle = 2 * math.pi * target_freq * i / SAMPLE_RATE
        normalized_sample = samples[i] / 32767.0
        in_phase += normalized_sample * math.cos(angle)
        quadrature += normalized_sample * math.sin(angle)
    
    magnitude = math.sqrt(in_phase**2 + quadrature**2) / num_samples
    return magnitude

def encode_data(text):
    """Encode text to binary with framing"""
    data_bytes = text.encode('utf-8')
    binary_data = ''.join(format(byte, '08b') for byte in data_bytes)
    return PREAMBLE + binary_data + POSTAMBLE

def decode_data(binary_str):
    """Decode binary to text, removing framing"""
    start = binary_str.find(PREAMBLE)
    if start != -1:
        end = binary_str.find(POSTAMBLE, start + len(PREAMBLE))
    else:
        end = -1

    if start == -1 or end == -1:
        return None
    
    data_bits = binary_str[start + len(PREAMBLE):end]
    
    byte_len = len(data_bits) - (len(data_bits) % 8)
    data_bits = data_bits[:byte_len]
    
    try:
        data_bytes = bytearray()
        for i in range(0, len(data_bits), 8):
            byte_str = data_bits[i:i+8]
            data_bytes.append(int(byte_str, 2))
        return data_bytes.decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"Decoding error: {e}", file=sys.stderr)
        return None

def send_data(text):
    """Encode and transmit data as audio"""
    binary_data = encode_data(text)
    
    audio_data = b''
    for bit in binary_data:
        freq = FREQ_1 if bit == '1' else FREQ_0
        audio_data += generate_tone(freq, BIT_DURATION)
    
    wav_buffer = BytesIO()
    with wave.open(wav_buffer, 'wb') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(SAMPLE_RATE)
        wav_file.writeframes(audio_data)
    
    wav_buffer.seek(0)
    sys.stdout.buffer.write(wav_buffer.read())
    sys.stdout.buffer.flush()

# FINAL CORRECTED VERSION of receive_data
def receive_data():
    """Receive and decode audio data"""
    wav_data = sys.stdin.buffer.read()
    if not wav_data:
        return
    
    try:
        wav_buffer = BytesIO(wav_data)
        with wave.open(wav_buffer, 'rb') as wav_file:
            sample_width = wav_file.getsampwidth() # e.g., 2 bytes for 16-bit
            frames = wav_file.readframes(wav_file.getnframes())
    except wave.Error:
        print("Error: Invalid WAV data", file=sys.stderr)
        return
    
    # CHANGED: All chunk/step sizes are now calculated in BYTES
    chunk_size_samples = int(SAMPLE_RATE * BIT_DURATION)
    chunk_size_bytes = chunk_size_samples * sample_width

    # 1. Find the start of the transmission to sync up
    start_offset_bytes = -1
    step_size_bytes = (chunk_size_samples // 4) * sample_width 
    for i in range(0, len(frames) - chunk_size_bytes, step_size_bytes):
        chunk = frames[i:i + chunk_size_bytes]
        mag0 = get_freq_magnitude(chunk, FREQ_0)
        mag1 = get_freq_magnitude(chunk, FREQ_1)
        
        if mag0 > SIGNAL_THRESHOLD or mag1 > SIGNAL_THRESHOLD:
            start_offset_bytes = i
            print(f"Debug: Signal detected at byte offset {start_offset_bytes}", file=sys.stderr)
            break
            
    if start_offset_bytes == -1:
        print("Error: No signal detected.", file=sys.stderr)
        return

    # 2. Decode bitstream from the detected start position
    binary_str = ""
    for i in range(start_offset_bytes, len(frames) - chunk_size_bytes, chunk_size_bytes):
        chunk = frames[i:i + chunk_size_bytes]
        mag0 = get_freq_magnitude(chunk, FREQ_0)
        mag1 = get_freq_magnitude(chunk, FREQ_1)
        
        binary_str += '1' if mag1 > mag0 else '0'

    print(f"Debug: Raw detected binary string (first 100 chars): {binary_str[:100]}...", file=sys.stderr)

    # 3. Decode the binary string to text
    decoded_text = decode_data(binary_str)
    if decoded_text:
        print(decoded_text, end='')
    else:
        print("Error: Could not decode data. Preamble/postamble not found.", file=sys.stderr)

def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ["send", "recv"]:
        print(f"Usage: {sys.argv[0]} {{send|recv}}", file=sys.stderr)
        sys.exit(1)
    
    mode = sys.argv[1]
    
    if mode == "send":
        input_text = sys.stdin.read()
        if input_text:
            send_data(input_text)
    elif mode == "recv":
        receive_data()

if __name__ == "__main__":
    main()