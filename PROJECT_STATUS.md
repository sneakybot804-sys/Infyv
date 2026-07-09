# Project Status

**Project:** Local AI Gaming Video Editor (Windows 11, fully local, Ollama)
**Status date:** 2026-07-09
**Language:** Python

## Completion

**Overall: ~45% of the planned roadmap (Phases 1–4A of 8).**

The foundation (architecture, media I/O, local AI integration, generic
analysis) is complete. The gaming intelligence, editing, subtitle and GUI
phases are not started.

| Phase | Scope | Status |
| --- | --- | --- |
| 1 | Project architecture | ✅ Done |
| 2 | FFmpeg service | ✅ Done |
| 3 | Ollama integration (streaming) | ✅ Done |
| 3.5 | Benchmark system | ✅ Done |
| 4A | Generic video analysis | ✅ Done (in review) |
| 5 | Gaming intelligence | ⬜ Not started (designed) |
| 6 | Automatic FFmpeg editing | ⬜ Not started |
| 7 | Subtitle engine (Whisper) | ⬜ Not started |
| 8 | GUI | ⬜ Not started |

## Completed phases (detail)

- **Phase 1 — Architecture.** `config.py` (dataclass config + shared
  `config` singleton), `logger.py` (rotating file + console), `app.py` CLI
  entry point, project folder layout.
- **Phase 2 — FFmpeg service.** `ffmpeg_service.py` — metadata (duration,
  resolution, FPS, codec, size) and operations (trim, merge, extract audio,
  extract frames, export MP4).
- **Phase 3 — Ollama.** `agent.py` — `GamingEditorAgent` talks to a local
  Ollama model and generates an edit plan from a text description.
- **Phase 3.5 — Benchmark.** `benchmark.py` — measures model latency and
  throughput.
- **Phase 4A — Generic analysis.** `video_analyzer.py` +
  `video_picker.py` — game-agnostic metadata, scene detection, motion,
  brightness, static score, idle and black-screen detection →
  `output/<video>_analysis.json`. No game heuristics, no editing.

## Remaining phases

See `ROADMAP.md` for full detail. Summary:

- **Phase 5:** kill/HUD detection, OCR, audio/voice excitement, highlight
  ranking, AI decision pipeline. Design in `PHASE5_DESIGN.md`.
- **Phase 6:** automatic FFmpeg editing (cuts, speed ramp, zoom, slow-mo,
  transitions, music).
- **Phase 7:** subtitle engine (Whisper, word highlighting, emoji).
- **Phase 8:** GUI (timeline, drag & drop, export, batch).

## Current branch structure

- `main` — Phases 1–3.5 (Phase 4A not yet merged at time of writing).
- `feature/phase-4a-generic-analysis` — Phase 4A implementation (MR !7).
- `feature/phase-4a-review` — Phase 4A quality fixes (MR !8, targets the
  Phase 4A branch).
- `docs/project-foundation` — this documentation set.

Branching model: one feature per branch, small focused MRs. Phase 4A review
fixes merge into the Phase 4A branch, which then merges into `main`.

## Current merge requests

- **!7 — Phase 4A: Generic Video Analysis** → `main`. Open.
- **!8 — Phase 4A review fixes** → `feature/phase-4a-generic-analysis`. Open.
- **!1 — Phases 1–3 core** → `main`. Merged.

(Documentation MR for this branch is opened separately.)

## Known limitations

- **CPU-only, slow LLM.** `qwen3:8b` is functional but too slow for
  production on the target CPU (see benchmark below).
- **Full frame decode.** The analyzer decodes every frame even though it
  sub-samples; decode dominates runtime on long high-FPS videos.
- **Heuristic motion only.** Motion is frame differencing, not optical
  flow — fast but approximate (a deliberate performance trade-off).
- **No automated acceptance run.** Unit tests exist; a real-gameplay run is
  performed manually by the maintainer.
- **No CI yet.** Tests run locally via `pytest`.
- **No game intelligence.** Kill/HUD/OCR/voice are not implemented (Phase 5).

## Benchmark results

| Metric | qwen3:8b |
| --- | --- |
| First token | 82.34 s |
| Total | 293 s |
| Speed | 7.53 tokens/s |

Hardware: Ryzen 7 5700G, 16 GB RAM, CPU-only.

**Conclusion:** `qwen3:8b` is functional but too slow for production on this
CPU. Smaller models are planned for benchmarking: `qwen2.5:3b`, `gemma3:4b`.

## Recommended Ollama model

- **Current default:** `qwen3:8b` (best reasoning, too slow for production).
- **Recommended to benchmark next / likely production pick:** `qwen2.5:3b`
  or `gemma3:4b` for acceptable latency on CPU. The model is configurable in
  `config.py` (`OllamaConfig.model`), so switching requires no code change.
