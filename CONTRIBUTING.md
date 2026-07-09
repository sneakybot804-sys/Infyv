# Contributing

Thank you for working on the Local AI Gaming Video Editor. This project
values **maintainability over quick features**. Please read
`ARCHITECTURE.md` and `DEVELOPER_GUIDE.md` before contributing.

## Principles

- **Local-first.** No cloud AI or external services. Ollama runs locally.
- **Never rewrite working modules.** Extend the architecture instead.
- **Small, focused MRs.** One feature per branch.
- **Production quality.** Type hints, docstrings, logging, tests.
- **Respect phase boundaries.** Generic analysis stays generic; game logic
  belongs to Phase 5+ modules.

## Branching

- `main` — stable, merged phases.
- `feature/<phase-or-topic>` — one feature/topic per branch.
- `docs/<topic>` — documentation-only changes.
- Phase sub-work (e.g. review fixes) may target the phase branch, which then
  merges to `main`.

## Commit messages

- Imperative subject line, scoped where useful (e.g.
  `video_analyzer: guard shape mismatch`).
- Body explains **what** and **why**, not just how.
- Group related changes; keep commits reviewable.

## Merge requests

- Describe scope, what changed, and any limitations.
- State the **verification status** honestly (what was and wasn't run).
- Keep MRs focused on a single concern.
- No new features in review/refactor/docs MRs.

## Coding conventions

- PEP 8; `from __future__ import annotations` first line of code.
- Type hints on all public APIs and dataclass fields.
- Docstrings on every public class/method.
- `frozen=True` dataclasses for config/value objects.
- Logging via `get_logger(__name__)` with lazy `%` formatting.
- One custom exception per service; `raise ... from exc`.
- No FFmpeg calls outside `FFmpegService`; no direct network calls outside
  the AI agent.

## Tests

- Framework: `pytest`.
- Use synthetic fixtures; **no binary media in the repo**.
- Unit tests must not require a network, a GPU, or a real Ollama/FFmpeg
  install (inject fakes / use the `MetadataReader` protocol).
- New detectors/effects/formats require tests.

Run:

```bash
pip install -r requirements.txt
pytest -q
```

## Documentation

- Update the relevant doc when behaviour or schemas change.
- Bump `schema_version` and update `JSON_SCHEMA.md` for any JSON change.
- Keep `PROJECT_STATUS.md` current when phases progress.
