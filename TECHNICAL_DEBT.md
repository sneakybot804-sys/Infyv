# Technical Debt

A review of the repository as of 2026-07-09 (Phases 1–4A). This tracks known
debt; it does **not** change code. Items are prioritized as Low / Medium /
High by likely future impact.

## Unused / redundant files

- **`utils/__init__.py`** — empty placeholder package with no modules.
  Harmless, but currently dead. *(Low)* — keep only if a shared util lands
  soon (see duplicate code below); otherwise remove.
- **`assets/`, `videos/`, `output/`** — runtime folders kept via
  placeholders. Expected; ensure generated artifacts (e.g. `output/*.json`,
  `logs/`) are git-ignored. *(Low)* — verify `.gitignore` covers runtime
  output so analysis files aren't accidentally committed.

## Duplicate code

- **`_validate_input` is duplicated** in `ffmpeg_service.py`,
  `scene_detector.py` and `video_analyzer.py` (identical exists/is-file
  logic, differing only in the raised error type). *(Medium)* — extract a
  shared `validate_video_path()` helper (e.g. a small `media_io.py`) that
  raises a passed-in error type. Deferred to avoid touching completed
  modules mid-phase.
- **Grayscale/downscale conversion** exists in both `scene_detector.py`
  (`_to_analysis_gray`) and `video_analyzer.py`. *(Medium)* — candidate for
  the same shared `media_io.py`.
- **Frame sampling loop** (open capture, step, read/skip, release) is
  structurally similar between `scene_detector.py` and `video_analyzer.py`.
  *(Medium)* — a shared frame-sampler utility would remove the duplication
  and give one place to add hardware-accelerated decode later.

## Overlapping responsibilities

- **`scene_detector.py` vs `video_analyzer.py`.** Both detect scenes and
  compute motion/brightness, but `scene_detector` is optical-flow based and
  contains game-flavoured heuristics (kill/explosion), while `video_analyzer`
  is the generic Phase 4A analyzer. *(Medium/High)* — decide the long-term
  role of `scene_detector.py`: either retire it, or refold its
  game-heuristic parts into Phase 5 detectors. Leaving both risks confusion
  about "which analyzer is canonical".

## Refactoring opportunities

- **Shared `media_io.py`** for path validation, gray/downscale, and frame
  sampling (addresses the duplicate-code items above). *(Medium)*
- **Config unification.** `GenericAnalysisConfig` (analyzer) and
  `AnalysisConfig` (scene_detector) overlap; if `scene_detector` survives,
  consider a shared base. *(Low)*
- **JSON schema validation.** Artifacts are generated but not validated on
  read. When Phase 5/6 start consuming `analysis.json`/`highlight.json`, add
  lightweight schema validation keyed off `schema_version`. *(Medium)*
- **Decode cost on long videos.** Every frame is decoded even when
  sub-sampling. *(Medium)* — explore hardware decode / segment parallelism
  (see `PERFORMANCE.md`). Behind a feature flag; CPU path stays default.

## Testing gaps

- **No CI pipeline.** Tests run only locally. *(Medium)* — add a CI job to
  run `pytest` on MRs. (OpenCV `VideoWriter` codec availability in CI is the
  main thing to validate.)
- **No tests for `agent.py` / `ffmpeg_service.py` / `benchmark.py`.**
  *(Medium)* — add tests with a stubbed HTTP layer for the agent and a
  synthetic clip for the FFmpeg service.
- **No acceptance harness.** Real-gameplay verification is manual. *(Low)*

## Operational / hygiene

- **Dependency pinning.** `requirements.txt` is unpinned. *(Medium)* — pin
  versions (or add a lockfile) for reproducible installs on Windows.
- **`agent.py` uses `urllib`** rather than a client library. Fine and
  dependency-free, but streaming/retries are manual. *(Low)*
- **No `pyproject.toml` / linter config.** *(Low)* — consider adding
  `ruff`/`black`/`mypy` config to enforce the documented standards
  automatically.

## Explicitly NOT debt (by design)

- Frame differencing instead of optical flow in `video_analyzer` — a
  deliberate performance trade-off, documented.
- CLI-only entry point — GUI is Phase 8.
- `qwen3:8b` slowness — tracked as a model-selection task, not code debt.
