# sendit_poc.py
#
# Proof of Concept: Generates a sequence of tones and saves them to a WAV file.
# This version uses Python's built-in 'wave' module and has no external dependencies besides numpy.
# Usage:
# uv run python3 sendit_poc.py
# afplay poc_signal.wav

import numpy as np
import time
import wave # Use Python's built-in wave module

# --- Configuration based on the specification ---
SAMPLE_RATE = 44100  # Standard CD-quality audio sample rate in Hz
BIT_DURATION = 0.05  # Duration of each tone in seconds (50ms)
FREQ_0 = 261.63      # Frequency for bit '0' (C4)
FREQ_1 = 392.00      # Frequency for bit '1' (G4)
OUTPUT_FILENAME = "poc_signal.wav" # The output file

# The hardcoded sequence for this PoC, as per the spec
POC_SEQUENCE = [1, 0, 1, 0]

def generate_tone(frequency, duration, sample_rate):
    """
    Generates a pure sine wave tone for a given frequency and duration.

    Args:
        frequency (float): The frequency of the tone in Hz.
        duration (float): The duration of the tone in seconds.
        sample_rate (int): The number of samples per second.

    Returns:
        np.ndarray: A 1D NumPy array representing the audio signal.
    """
    # Generate a sequence of numbers from 0 to duration, with sample_rate steps
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    
    # Generate the sine wave: 2 * pi * frequency * t
    tone = np.sin(frequency * t * 2 * np.pi)
    
    # Apply a simple fade-in/fade-out to prevent clicking sounds between tones
    # This is a basic "windowing" function
    fade_len = int(sample_rate * 0.005) # 5ms fade
    fade_in = np.linspace(0, 1, fade_len)
    fade_out = np.linspace(1, 0, fade_len)
    
    tone[:fade_len] *= fade_in
    tone[-fade_len:] *= fade_out

    return tone

def main():
    """
    Main function to generate the PoC audio sequence and save it to a file.
    """
    print("--- Sender PoC (File Mode, using 'wave' module) ---")
    print(f"Preparing to generate signal for sequence: {POC_SEQUENCE}")
    print(f"Bit '0' Freq: {FREQ_0} Hz (C4), Bit '1' Freq: {FREQ_1} Hz (G4)")
    
    # Create an empty numpy array to hold the full audio signal
    # Using float32, which is common for audio processing
    full_signal = np.array([], dtype=np.float32)
    
    # Generate the tone for each bit in the sequence and concatenate them
    for bit in POC_SEQUENCE:
        frequency = FREQ_1 if bit == 1 else FREQ_0
        print(f"Generating tone for bit '{bit}' at {frequency:.2f} Hz...")
        tone = generate_tone(frequency, BIT_DURATION, SAMPLE_RATE)
        full_signal = np.concatenate([full_signal, tone])
            
    print(f"\nSaving audio signal to '{OUTPUT_FILENAME}'...")
    
    # --- Save to WAV file using the built-in 'wave' module ---
    # Normalize the float32 signal to the 16-bit integer range (-32767 to 32767)
    scaled_signal = np.int16(full_signal / np.max(np.abs(full_signal)) * 32767)
    
    # Open the file in write-binary mode
    with wave.open(OUTPUT_FILENAME, 'wb') as f:
        f.setnchannels(1)  # Mono audio
        f.setsampwidth(2)  # 2 bytes per sample (16-bit)
        f.setframerate(SAMPLE_RATE)
        f.writeframes(scaled_signal.tobytes()) # Write the raw bytes of the signal
    
    print("File saved successfully.")

if __name__ == "__main__":
    main()

