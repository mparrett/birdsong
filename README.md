# Birdsong

An acoustic modem proof-of-concept that transmits data using audio signals through Frequency Shift Keying (FSK) modulation.

## Overview

Birdsong is an acoustic modem proof-of-concept with two implementations:

### **`birdsong.py`** - Pure FSK Implementation
- **Purpose**: Production-ready, elegantly simple acoustic modem
- **Encoding**: Traditional binary frequency shift keying
- **Frequencies**: G3 (196 Hz) / A6 (1760 Hz)
- **Performance**: 20 bits/s with 100% reliability
- **Philosophy**: Unix simplicity, stdin/stdout piping

### **`birdsong_fsk_sweeps.py`** - Hybrid Dual-Mode System
- **Purpose**: Research showcase demonstrating biomimetic discoveries
- **FSK Mode**: 20 bits/s (same as pure version)
- **Sweep Mode**: 100 bits/s (5x faster) using frequency sweep encoding
- **Features**: 4 tonal symbols, G-C perfect fourth harmonies
- **Sound**: Natural, bird-like frequency transitions

Choose `birdsong.py` for reliability, `birdsong_fsk_sweeps.py` for performance exploration.

## Requirements

- Python 3.11+
- UV package manager

## Installation

```bash
uv sync
```

## Usage

### **Pure FSK Mode (`birdsong.py`)**

```bash
# Basic transmission (20 bits/s, rock-solid reliable)
echo "Hello World" | python birdsong.py send     # Play through speakers
echo "Hello World" | python birdsong.py send -o message.wav  # Save to file

python birdsong.py recv                          # Listen with microphone  
python birdsong.py recv -i message.wav           # Read from file
```

### **Hybrid Dual-Mode (`birdsong_fsk_sweeps.py`)**

```bash
# FSK mode (same as pure version)
echo "Hello World" | python birdsong_fsk_sweeps.py send

# Sweep mode (100 bits/s, 5x faster, experimental)
echo "Hello World" | python birdsong_fsk_sweeps.py send --sweep-mode
python birdsong_fsk_sweeps.py recv --sweep-mode
```

### **Advanced Options**

```bash
# Custom frequencies (musical notes or Hz) - works with both versions
echo "Test" | python birdsong.py send --freq0 C4 --freq1 G4
echo "Test" | python birdsong_fsk_sweeps.py send --freq0 C4 --freq1 G4

# Adjust timing (hybrid version only)
echo "Test" | python birdsong_fsk_sweeps.py send --sweep-mode --symbol-duration 0.015  # 133 bits/s

# File I/O with pipes (both versions)
echo "Data" | python birdsong.py send -o - | python birdsong.py recv -i -

# Verbose mode for debugging
python birdsong.py recv -v
python birdsong_fsk_sweeps.py recv --sweep-mode -v
```

## Technical Details

### **FSK Mode (Traditional)**
- **Frequencies**: 196 Hz (G3) / 1760 Hz (A6) - wide separation for reliability
- **Bit Duration**: 50ms per bit (configurable)
- **Performance**: 20 bits/s
- **Detection**: FFT-based frequency analysis
- **Reliability**: 100% accuracy, production-ready

### **Sweep Mode (Biomimetic)**  
- **Encoding**: 4 symbols = 2 bits each (00, 01, 10, 11)
- **Symbols**: Low/High Rising/Falling frequency sweeps
- **Frequencies**: G5-C6 (784-1046 Hz), G6-C7 (1568-2093 Hz)
- **Symbol Duration**: 20ms (configurable down to 12.5ms)
- **Performance**: 100 bits/s (5x improvement)
- **Detection**: Spectrogram-based sweep direction analysis
- **Sound Quality**: Natural, musical frequency transitions

### **Signal Processing**
- **Sample Rate**: 44.1 kHz (CD quality)
- **Windowing**: Fade-in/fade-out to prevent audio artifacts
- **Phase Continuity**: Smooth frequency transitions in sweep mode
- **Audio I/O**: Real-time microphone/speaker via SoundDevice
- **Error Detection**: Checksum validation in both modes

### **Protocol Features**
- **Handshake Detection**: C8 (4186 Hz) synchronization tone
- **State Machine**: Robust receiver with timeout handling
- **Stdin/Stdout Piping**: Unix-style data flow
- **File I/O**: WAV file generation and processing
- **Musical Note Support**: Specify frequencies as notes (C4, G5, etc.)

## Implementation Comparison

| File | Mode | Encoding | Rate | "Hello World" Time | Reliability | Use Case |
|------|------|----------|------|-------------------|-------------|----------|
| `birdsong.py` | FSK | Binary bits | 20 bits/s | 3.5s | 100% ✅ | Production |
| `birdsong_fsk_sweeps.py` | FSK | Binary bits | 20 bits/s | 3.5s | 100% ✅ | Compatibility |
| `birdsong_fsk_sweeps.py` | Sweep | Tonal symbols | 100 bits/s | 0.7s | ~95% ⚠️ | Research |

**Recommendation:** Use `birdsong.py` for reliable communication, `birdsong_fsk_sweeps.py` for exploring biomimetic performance gains.

## Additional Implementations

The repository includes several experimental implementations exploring advanced modulation techniques:

### Frequency Sweep Variants
- **`birdsong_sweeps.py`** - Base frequency sweep implementation
- **`birdsong_sweeps_4sym.py`** - 4-symbol sweep variant (2 bits per symbol)
- **`birdsong_sweeps_8sym.py`** - 8-symbol sweep variant (3 bits per symbol)

These explore different symbol alphabets, trading reliability for throughput.

### Multi-Band Parallel Carrier
- **`birdsong_2band.py`** - 2 parallel frequency channels
- **`birdsong_4band.py`** - 4 parallel frequency channels
- **`birdsong_8band.py`** - 8 parallel frequency channels (most advanced)

**Multi-band approach:**
- Multiple simultaneous frequency carriers transmitting in parallel
- Uses G-C perfect fourth musical intervals for natural sound
- Potential for 4-8x throughput improvement
- Requires sophisticated cross-talk management
- See `frequency_analysis.py` for harmonic interference diagnostics

### Spectrogram Bitmap Encoding
- **`birdsong_bitmap.py`** - Treats time-frequency spectrograms as 2D images for data encoding
- Pattern-based transmission using spectrogram "pixels"
- Exploits 2D nature of spectrograms for parallel data encoding

### Minimal/Alternative Versions
- **`poc.py`** - File-based proof-of-concept (196 Hz/1760 Hz, simple send/recv)
- **`modem.py`** - Minimal stdlib-only version (no numpy/scipy dependencies)

### Utilities
- **`generate_spectrogram.py`** - Visualize WAV files as spectrograms
- **`frequency_analysis.py`** - Diagnostic tools for harmonic interference
- **`debug.py`** - Bit sequence visualization
- **`test_bit_conversion.py`** - Unit tests for bit conversion pipeline

See `/workspace/` directory for research documentation explaining advanced techniques.
