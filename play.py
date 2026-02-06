#!/usr/bin/env python3
"""
Simple note player for the 8-band G-C CPFSK system.

Usage:
    python play.py G3       # Play single note
    python play.py G3 C4    # Play multiple notes as chord
    python play.py --list   # List all available notes
"""

import numpy as np
import sounddevice as sd
import argparse
import wave

# Sample rate and duration
SAMPLE_RATE = 44100
DEFAULT_DURATION = 1.0  # seconds

# 8-band G-C frequency configuration
NOTES = {
    "G3": 196.0,  # Bass foundation
    "C4": 261.6,  # Perfect fourth above G3
    "G4": 392.0,  # Octave
    "C5": 523.3,  # Perfect fourth above G4
    "G5": 784.0,  # Octave
    "C6": 1046.5,  # Perfect fourth above G5
    "G6": 1568.0,  # Octave
    "C7": 2093.0,  # Perfect fourth above G6
}


def generate_tone(frequency, duration, sample_rate, amplitude=0.3):
    """Generate a sine wave tone with fade in/out."""
    num_samples = int(sample_rate * duration)
    t = np.linspace(0, duration, num_samples, False)

    # Generate sine wave
    tone = amplitude * np.sin(2 * np.pi * frequency * t)

    # Add fade in/out to prevent clicks
    fade_samples = min(int(num_samples * 0.05), 1000)  # 5% or 1000 samples max

    if fade_samples > 0:
        # Fade in
        fade_in = np.linspace(0, 1, fade_samples)
        tone[:fade_samples] *= fade_in

        # Fade out
        fade_out = np.linspace(1, 0, fade_samples)
        tone[-fade_samples:] *= fade_out

    return tone.astype(np.float32)


def play_notes(note_names, duration=DEFAULT_DURATION, output_file=None):
    """Play notes - either simultaneously (chord) or sequentially (with _ separator)."""
    if not note_names:
        print("No notes specified!")
        return

    # Check for sequence mode (contains '_' separator)
    if "_" in note_names:
        play_sequence(note_names, duration, output_file)
    else:
        play_chord(note_names, duration, output_file)


def save_wav(signal, filename, sample_rate=SAMPLE_RATE):
    """Save audio signal to WAV file."""
    # Convert to 16-bit integers
    audio_data = (signal * 32767).astype(np.int16)

    with wave.open(filename, "w") as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 2 bytes = 16 bits
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio_data.tobytes())


def play_chord(note_names, duration=DEFAULT_DURATION, output_file=None):
    """Play multiple notes simultaneously as a chord."""
    # Validate notes
    invalid_notes = [note for note in note_names if note not in NOTES]
    if invalid_notes:
        print(f"Invalid notes: {', '.join(invalid_notes)}")
        print(f"Available notes: {', '.join(NOTES.keys())}")
        return

    # Generate individual tones
    tones = []
    for note in note_names:
        freq = NOTES[note]
        tone = generate_tone(freq, duration, SAMPLE_RATE)
        tones.append(tone)

    # Mix tones together (reduce amplitude to prevent clipping)
    amplitude_scale = 0.7 / len(tones)  # Scale down for multiple notes
    mixed_signal = np.sum(tones, axis=0) * amplitude_scale

    # Display info
    if len(note_names) == 1:
        action = "Saving" if output_file else "Playing"
        print(
            f"{action} {note_names[0]} ({NOTES[note_names[0]]} Hz) for {duration}s..."
        )
    else:
        note_info = [f"{note} ({NOTES[note]} Hz)" for note in note_names]
        action = "Saving" if output_file else "Playing"
        print(f"{action} chord: {', '.join(note_info)} for {duration}s...")

    # Save to file or play
    if output_file:
        try:
            save_wav(mixed_signal, output_file)
            print(f"✓ Saved to {output_file}")
        except Exception as e:
            print(f"Error saving file: {e}")
    else:
        # Play the sound
        try:
            sd.play(mixed_signal, SAMPLE_RATE)
            sd.wait()  # Wait until playback is finished
            print("✓ Playback complete")
        except Exception as e:
            print(f"Error playing audio: {e}")
            print("Try installing sounddevice: pip install sounddevice")


def play_sequence(sequence, duration=DEFAULT_DURATION, output_file=None):
    """Play a sequence of notes/chords separated by '_'."""
    # Split by '_' to get individual segments
    segments = []
    current_segment = []

    for item in sequence:
        if item == "_":
            if current_segment:
                segments.append(current_segment)
                current_segment = []
        else:
            current_segment.append(item)

    # Add the last segment if it exists
    if current_segment:
        segments.append(current_segment)

    if not segments:
        print("No valid segments found in sequence!")
        return

    action = "Saving" if output_file else "Playing"
    print(f"{action} sequence of {len(segments)} segments, {duration}s each:")

    # Generate all segments
    all_segments_audio = []

    for i, segment in enumerate(segments, 1):
        # Validate notes in this segment
        invalid_notes = [note for note in segment if note not in NOTES]
        if invalid_notes:
            print(f"Segment {i}: Invalid notes: {', '.join(invalid_notes)}")
            continue

        # Display segment info
        if len(segment) == 1:
            print(f"  {i}. {segment[0]} ({NOTES[segment[0]]} Hz)")
        else:
            note_info = [f"{note} ({NOTES[note]} Hz)" for note in segment]
            print(f"  {i}. Chord: {', '.join(note_info)}")

        # Generate tones for this segment
        tones = []
        for note in segment:
            freq = NOTES[note]
            tone = generate_tone(freq, duration, SAMPLE_RATE)
            tones.append(tone)

        # Mix tones together
        amplitude_scale = 0.7 / len(tones)
        mixed_signal = np.sum(tones, axis=0) * amplitude_scale

        if output_file:
            # Collect audio for later saving
            all_segments_audio.append(mixed_signal)
        else:
            # Play the segment immediately
            try:
                sd.play(mixed_signal, SAMPLE_RATE)
                sd.wait()  # Wait until this segment finishes before playing next
            except Exception as e:
                print(f"Error playing segment {i}: {e}")
                return

    if output_file:
        # Concatenate all segments and save
        try:
            full_sequence = np.concatenate(all_segments_audio)
            save_wav(full_sequence, output_file)
            print(f"✓ Saved sequence to {output_file}")
        except Exception as e:
            print(f"Error saving sequence: {e}")
    else:
        print("✓ Sequence complete")


def list_notes():
    """List all available notes with frequencies."""
    print("Available notes in 8-band G-C CPFSK system:")
    print("=" * 45)
    for note, freq in NOTES.items():
        print(f"{note:3s} : {freq:7.1f} Hz")
    print("=" * 45)
    print("Perfect fourth harmonies: G-C pattern across 4 octaves")


def main():
    parser = argparse.ArgumentParser(
        description="Play musical notes from the 8-band G-C CPFSK system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python play.py G3           # Play single note
  python play.py G3 C4        # Play perfect fourth chord
  python play.py G3 G4 G5     # Play G octaves chord
  python play.py --list       # List all notes
  
  # Sequences (use _ to separate time segments):
  python play.py G3 _ C4 _ G4  # Play G3, then C4, then G4 in sequence
  python play.py G3 C4 _ G4 C5 _ G5  # Chord, then chord, then single note
  python play.py G3 _ G4 _ G5 _ C7 _ _ G3  # Include pauses with empty segments
  
  python play.py G3 C4 G4 C5 G5 C6 G6 C7  # Play all 8 bands (full chord!)
        """,
    )

    parser.add_argument("notes", nargs="*", help="Note names to play (e.g., G3, C4)")
    parser.add_argument("--list", action="store_true", help="List all available notes")
    parser.add_argument(
        "--duration",
        "-d",
        type=float,
        default=DEFAULT_DURATION,
        help=f"Duration in seconds (default: {DEFAULT_DURATION})",
    )
    parser.add_argument(
        "--output", "-o", metavar="FILE", help="Save to WAV file instead of playing"
    )

    args = parser.parse_args()

    if args.list:
        list_notes()
        return

    if not args.notes:
        parser.print_help()
        return

    play_notes(args.notes, args.duration, args.output)


if __name__ == "__main__":
    main()
