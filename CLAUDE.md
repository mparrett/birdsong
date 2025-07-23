# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Birdsong is a Python-based acoustic modem proof-of-concept that implements full bidirectional communication using audio signals through Frequency Shift Keying (FSK) modulation. The project has evolved from a single-file sender to a complete communication system.

## Development Commands

### Just Build System
This project uses [Just](https://github.com/casey/just) as the primary build tool:

```bash
# Primary commands
just send [args]    # Generate acoustic signal WAV file
just recv [args]    # Decode acoustic signal from WAV file  
just e2e           # End-to-end test: send -> play -> recv

# Development commands
just install       # Install dependencies (including dev)
just format        # Format code with ruff
just lint          # Lint and fix code with ruff
just check         # Check code without fixing
just clean         # Remove generated WAV files
just help          # Show all available commands
```

### Package Management
```bash
# Manual UV commands (if not using Just)
uv sync            # Install dependencies
uv sync --group dev # Install with dev dependencies
uv run python poc.py send  # Run main implementation
```

### Dependencies
- **UV**: Modern Python package manager for dependency management
- **Python 3.11+**: Required (specified in `.python-version`)
- **Ruff**: Code formatting and linting (dev dependency)

## Architecture

### Multiple Implementations
The codebase contains three main implementations with different architectural approaches:

#### 1. `poc.py` - Primary Implementation (File-based)
- **Purpose**: Main development version with full send/recv functionality
- **I/O**: WAV file generation and processing using built-in `wave` module
- **Frequencies**: 196 Hz (G3) for '0', 1760 Hz (A6) for '1'
- **Features**: Noise injection, hardcoded test sequences, bidirectional communication

#### 2. `birdsong.py` - Real-time Version
- **Purpose**: Advanced real-time audio I/O with microphone/speaker support
- **Dependencies**: NumPy, SciPy, SoundDevice for real-time processing
- **Features**: State machine receiver, handshake detection, checksum validation
- **I/O**: Real-time microphone input, speaker output, stdin/stdout pipes

#### 3. `modem.py` - Minimal Version
- **Purpose**: Minimal dependencies (stdlib only) with stdin/stdout piping
- **Features**: Preamble/postamble framing, UTF-8 text encoding
- **Approach**: Mathematical signal processing without NumPy

### Signal Processing Architecture
- **FSK Modulation**: Binary data encoded as musical note frequencies
- **Sample Rate**: 44.1 kHz (CD quality audio)
- **Bit Duration**: 8-50ms (varies by implementation)
- **Windowing**: Fade-in/fade-out to prevent audio clicks and artifacts
- **Anti-aliasing**: Applied to prevent signal artifacts

### Protocol Design
- **Framing**: Handshake patterns for synchronization
- **Error Detection**: Checksum validation in advanced implementations  
- **State Machine**: Robust receiver with handshake detection
- **Noise Resilience**: Configurable noise injection for testing

## Code Structure and Patterns

### Functional Programming Approach
- **Pure Functions**: Signal generation functions with no side effects
- **Constants-based Configuration**: All parameters defined as module constants
- **Clear Separation**: Signal processing vs orchestration/I/O logic
- **Memory Efficiency**: Signal concatenation before playback

### Key Technical Components
- **Signal Generation**: Pure sine wave generation with NumPy or stdlib math
- **Audio I/O**: Multiple backends (file-based, real-time, piped)
- **State Management**: Callback-based receivers with synchronization
- **Cross-platform**: Works on macOS, Linux, Windows with appropriate audio drivers

## Development Workflow

### Current Branch Structure
- **main**: Original single-file sender implementation
- **feat/stdin-handling**: Current active development (bidirectional communication)
- Active development happens on feature branches with descriptive names

### Code Quality Tools
- **Formatter**: Ruff (replaces Black)
- **Linter**: Ruff (replaces Flake8, Pylint)
- **Configuration**: Defined in `pyproject.toml`
- **Usage**: Always run `just format` and `just lint` before committing

### Testing and Validation
- **End-to-end Testing**: Use `just e2e` for complete signal round-trip
- **Signal Validation**: Generate spectrograms with `generate_spectrogram.py`
- **Debug Utilities**: Available in `debug.py` for troubleshooting
- **No Unit Testing**: Framework not yet implemented - consider pytest for future development

## Common Development Tasks

### Adding New Features
1. Choose appropriate implementation file based on requirements:
   - `poc.py` for file-based prototyping
   - `birdsong.py` for real-time audio features
   - `modem.py` for minimal dependency changes
2. Follow functional programming patterns with pure functions
3. Test with `just e2e` workflow
4. Format and lint with `just format` and `just lint`

### Signal Processing Modifications
- Frequency mappings are implementation-specific constants
- All implementations use 44.1kHz sample rate as baseline
- Windowing functions prevent audio artifacts - preserve these patterns
- Test changes with spectrogram generation for visual validation

### Protocol Changes
- Handshake patterns in `birdsong.py` for synchronization
- Framing logic in `modem.py` for stdin/stdout compatibility
- Error detection mechanisms vary by implementation
- Maintain backward compatibility when possible