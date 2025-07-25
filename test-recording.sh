#!/bin/bash

OUT="test_out"

# Create output directory
mkdir -p $OUT

# --- MICROPHONE CAPTURE ---
echo "Capturing..."

# Start recording in the background for 8 seconds at 48000 Hz.
# We will resample to 44100 Hz after capture, as `rec` may not support 44100 Hz.
# To try: apply 6dB gain, trim to first 8 seconds (`gain 6`)
rec -c 1 -r 48000 -b 16 $OUT/captured.wav trim 0 8 &
REC_PID=$! # Save the Process ID (PID) of the recording

# Give recording a moment to initialize before generating any noise
sleep 0.4

# --- AUDIO GENERATION ---
echo "Singing..."

# Generate speech audio to speaker
MSG="Hello world"
echo $MSG | uv run python3 birdsong.py send

echo "Waiting for capture to finish..."
wait $REC_PID # <-- waits for the 'rec' process to end.

echo "Finished. Resampling and analyzing files."

# --- RESAMPLING AND ANALYSIS ---

# Resample captured audio to 44100 Hz to match our script's sample rate
sox $OUT/captured.wav -r 44100 $OUT/captured.resampled.wav
sox $OUT/captured.wav -n spectrogram -o $OUT/spectro_captured.png

# Analyze the audio files
echo "=== Captured Audio Stats ==="
sox $OUT/captured.resampled.wav -n stats 2>&1 | grep 'Length '
sox $OUT/captured.resampled.wav -n spectrogram -o $OUT/spectro_captured_resampled.png

echo "=== Decode from resampled capture ==="
uv run python3 birdsong.py recv --verbose < $OUT/captured.resampled.wav
# --- NOISE REDUCTION ---

# reduce noise by 10dB (tune this for better results)
# nf=-30 use noise floor (level) as -30dB (tune this for better results)
# tn=1 noise level will be tracked and gradually changed during processing

echo "=== Applying noise reduction ==="
ffmpeg -i $OUT/captured.resampled.wav \
	-hide_banner -loglevel error -y \
	-af "afftdn=nr=10:nf=-30:tn=1" $OUT/captured.resampled.filtered.wav

echo "=== Decode from filtered capture ==="
uv run python3 birdsong.py recv --verbose < $OUT/captured.resampled.filtered.wav

echo "=== Filtered Audio Stats ==="
sox $OUT/captured.resampled.filtered.wav -n stats 2>&1 | grep 'Length '
sox $OUT/captured.resampled.filtered.wav -n spectrogram -o $OUT/spectro_captured_filtered.png

# --- REFERENCE GENERATION ---

echo "=== Generate reference WAV for comparison ==="
echo $MSG | uv run python3 birdsong.py send -o $OUT/sent.wav

echo "=== Reference Audio Stats ==="
sox $OUT/sent.wav -n stats 2>&1 | grep 'Length '
sox $OUT/sent.wav -n spectrogram -o $OUT/spectro_sent.png

# --- DECODE REFERENCE ---

echo "=== Decode reference (should be perfect) ==="
uv run python3 birdsong.py recv --verbose < $OUT/sent.wav

# --- SUMMARY ---

echo ""
echo "=== TEST COMPLETE ==="
echo "Message: '$MSG'"
echo "Generated files in $OUT/:"
echo "  - captured.wav (original 48kHz capture)"
echo "  - captured.resampled.wav (44.1kHz resampled)"
echo "  - captured.resampled.filtered.wav (with noise reduction)"
echo "  - sent.wav (reference signal)"
echo "  - spectro_*.png (spectrograms for visual analysis)"
echo ""
echo "Check spectrograms to analyze signal quality and decoding performance."
