# Birdsong acoustic modem justfile

# Run the acoustic modem sender
send *args:
    uv run python3 sing.py send {{args}}
recv *args:
    uv run python3 sing.py recv {{args}}

# Alias for send
run *args:
    uv run python3 sing.py send {{args}}

# Install dependencies (including dev dependencies)
install:
    uv sync --group dev

# Format code with ruff
format:
    uv run ruff format .

# Lint and fix code with ruff
lint:
    uv run ruff check . --fix

# Check code without fixing
check:
    uv run ruff check .

# Clean generated files
clean:
    rm -f *.wav

# Show help
help:
    @echo "Available commands:"
    @echo "  just send [args] - Generate and save acoustic signal to WAV file"
    @echo "  just recv [args] - Decode acoustic signal from WAV file"
    @echo "  just run [args]  - Alias for 'just send'"
    @echo "  just install     - Install dependencies (including dev)"
    @echo "  just format      - Format code with ruff"
    @echo "  just lint        - Lint and fix code with ruff"
    @echo "  just check       - Check code without fixing"
    @echo "  just clean       - Remove generated WAV files"
    @echo "  just help        - Show this help"
