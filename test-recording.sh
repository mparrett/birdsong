#!/bin/bash

echo "Capturing..."

# Start recording in the background for 8 seconds at 48000 Hz.
# We will resample to 44100 Hz after capture, as `rec` may not support 44100 Hz.
# apply 6dB gain, trim to first 8 seconds
rec -c 1 -r 48000 -b 16 captured.wav gain 6 trim 0 8 &

REC_PID=$! # Save the Process ID (PID) of the recording

# Give recording a moment to initialize before we make noise
sleep 0.4
echo "Go."

# Generate speech audio to speaker
MSG="Hello world"
echo $MSG | uv run python3 birdsong.py send \
	--freq0 A3 --freq1 C6

echo "Waiting for capture to finish..."
wait $REC_PID # <-- This is the crucial fix. It waits for the 'rec' process to end.

echo "Done. Resampling and analyzing files."

# Resample captured audio to 44100 Hz to match our script's sample rate
sox captured.wav -r 44100 captured.resampled.wav

# Analyze the audio files
sox captured.resampled.wav -n stats
sox captured.resampled.wav -n spectrogram -o spectro_captured.png


# Generate to wav file
echo $MSG | uv run python3 birdsong.py send -o sent.wav
sox sent.wav -n stats
sox sent.wav -n spectrogram -o spectro_sent.png

echo "Spectrograms created: spectro_captured.png, specro_sent.png"

