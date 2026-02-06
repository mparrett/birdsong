# CLAUDE.md

Acoustic modem using FSK modulation. Primary implementation: `birdsong.py` (100% reliable, 20 bits/s).

## Commands

```bash
just format && just lint        # ALWAYS run before committing
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
- `birdsong_fsk_sweeps.py` - Research: hybrid FSK + frequency sweeps (100 bits/s experimental)
- `birdsong_*band.py` - Research: multi-band parallel carriers
- `poc.py`, `modem.py` - Alternative implementations

## Project Memory

Memory files live in `docs/project_notes/`.

**Before proposing changes**: Check `decisions.md` for existing ADRs
**When encountering errors**: Search `bugs.md` for known solutions
**When looking up config**: Check `key_facts.md` for ports, URLs, environments

When resolving bugs or making decisions, update the relevant file.
