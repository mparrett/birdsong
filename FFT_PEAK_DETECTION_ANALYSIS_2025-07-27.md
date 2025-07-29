# FFT Peak Detection Analysis - 8-Band G-C CPFSK System

**Date:** July 27, 2025  
**System:** Birdsong Acoustic Modem - 8-band G-C CPFSK with Perfect Fourth Harmonies  
**Performance:** 151.4 bits/s at 0.05s bit duration, degrades at 0.03s, corrupts at 0.02s  

## Current FFT Peak Detection Algorithm

The 8-band symbol detector (`find_8band_symbol()`) uses the following approach:

### Algorithm Steps:
1. **Single FFT snapshot**: Takes one FFT of the entire symbol duration
2. **Nearest-bin lookup**: `np.argmin(np.abs(fft_freqs - freq))` finds the closest FFT bin to each target frequency
3. **Simple magnitude extraction**: Reads the magnitude at that single bin
4. **Adaptive thresholding**: Uses 30% of peak signal OR noise floor + 2σ 
5. **Binary decision**: Each band is either "on" or "off" based on threshold
6. **Symbol reconstruction**: Converts 8-bit band pattern to symbol (0-255)

### Code Implementation:
```python
def find_8band_symbol(data, sample_rate, freq_config):
    # FFT-based frequency detection
    fft_result = np.fft.rfft(data)
    fft_magnitude = np.abs(fft_result)
    fft_freqs = np.fft.rfftfreq(len(data), 1.0 / sample_rate)
    
    # Find magnitudes at all 8 target frequencies
    frequencies = [196.0, 261.6, 392.0, 523.3, 784.0, 1046.5, 1568.0, 2093.0]
    magnitudes = []
    
    for freq in frequencies:
        freq_idx = np.argmin(np.abs(fft_freqs - freq))  # Nearest bin
        magnitudes.append(fft_magnitude[freq_idx])       # Single bin magnitude
    
    # Adaptive thresholding
    noise_floor = np.mean(fft_magnitude) + 2 * np.std(fft_magnitude)
    max_mag = max(magnitudes)
    threshold = max(max_mag * 0.3, noise_floor, 10.0)
    
    # Binary band detection
    band_active = [mag > threshold for mag in magnitudes]
    
    # Convert to symbol
    symbol = 0
    for i, active in enumerate(band_active):
        if active:
            symbol |= (1 << i)
    
    return symbol
```

## Performance Analysis

### Frequency Configuration (G-C Perfect Fourths):
- **G3**: 196.0 Hz → **C4**: 261.6 Hz (65.6 Hz spacing)
- **G4**: 392.0 Hz → **C5**: 523.3 Hz (131.3 Hz spacing)  
- **G5**: 784.0 Hz → **C6**: 1046.5 Hz (262.5 Hz spacing)
- **G6**: 1568.0 Hz → **C7**: 2093.0 Hz (525.0 Hz spacing)

### FFT Resolution vs Bit Duration:

| Bit Duration | Samples @ 44.1kHz | FFT Bin Spacing | Status |
|--------------|-------------------|------------------|---------|
| 0.05s | 2205 samples | ~20 Hz | ✅ Perfect |
| 0.03s | 1323 samples | ~33 Hz | ⚠️ Marginal |
| 0.02s | 882 samples | ~50 Hz | ❌ Corrupted |

### Critical Issue at 0.02s:
- **Minimum frequency spacing**: G3-C4 = 65.6 Hz
- **FFT resolution**: ~50 Hz bins
- **Problem**: Adjacent frequencies G3 (196Hz) and C4 (261.6Hz) are barely separated!

## Algorithm Weaknesses

### 1. **Poor Frequency Resolution**
- Short time windows → wide FFT bins
- G3/C4 separation approaches FFT resolution limit
- Frequency content "bleeds" between adjacent bins

### 2. **Single-Bin Vulnerability** 
- Algorithm reads magnitude from exactly one FFT bin per frequency
- If target frequency falls between bins, energy spreads across multiple bins
- No interpolation or neighboring bin analysis

### 3. **No Temporal Averaging**
- Takes single FFT snapshot of entire symbol duration
- One corrupted sample or brief interference affects entire symbol
- No redundancy or voting across time

### 4. **Spectral Leakage**
- Rectangular windowing causes frequency bleeding
- Short time windows worsen leakage effects
- Adjacent frequency bands interfere with each other

### 5. **Fixed Thresholding**
- Simple 30% threshold may not adapt well to varying SNR conditions
- No frequency-specific threshold adaptation
- Noise floor estimation may be inadequate

## Improvement Strategies

### 1. **Forward Error Correction (FEC)**
- Add Reed-Solomon or convolutional codes
- Trade bandwidth for reliability (2x redundancy = 4x error correction)
- Could maintain ~75 bits/s at 0.02s with strong error correction

### 2. **Enhanced Frequency Detection**
- **Bin interpolation**: Average multiple bins around each target frequency
- **Parabolic interpolation**: Sub-bin frequency estimation
- **Windowing**: Hann/Hamming windows to reduce spectral leakage
- **Zero-padding**: Increase FFT resolution artificially

### 3. **Temporal Processing**
- **Overlap-add windowing**: Multiple overlapping FFTs with voting
- **Moving average**: Smooth magnitude estimates across time
- **Multi-sample correlation**: Compare against expected symbol templates

### 4. **Correlation-Based Detection**
- Replace FFT peak detection with template matching
- Cross-correlate received signal with expected symbol waveforms
- More robust to noise and frequency errors
- Could analyze full symbol shape instead of just frequency content

### 5. **Frequency Spacing Optimization**
- **Wider gaps**: Increase minimum frequency separation
- **Fewer bands**: Use 4-band or 6-band mode at short durations
- **Guard bands**: Leave unused frequency ranges between active bands
- **Harmonic series**: Use pure octaves (2:1 ratios) for maximum separation

### 6. **Adaptive Signal Processing**
- **AGC (Automatic Gain Control)**: Normalize signal levels
- **Noise filtering**: Bandpass filters around each frequency band
- **Frequency tracking**: Adapt to transmitter frequency drift
- **Dynamic thresholding**: Per-band threshold adaptation

## Recommended Next Steps

### Immediate Improvements:
1. **Bin interpolation**: Average 3-5 FFT bins around each target frequency
2. **Better windowing**: Replace rectangular with Hann window
3. **Temporal averaging**: Use overlapping analysis windows

### Medium-term Enhancements:
1. **Template correlation**: Implement correlation-based symbol detection
2. **FEC coding**: Add Reed-Solomon error correction
3. **Frequency spacing**: Optimize band allocation for short durations

### Architectural Changes:
1. **Adaptive mode**: Switch to fewer bands at shorter bit durations
2. **Multi-rate system**: Different configurations for different speeds
3. **Real-time feedback**: Monitor error rate and adjust parameters

## Conclusion

The current FFT peak detection works excellently at 0.05s bit duration but breaks down at 0.02s due to insufficient frequency resolution. The G3-C4 spacing (65.6 Hz) approaches the FFT resolution limit (~50 Hz), causing cross-talk and corruption.

The most promising improvements are **bin interpolation** for immediate gains and **correlation-based detection** for fundamental robustness. The beautiful G-C harmonic structure can be preserved while making the system more resilient to timing constraints.

**Current Achievement**: 151.4 bits/s with perfect reliability  
**Target**: Maintain reliability down to 0.02s (potentially 300+ bits/s with improvements)