# birdsong_fsk_sweeps.py
#
# Active experiment: hybrid FSK + frequency sweeps.
# The file-based FSK path is smoke-tested; sweep mode is exploratory.
#
# Usage from repo root:
#   echo "hello" | python experiments/active/birdsong_fsk_sweeps.py send
#   python experiments/active/birdsong_fsk_sweeps.py recv -i message.wav
#   echo "hello" | python experiments/active/birdsong_fsk_sweeps.py send --sweep-mode

import numpy as np
import sys
import time
import sounddevice as sd
import argparse
from scipy.io import wavfile
import io
from dataclasses import dataclass


class _Logger:
    def __init__(self, verbose=False):
        self.verbose = verbose

    def info(self, *args, **kwargs):
        if self.verbose:
            print(*args, file=sys.stderr, **kwargs)

    def warn(self, *args, **kwargs):
        if self.verbose:
            print(*args, file=sys.stderr, **kwargs)

    def error(self, *args, **kwargs):
        # Always print errors
        print(*args, file=sys.stderr, **kwargs)


log = _Logger()


@dataclass
class FrequencyConfig:
    """Configuration for FSK frequencies."""

    freq0: float = 196.00  # G3 - frequency for bit '0'
    freq1: float = 1760.00  # A6 - frequency for bit '1'
    freq_start: float = 4186.01  # C8 - handshake frequency


@dataclass
class SweepConfig:
    """Configuration for frequency sweep transmission."""

    # Frequency ranges (G-C perfect fourth harmonies)
    low_freq_start: float = 784.0  # G5
    low_freq_end: float = 1046.5  # C6
    high_freq_start: float = 1568.0  # G6
    high_freq_end: float = 2093.0  # C7
    freq_start: float = 4186.01  # C8 - handshake frequency

    # Timing
    symbol_duration: float = 0.020  # 20ms per symbol for 100 bits/s
    overlap_factor: float = 0.1  # 10% overlap between symbols

    @property
    def samples_per_symbol(self):
        """Number of audio samples per symbol."""
        return int(self.symbol_duration * SAMPLE_RATE)

    @property
    def overlap_samples(self):
        """Number of samples for overlap between symbols."""
        return int(self.overlap_factor * self.samples_per_symbol)


# --- Protocol & Configuration ---
SAMPLE_RATE = 44100

# NOTE: Increased duration for better real-world reliability over the air.
BIT_DURATION = 0.05
CHUNK_SIZE = None  # Will be set in main after parsing args

# Default frequency configuration
_default_freq_config = FrequencyConfig()

# Console output constants
CONSOLE_CLEAR_WIDTH = 50

# Sine wave generation
REFERENCE_OCTAVE = 4
SEMITONES_PER_OCTAVE = 12
A_NOTE_INDEX = 9

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


def bits_to_symbols(bits):
    """Converts a list of bits to 2-bit symbols (0-3)."""
    symbols = []
    for i in range(0, len(bits), 2):
        if i + 1 < len(bits):
            symbol = (bits[i] << 1) | bits[i + 1]
            symbols.append(symbol)
        else:
            # Pad with zero if odd number of bits
            symbol = bits[i] << 1
            symbols.append(symbol)
    return symbols


def symbols_to_bits(symbols):
    """Converts 2-bit symbols back to bits."""
    bits = []
    for symbol in symbols:
        bits.append((symbol >> 1) & 1)  # High bit
        bits.append(symbol & 1)  # Low bit
    return bits


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


def generate_frequency_sweep(start_freq, end_freq, duration, sample_rate):
    """Generates a smooth frequency sweep from start_freq to end_freq."""
    num_samples = int(duration * sample_rate)
    t = np.linspace(0, duration, num_samples, endpoint=False)

    # Linear frequency sweep: f(t) = start_freq + (end_freq - start_freq) * t / duration
    # Phase: φ(t) = ∫f(t)dt = start_freq*t + (end_freq - start_freq) * t²/(2*duration)
    freq_rate = (end_freq - start_freq) / duration
    phase = 2 * np.pi * (start_freq * t + 0.5 * freq_rate * t**2)

    sweep = np.sin(phase).astype(np.float32)

    # Apply fade-in/fade-out to prevent audio artifacts
    fade_len = int(num_samples * 0.05)  # 5% fade for sweeps
    if fade_len > 0:
        fade_in = np.linspace(0, 1, fade_len)
        fade_out = np.linspace(1, 0, fade_len)
        sweep[:fade_len] *= fade_in
        sweep[-fade_len:] *= fade_out

    return sweep


def generate_symbol_sweep(symbol, sweep_config):
    """
    Generate audio for a 2-bit symbol using frequency sweeps.

    Symbol encoding:
    0 (00): Low Rising   (784Hz → 1046Hz)
    1 (01): Low Falling  (1046Hz → 784Hz)
    2 (10): High Rising  (1568Hz → 2093Hz)
    3 (11): High Falling (2093Hz → 1568Hz)
    """
    duration = sweep_config.symbol_duration

    if symbol == 0:  # 00: Low Rising
        return generate_frequency_sweep(
            sweep_config.low_freq_start,
            sweep_config.low_freq_end,
            duration,
            SAMPLE_RATE,
        )
    elif symbol == 1:  # 01: Low Falling
        return generate_frequency_sweep(
            sweep_config.low_freq_end,
            sweep_config.low_freq_start,
            duration,
            SAMPLE_RATE,
        )
    elif symbol == 2:  # 10: High Rising
        return generate_frequency_sweep(
            sweep_config.high_freq_start,
            sweep_config.high_freq_end,
            duration,
            SAMPLE_RATE,
        )
    elif symbol == 3:  # 11: High Falling
        return generate_frequency_sweep(
            sweep_config.high_freq_end,
            sweep_config.high_freq_start,
            duration,
            SAMPLE_RATE,
        )
    else:
        raise ValueError(f"Invalid symbol: {symbol} (must be 0-3)")


def command_send(
    output_file, bit_duration, freq_config, sweep_mode=False, sweep_config=None
):
    """Reads from stdin, frames the data, and plays or saves it as audio."""
    payload_bytes = sys.stdin.buffer.read()
    if not payload_bytes:
        log.error("Sender: No input data received. Exiting.")
        return

    log.info(f"Sender: Read {len(payload_bytes)} bytes from stdin.")

    if sweep_mode and sweep_config:
        # Sweep mode: use 2-bit symbols
        payload_bits = bytes_to_bits(payload_bytes)
        checksum_val = calculate_checksum(payload_bytes)
        checksum_bits = bytes_to_bits(bytes([checksum_val]))

        all_bits = payload_bits + checksum_bits
        symbols = bits_to_symbols(all_bits)

        log.info(
            f"Sender: Transmitting {len(symbols)} symbols ({len(all_bits)} bits) in sweep mode."
        )

        # Generate handshake tone + sweep symbols
        handshake_tone = generate_tone(
            sweep_config.freq_start, bit_duration * 2, SAMPLE_RATE
        )
        symbol_sweeps = [
            generate_symbol_sweep(symbol, sweep_config) for symbol in symbols
        ]

        full_signal = np.hstack([handshake_tone] + symbol_sweeps)

    else:
        # Original FSK mode
        handshake_bits = [2, 2]
        payload_bits = bytes_to_bits(payload_bytes)
        checksum_val = calculate_checksum(payload_bytes)
        checksum_bits = bytes_to_bits(bytes([checksum_val]))

        bits_to_transmit = handshake_bits + payload_bits + checksum_bits
        log.info(f"Sender: Transmitting {len(bits_to_transmit)} total tones.")

        full_signal = np.hstack(
            [
                generate_tone(
                    freq_config.freq0
                    if bit == 0
                    else (freq_config.freq1 if bit == 1 else freq_config.freq_start),
                    bit_duration,
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
    "all_symbols": [],
    "handshake_counter": 0,
    "silence_counter": 0,
    "freq_config": None,  # Will be set when receiver starts
    "sweep_mode": False,
    "sweep_config": None,
}


def process_received_bits():
    """Processes the collected bits after a transmission ends."""
    # Clear the last debug line from the screen
    if sys.stdout.isatty():
        print(" " * CONSOLE_CLEAR_WIDTH, end="\r")

    if receiver_state["sweep_mode"]:
        # Process symbols in sweep mode
        if not receiver_state["all_symbols"]:
            log.error("\nReceiver Error: No symbol data found.")
            return

        # Convert symbols to bits
        all_bits = symbols_to_bits(receiver_state["all_symbols"])

        if len(all_bits) < 8:
            log.error("\nReceiver Error: Insufficient data for checksum.")
            return

        payload_bits = all_bits[:-8]
        checksum_bits = all_bits[-8:]

        log.info(
            f"\nReceiver: Decoded {len(receiver_state['all_symbols'])} symbols → {len(all_bits)} bits"
        )

    else:
        # Process bits in FSK mode
        if not receiver_state["all_bits"] or len(receiver_state["all_bits"]) < 8:
            log.error("\nReceiver Error: No data payload found.")
            return

        payload_bits = receiver_state["all_bits"][:-8]
        checksum_bits = receiver_state["all_bits"][-8:]

    received_bytes = bits_to_bytes(payload_bits)
    received_checksum = bits_to_bytes(checksum_bits)[0]
    expected_checksum = calculate_checksum(received_bytes)

    if received_checksum == expected_checksum:
        green = "\033[92m"
        reset = "\033[0m"
        log.info(f"\n{green}Receiver: Checksum VALID.{reset}")
        sys.stdout.buffer.write(received_bytes)
        sys.stdout.flush()
    else:
        log.error(
            f"\nReceiver Error: Checksum mismatch! Expected {expected_checksum}, got {received_checksum}"
        )
        if log.verbose:
            log.info(f"Received bytes (possibly corrupted): {received_bytes}")


def reset_receiver():
    """Resets the state machine to listen for a new message."""
    # Preserve configuration
    freq_config = receiver_state["freq_config"]
    sweep_mode = receiver_state["sweep_mode"]
    sweep_config = receiver_state["sweep_config"]

    receiver_state.update(
        {
            "state": "WAITING_FOR_HANDSHAKE",
            "all_bits": [],
            "all_symbols": [],
            "handshake_counter": 0,
            "silence_counter": 0,
            "freq_config": freq_config,
            "sweep_mode": sweep_mode,
            "sweep_config": sweep_config,
        }
    )
    log.info("\nReceiver: Ready for next transmission.")


def find_dominant_bit(data, sample_rate, freq_config):
    """Analyzes a float32 audio chunk to find the dominant bit."""
    fft_result = np.fft.rfft(data)
    fft_magnitude = np.abs(fft_result)
    fft_freqs = np.fft.rfftfreq(len(data), 1.0 / sample_rate)

    freq0_idx = np.argmin(np.abs(fft_freqs - freq_config.freq0))
    freq1_idx = np.argmin(np.abs(fft_freqs - freq_config.freq1))
    freq_start_idx = np.argmin(np.abs(fft_freqs - freq_config.freq_start))

    mag0 = fft_magnitude[freq0_idx]
    mag1 = fft_magnitude[freq1_idx]
    mag_start = fft_magnitude[freq_start_idx]

    if receiver_state["state"] == "WAITING_FOR_HANDSHAKE":
        log_msg = f"Mags: Start={mag_start:5.2f}, F0={mag0:5.2f}, F1={mag1:5.2f}"
        log.info(log_msg, end="\r")

    # This is important for tuning
    AMPLITUDE_THRESHOLD = 2.0

    if mag_start > AMPLITUDE_THRESHOLD and mag_start > mag1 and mag_start > mag0:
        return 2
    elif mag1 > AMPLITUDE_THRESHOLD and mag1 > mag0:
        return 1
    elif mag0 > AMPLITUDE_THRESHOLD:
        return 0
    else:
        return None


def detect_sweep_symbol(data, sample_rate, sweep_config):
    """Detects which 2-bit symbol based on frequency sweep analysis."""
    from scipy import signal

    # Compute spectrogram to analyze frequency trajectory
    f, t, Sxx = signal.spectrogram(data, sample_rate, nperseg=64, noverlap=32)

    if Sxx.shape[1] < 2:
        return None  # Can't analyze

    # Find dominant frequency at start and end
    start_spectrum = Sxx[:, 0]
    end_spectrum = Sxx[:, -1]

    start_freq = f[np.argmax(start_spectrum)]
    end_freq = f[np.argmax(end_spectrum)]

    # Classify based on frequency band and direction
    low_range = (sweep_config.low_freq_start + sweep_config.low_freq_end) / 2
    high_range = (sweep_config.high_freq_start + sweep_config.high_freq_end) / 2

    # Determine if we're in low or high frequency band
    avg_freq = (start_freq + end_freq) / 2
    is_low_band = avg_freq < (low_range + high_range) / 2

    # Determine sweep direction
    is_rising = end_freq > start_freq

    # Map to symbols
    if is_low_band:
        return 0 if is_rising else 1  # Low Rising=0, Low Falling=1
    else:
        return 2 if is_rising else 3  # High Rising=2, High Falling=3


def audio_callback(indata, frames, time, status):
    """This function is called by sounddevice for each new audio chunk."""
    if status:
        log.error(status)

    if receiver_state["sweep_mode"]:
        # Sweep mode processing
        if receiver_state["state"] == "WAITING_FOR_HANDSHAKE":
            # Check for handshake tone
            bit = find_dominant_bit(
                indata.flatten(), SAMPLE_RATE, receiver_state["freq_config"]
            )
            if bit == 2:  # Handshake frequency detected
                if sys.stdout.isatty():
                    sys.stdout.write(" " * CONSOLE_CLEAR_WIDTH + "\r")
                    sys.stdout.flush()
                log.info(
                    "Receiver: Handshake detected. Receiving sweep data...", flush=True
                )
                receiver_state["state"] = "RECEIVING_DATA"

        elif receiver_state["state"] == "RECEIVING_DATA":
            # Detect symbols in sweep mode
            symbol = detect_sweep_symbol(
                indata.flatten(), SAMPLE_RATE, receiver_state["sweep_config"]
            )

            if symbol is not None:
                if log.verbose:
                    symbol_names = ["L↗", "L↘", "H↗", "H↘"]
                    log.info(symbol_names[symbol], end=" ", flush=True)
                receiver_state["all_symbols"].append(symbol)
                receiver_state["silence_counter"] = 0
            else:
                receiver_state["silence_counter"] += 1
                TIMEOUT_CHUNKS = 10  # Shorter timeout for sweep mode
                if receiver_state["silence_counter"] > TIMEOUT_CHUNKS:
                    process_received_bits()
                    reset_receiver()

    else:
        # Original FSK mode processing
        bit = find_dominant_bit(
            indata.flatten(), SAMPLE_RATE, receiver_state["freq_config"]
        )

        if receiver_state["state"] == "WAITING_FOR_HANDSHAKE":
            if bit == 2:
                receiver_state["handshake_counter"] += 1
                if receiver_state["handshake_counter"] >= 2:
                    if sys.stdout.isatty():
                        sys.stdout.write(" " * CONSOLE_CLEAR_WIDTH + "\r")
                        sys.stdout.flush()
                    log.info(
                        "Receiver: Handshake detected. Receiving data...",
                        flush=True,
                    )
                    receiver_state["state"] = "RECEIVING_DATA"
            else:
                receiver_state["handshake_counter"] = 0

        elif receiver_state["state"] == "RECEIVING_DATA":
            # Only 0 and 1 are valid bits for the received data stream, as the system processes binary data.
            if bit == 0 or bit == 1:
                if log.verbose:
                    log.info("▁" if bit == 0 else "▇", end="", flush=True)
                receiver_state["all_bits"].append(bit)
                receiver_state["silence_counter"] = 0
                n_bits = len(receiver_state["all_bits"])
                if log.verbose:
                    if n_bits % 8 == 0:
                        log.info(" ", end="", flush=True)
                        if n_bits % 48 == 0:
                            log.info("", flush=True)
            else:
                # This handles both silence (bit is None) and stray START bits
                receiver_state["silence_counter"] += 1
                TIMEOUT_CHUNKS = 20
                if receiver_state["silence_counter"] > TIMEOUT_CHUNKS:
                    process_received_bits()
                    reset_receiver()


def process_wav_data(wav_source, chunk_size):
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
                f"Fatal Receiver Error: WAV file has sample rate {rate}, but script requires {SAMPLE_RATE}."
            )
            return

        if data.dtype == np.int16:
            data = data.astype(np.float32) / 32767.0
        elif data.dtype != np.float32:
            log.error(
                f"Receiver Error: Unsupported WAV data type '{data.dtype}'. Trying to proceed."
            )

        # Process the file chunk by chunk
        num_samples = len(data)
        for i in range(0, num_samples, chunk_size):
            chunk = data[i : i + chunk_size]
            if len(chunk) < chunk_size:
                chunk = np.pad(chunk, (0, chunk_size - len(chunk)), "constant")

            audio_callback(chunk, len(chunk), None, None)

        # After processing the file, if data is still being received, finalize it.
        if receiver_state["state"] == "RECEIVING_DATA":
            process_received_bits()
            reset_receiver()

    except FileNotFoundError:
        log.error(f"Receiver Error: File not found at '{wav_source}'")
    except Exception as e:
        log.error(f"An error occurred while processing the WAV data: {e}")


def command_recv(
    input_file, chunk_size, freq_config, sweep_mode=False, sweep_config=None
):
    """Listens, decodes a stream, or processes a WAV file from a file or stdin."""
    receiver_state["freq_config"] = freq_config
    receiver_state["sweep_mode"] = sweep_mode
    receiver_state["sweep_config"] = sweep_config

    if sweep_mode:
        # Adjust chunk size for sweep mode
        chunk_size = sweep_config.samples_per_symbol
    # Handle explicit stdin ('-') or implicit pipe (no tty)
    if (input_file and input_file == "-") or (
        not input_file and not sys.stdin.isatty()
    ):
        log.info("Receiver: Reading from stdin pipe...")
        process_wav_data(sys.stdin.buffer, chunk_size)
    # Handle a file path
    elif input_file:
        log.info(f"Receiver: Reading from '{input_file}'...")
        process_wav_data(input_file, chunk_size)
    # Default to microphone
    else:
        log.info("Receiver: Listening to microphone... Press Ctrl+C to stop.")
        try:
            with sd.InputStream(
                samplerate=SAMPLE_RATE,
                blocksize=chunk_size,
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


# --- Argument Parsing Helper ---
def get_frequency(note_name):
    """Converts a musical note name (e.g., 'A4') to its frequency in Hz."""
    NOTES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

    note_str = "".join(filter(str.isalpha, note_name)).upper()
    sharp_count = note_name.count("#")
    flat_count = note_name.count("b")
    note_str += "#" * sharp_count
    note_str += "b" * flat_count

    octave_str = "".join(filter(str.isdigit, note_name))
    if not octave_str:
        raise ValueError("Note name must include an octave number (e.g., 'A4')")
    octave = int(octave_str)

    try:
        pos = NOTES.index(note_str)
    except ValueError:
        raise ValueError(f"Unknown note '{note_str}'")

    dist = (octave - REFERENCE_OCTAVE) * SEMITONES_PER_OCTAVE + (pos - A_NOTE_INDEX)
    return 440 * (2 ** (1 / 12)) ** dist


def freq_type(value):
    """Custom argparse type that accepts a float or a musical note string (e.g., 'C4')."""
    try:
        return float(value)
    except ValueError:
        try:
            return get_frequency(value)
        except (ValueError, KeyError, IndexError) as e:
            raise argparse.ArgumentTypeError(
                f"Invalid frequency or note '{value}'. Use a number (e.g., 440.0) or a note (e.g., 'A4'). Details: {e}"
            )


# --- Main Execution Block ---

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Transmit or receive data using Frequency-Shift Keying (FSK) modulation over audio.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # Parent parser for shared arguments
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose status messages to stderr.",
    )
    parent_parser.add_argument(
        "--bit-duration",
        type=float,
        default=0.05,
        help="Duration of each data bit in seconds.",
    )
    parent_parser.add_argument(
        "--freq0",
        type=freq_type,
        default=196.00,
        help='Frequency in Hz for bit "0" (or a note like "G3").',
    )
    parent_parser.add_argument(
        "--freq1",
        type=freq_type,
        default=1760.00,
        help='Frequency in Hz for bit "1" (or a note like "A6").',
    )
    parent_parser.add_argument(
        "--freq-start",
        type=freq_type,
        default=4186.01,
        help='Frequency in Hz for handshake signal (or a note like "C8"). Lower frequencies are less disturbing to pets.',
    )

    # Sweep mode arguments
    parent_parser.add_argument(
        "--sweep-mode",
        action="store_true",
        help="Enable frequency sweep mode for 5x faster transmission (100 bits/s)",
    )
    parent_parser.add_argument(
        "--symbol-duration",
        type=float,
        default=0.020,
        help="Duration of each symbol in sweep mode (seconds)",
    )
    parent_parser.add_argument(
        "--sweep-low-start",
        type=freq_type,
        default=784.0,
        help="Low sweep start frequency (G5)",
    )
    parent_parser.add_argument(
        "--sweep-low-end",
        type=freq_type,
        default=1046.5,
        help="Low sweep end frequency (C6)",
    )
    parent_parser.add_argument(
        "--sweep-high-start",
        type=freq_type,
        default=1568.0,
        help="High sweep start frequency (G6)",
    )
    parent_parser.add_argument(
        "--sweep-high-end",
        type=freq_type,
        default=2093.0,
        help="High sweep end frequency (C7)",
    )

    subparsers = parser.add_subparsers(
        dest="command", required=True, help="Available commands"
    )

    # Sender command
    parser_send = subparsers.add_parser(
        "send", help="Transmit data from stdin.", parents=[parent_parser]
    )
    parser_send.add_argument(
        "-o",
        "--output",
        metavar="FILE",
        help="Write audio to a WAV file. Use '-' for stdout.",
    )

    # Receiver command
    parser_recv = subparsers.add_parser(
        "recv", help="Receive data from microphone or file.", parents=[parent_parser]
    )
    parser_recv.add_argument(
        "-i",
        "--input",
        metavar="FILE",
        help="Read audio from a WAV file. Use '-' for stdin.",
    )

    args = parser.parse_args()

    # --- Update global configuration from CLI arguments ---
    log.verbose = args.verbose

    # Create frequency configuration from CLI arguments
    freq_config = FrequencyConfig(
        freq0=args.freq0, freq1=args.freq1, freq_start=getattr(args, "freq_start")
    )

    # Create sweep configuration if sweep mode is enabled
    sweep_config = None
    if args.sweep_mode:
        sweep_config = SweepConfig(
            low_freq_start=args.sweep_low_start,
            low_freq_end=args.sweep_low_end,
            high_freq_start=args.sweep_high_start,
            high_freq_end=args.sweep_high_end,
            freq_start=getattr(args, "freq_start"),
            symbol_duration=args.symbol_duration,
        )
        log.info(
            f"Sweep mode enabled: {1 / args.symbol_duration:.0f} symbols/s ≈ {2 / args.symbol_duration:.0f} bits/s"
        )

    # Calculate chunk size
    if args.sweep_mode and sweep_config:
        chunk_size = sweep_config.samples_per_symbol
    else:
        chunk_size = int(SAMPLE_RATE * args.bit_duration)

    # --- Execute command ---
    if args.command == "send":
        command_send(
            output_file=args.output,
            bit_duration=args.bit_duration,
            freq_config=freq_config,
            sweep_mode=args.sweep_mode,
            sweep_config=sweep_config,
        )
    elif args.command == "recv":
        command_recv(
            input_file=args.input,
            chunk_size=chunk_size,
            freq_config=freq_config,
            sweep_mode=args.sweep_mode,
            sweep_config=sweep_config,
        )
    else:
        # This case is technically unreachable due to `required=True`
        log.error(f"Unknown command: '{args.command}'")
        sys.exit(1)
