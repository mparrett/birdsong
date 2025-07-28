# generate_spectrogram.py
#
# A utility to generate a spectrogram image from a WAV file.
#
# Usage:
#   python generate_spectrogram.py poc_signal.wav
#   python generate_spectrogram.py poc_signal.wav --ylim 3000
#   python generate_spectrogram.py poc_signal.wav --ylim-khz 3.5
#
# This will create 'spectrogram.png' in the same directory.

import sys
import argparse
from scipy.io import wavfile
from scipy import signal
import matplotlib.pyplot as plt
import numpy as np

def create_spectrogram(wav_path, ylim_hz=2500):
    """
    Reads a WAV file and creates a spectrogram image from it.

    Args:
        wav_path (str): The path to the input WAV file.
        ylim_hz (int): Upper limit for Y-axis in Hz.
    """
    try:
        # Read the WAV file
        sample_rate, samples = wavfile.read(wav_path)
        print(f"Successfully read '{wav_path}' with sample rate {sample_rate}.")
    except FileNotFoundError:
        print(f"Error: The file '{wav_path}' was not found.")
        return
    except Exception as e:
        print(f"An error occurred while reading the file: {e}")
        return

    # Generate the spectrogram
    # The `signal.spectrogram` function returns:
    # f: Array of sample frequencies.
    # t: Array of segment times.
    # Sxx: The spectrogram itself.
    frequencies, times, Sxx = signal.spectrogram(samples, sample_rate)

    # For visualization, it's common to plot the log of the power spectral density
    # We add a small epsilon to avoid taking the log of zero
    log_Sxx = np.log1p(Sxx)

    # Create the plot
    plt.figure(figsize=(10, 4)) # Set the figure size
    
    # pcolormesh is used to create a pseudocolor plot of a 2D array
    plt.pcolormesh(times, frequencies, log_Sxx, shading='gouraud')

    # Set the labels and title
    plt.ylabel('Frequency [Hz]')
    plt.xlabel('Time [sec]')
    plt.title('Spectrogram')
    
    # Limit the Y-axis to show our 8-band frequencies clearly
    # Default 2500 Hz covers C7 (2093 Hz) with some headroom
    plt.ylim(0, ylim_hz) 

    # Save the figure to a file
    output_filename = 'spectrogram.png'
    plt.savefig(output_filename)
    print(f"Spectrogram saved to '{output_filename}'")
    plt.close() # Close the plot to free up memory

def main():
    parser = argparse.ArgumentParser(
        description="Generate spectrogram from WAV file",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python generate_spectrogram.py audio.wav              # Default 2.5 kHz range
  python generate_spectrogram.py audio.wav --ylim 3000  # 3 kHz range
  python generate_spectrogram.py audio.wav --ylim-khz 4.5  # 4.5 kHz range
  
8-band G-C CPFSK frequencies:
  G3: 196 Hz, C4: 262 Hz, G4: 392 Hz, C5: 523 Hz
  G5: 784 Hz, C6: 1047 Hz, G6: 1568 Hz, C7: 2093 Hz
        """
    )
    
    parser.add_argument('wav_file', help='Input WAV file path')
    parser.add_argument('--ylim', type=int, metavar='HZ', 
                       help='Y-axis upper limit in Hz')
    parser.add_argument('--ylim-khz', type=float, metavar='KHZ',
                       help='Y-axis upper limit in kHz (e.g., 2.5 for 2500 Hz)')
    
    args = parser.parse_args()
    
    # Determine Y-axis limit
    if args.ylim_khz:
        ylim_hz = int(args.ylim_khz * 1000)
    elif args.ylim:
        ylim_hz = args.ylim
    else:
        ylim_hz = 2500  # Default: covers C7 (2093 Hz) with headroom
    
    print(f"Generating spectrogram with Y-axis range: 0-{ylim_hz} Hz")
    create_spectrogram(args.wav_file, ylim_hz)

if __name__ == "__main__":
    main()

