# birdsong.py
#
# MVP: Transmits data from stdin to stdout using an acoustic modem protocol.
#
# Sender Usage:
#   echo "hello" | python birdsong.py send > transmission.wav
#
# Receiver Usage:
#   python birdsong.py recv < transmission.wav > received_message.txt

import numpy as np
import wave
import sys
import time

# --- Protocol & Configuration ---
SAMPLE_RATE = 44100
BIT_DURATION = 0.008  # Your high-speed setting
CHUNK_SIZE = int(SAMPLE_RATE * BIT_DURATION)

# Frequencies chosen for wide separation and performance
FREQ_0 = 196.00      # G3
FREQ_1 = 1760.00     # A6
FREQ_START = 4186.01 # C8 (A high, distinct frequency for the handshake)

# --- Helper Functions ---

def bytes_to_bits(byte_data):
    """Converts a byte string into a list of bits (0s and 1s)."""
    bits = []
    for byte in byte_data:
        # Get the 8 bits for each byte, MSB first
        for i in range(7, -1, -1):
            bits.append((byte >> i) & 1)
    return bits

def bits_to_bytes(bits):
    """Converts a list of bits back into bytes."""
    byte_list = []
    for i in range(0, len(bits), 8):
        byte_chunk = bits[i:i+8]
        if len(byte_chunk) < 8:
            # Ignore trailing bits that don't form a full byte
            continue
        byte_val = 0
        for bit in byte_chunk:
            byte_val = (byte_val << 1) | bit
        byte_list.append(byte_val)
    return bytes(byte_list)

def calculate_checksum(byte_data):
    """Calculates a simple 8-bit checksum."""
    return sum(byte_data) % 256

# --- Sender Logic ---

def generate_tone(frequency, duration, sample_rate):
    """Generates a pure sine wave tone."""
    num_samples = int(sample_rate * duration)
    t = np.linspace(0, duration, num_samples, False)
    tone = np.sin(frequency * t * 2 * np.pi)
    fade_len = int(num_samples * 0.10)
    if fade_len > 0:
        fade_in = np.linspace(0, 1, fade_len)
        fade_out = np.linspace(1, 0, fade_len)
        tone[:fade_len] *= fade_in
        tone[-fade_len:] *= fade_out
    return tone

def command_send():
    """Reads from stdin, frames the data, and writes tones to stdout."""
    # Read raw bytes from standard input
    payload_bytes = sys.stdin.buffer.read()
    if not payload_bytes:
        print("Sender: No input data received. Exiting.", file=sys.stderr)
        return

    print(f"Sender: Read {len(payload_bytes)} bytes from stdin.", file=sys.stderr)

    # 1. PREPARE THE FRAME
    # Handshake: Two start bits
    handshake_bits = [2, 2] # Using '2' to represent the START frequency
    # Payload
    payload_bits = bytes_to_bits(payload_bytes)
    # Checksum
    checksum_val = calculate_checksum(payload_bytes)
    checksum_bits = bytes_to_bits(bytes([checksum_val]))
    
    bits_to_transmit = handshake_bits + payload_bits + checksum_bits
    print(f"Sender: Transmitting {len(bits_to_transmit)} total tones.", file=sys.stderr)

    # 2. GENERATE AUDIO
    full_signal = np.array([], dtype=np.float32)
    for bit in bits_to_transmit:
        if bit == 0:
            freq = FREQ_0
        elif bit == 1:
            freq = FREQ_1
        else: # bit == 2
            freq = FREQ_START
        
        tone = generate_tone(freq, BIT_DURATION, SAMPLE_RATE)
        full_signal = np.concatenate([full_signal, tone])
    
    # 3. WRITE TO STDOUT
    scaled_signal = np.int16(full_signal / np.max(np.abs(full_signal)) * 32767)
    with wave.open(sys.stdout.buffer, 'wb') as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SAMPLE_RATE)
        f.writeframes(scaled_signal.tobytes())
    print("Sender: WAV data written to stdout.", file=sys.stderr)


# --- Receiver Logic ---

def find_dominant_bit(data, sample_rate):
    """Analyzes an audio chunk to find the dominant bit (0, 1, or START)."""
    fft_result = np.fft.rfft(data)
    fft_magnitude = np.abs(fft_result)
    fft_freqs = np.fft.rfftfreq(len(data), 1.0 / sample_rate)
    
    freq0_idx = np.argmin(np.abs(fft_freqs - FREQ_0))
    freq1_idx = np.argmin(np.abs(fft_freqs - FREQ_1))
    freq_start_idx = np.argmin(np.abs(fft_freqs - FREQ_START))
    
    mag0 = fft_magnitude[freq0_idx]
    mag1 = fft_magnitude[freq1_idx]
    mag_start = fft_magnitude[freq_start_idx]
    
    AMPLITUDE_THRESHOLD = 1000 # May need tuning for real audio

    # Find the strongest signal among the three possibilities
    if mag_start > AMPLITUDE_THRESHOLD and mag_start > mag1 and mag_start > mag0:
        return 2 # START bit
    elif mag1 > AMPLITUDE_THRESHOLD and mag1 > mag0:
        return 1
    elif mag0 > AMPLITUDE_THRESHOLD:
        return 0
    else:
        return None

def command_recv():
    """Reads WAV data from stdin, decodes the frame, and writes data to stdout."""
    # Read all WAV data from standard input
    with wave.open(sys.stdin.buffer, 'rb') as f:
        if f.getframerate() != SAMPLE_RATE:
            print(f"Receiver Error: Incorrect sample rate.", file=sys.stderr)
            return
        audio_data = np.frombuffer(f.readframes(f.getnframes()), dtype=np.int16)

    # STATE MACHINE
    state = "WAITING_FOR_HANDSHAKE"
    all_bits = []
    handshake_counter = 0

    print("Receiver: Decoding...", file=sys.stderr)
    for i in range(0, len(audio_data), CHUNK_SIZE):
        chunk = audio_data[i:i+CHUNK_SIZE]
        if len(chunk) < CHUNK_SIZE: continue

        bit = find_dominant_bit(chunk, SAMPLE_RATE)
        if bit is None: continue

        if state == "WAITING_FOR_HANDSHAKE":
            if bit == 2: # START bit
                handshake_counter += 1
                if handshake_counter == 2:
                    print("Receiver: Handshake detected.", file=sys.stderr)
                    state = "RECEIVING_DATA"
            else:
                # Reset if we see a non-start bit during handshake
                handshake_counter = 0
        
        elif state == "RECEIVING_DATA":
            # Just collect all data bits until the end
            all_bits.append(bit)

    if not all_bits or len(all_bits) < 8:
        print("Receiver Error: No data payload found after handshake.", file=sys.stderr)
        return

    # Separate payload from checksum (last 8 bits)
    payload_bits = all_bits[:-8]
    checksum_bits = all_bits[-8:]

    # Convert to bytes
    received_bytes = bits_to_bytes(payload_bits)
    received_checksum = bits_to_bytes(checksum_bits)[0]

    # Verify checksum
    expected_checksum = calculate_checksum(received_bytes)

    if received_checksum == expected_checksum:
        print("Receiver: Checksum VALID.", file=sys.stderr)
        print(f"Receiver: Writing {len(received_bytes)} bytes to stdout.", file=sys.stderr)
        sys.stdout.buffer.write(received_bytes)
    else:
        print(f"Receiver Error: Checksum mismatch!", file=sys.stderr)
        print(f"  -> Expected: {expected_checksum}", file=sys.stderr)
        print(f"  -> Received: {received_checksum}", file=sys.stderr)
        sys.exit(1)


# --- Main Execution Block ---

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python birdsong.py [send|recv]", file=sys.stderr)
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "send":
        command_send()
    elif command == "recv":
        command_recv()
    else:
        print(f"Unknown command: '{command}'", file=sys.stderr)
        sys.exit(1)
