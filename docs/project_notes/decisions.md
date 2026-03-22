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

## ADR-002: One Kept Branch Per Experiment Idea (2026-03-22)

**Context**: The experiment tree still contained exact duplicates and several
branches whose headers implied they were current or final when they were really
historical side paths.

**Decision**: Keep only one distinct branch per idea unless a second file adds
real explanatory value. Remove exact duplicates, keep only smoke-tested
experiments in `experiments/active/`, and mark archived branches explicitly in
their headers or directory docs.

**Alternatives**: Keep every branch indefinitely, or collapse all experiments
into a single large framework.

**Consequences**: The experiment tree stays smaller and easier to trust. Some
historical redundancy is removed, but the preserved branches carry clearer
status and intent.
