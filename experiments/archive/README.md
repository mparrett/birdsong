# Archived Experiments

These scripts are preserved for comparison, not maintained as active paths.

- `birdsong_2band.py`: early multiband branch, superseded by the 8-band
  experiment.
- `birdsong_4band.py`: intermediate multiband branch, superseded by the 8-band
  experiment.
- `birdsong_bitmap.py`: bitmap/spectrogram idea preserved as a prototype; its
  text loopback currently fails and should be treated as a rebuild candidate,
  not a small-fix branch.
- `birdsong_sweeps_4sym.py`: preserved baseline 4-symbol sweep branch.
- `birdsong_sweeps_8sym.py`: higher-throughput 8-symbol sweep variant.

Notes:

- The former `birdsong_sweeps.py` file was removed because it was effectively a
  duplicate of `birdsong_sweeps_4sym.py`.
- Archived code may still contain useful DSP ideas, but it should not be read as
  trustworthy current behavior.
- The bitmap prototype has a dedicated follow-up ticket in
  `docs/project_notes/bitmap_rebuild_ticket.md`.
