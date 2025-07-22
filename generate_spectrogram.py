# generate_spectrogram.py
#
# A utility to generate a spectrogram image from a WAV file.
#
# Usage:
#   python generate_spectrogram.py poc_signal.wav
#
# This will create 'spectrogram.png' in the same directory.

import sys
from scipy.io import wavfile
from scipy import signal
import matplotlib.pyplot as plt
import numpy as np

def create_spectrogram(wav_path):
    """
    Reads a WAV file and creates a spectrogram image from it.

    Args:
        wav_path (str): The path to the input WAV file.
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
    
    # Limit the Y-axis to a reasonable range to see our frequencies clearly
    plt.ylim(0, 1000) 

    # Save the figure to a file
    output_filename = 'spectrogram.png'
    plt.savefig(output_filename)
    print(f"Spectrogram saved to '{output_filename}'")
    plt.close() # Close the plot to free up memory

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python generate_spectrogram.py <path_to_wav_file>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    create_spectrogram(input_file)

