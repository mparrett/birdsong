# Birdsong

An acoustic modem proof-of-concept that transmits data using audio signals through Frequency Shift Keying (FSK) modulation.

## Overview

Birdsong demonstrates acoustic data transmission by encoding binary data as audio frequencies:
- Bit '0': 261.63 Hz (C4 musical note)
- Bit '1': 392.00 Hz (G4 musical note)

The current implementation focuses on the transmission side, generating and playing audio signals that represent binary data.

## Requirements

- Python 3.11+
- UV package manager

## Installation

```bash
uv sync
```

## Usage

Run the acoustic modem sender:

```bash
python sing.py
```

This will play a test sequence [1, 0, 1, 0] as audio tones through your default audio device.

## Technical Details

- **Sample Rate**: 44.1 kHz
- **Bit Duration**: 50ms per bit
- **Windowing**: 5ms fade-in/fade-out to prevent audio artifacts
- **Signal Processing**: Pure sine wave generation with NumPy
- **Audio I/O**: Real-time playback via SoundDevice

## Future Development

This proof-of-concept is designed to be extended with:
- Receiver implementation (demodulation)
- Error correction and detection
- Real data encoding/decoding
- Bidirectional communication
- Performance optimization
