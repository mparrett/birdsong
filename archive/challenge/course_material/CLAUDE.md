# CLAUDE.md

This file provides guidance to Claude Code when working with the acoustic modem project.

## Development Commands

### UV Package Management
```bash
uv add [package]     # Add dependencies
uv run python modem.py  # Run modem with UV environment
uv sync              # Install/sync dependencies
```

### Just Build System
```bash
just test           # Run tests
just format         # Format code with ruff
just lint           # Lint code with ruff
just demo           # Quick demonstration
```

### Ruff Code Quality
```bash
ruff format .       # Format Python code
ruff check .        # Lint and check code quality
ruff check --fix .  # Auto-fix linting issues
```

## Python Code Quality Guidelines

- Keep the single-file `modem.py` under 800 logical lines of code
- Use clear, descriptive function and variable names that explain DSP concepts
- Prefer numpy vectorized operations over explicit loops for signal processing
- Document complex DSP algorithms with brief inline comments explaining the mathematical approach
- Structure code with pure functions for signal processing separate from I/O operations