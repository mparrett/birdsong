# Cleanup Untracked Files

**Date**: 2026-02-05

## Summary

Several untracked files in the repo appear to be cruft or temporary files that should be cleaned up.

## Files to Review

### Likely Delete
- `modem_old.py` - Old version of modem.py, likely superseded
- `gemini-feedback.txt` - Appears to be LLM feedback, probably temporary
- `gemini.txt` - Same
- `to-prompt.txt` - Same

### Justfile Issue
- `e2e-spectro` recipe has a truncated/broken line (line 40 ends with `|uv`)

## Suggested Actions

1. Delete or `.gitignore` the temporary text files
2. Review `modem_old.py` - if functionality is preserved in `modem.py`, delete it
3. Fix the broken `e2e-spectro` justfile recipe or remove it if unused
