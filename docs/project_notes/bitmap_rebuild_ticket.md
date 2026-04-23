# Bitmap Rebuild Ticket

## Summary

The archived bitmap prototype in
`experiments/archive/birdsong_bitmap.py` should not receive incremental bug
fixes. It needs a larger repair/rebuild pass as a new experiment branch.

Current evidence:

- file-based text loopback decodes to the wrong bitmap and empty text
- checkerboard pattern loopback collapses to `all_zeros`
- in-memory `bitmap_to_audio(...) -> audio_to_bitmap(...)` also fails

That means the current failure is not just WAV I/O or a small threshold tweak.

## Why A Rebuild Is Required

The current prototype has several structural weaknesses:

- no explicit sync/preamble, so decode assumes perfect slot alignment
- no payload length or checksum framing, so small bit shifts can collapse text
  decode immediately
- adaptive thresholding is too brittle across sparse vs dense patterns
- silence-vs-energy cell encoding is fragile without stronger calibration or
  per-band normalization

The current file is still useful as a record of the idea, but it should be
treated as a concept prototype rather than a partially-broken near-production
path.

## Proposed Direction

Treat the next pass as `bitmap v2`, not "fix the old one in place".

Suggested rebuild shape:

1. Keep the old script archived as historical reference.
2. Start a fresh experiment file rather than layering more heuristics into the
   archived version.
3. Add explicit framing:
   - preamble/sync region
   - payload length
   - checksum or CRC
4. Revisit the symbol design:
   - consider explicit active symbols instead of pure silence-vs-energy cells
   - consider calibration rows/columns or reserved sync bands
5. Add deterministic loopback tests before calling it active again.

## Acceptance Criteria

The rebuild should not leave archive status until it has all of the following:

- in-memory encode/decode round-trip for both text and known bitmap patterns
- file-based WAV round-trip for both text and known bitmap patterns
- at least one automated smoke test in `tests/`
- README/experiment docs that describe its status honestly

## Non-Goals

- Do not retrofit the archived file with large new layers just to preserve its
  exact structure.
- Do not promote the bitmap idea back to `experiments/active/` without tests.
- Do not claim robustness over speaker/mic paths until file loopback is solid.
