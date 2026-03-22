# Bitmap v2 Robustness Characterization

Date: 2026-03-22
Pattern: checkerboard (8x16), seed=42, 5 trials per noise point

## Summary

The calibration-based threshold design (sync columns as reference) makes
bitmap v2 inherently robust to amplitude-domain corruptions. The system's
main vulnerability is timing: without cross-correlation sync detection,
sample offsets beyond ~22% of a slot cause catastrophic failure.

## Results by corruption type

### White noise: robust to 0 dB SNR

Zero errors at 0 dB (signal power = noise power). First errors appear at
-5 dB (BER 2.7%), scattered across bands with no clear frequency bias.
The calibration threshold scales with noise because sync columns see the
same noise floor as data columns.

### Band-limited noise (< 3 kHz): degrades below 5 dB

At 0 dB, lower bands (B0-B4, 784-2637 Hz) show 17-26% BER while upper
bands (B5-B7, 3520-5274 Hz) remain clean. This is expected: the noise
energy concentrates in the same spectral region as the lower bands, so
calibration can't distinguish signal from noise.

### Clipping: immune

Zero errors even at 10% clipping (extreme hard saturation). Clipping is a
monotonic amplitude transform that affects sync and data equally, so
calibration thresholds remain valid.

### Sample offset: cliff at ~45% of slot

- 0-22% of slot (0-500 samples): zero errors
- 45% of slot (1000 samples): 47% BER (catastrophic)
- 91% of slot (2000 samples): 96% BER (total failure)

The decoder currently assumes audio starts at sample 0. There is no
cross-correlation sync search. This is the primary vulnerability for
real-world over-the-air use.

### High-pass rolloff (small speaker): immune up to 2 kHz

Zero errors with rolloff up to 2000 Hz, even though band B0 is at 784 Hz.
The rolloff attenuates sync and data columns proportionally, so
calibration compensates automatically.

### Low-pass rolloff (mic bandwidth): immune down to 2 kHz

Zero errors with rolloff down to 2000 Hz, even though bands B6-B7 are at
4186-5274 Hz. Same self-calibrating behavior.

### Combined channel (HP=500 Hz, LP=6000 Hz, white noise): robust to 0 dB

The realistic channel simulation shows zero errors across all tested SNR
levels. The combined effect of rolloff + noise doesn't break calibration.

## Key insight

The calibration-based threshold is the architectural advantage over v1.
Because threshold = 30% of sync column energy per band, any corruption
that affects sync and data equally (clipping, rolloff, gain changes) is
automatically compensated. The system only fails when corruption is
spectrally asymmetric (band-limited noise hitting lower bands harder) or
when timing alignment is lost.

## Next steps if this experiment is picked up again

1. **Cross-correlation sync detection** — port from `birdsong_8band.py`
   `find_preamble_sync()`. The two all-bands-on sync columns are an ideal
   correlation target. This would close the timing vulnerability.
2. **Per-band SNR measurement** — use sync column energy vs. silence gap
   energy to estimate per-band SNR, enabling adaptive error reporting.
3. **Real-world over-the-air test** — speaker/mic loopback to validate
   whether simulated rolloff matches actual device characteristics.

## Raw data

See `sweep_output.txt` for full per-band BER tables.
