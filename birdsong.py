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
import argparse
from scipy.io import wavfile
import io


class _Logger:
    def __init__(self, verbose=False):
        self.verbose = verbose

    def info(self, *args, **kwargs):
        if self.verbose:
            print(*args, file=sys.stderr, **kwargs)

    def error(self, *args, **kwargs):
        # Always print errors
        print(*args, file=sys.stderr, **kwargs)


log = _Logger()

# --- Protocol & Configuration ---
SAMPLE_RATE = 44100
# NOTE: Increased duration for better real-world reliability over the air.
BIT_DURATION = 0.05
CHUNK_SIZE = int(SAMPLE_RATE * BIT_DURATION)

# Frequencies chosen for wide separation and performance
FREQ_0 = 196.00  # G3
FREQ_1 = 1760.00  # A6
FREQ_START = 4186.01  # C8 (A high, distinct frequency for the handshake)

# Console output constants
CONSOLE_CLEAR_WIDTH = 50

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
        byte_chunk = bits[i : i + 8]
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
    # Convert the tone from float64 to float32 to ensure compatibility with audio processing libraries and reduce memory usage.
    tone = tone.astype(np.float32)
    fade_len = int(num_samples * 0.10)
    if fade_len > 0:
        fade_in = np.linspace(0, 1, fade_len)
        fade_out = np.linspace(1, 0, fade_len)
        tone[:fade_len] *= fade_in
        tone[-fade_len:] *= fade_out
    return tone


def command_send(output_file=None):
    """Reads from stdin, frames the data, and plays or saves it as audio."""
    payload_bytes = sys.stdin.buffer.read()
    if not payload_bytes:
        log.error("Sender: No input data received. Exiting.")
        return

    log.info(f"Sender: Read {len(payload_bytes)} bytes from stdin.")

    handshake_bits = [2, 2]
    payload_bits = bytes_to_bits(payload_bytes)
    checksum_val = calculate_checksum(payload_bytes)
    checksum_bits = bytes_to_bits(bytes([checksum_val]))

    bits_to_transmit = handshake_bits + payload_bits + checksum_bits
    log.info(f"Sender: Transmitting {len(bits_to_transmit)} total tones.")

    full_signal = np.hstack(
        [
            generate_tone(
                FREQ_0 if bit == 0 else (FREQ_1 if bit == 1 else FREQ_START),
                BIT_DURATION,
                SAMPLE_RATE,
            )
            for bit in bits_to_transmit
        ]
    )

    if output_file:
        if output_file == "-":
            log.info("Sender: Writing audio to stdout...")
            try:
                # Use an in-memory buffer to create the WAV file, then write to stdout
                buffer = io.BytesIO()
                wavfile.write(buffer, SAMPLE_RATE, full_signal)
                sys.stdout.buffer.write(buffer.getvalue())
            except Exception as e:
                log.error(f"Error writing WAV to stdout: {e}")
        else:
            log.info(f"Sender: Writing audio to {output_file}...")
            try:
                wavfile.write(output_file, SAMPLE_RATE, full_signal)
                log.info("Sender: File written successfully.")
            except Exception as e:
                log.error(f"Error writing WAV file: {e}")
    else:
        log.info("Sender: Playing audio signal...")
        sd.play(full_signal, SAMPLE_RATE)
        sd.wait()
        log.info("Sender: Playback complete.")


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
    log.info(" " * CONSOLE_CLEAR_WIDTH, end="\r")
    if not receiver_state["all_bits"] or len(receiver_state["all_bits"]) < 8:
        log.error("\nReceiver Error: No data payload found.")
        return

    payload_bits = receiver_state["all_bits"][:-8]
    checksum_bits = receiver_state["all_bits"][-8:]

    received_bytes = bits_to_bytes(payload_bits)
    received_checksum = bits_to_bytes(checksum_bits)[0]
    expected_checksum = calculate_checksum(received_bytes)

    if received_checksum == expected_checksum:
        log.info("\nReceiver: Checksum VALID.")
        sys.stdout.buffer.write(received_bytes)
        sys.stdout.flush()
    else:
        log.error(
            f"\nReceiver Error: Checksum mismatch! Expected {expected_checksum}, got {received_checksum}"
        )


def reset_receiver():
    """Resets the state machine to listen for a new message."""
    receiver_state.update(
        {
            "state": "WAITING_FOR_HANDSHAKE",
            "all_bits": [],
            "handshake_counter": 0,
            "silence_counter": 0,
        }
    )
    log.info("\nReceiver: Ready for next transmission.")


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
        log.info(log_msg, end="\r")

    AMPLITUDE_THRESHOLD = 2.0

    if mag_start > AMPLITUDE_THRESHOLD and mag_start > mag1 and mag_start > mag0:
        return 2
    elif mag1 > AMPLITUDE_THRESHOLD and mag1 > mag0:
        return 1
    elif mag0 > AMPLITUDE_THRESHOLD:
        return 0
    else:
        return None


def audio_callback(indata, frames, time, status):
    """This function is called by sounddevice for each new audio chunk."""
    if status:
        log.error(status)

    bit = find_dominant_bit(indata.flatten(), SAMPLE_RATE)

    if receiver_state["state"] == "WAITING_FOR_HANDSHAKE":
        if bit == 2:
            receiver_state["handshake_counter"] += 1
            if receiver_state["handshake_counter"] >= 2:
                log.info(" " * CONSOLE_CLEAR_WIDTH, end="\r")
                log.info(
                    "Receiver: Handshake detected. Receiving data...",
                    end="",
                    flush=True,
                )
                receiver_state["state"] = "RECEIVING_DATA"
        else:
            receiver_state["handshake_counter"] = 0

    elif receiver_state["state"] == "RECEIVING_DATA":
        # --- FIX: Only append valid data bits (0 or 1) ---
        if bit == 0 or bit == 1:
            log.info(".", end="", flush=True)
            receiver_state["all_bits"].append(bit)
            receiver_state["silence_counter"] = 0
        else:
            # This handles both silence (bit is None) and stray START bits
            receiver_state["silence_counter"] += 1
            TIMEOUT_CHUNKS = 20
            if receiver_state["silence_counter"] > TIMEOUT_CHUNKS:
                process_received_bits()
                reset_receiver()


def process_wav_data(wav_source):
    """Reads and processes audio data from a WAV source (file path or stream)."""
    try:
        # If reading from a stream (like stdin), read it all into memory first
        # as wavfile.read may need to seek.
        if hasattr(wav_source, "read"):
            wav_bytes = wav_source.read()
            wav_stream = io.BytesIO(wav_bytes)
            rate, data = wavfile.read(wav_stream)
        else:  # It's a file path
            rate, data = wavfile.read(wav_source)

        if rate != SAMPLE_RATE:
            log.error(
                f"Receiver Error: WAV file has sample rate {rate}, but script requires {SAMPLE_RATE}."
            )
            return

        if data.dtype == np.int16:
            data = data.astype(np.float32) / 32767.0
        elif data.dtype != np.float32:
            log.info(
                f"Receiver Warning: Unsupported WAV data type '{data.dtype}'. Trying to proceed."
            )

        # Process the file chunk by chunk
        num_samples = len(data)
        for i in range(0, num_samples, CHUNK_SIZE):
            chunk = data[i : i + CHUNK_SIZE]
            if len(chunk) < CHUNK_SIZE:
                chunk = np.pad(chunk, (0, CHUNK_SIZE - len(chunk)), "constant")

            audio_callback(chunk, len(chunk), None, None)

        # After processing the file, if data is still being received, finalize it.
        if receiver_state["state"] == "RECEIVING_DATA":
            process_received_bits()
            reset_receiver()

    except FileNotFoundError:
        log.error(f"Receiver Error: File not found at '{wav_source}'")
    except Exception as e:
        log.error(f"An error occurred while processing the WAV data: {e}")


def command_recv(input_file=None):
    """Listens, decodes a stream, or processes a WAV file from a file or stdin."""
    # Handle explicit stdin ('-') or implicit pipe (no tty)
    if (input_file and input_file == "-") or (
        not input_file and not sys.stdin.isatty()
    ):
        log.info("Receiver: Reading from stdin pipe...")
        process_wav_data(sys.stdin.buffer)
    # Handle a file path
    elif input_file:
        log.info(f"Receiver: Reading from '{input_file}'...")
        process_wav_data(input_file)
    # Default to microphone
    else:
        log.info("Receiver: Listening to microphone... Press Ctrl+C to stop.")
        try:
            with sd.InputStream(
                samplerate=SAMPLE_RATE,
                blocksize=CHUNK_SIZE,
                channels=1,
                dtype="float32",
                callback=audio_callback,
            ):
                while True:
                    time.sleep(1)
        except KeyboardInterrupt:
            log.info("\nReceiver: Stopped by user.")
        except Exception as e:
            log.error(f"An error occurred: {e}")


# --- Main Execution Block ---

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Transmit data as audio signals (birdsong)."
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose status messages to stderr.",
    )
    subparsers = parser.add_subparsers(
        dest="command", required=True, help="Available commands"
    )

    # --- Send Command ---
    parser_send = subparsers.add_parser(
        "send", help="Encode data from stdin and transmit it."
    )
    parser_send.add_argument(
        "-o",
        "--output",
        metavar="FILE",
        help="Write audio to a WAV file. Use '-' for stdout.",
    )

    # --- Recv Command ---
    parser_recv = subparsers.add_parser(
        "recv", help="Listen for audio and decode data to stdout."
    )
    parser_recv.add_argument(
        "-i",
        "--input",
        metavar="FILE",
        help="Read audio from a WAV file. Use '-' for stdin.",
    )

    args = parser.parse_args()
    log.verbose = args.verbose

    if args.command == "send":
        command_send(output_file=args.output)
    elif args.command == "recv":
        command_recv(input_file=args.input)
    else:
        # This part should not be reachable due to `required=True`
        log.error(f"Unknown command: '{args.command}'")
        sys.exit(1)
