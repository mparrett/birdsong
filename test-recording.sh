#!/bin/bash

echo "Capturing..."

# Start recording in the background for 8 seconds at 32-bit depth
rec -c 1 -r 48000 -b 16 captured.wav trim 0 8 &

REC_PID=$! # Save the Process ID (PID) of the recording

# Give recording a moment to initialize before we make noise
sleep 0.2
echo "Go."

# Generate the speech file. This happens while the recording is active.
echo "Hello great world, how are you today? What is new or not new?" \
  | uv run python3 birdsong.py send

echo "Waiting for capture to finish..."
wait $REC_PID # <-- This is the crucial fix. It waits for the 'rec' process to end.

echo "Done. Analyzing files."

# Analyze the audio files
sox captured.wav -n stats
sox sent.wav -n stats

# Generate spectrograms with direct output filenames
sox captured.wav -n spectrogram -o captured.png
sox sent.wav -n spectrogram -o sent.png

echo "Spectrograms created: captured.png, sent.png"

