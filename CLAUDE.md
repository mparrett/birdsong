# CLAUDE.md

Acoustic modem using FSK modulation. Primary supported implementation:
`birdsong.py`.

## Commands

```bash
just format && just lint        # ALWAYS run before committing
just test                       # Supported automated validation
just e2e-pipes                  # End-to-end validation (checksums match = working)
uv run python birdsong.py send -o out.wav  # Generate signal
uv run python birdsong.py recv -i out.wav  # Decode signal
```

## Code Style

- Pure functions for signal processing
- Module-level constants: `SAMPLE_RATE`, `BIT_DURATION`, `FREQ_*`
- 44.1 kHz sample rate
- IMPORTANT: Always preserve fade-in/fade-out windowing to prevent audio artifacts

## Key Files

- `birdsong.py` - Production FSK modem
- `experiments/active/birdsong_fsk_sweeps.py` - Active research: hybrid FSK +
  frequency sweeps
- `experiments/active/birdsong_8band.py` - Active research: multiband carrier
  experiment
- `tools/` - Spectrogram, analysis, playback, and recording helpers
- `archive/` - Historical prototypes, challenge material, and preserved notes

## Project Memory

Memory files live in `docs/project_notes/`.

**Before proposing changes**: Check `decisions.md` for existing ADRs
**When encountering errors**: Search `bugs.md` for known solutions
**When looking up config**: Check `key_facts.md` for ports, URLs, environments

When resolving bugs or making decisions, update the relevant file.
