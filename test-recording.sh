#!/bin/bash

echo "Capturing..."

# Start recording in the background for 8 seconds at 48000 Hz.
# We will resample to 44100 Hz after capture, as `rec` may not support 44100 Hz.
# apply 6dB gain, trim to first 8 seconds (gain 6)
rec -c 1 -r 48000 -b 16 captured.wav trim 0 8 &

REC_PID=$! # Save the Process ID (PID) of the recording

# Give recording a moment to initialize before we make noise
sleep 0.4
echo "Go."

# Generate speech audio to speaker
MSG="Hello world"
echo $MSG | uv run python3 birdsong.py send

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
sox sent.wav -n stats 2>&1 | grep 'Length '
sox sent.wav -n spectrogram -o spectro_sent.png

echo "Spectrograms created: spectro_captured.png, specro_sent.png"

uv run python3 birdsong.py recv --verbose < captured.resampled.wav

# try noise reduction

# reduce noise by 10dB (tune this for better results)
# nf=-30 use noise floor (level) as -30dB (tune this for better results)
# tn=1 noise level will be tracked and gradually changed during processing

ffmpeg -i captured.resampled.wav \
	-hide_banner -loglevel error -y \
	-af "afftdn=nr=10:nf=-30:tn=1" captured.resampled.filtered.wav

uv run python3 birdsong.py recv --verbose < captured.resampled.filtered.wav

sox captured.resampled.filtered.wav -n stats 2>&1 | grep 'Length '
sox captured.resampled.filtered.wav -n spectrogram -o spectro_captured_filtered.png
