# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Birdsong is a Python-based acoustic modem proof-of-concept that transmits data using audio signals. The current implementation focuses on the "sender" half using Frequency Shift Keying (FSK) modulation.

## Development Commands

### Package Management
```bash
# Install dependencies
uv sync

# Run the application
python sing.py
uv run python sing.py
```

### Dependencies
- Uses **UV** as the Python package manager (modern alternative to pip/poetry)
- Dependencies locked in `uv.lock` for reproducible builds
- Python 3.11+ required (specified in `.python-version`)

## Architecture

### Core Signal Processing
- **FSK Modulation**: Binary data encoded as audio frequencies
  - Bit '0': 261.63 Hz (C4 note)
  - Bit '1': 392.00 Hz (G4 note)
- **Signal Generation**: Pure sine waves with fade-in/fade-out windowing (5ms)
- **Audio Specs**: 44.1kHz sample rate, 50ms bit duration

### Code Structure
- **Single-file application** (`sing.py`)
- **Functional approach**: Pure functions for signal generation
- **Constants-based configuration**: All parameters defined as module constants
- **Clear separation**: `generate_tone()` for signal processing, `main()` for orchestration

### Key Technical Details
- Uses NumPy for mathematical signal generation
- SoundDevice for real-time audio I/O
- Anti-aliasing windowing to prevent audio clicks
- Memory-based audio concatenation before playback

## Development Notes

### Current State
This is a proof-of-concept focusing on transmission only. The architecture is designed to be extended for:
- Receiver implementation (demodulation)
- Bidirectional communication
- Error correction/detection
- More sophisticated modulation schemes

### Missing Infrastructure
No testing framework, linting, or formatting tools are currently configured. When adding these, consider pytest, ruff, and black for Python development best practices.