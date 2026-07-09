# Architecture

The Local AI Gaming Video Editor is a **modular, local-only** Python
application. Every module has a single responsibility, depends on
abstractions where practical, and shares one configuration singleton and one
logging helper.

## High-level pipeline

```
Gameplay Video
      │
      ▼
Video Picker            (video_picker.py)
      │
      ▼
Video Analyzer          (video_analyzer.py)   ← reuses FFmpeg service
      │
      ▼
analysis.json           (output/<video>_analysis.json)
      │
      ▼
Ollama                  (agent.py)            ← local LLM
      │
      ▼
edit_plan.json          (planned, Phase 6)
      │
      ▼
FFmpeg Editor           (planned, Phase 6, builds on ffmpeg_service.py)
      │
      ▼
Final Video
```

Today, everything up to `analysis.json` is implemented, plus a text-based
edit-plan path via Ollama. The `edit_plan.json` → FFmpeg Editor → Final
Video stages are future work (Phases 5–6).

## Module responsibilities

### `config.py`
Dataclass-based configuration. `OllamaConfig` (host, model, timeout,
temperature), `PathConfig` (project directory layout), and `AppConfig` (the
top-level object). A single shared `config` instance is imported across the
app. `ensure_directories()` creates the working folders. Frozen dataclasses
keep config immutable at runtime.

### `logger.py`
`get_logger(name)` returns a configured logger with a console handler and a
rotating file handler (`logs/app.log`, 5 MB × 3). Handlers are attached once
per logger name to avoid duplicate output. All modules log through this.

### `ffmpeg_service.py`
`FFmpegService` wraps the system FFmpeg binary via `ffmpeg-python`.
Responsibilities: read metadata (`VideoMetadata`) and perform core
operations — `trim_video`, `merge_videos`, `extract_audio`,
`extract_frames`, `export_mp4`. Errors are normalized to
`FFmpegServiceError`. This is the single choke point for all FFmpeg access.

### `agent.py`
`GamingEditorAgent` connects to a local Ollama model over HTTP
(`/api/generate`) and produces an edit plan from a gameplay description.
Strips qwen `<think>` blocks. Errors are normalized to
`OllamaConnectionError`. Prompt text lives in `prompts/edit_plan.py`.

### `scene_detector.py` (Phase 3 legacy analyzer)
`SceneDetector` combines PySceneDetect with OpenCV optical-flow analysis to
produce scene/highlight/boring-section JSON. It contains **game-flavoured
heuristics** (kill/explosion/camera). It predates Phase 4A and is kept
unchanged; Phase 4A intentionally provides a separate, **generic** analyzer.

### `video_picker.py` (Phase 4A)
`VideoPicker` selects a video via a native Tkinter dialog, falling back to a
CLI list of `videos/`. Decoupled from analysis so the Phase 8 GUI can swap
the selection strategy without touching analysis code. Exposes pure helpers
(`filter_videos`, `list_videos`).

### `video_analyzer.py` (Phase 4A)
`VideoAnalyzer` is the generic, game-agnostic analyzer. It reuses
`FFmpegService` for metadata (through a `MetadataReader` Protocol),
PySceneDetect for scene boundaries, and lightweight OpenCV frame
differencing for motion/brightness/static scores, idle sections and
black-screen detection. Output is `VideoAnalysis` → `analysis.json`. Pure
metric functions are static for testability.

### `app.py`
CLI entry point. A small menu dispatches to the Ollama edit-plan flow
(Phase 3) or the Phase 4A analyze flow.

### `benchmark.py`
Measures Ollama model latency (first token, total, tokens/sec) to guide
model selection.

## Dependency direction

```
app.py ──► agent.py ──► prompts/, config, logger
app.py ──► video_picker.py ──► config, logger
app.py ──► video_analyzer.py ──► ffmpeg_service.py ──► config, logger
video_analyzer.py ──► (config, logger, OpenCV, PySceneDetect)
logger.py ──► config.py
```

No circular dependencies. Leaf modules (`config`, `logger`) depend on
nothing project-specific. `video_analyzer` depends on `ffmpeg_service` only
through the `MetadataReader` protocol, so the concrete service is
substitutable (used in tests).

## Design principles

- **Local-first:** no cloud AI; Ollama runs on `localhost`.
- **SRP:** one responsibility per module.
- **DIP:** analyzer depends on a metadata *protocol*, not a concrete class.
- **OCP:** thresholds and model choice live in config, not in logic.
- **Fail loud, normalized:** each service raises its own error type and logs
  before raising.
- **Read-only analysis:** analyzers never modify source video or existing
  project files.
