#!/bin/bash

#VERBOSE="--verbose"
VERBOSE=""
SOX_OPTS=""
if [ -n "$VERBOSE" ]; then
    SOX_OPTS="-V 1"
fi

BIRDSONG_PY=${BIRDSONG_PY:-birdsong.py}
BIRDSONG_OPTS=${BIRDSONG_OPTS:-""}
OUT="test_out/$BIRDSONG_PY"  # separate for each script
MSG="Hello world, bird style"

MAGENTA=$'\033[35m'
CLEAR=$'\033[0m'

# Create output directory
mkdir -p $OUT

# --- MICROPHONE CAPTURE ---
if [ -n "$VERBOSE" ]; then
    echo "Capturing..."
fi

# Start recording in the background for 8 seconds at 48000 Hz.
# We will resample to 44100 Hz after capture, as `rec` may not support 44100 Hz.
# To try: apply 6dB gain, trim to first 8 seconds (`gain 6`)
rec $SOX_OPTS -c 1 -r 48000 -b 16 $OUT/captured.wav trim 0 8 &
REC_PID=$! # Save the Process ID (PID) of the recording

# Give recording a moment to initialize before generating any noise
sleep 0.4

# --- AUDIO GENERATION ---
if [ -n "$VERBOSE" ]; then
    echo "Singing..."
fi

# Generate speech audio to speaker
echo $MSG | uv run python3 $BIRDSONG_PY send $BIRDSONG_OPTS

if [ -n "$VERBOSE" ]; then
    echo "Waiting for capture to finish..."
fi
wait $REC_PID # <-- waits for the 'rec' process to end.

if [ -n "$VERBOSE" ]; then
    echo "Finished. Resampling and analyzing files."
fi

# --- RESAMPLING AND ANALYSIS ---

# Resample captured audio to 44100 Hz to match our script's sample rate
sox $SOX_OPTS $OUT/captured.wav -n spectrogram -o $OUT/spectro_captured.png
sox $SOX_OPTS $OUT/captured.wav -r 44100 $OUT/captured.resampled.wav

# Analyze the audio files
if [ -n "$VERBOSE" ]; then
    echo "=== Captured Audio Stats ==="
    sox $SOX_OPTS $OUT/captured.resampled.wav -n stats 2>&1 | grep 'Length '
fi
sox $SOX_OPTS $OUT/captured.resampled.wav -n spectrogram -o $OUT/spectro_captured_resampled.png

if [ -n "$VERBOSE" ]; then
    echo "=== Decode from resampled capture ==="
fi
uv run python3 $BIRDSONG_PY recv $VERBOSE $BIRDSONG_OPTS < $OUT/captured.resampled.wav


# --- NOISE REDUCTION ---

# reduce noise by 10dB (tune this for better results)
# nf=-30 use noise floor (level) as -30dB (tune this for better results)
# tn=1 noise level will be tracked and gradually changed during processing

if [ -n "$VERBOSE" ]; then
    echo "=== Applying noise reduction ==="
fi
ffmpeg -i $OUT/captured.resampled.wav \
	-hide_banner -loglevel error -y \
	-af "afftdn=nr=10:nf=-30:tn=1" $OUT/captured.resampled.filtered.wav

echo "=== Decode from filtered capture ==="

uv run python3 $BIRDSONG_PY recv $VERBOSE $BIRDSONG_OPTS < $OUT/captured.resampled.filtered.wav

if [ -n "$VERBOSE" ]; then
    echo "=== Filtered Audio Stats ==="
    sox $SOX_OPTS $OUT/captured.resampled.filtered.wav -n stats 2>&1 | grep 'Length '
fi
sox $SOX_OPTS $OUT/captured.resampled.filtered.wav -n spectrogram -o $OUT/spectro_captured_filtered.png

# --- REFERENCE GENERATION / VERIFICATION ---

echo "$MAGENTA === Generate reference WAV and decode for comparison === $CLEAR"
echo $MSG | uv run python3 $BIRDSONG_PY send $BIRDSONG_OPTS -o $OUT/sent_ref.wav

sox $SOX_OPTS $OUT/sent_ref.wav -n spectrogram -o $OUT/spectro_sent.png

uv run python3 $BIRDSONG_PY recv $VERBOSE $BIRDSONG_OPTS < $OUT/sent_ref.wav

if [ -n "$VERBOSE" ]; then
    echo "=== Reference Audio Stats ==="
    sox $SOX_OPTS $OUT/sent_ref.wav -n stats 2>&1 | grep 'Length '
fi

if [ -n "$VERBOSE" ]; then
    echo

    # --- SUMMARY ---

    echo ""
    echo "=== TEST COMPLETE ==="
    echo "Message: '$MSG'"
    echo "Generated files in $OUT/:"
    echo "  - captured.wav (original 48kHz capture)"
    echo "  - captured.resampled.wav (44.1kHz resampled)"
    echo "  - captured.resampled.filtered.wav (with noise reduction)"
    echo "  - sent_ref.wav (reference signal)"
    echo "  - spectro_*.png (spectrograms for visual analysis)"
    echo ""
    echo "Check spectrograms to analyze signal quality and decoding performance."
fi
