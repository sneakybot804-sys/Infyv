# Developer Guide

How to extend the project without breaking the foundation. Read
`ARCHITECTURE.md` first.

## Golden rules

1. **Never rewrite working modules.** Extend; don't replace.
2. **One feature per branch, small MRs.**
3. **No cloud services.** Everything runs locally.
4. **Analysis is read-only** with respect to source video.
5. **Config over code.** Tunables go in `config.py` / a config dataclass.

## How to add a new detector

A "detector" produces a signal from a video or from `analysis.json`.

1. Create a new module (e.g. `kill_detector.py`). **Do not** add game logic
   to `video_analyzer.py` — it must stay generic.
2. Define a config dataclass for its thresholds (mirror
   `GenericAnalysisConfig`), so behaviour is tunable without code edits.
3. Prefer **consuming `analysis.json`** (or `FrameMetrics`) over re-decoding
   the video. If you need pixels, reuse the analyzer's sampling pattern.
4. Return **dataclasses** with `to_dict()`; add a `schema_version`.
5. Raise a module-specific error (e.g. `KillDetectorError`) and log before
   raising, matching the existing pattern.
6. Add unit tests using synthetic fixtures (see `tests/conftest.py`).
7. Wire it into the pipeline at the call site (e.g. `app.py`), not by
   editing unrelated modules.

## How to add a new AI model

1. Change `OllamaConfig.model` in `config.py` (no code change needed for a
   drop-in Ollama model).
2. Benchmark it with `benchmark.py`; record numbers in `PROJECT_STATUS.md`.
3. If the new model needs different prompting, add a prompt module under
   `prompts/` rather than editing `agent.py` logic.
4. If it needs a different backend/protocol, define an interface (Protocol)
   and keep `GamingEditorAgent` depending on the abstraction (DIP).

## How to add a new FFmpeg effect

1. Add a method to `FFmpegService` (Phase 6 work); do not call FFmpeg from
   elsewhere — the service is the single FFmpeg choke point.
2. Validate inputs, build the `ffmpeg-python` graph, run with
   `overwrite_output().run(quiet=True)`.
3. Normalize failures via `_raise_run_error(...)` → `FFmpegServiceError`.
4. Return the output `Path`.
5. Add a docstring, type hints, and a test (can assert the constructed
   command / run against a tiny synthetic clip).

## How to add a new export format

1. Add an `export_<fmt>` method to `FFmpegService` alongside `export_mp4`.
2. Keep codec/container choices as parameters with sensible defaults.
3. Use `movflags="+faststart"`-style container-appropriate flags.
4. Document the format and defaults in `JSON_SCHEMA.md` / `DEVELOPER_GUIDE`
   as relevant, and add a test.

## Coding standards

- **Python style:** PEP 8, `from __future__ import annotations` at the top.
- **Type hints:** required on all public functions and dataclass fields.
- **Docstrings:** required on every public class and method.
- **Dataclasses:** use for structured data; `frozen=True` for config/value
  objects.
- **Logging:** always via `get_logger(__name__)`; `%`-style lazy formatting
  (`logger.info("x=%s", x)`), never f-strings inside log calls.
- **Errors:** one custom exception type per service; log then raise; use
  `raise ... from exc` to preserve the cause.
- **Purity:** keep computation in static/pure functions where possible for
  testability.
- **Tests:** `pytest`; synthetic fixtures; no binary media in the repo; no
  network or FFmpeg dependency in unit tests (inject fakes).

## Running tests

```bash
pip install -r requirements.txt
pytest -q
```
