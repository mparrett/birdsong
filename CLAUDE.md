# CLAUDE.md

Birdsong is a Python-based acoustic modem that transmits data using audio signals (FSK modulation).

## Bash Commands

```bash
# Primary workflow (see justfile for all commands)
just install                    # Install dependencies
uv run python birdsong.py send  # Generate audio signal
uv run python birdsong.py recv  # Decode audio signal
just e2e-poc                    # End-to-end test: send -> play -> recv
just format                     # Format code with ruff
just lint                       # Lint and fix code
```

## Dependencies

- **Python 3.11+** (specified in `.python-version`)
- **UV** for package management
- **NumPy, SciPy** for signal processing
- **SoundDevice** for real-time audio I/O (not yet in pyproject.toml - add if needed)
- **Matplotlib** for spectrograms
- **Ruff** for formatting/linting (dev)

## Core Files

### Production Implementations
- **`birdsong.py`** - Primary FSK implementation (20 bits/s, 100% reliable, real-time audio I/O)
- **`poc.py`** - File-based proof-of-concept (196 Hz/1760 Hz, simple send/recv)
- **`modem.py`** - Minimal stdlib-only version (no numpy/scipy)

### Research Implementations
- **`birdsong_fsk_sweeps.py`** - Hybrid dual-mode (FSK + frequency sweeps, 100 bits/s experimental)
- **`birdsong_8band.py`** - 8-band parallel carrier (highest throughput research)
- **`birdsong_bitmap.py`** - Spectrogram bitmap encoding
- Various sweep and multi-band variants (2band, 4band, sweeps_4sym, sweeps_8sym)

### Utilities
- **`generate_spectrogram.py`** - Visualize signals
- **`frequency_analysis.py`** - Harmonic interference diagnostics
- **`debug.py`** - Bit sequence visualization

## Code Style

- **Functional approach**: Pure functions for signal processing, no side effects
- **Constants-based config**: Module-level constants for all parameters (SAMPLE_RATE, BIT_DURATION, FREQ_*)
- **Clear separation**: Signal generation vs I/O logic
- **Sample rate**: 44.1 kHz baseline across implementations
- **Windowing**: Always preserve fade-in/fade-out to prevent audio artifacts

## Workflow

- **Development status**: Currently consolidating research prototypes (in progress)
- **Testing**: Use `just e2e-*` commands for end-to-end validation
- **Visualization**: Generate spectrograms to validate signal changes
- **Always run** `just format` and `just lint` before committing
- Use `uv run python` to run scripts

## Important Notes

- Production use: **`birdsong.py`** (100% reliable)
- Research/experimentation: Choose based on technique interest
- See **README.md** for detailed documentation and performance comparisons
- Challenge subproject in `/challenge/` directory (separate coursework version)
