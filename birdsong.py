# birdsong.py
#
# Final Version: Transmits data from stdin using real-time audio.
#
# Sender Usage:
#   echo "hello" | python birdsong.py send
#
# Receiver Usage:
#   python birdsong.py recv

import numpy as np
import sys
import time
import sounddevice as sd

# --- Protocol & Configuration ---
SAMPLE_RATE = 44100
# NOTE: Increased duration for better real-world reliability over the air.
BIT_DURATION = 0.05
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
        for i in range(7, -1, -1):
            bits.append((byte >> i) & 1)
    return bits

def bits_to_bytes(bits):
    """Converts a list of bits back into bytes."""
    byte_list = []
    for i in range(0, len(bits), 8):
        byte_chunk = bits[i:i+8]
        if len(byte_chunk) < 8:
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
    """Reads from stdin, frames the data, and plays it as audio."""
    payload_bytes = sys.stdin.buffer.read()
    if not payload_bytes:
        print("Sender: No input data received. Exiting.", file=sys.stderr)
        return

    print(f"Sender: Read {len(payload_bytes)} bytes from stdin.", file=sys.stderr)

    handshake_bits = [2, 2]
    payload_bits = bytes_to_bits(payload_bytes)
    checksum_val = calculate_checksum(payload_bytes)
    checksum_bits = bytes_to_bits(bytes([checksum_val]))
    
    bits_to_transmit = handshake_bits + payload_bits + checksum_bits
    print(f"Sender: Transmitting {len(bits_to_transmit)} total tones.", file=sys.stderr)

    full_signal = np.array([], dtype=np.float32)
    for bit in bits_to_transmit:
        freq = FREQ_0 if bit == 0 else (FREQ_1 if bit == 1 else FREQ_START)
        tone = generate_tone(freq, BIT_DURATION, SAMPLE_RATE)
        full_signal = np.concatenate([full_signal, tone])
    
    print("Sender: Playing audio signal...", file=sys.stderr)
    sd.play(full_signal, SAMPLE_RATE)
    sd.wait()
    print("Sender: Playback complete.", file=sys.stderr)

# --- Receiver Logic ---

# Global state for the receiver's callback
receiver_state = {
    "state": "WAITING_FOR_HANDSHAKE",
    "all_bits": [],
    "handshake_counter": 0,
    "silence_counter": 0,
}

def process_received_bits():
    """Processes the collected bits after a transmission ends."""
    # Clear the last debug line from the screen
    print(" " * 50, end='\r', file=sys.stderr)
    if not receiver_state["all_bits"] or len(receiver_state["all_bits"]) < 8:
        print("\nReceiver Error: No data payload found.", file=sys.stderr)
        return

    payload_bits = receiver_state["all_bits"][:-8]
    checksum_bits = receiver_state["all_bits"][-8:]

    received_bytes = bits_to_bytes(payload_bits)
    received_checksum = bits_to_bytes(checksum_bits)[0]
    expected_checksum = calculate_checksum(received_bytes)

    if received_checksum == expected_checksum:
        print("\nReceiver: Checksum VALID.", file=sys.stderr)
        sys.stdout.buffer.write(received_bytes)
        sys.stdout.flush()
    else:
        print(f"\nReceiver Error: Checksum mismatch! Expected {expected_checksum}, got {received_checksum}", file=sys.stderr)

def reset_receiver():
    """Resets the state machine to listen for a new message."""
    receiver_state.update({
        "state": "WAITING_FOR_HANDSHAKE", "all_bits": [], 
        "handshake_counter": 0, "silence_counter": 0
    })
    print("\nReceiver: Ready for next transmission.", file=sys.stderr)

def find_dominant_bit(data, sample_rate):
    """Analyzes a float32 audio chunk to find the dominant bit."""
    fft_result = np.fft.rfft(data)
    fft_magnitude = np.abs(fft_result)
    fft_freqs = np.fft.rfftfreq(len(data), 1.0 / sample_rate)
    
    freq0_idx = np.argmin(np.abs(fft_freqs - FREQ_0))
    freq1_idx = np.argmin(np.abs(fft_freqs - FREQ_1))
    freq_start_idx = np.argmin(np.abs(fft_freqs - FREQ_START))
    
    mag0 = fft_magnitude[freq0_idx]
    mag1 = fft_magnitude[freq1_idx]
    mag_start = fft_magnitude[freq_start_idx]
    
    if receiver_state["state"] == "WAITING_FOR_HANDSHAKE":
        log_msg = f"Mags: Start={mag_start:5.2f}, F0={mag0:5.2f}, F1={mag1:5.2f}"
        print(log_msg, end='\r', file=sys.stderr)

    AMPLITUDE_THRESHOLD = 2.0

    if mag_start > AMPLITUDE_THRESHOLD and mag_start > mag1 and mag_start > mag0: return 2
    elif mag1 > AMPLITUDE_THRESHOLD and mag1 > mag0: return 1
    elif mag0 > AMPLITUDE_THRESHOLD: return 0
    else: return None

def audio_callback(indata, frames, time, status):
    """This function is called by sounddevice for each new audio chunk."""
    if status: print(status, file=sys.stderr)
    
    bit = find_dominant_bit(indata.flatten(), SAMPLE_RATE)

    if receiver_state["state"] == "WAITING_FOR_HANDSHAKE":
        if bit == 2:
            receiver_state["handshake_counter"] += 1
            if receiver_state["handshake_counter"] >= 2:
                print(" " * 50, end='\r', file=sys.stderr)
                print("Receiver: Handshake detected. Receiving data...", end="", flush=True, file=sys.stderr)
                receiver_state["state"] = "RECEIVING_DATA"
        else:
            receiver_state["handshake_counter"] = 0
    
    elif receiver_state["state"] == "RECEIVING_DATA":
        # --- FIX: Only append valid data bits (0 or 1) ---
        if bit == 0 or bit == 1:
            print(".", end="", flush=True, file=sys.stderr)
            receiver_state["all_bits"].append(bit)
            receiver_state["silence_counter"] = 0
        else:
            # This handles both silence (bit is None) and stray START bits
            receiver_state["silence_counter"] += 1
            TIMEOUT_CHUNKS = 20
            if receiver_state["silence_counter"] > TIMEOUT_CHUNKS:
                process_received_bits()
                reset_receiver()

def command_recv():
    """Listens to the microphone and decodes a real-time stream."""
    print("Receiver: Listening to microphone... Press Ctrl+C to stop.", file=sys.stderr)
    try:
        with sd.InputStream(samplerate=SAMPLE_RATE, blocksize=CHUNK_SIZE, channels=1, dtype='float32', callback=audio_callback):
            while True: time.sleep(1)
    except KeyboardInterrupt:
        print("\nReceiver: Stopped by user.", file=sys.stderr)
    except Exception as e:
        print(f"An error occurred: {e}", file=sys.stderr)

# --- Main Execution Block ---

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python birdsong.py [send|recv]", file=sys.stderr)
        sys.exit(1)

    command = sys.argv[1].lower()
    if command == "send": command_send()
    elif command == "recv": command_recv()
    else:
        print(f"Unknown command: '{command}'", file=sys.stderr)
        sys.exit(1)
