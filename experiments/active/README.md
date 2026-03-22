# Active Experiments

These scripts are still live research branches, but they are not part of the
supported root surface.

- `birdsong_fsk_sweeps.py`: hybrid FSK plus sweep experiment. The FSK path is
  smoke-tested in file loopback; sweep mode remains exploratory.
- `birdsong_8band.py`: multiband carrier experiment. Short file loopback is
  smoke-tested; the code is large and intentionally isolated from the supported
  root modem.

- `birdsong_bitmap_v2.py`: spectrogram bitmap modem with sync preamble,
  calibration-based thresholds, and length/checksum framing. Passes all
  in-memory and WAV round-trips. See `bitmap_v2_results/` for robustness
  characterization.
- `bitmap_v2_results/`: robustness sweep harness and findings. Tests white
  noise, band-limited noise, clipping, sample offset, rolloff, and combined
  channel corruption.

Guideline:

- Keep these visible only while they represent distinct and still-interesting
  ideas. If a branch stops paying rent, archive it.
