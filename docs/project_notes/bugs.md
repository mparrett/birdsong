# Bug Log

## 2026-03-21 - Stale Validation Surface

**Issue**: The repo exposed a broken validation path through
`test_bit_conversion.py`, and the root `justfile` still routed default commands
through older entrypoints instead of `birdsong.py`.

**Root Cause**: Earlier experiment and coursework branches remained in the
working surface after the repo evolved, but the surrounding docs and validation
commands were not pruned or updated.

**Solution**: Replace the stale test with real coverage for current code, make
`birdsong.py` the supported root entrypoint in the repo commands, and move old
branches into explicit archive areas.

**Prevention**: Keep support status explicit in the file layout and require any
promoted root command or README claim to correspond to an exercised test or
end-to-end recipe.

## 2026-03-21 - Bitmap Prototype Fails Text Loopback

**Issue**: `birdsong_bitmap.py` can generate a text transmission, but a
file-based loopback currently decodes to the wrong bitmap and empty text.

**Root Cause**: The bitmap prototype does not currently have robust enough sync
or slicing behavior to recover its own emitted signal in a clean round-trip.

**Solution**: Move it out of the active experiment set and preserve it as an
archived historical branch until it receives a dedicated repair pass.

**Prevention**: Require loopback smoke tests before classifying an experiment as
active.
