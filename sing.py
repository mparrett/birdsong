# rs_poc.py
#
# Proof of Concept: A single-file script to either send (generate a WAV file)
# or receive (decode a WAV file) an acoustic signal.
#
# Usage:
#   python rs_poc.py send  # Creates 'poc_signal.wav'
#   python rs_poc.py recv  # Reads 'poc_signal.wav' and decodes it

import numpy as np
import wave
import sys

# --- Shared Configuration ---
SAMPLE_RATE = 44100  # Standard CD-quality audio sample rate in Hz
BIT_DURATION = 0.05  # Duration of each tone in seconds (50ms)
CHUNK_SIZE = int(SAMPLE_RATE * BIT_DURATION) # Samples per bit
FREQ_0 = 261.63      # Frequency for bit '0' (C4)
FREQ_1 = 392.00      # Frequency for bit '1' (G4)
FILENAME = "poc_signal.wav" # The file used for communication

# The hardcoded sequence for this PoC
POC_SEQUENCE = [1, 0, 1, 0]

# --- Sender Logic ---

def generate_tone(frequency, duration, sample_rate):
    """Generates a pure sine wave tone."""
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    tone = np.sin(frequency * t * 2 * np.pi)
    
    # Apply a simple fade-in/fade-out to prevent clicking
    fade_len = int(sample_rate * 0.005) # 5ms fade
    fade_in = np.linspace(0, 1, fade_len)
    fade_out = np.linspace(1, 0, fade_len)
    
    tone[:fade_len] *= fade_in
    tone[-fade_len:] *= fade_out
    return tone

def command_send():
    """Generates the PoC audio sequence and saves it to a file."""
    print("--- Command: send ---")
    print(f"Preparing to generate signal for sequence: {POC_SEQUENCE}")
    
    full_signal = np.array([], dtype=np.float32)
    
    for bit in POC_SEQUENCE:
        frequency = FREQ_1 if bit == 1 else FREQ_0
        print(f"Generating tone for bit '{bit}' at {frequency:.2f} Hz...")
        tone = generate_tone(frequency, BIT_DURATION, SAMPLE_RATE)
        full_signal = np.concatenate([full_signal, tone])
            
    print(f"\nSaving audio signal to '{FILENAME}'...")
    
    scaled_signal = np.int16(full_signal / np.max(np.abs(full_signal)) * 32767)
    
    with wave.open(FILENAME, 'wb') as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SAMPLE_RATE)
        f.writeframes(scaled_signal.tobytes())
    
    print("File saved successfully.")

# --- Receiver Logic ---

def find_dominant_bit(data, sample_rate):
    """Analyzes an audio chunk using FFT to find the dominant bit."""
    # Perform FFT
    fft_result = np.fft.rfft(data)
    fft_magnitude = np.abs(fft_result)
    fft_freqs = np.fft.rfftfreq(len(data), 1.0 / sample_rate)
    
    # Find the magnitude at the specific index for FREQ_0 and FREQ_1
    freq0_idx = np.argmin(np.abs(fft_freqs - FREQ_0))
    freq1_idx = np.argmin(np.abs(fft_freqs - FREQ_1))
    
    mag0 = fft_magnitude[freq0_idx]
    mag1 = fft_magnitude[freq1_idx]
    
    # An amplitude threshold is needed to distinguish signal from silence/noise.
    # This value may need tuning based on recording levels.
    AMPLITUDE_THRESHOLD = 1000 

    if mag0 > AMPLITUDE_THRESHOLD and mag0 > mag1:
        return 0
    elif mag1 > AMPLITUDE_THRESHOLD and mag1 > mag0:
        return 1
    else:
        return None

def command_recv():
    """Reads a WAV file and decodes the tones back into bits."""
    print("--- Command: recv ---")
    try:
        print(f"Reading audio data from '{FILENAME}'...")
        with wave.open(FILENAME, 'rb') as f:
            if f.getframerate() != SAMPLE_RATE:
                print(f"Error: File sample rate ({f.getframerate()}) does not match.")
                return
            
            n_frames = f.getnframes()
            audio_bytes = f.readframes(n_frames)
            # Convert byte data to numpy array of 16-bit integers
            audio_data = np.frombuffer(audio_bytes, dtype=np.int16)

    except FileNotFoundError:
        print(f"Error: Input file '{FILENAME}' not found.")
        print("Please run 'python rs_poc.py send' first to generate it.")
        return
    
    print("Decoding bits from signal...")
    detected_bits = []
    
    # Iterate through the audio data in chunks
    for i in range(0, len(audio_data), CHUNK_SIZE):
        chunk = audio_data[i:i+CHUNK_SIZE]
        
        if len(chunk) < CHUNK_SIZE:
            continue

        bit = find_dominant_bit(chunk, SAMPLE_RATE)
        if bit is not None:
            detected_bits.append(bit)

    print("\n--- Decoding Complete ---")
    print(f"Original sequence:   {POC_SEQUENCE}")
    print(f"Detected sequence:   {detected_bits}")
    
    if detected_bits == POC_SEQUENCE:
        print("Success: Detected sequence matches original.")
    else:
        print("Failure: Detected sequence does not match.")


# --- Main Execution Block ---

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python rs_poc.py [send|recv]")
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "send":
        command_send()
    elif command == "recv":
        command_recv()
    else:
        print(f"Unknown command: '{command}'")
        print("Usage: python rs_poc.py [send|recv]")
        sys.exit(1)

