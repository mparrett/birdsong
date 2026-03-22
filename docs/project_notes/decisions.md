# Decisions

## ADR-001: Minimal Root With Explicit Experiment Status (2026-03-21)

**Context**: The repository mixed supported code, research variants, and
historical coursework material in the repo root. This made the primary modem,
the active experiments, and the historical record hard to distinguish.

**Decision**: Keep the root focused on `birdsong.py`, core project metadata,
tests, and docs. Move active experiments under `experiments/active/`, older or
unsupported branches under `experiments/archive/`, helper scripts under
`tools/`, and preserved historical material under `archive/`.

**Alternatives**: Leave the flat layout in place and rely on documentation
alone, or create a larger package-style refactor with more abstraction.

**Consequences**: The repo becomes easier to trust and navigate. Some familiar
paths move, but the resulting support story is explicit and simpler.
