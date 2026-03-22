# birdsong_2band.py
#
# Archived experiment: early multiband branch superseded by the 8-band variant.
# Preserved for comparison, not maintained as a current path.

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

    freq0: float = 440  # 196.00  # G3 - frequency for bit '0'
    freq1: float = 1760.00  # A6 - frequency for bit '1'
    freq_start: float = 196.0  # G3 (low) 196.0; or C8 (high) 4186.01 - handshake frequency; lower is less disturbing for humans

    # Multi-band CPFSK settings
    multi_band: bool = True  # Enable multi-band mode for 2x data rate
    freq_low: float = 196.0  # G3 - Low frequency band
    freq_high: float = 1760.0  # A6 - High frequency band


# --- Protocol & Configuration ---
SAMPLE_RATE = 44100

# NOTE: Increased duration for better real-world reliability over the air.
BIT_DURATION = 0.05
CHUNK_SIZE = None  # Will be set in main after parsing args

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


def bits_to_symbols(bits):
    """Converts a list of bits into 2-bit symbols (0-3) for multi-band encoding."""
    symbols = []
    # Pad with 0 if odd number of bits
    if len(bits) % 2 == 1:
        bits = bits + [0]

    for i in range(0, len(bits), 2):
        symbol = bits[i] * 2 + bits[i + 1]  # Convert 2 bits to symbol 0-3
        symbols.append(symbol)
    return symbols


def symbols_to_bits(symbols):
    """Converts 2-bit symbols back to individual bits."""
    bits = []
    for symbol in symbols:
        bits.append((symbol >> 1) & 1)  # High bit
        bits.append(symbol & 1)  # Low bit
    return bits


def get_band_amplitudes(symbol):
    """Get amplitude values for low and high bands based on symbol.

    Returns (low_amplitude, high_amplitude) for smooth band control:
    Symbol 0 (00): (0.0, 0.0) - silence
    Symbol 1 (01): (1.0, 0.0) - low band only
    Symbol 2 (10): (0.0, 1.0) - high band only
    Symbol 3 (11): (0.7, 0.7) - both bands (chord)
    """
    if symbol == 0:
        return (0.0, 0.0)  # Silence
    elif symbol == 1:
        return (1.0, 0.0)  # Low band only
    elif symbol == 2:
        return (0.0, 1.0)  # High band only
    elif symbol == 3:
        return (0.7, 0.7)  # Both bands (chord, reduced to prevent clipping)
    else:
        return (0.0, 0.0)  # Default to silence for invalid symbols


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


def generate_cpfsk_signal(bitstream, bit_duration, sample_rate, freq_config):
    """Generates a continuous phase FSK signal from a bitstream."""
    # Handle different bit types
    processed_bitstream = []
    for bit in bitstream:
        if bit is None:
            # Silence - use zero (no frequency deviation)
            processed_bitstream.append(0.0)
        elif bit == 2:
            # Handshake - map to freq_start
            f_center = (freq_config.freq0 + freq_config.freq1) / 2
            f_delta = abs(freq_config.freq1 - freq_config.freq0) / 2
            processed_bitstream.append((freq_config.freq_start - f_center) / f_delta)
        else:
            # Normal bits (0,1) -> NRZ encoding (-1,+1)
            processed_bitstream.append(bit * 2 - 1)

    nrz_bitstream = np.array(processed_bitstream)

    # Calculate parameters
    f_center = (freq_config.freq0 + freq_config.freq1) / 2
    f_delta = abs(freq_config.freq1 - freq_config.freq0) / 2

    steps_per_bit = int(sample_rate * bit_duration)
    total_samples = len(bitstream) * steps_per_bit

    # Initialize output array
    y = np.zeros(total_samples, dtype=np.float32)

    # Integration variable (frequency modulation state)
    m = 0.0

    for i in range(1, total_samples):
        # Interpolate bitstream to steps_per_bit points per bit
        bit_index = min(i // steps_per_bit, len(nrz_bitstream) - 1)
        prev_bit_index = min((i - 1) // steps_per_bit, len(nrz_bitstream) - 1)

        # Trapezoidal integration of the bitstream
        m += (nrz_bitstream[prev_bit_index] + nrz_bitstream[bit_index]) / 2

        # FM modulation with continuous phase
        phase = 2 * np.pi * i * (f_center / sample_rate) + 2 * np.pi * m * (
            f_delta / sample_rate
        )
        y[i] = np.cos(phase)

    return y


def generate_multiband_cpfsk_signal(
    symbolstream, bit_duration, sample_rate, freq_config
):
    """Generates multi-band continuous phase FSK signal from symbols (0-3).

    Each symbol encodes 2 bits using amplitude-controlled frequency bands:
    - Maintains continuous phase on both bands even when amplitude=0
    - Smooth amplitude transitions prevent audio clicks
    - 2x data rate improvement over single-band CPFSK
    """
    steps_per_symbol = int(sample_rate * bit_duration)
    total_samples = len(symbolstream) * steps_per_symbol

    # Initialize output array
    y = np.zeros(total_samples, dtype=np.float32)

    # Phase integration variables for continuous phase on each band
    low_phase_integrator = 0.0
    high_phase_integrator = 0.0

    # Process each symbol with smooth amplitude transitions
    for symbol_idx, symbol in enumerate(symbolstream):
        start_sample = symbol_idx * steps_per_symbol
        end_sample = start_sample + steps_per_symbol

        # Get amplitude values for this symbol
        low_amp, high_amp = get_band_amplitudes(symbol)

        # Generate time array for this symbol
        t_symbol = np.arange(steps_per_symbol) / sample_rate

        # Generate continuous phase signals for both bands
        # Low band continuous phase
        low_phase_base = (
            2 * np.pi * freq_config.freq_low * t_symbol + low_phase_integrator
        )
        low_signal = low_amp * np.cos(low_phase_base)

        # High band continuous phase
        high_phase_base = (
            2 * np.pi * freq_config.freq_high * t_symbol + high_phase_integrator
        )
        high_signal = high_amp * np.cos(high_phase_base)

        # Combine bands
        symbol_signal = low_signal + high_signal

        # Apply smooth amplitude envelope to prevent clicks at symbol boundaries
        if symbol_idx == 0 or symbol_idx == len(symbolstream) - 1:
            # Fade in/out at start/end of transmission
            fade_samples = min(steps_per_symbol // 10, 100)
            if symbol_idx == 0:
                fade_in = np.linspace(0, 1, fade_samples)
                symbol_signal[:fade_samples] *= fade_in
            if symbol_idx == len(symbolstream) - 1:
                fade_out = np.linspace(1, 0, fade_samples)
                symbol_signal[-fade_samples:] *= fade_out

        # Store in output array
        y[start_sample:end_sample] = symbol_signal

        # Update phase integrators for continuous phase across symbol boundaries
        low_phase_integrator += 2 * np.pi * freq_config.freq_low * bit_duration
        high_phase_integrator += 2 * np.pi * freq_config.freq_high * bit_duration

        # Keep phases in reasonable range to prevent numerical issues
        low_phase_integrator = low_phase_integrator % (2 * np.pi)
        high_phase_integrator = high_phase_integrator % (2 * np.pi)

    return y


def command_send(output_file, bit_duration, freq_config):
    """Reads from stdin, frames the data, and plays or saves it as audio."""
    payload_bytes = sys.stdin.buffer.read()
    if not payload_bytes:
        log.error("Sender: No input data received. Exiting.")
        return

    log.info(f"Sender: Read {len(payload_bytes)} bytes from stdin.")

    if freq_config.multi_band:
        # Multi-band mode: convert bits to symbols for 2x data rate
        payload_bits = bytes_to_bits(payload_bytes)
        checksum_val = calculate_checksum(payload_bytes)
        checksum_bits = bytes_to_bits(bytes([checksum_val]))

        # Handshake in symbol format: [2, 2, 0, 0] (high, high, silence, silence)
        handshake_symbols = [2, 2, 0, 0]
        data_symbols = bits_to_symbols(payload_bits + checksum_bits)
        symbols_to_transmit = handshake_symbols + data_symbols

        log.info(
            f"Sender: Multi-band CPFSK transmitting {len(symbols_to_transmit)} symbols (2 bits each)."
        )
        log.info(
            f"Sender: Data rate: {len(payload_bits + checksum_bits) / (len(symbols_to_transmit) * bit_duration):.1f} bits/s"
        )

        # Generate multi-band CPFSK signal
        full_signal = generate_multiband_cpfsk_signal(
            symbols_to_transmit, bit_duration, SAMPLE_RATE, freq_config
        )
    else:
        # Single-band mode (original CPFSK)
        handshake_bits = [2, 2]
        spacing_bits = [None, None]  # Add silence gap after handshake
        payload_bits = bytes_to_bits(payload_bytes)
        checksum_val = calculate_checksum(payload_bytes)
        checksum_bits = bytes_to_bits(bytes([checksum_val]))

        bits_to_transmit = handshake_bits + spacing_bits + payload_bits + checksum_bits
        log.info(
            f"Sender: Transmitting {len(bits_to_transmit)} total symbols using continuous CPFSK."
        )

        # Generate continuous CPFSK signal
        full_signal = generate_cpfsk_signal(
            bits_to_transmit, bit_duration, SAMPLE_RATE, freq_config
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
    "freq_config": None,  # Will be set when receiver starts
    "rolling_decisions": [],  # Buffer for rolling window decisions
    "decisions_per_bit": 4,  # Number of overlapping measurements per bit
}


def process_received_bits():
    """Processes the collected bits after a transmission ends."""
    # Clear the last debug line from the screen
    if sys.stdout.isatty():
        print(" " * CONSOLE_CLEAR_WIDTH, end="\r")
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
    freq_config = receiver_state["freq_config"]  # Preserve freq_config
    decisions_per_bit = receiver_state[
        "decisions_per_bit"
    ]  # Preserve decisions_per_bit
    receiver_state.update(
        {
            "state": "WAITING_FOR_HANDSHAKE",
            "all_bits": [],
            "handshake_counter": 0,
            "silence_counter": 0,
            "freq_config": freq_config,
            "rolling_decisions": [],
            "decisions_per_bit": decisions_per_bit,
        }
    )
    log.info("\nReceiver: Ready for next transmission.")


def find_preamble_sync(audio_data, bit_duration, sample_rate, freq_config):
    """Find synchronization point using preamble correlation."""
    if freq_config.multi_band:
        # Multi-band mode: generate expected preamble as symbols [2, 2, 0, 0]
        preamble_pattern = [2, 2, 0, 0]
        expected_preamble = generate_multiband_cpfsk_signal(
            preamble_pattern, bit_duration, sample_rate, freq_config
        )
    else:
        # Single-band mode: generate expected preamble signal: [2, 2, None, None]
        preamble_pattern = [2, 2, None, None]
        expected_preamble = generate_cpfsk_signal(
            preamble_pattern, bit_duration, sample_rate, freq_config
        )

    # Cross-correlate to find best match
    if len(audio_data) < len(expected_preamble):
        return None, None

    # Normalize both signals for better correlation
    audio_norm = (audio_data - np.mean(audio_data)) / (np.std(audio_data) + 1e-10)
    preamble_norm = (expected_preamble - np.mean(expected_preamble)) / (
        np.std(expected_preamble) + 1e-10
    )

    # Cross-correlation
    correlation = np.correlate(audio_norm, preamble_norm, mode="valid")

    if len(correlation) == 0:
        return None, None

    # Find peak correlation
    sync_point = np.argmax(correlation)
    correlation_strength = correlation[sync_point]

    # Use the first strong correlation if it's near the beginning (like before)
    strong_threshold = np.max(correlation) * 0.7
    early_peaks = np.where(correlation > strong_threshold)[0]
    if len(early_peaks) > 0 and early_peaks[0] < len(correlation) // 4:
        sync_point = early_peaks[0]
        correlation_strength = correlation[sync_point]

    # Calculate bit boundaries from sync point
    samples_per_bit = int(sample_rate * bit_duration)
    preamble_end = sync_point + len(expected_preamble)

    # Data starts after the preamble
    data_start = preamble_end

    return data_start, samples_per_bit, correlation_strength


def decode_synchronized_bits(audio_data, data_start, samples_per_bit, freq_config):
    """Decode bits/symbols using synchronized sampling."""
    if freq_config.multi_band:
        return decode_synchronized_symbols(
            audio_data, data_start, samples_per_bit, freq_config
        )
    else:
        return decode_synchronized_bits_single(
            audio_data, data_start, samples_per_bit, freq_config
        )


def decode_synchronized_symbols(audio_data, data_start, samples_per_bit, freq_config):
    """Decode multi-band symbols using synchronized sampling."""
    symbols = []

    # Sample at symbol centers (same as bit centers but decode symbols instead)
    max_symbols = (len(audio_data) - data_start) // samples_per_bit

    for symbol_idx in range(max_symbols):
        symbol_center = data_start + symbol_idx * samples_per_bit + samples_per_bit // 2
        symbol_end = min(symbol_center + samples_per_bit // 4, len(audio_data))
        symbol_start = max(symbol_center - samples_per_bit // 4, 0)

        if symbol_end <= symbol_start:
            break

        # Extract symbol window
        symbol_window = audio_data[symbol_start:symbol_end]

        # Detect multi-band symbol
        detected_symbol = find_multiband_symbol(symbol_window, SAMPLE_RATE, freq_config)

        if detected_symbol is not None:
            symbols.append(detected_symbol)
        else:
            # Hit silence or noise, probably end of transmission
            break

    # Convert symbols back to bits
    return symbols_to_bits(symbols)


def decode_synchronized_bits_single(
    audio_data, data_start, samples_per_bit, freq_config
):
    """Decode bits using synchronized sampling at bit centers (single-band mode)."""
    bits = []

    # Sample at bit centers
    for bit_idx in range((len(audio_data) - data_start) // samples_per_bit):
        bit_center = data_start + bit_idx * samples_per_bit + samples_per_bit // 2
        bit_end = min(
            bit_center + samples_per_bit // 4, len(audio_data)
        )  # Use quarter-bit window around center
        bit_start = max(bit_center - samples_per_bit // 4, 0)

        if bit_end <= bit_start:
            break

        # Extract bit window
        bit_window = audio_data[bit_start:bit_end]

        # Use our frequency estimation to decode this bit
        detected_bit = find_dominant_bit(bit_window, SAMPLE_RATE, freq_config)

        # Only accept data bits (0 or 1), stop on silence/noise
        if detected_bit in [0, 1]:
            bits.append(detected_bit)
        else:
            # Hit silence or noise, probably end of transmission
            break

    return bits


def find_dominant_bit(data, sample_rate, freq_config):
    """Analyzes a float32 audio chunk to find the dominant bit using frequency estimation."""
    if len(data) < 2:
        return None

    # FFT-based frequency estimation
    fft_result = np.fft.rfft(data)
    fft_magnitude = np.abs(fft_result)
    fft_freqs = np.fft.rfftfreq(len(data), 1.0 / sample_rate)

    # Find peak in spectrum
    peak_idx = np.argmax(fft_magnitude)
    peak_freq = fft_freqs[peak_idx]
    peak_magnitude = fft_magnitude[peak_idx]

    # Calculate weighted average frequency (centroid) around peak for better estimation
    # Use a window around the peak
    window_size = max(3, len(fft_magnitude) // 100)
    start_idx = max(0, peak_idx - window_size)
    end_idx = min(len(fft_magnitude), peak_idx + window_size + 1)

    window_freqs = fft_freqs[start_idx:end_idx]
    window_mags = fft_magnitude[start_idx:end_idx]

    # Weighted frequency centroid
    if np.sum(window_mags) > 0:
        estimated_freq = np.sum(window_freqs * window_mags) / np.sum(window_mags)
    else:
        estimated_freq = peak_freq

    if receiver_state["state"] == "WAITING_FOR_HANDSHAKE":
        log_msg = f"Est: {estimated_freq:6.1f}Hz (mag={peak_magnitude:5.1f})"
        log.info(log_msg, end="\r")

    # Amplitude threshold check
    AMPLITUDE_THRESHOLD = 10.0  # Adjusted for continuous signals
    if peak_magnitude < AMPLITUDE_THRESHOLD:
        return None

    # Snap to closest target frequency
    distances = {
        0: abs(estimated_freq - freq_config.freq0),
        1: abs(estimated_freq - freq_config.freq1),
        2: abs(estimated_freq - freq_config.freq_start),
    }

    closest_bit = min(distances.keys(), key=lambda k: distances[k])
    closest_distance = distances[closest_bit]

    # Only snap if reasonably close (within ~100Hz tolerance)
    MAX_SNAP_DISTANCE = 100.0
    if closest_distance <= MAX_SNAP_DISTANCE:
        return closest_bit
    else:
        return None


def find_multiband_symbol(data, sample_rate, freq_config):
    """Analyzes a float32 audio chunk to find the multi-band symbol (0-3)."""
    if len(data) < 2:
        return None

    # FFT-based frequency detection
    fft_result = np.fft.rfft(data)
    fft_magnitude = np.abs(fft_result)
    fft_freqs = np.fft.rfftfreq(len(data), 1.0 / sample_rate)

    # Find magnitudes at target frequencies
    freq_low_idx = np.argmin(np.abs(fft_freqs - freq_config.freq_low))
    freq_high_idx = np.argmin(np.abs(fft_freqs - freq_config.freq_high))

    mag_low = fft_magnitude[freq_low_idx]
    mag_high = fft_magnitude[freq_high_idx]

    # Adaptive threshold based on signal strength and noise floor
    noise_floor = np.mean(fft_magnitude) + 2 * np.std(fft_magnitude)
    max_mag = max(mag_low, mag_high)

    # Use adaptive threshold: either 30% of peak signal or above noise floor
    threshold = max(max_mag * 0.3, noise_floor, 10.0)  # Minimum threshold of 10

    has_low = mag_low > threshold
    has_high = mag_high > threshold

    # Decode symbol based on frequency presence
    if not has_low and not has_high:
        return 0  # Silence
    elif has_low and not has_high:
        return 1  # Low frequency only
    elif not has_low and has_high:
        return 2  # High frequency only
    elif has_low and has_high:
        return 3  # Both frequencies (chord)
    else:
        return None


def audio_callback(indata, _frames, _time, status):
    """This function is called by sounddevice for each new audio chunk."""
    if status:
        log.error(status)

    bit = find_dominant_bit(
        indata.flatten(), SAMPLE_RATE, receiver_state["freq_config"]
    )

    # Add this decision to our rolling buffer
    receiver_state["rolling_decisions"].append(bit)

    # Only make decisions when we have enough overlapping measurements
    decisions_per_bit = receiver_state["decisions_per_bit"]
    if len(receiver_state["rolling_decisions"]) >= decisions_per_bit:
        # For microphone mode, we still need some basic voting logic
        # Take the most recent decision
        recent_decisions = receiver_state["rolling_decisions"][-decisions_per_bit:]
        voted_bit = recent_decisions[-1] if recent_decisions else None

        # Remove old decision to prevent buffer growth
        receiver_state["rolling_decisions"] = receiver_state["rolling_decisions"][
            -decisions_per_bit:
        ]

        if receiver_state["state"] == "WAITING_FOR_HANDSHAKE":
            if voted_bit == 2:
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
            # Only 0 and 1 are valid bits for the received data stream
            if voted_bit == 0 or voted_bit == 1:
                if log.verbose:
                    log.info("▁" if voted_bit == 0 else "▇", end="", flush=True)
                receiver_state["all_bits"].append(voted_bit)
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
                TIMEOUT_CHUNKS = (
                    20 * decisions_per_bit
                )  # Adjust timeout for higher decision rate
                if receiver_state["silence_counter"] > TIMEOUT_CHUNKS:
                    process_received_bits()
                    reset_receiver()


def process_wav_data(wav_source, chunk_size, freq_config):
    """Reads and processes audio data using preamble synchronization."""
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

        # Use preamble synchronization instead of rolling windows
        log.info("Processing with preamble synchronization...")

        bit_duration = (
            chunk_size / SAMPLE_RATE
        )  # Calculate bit duration from chunk size
        result = find_preamble_sync(data, bit_duration, SAMPLE_RATE, freq_config)

        # Check if we got a valid result (new function returns 3 values)
        if len(result) == 3:
            data_start, samples_per_bit, correlation_strength = result
        else:
            data_start, samples_per_bit = result
            correlation_strength = 0

        if data_start is None:
            log.error("Receiver Error: No preamble found in audio data.")
            return

        log.info(
            f"Preamble found at sample {data_start}, correlation strength: {correlation_strength:.3f}"
        )

        # Decode bits using synchronized sampling
        decoded_bits = decode_synchronized_bits(
            data, data_start, samples_per_bit, freq_config
        )

        if not decoded_bits or len(decoded_bits) < 8:
            log.error("Receiver Error: No valid data bits found.")
            return

        # Process the decoded bits
        if len(decoded_bits) >= 8:
            # Split payload and checksum
            payload_bits = decoded_bits[:-8]
            checksum_bits = decoded_bits[-8:]

            if len(payload_bits) % 8 != 0:
                # Trim to complete bytes
                payload_bits = payload_bits[: -(len(payload_bits) % 8)]

            if payload_bits:
                received_bytes = bits_to_bytes(payload_bits)
                received_checksum = bits_to_bytes(checksum_bits)[0]
                expected_checksum = calculate_checksum(received_bytes)

                if received_checksum == expected_checksum:
                    green = "\033[92m"
                    reset = "\033[0m"
                    log.info(f"{green}Receiver: Checksum VALID.{reset}")
                    sys.stdout.buffer.write(received_bytes)
                    sys.stdout.flush()
                else:
                    log.error(
                        f"Receiver Error: Checksum mismatch! Expected {expected_checksum}, got {received_checksum}"
                    )
                    if log.verbose:
                        log.info(
                            f"Received bytes (possibly corrupted): {received_bytes}"
                        )

    except FileNotFoundError:
        log.error(f"Receiver Error: File not found at '{wav_source}'")
    except Exception as e:
        log.error(f"An error occurred while processing the WAV data: {e}")


def command_recv(input_file, chunk_size, freq_config):
    """Listens, decodes a stream, or processes a WAV file from a file or stdin."""
    receiver_state["freq_config"] = freq_config
    # Handle explicit stdin ('-') or implicit pipe (no tty)
    if (input_file and input_file == "-") or (
        not input_file and not sys.stdin.isatty()
    ):
        log.info("Receiver: Reading from stdin pipe...")
        process_wav_data(sys.stdin.buffer, chunk_size, freq_config)
    # Handle a file path
    elif input_file:
        log.info(f"Receiver: Reading from '{input_file}'...")
        process_wav_data(input_file, chunk_size, freq_config)
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
        freq0=args.freq0,
        freq1=args.freq1,
        freq_start=getattr(args, "freq_start"),
        freq_low=args.freq0,  # Use freq0 as low band
        freq_high=args.freq1,  # Use freq1 as high band
    )
    # We must declare CHUNK_SIZE as global to modify it.
    # It's calculated here so it can use the user-provided BIT_DURATION.
    chunk_size = int(SAMPLE_RATE * args.bit_duration)

    # --- Execute command ---
    if args.command == "send":
        command_send(
            output_file=args.output,
            bit_duration=args.bit_duration,
            freq_config=freq_config,
        )
    elif args.command == "recv":
        command_recv(
            input_file=args.input, chunk_size=chunk_size, freq_config=freq_config
        )
    else:
        # This case is technically unreachable due to `required=True`
        log.error(f"Unknown command: '{args.command}'")
        sys.exit(1)
