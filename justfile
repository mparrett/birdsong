# Birdsong acoustic modem justfile

# Run the acoustic modem sender
send *args:
    uv run python3 poc.py send {{args}}

recv *args:
    uv run python3 poc.py recv {{args}}

e2e-poc:
    uv run python3 poc.py send
    afplay poc_signal.wav
    uv run python3 poc.py recv

# Modem.py commands (stdlib-only version)
modem-send *args:
    uv run python3 modem.py send {{args}}

modem-recv *args:
    uv run python3 modem.py recv {{args}}

e2e-modem:
    uv run python3 modem.py send -m "Hello, modem test!" -o modem_test.wav
    uv run python3 modem.py recv -i modem_test.wav

e2e-pipes:
   md5sum DEV_NOTES.md
   cat DEV_NOTES.md|uv run python3 birdsong.py send -o - 2>/dev/null|uv run python3 birdsong.py recv 2>/dev/null|md5sum

e2e-spectro:
   echo "hello, great and wonderful world, what shall we do today"|uv run python3 birdsong.py send -o out.wav
   sox out.wav -n spectrogram -d 3
   mv spectrogram.png spectrogram_3.png
   sox out.wav -n spectrogram -d 5
   mv spectrogram.png spectrogram_5.png
   sox out.wav -n spectrogram -d 10 
   mv spectrogram.png spectrogram_10.png
   open spectrogram_3.png
   open spectrogram_10.png
   cat DEV_NOTES.md|uv run python3 birdsong.py send -o out2.wav 2>/dev/null|uv
   sox out2.wav -n stat 2>&1| grep Length
   sox out2.wav -n spectrogram 
   


# Alias for send
run *args:
    uv run python3 poc.py send {{args}}

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
    find . -name '*.pyc' -delete

# Show help
help:
    @echo "Available commands:"
    @echo "  just send [args]     - Generate and save acoustic signal to WAV file (poc.py)"
    @echo "  just recv [args]     - Decode acoustic signal from WAV file (poc.py)"
    @echo "  just run [args]      - Alias for 'just send'"
    @echo "  just modem-send [args] - Generate signal using modem.py (stdlib-only)"
    @echo "  just modem-recv [args] - Decode signal using modem.py (stdlib-only)"
    @echo "  just e2e-modem       - End-to-end test with modem.py"
    @echo "  just install         - Install dependencies (including dev)"
    @echo "  just format          - Format code with ruff"
    @echo "  just lint            - Lint and fix code with ruff"
    @echo "  just check           - Check code without fixing"
    @echo "  just clean           - Remove generated WAV files"
    @echo "  just help            - Show this help"
