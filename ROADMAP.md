# Roadmap

The project is built in phases. Each phase is self-contained, ships behind
small focused merge requests, and must not break earlier phases.

## Done

- **Phase 1 — Architecture.** Config, logging, CLI skeleton, folder layout.
- **Phase 2 — FFmpeg service.** Metadata + core operations.
- **Phase 3 — Ollama integration.** Local LLM edit-plan generation.
- **Phase 3.5 — Benchmark.** Model latency/throughput measurement.
- **Phase 4A — Generic video analysis.** Game-agnostic
  metadata/scene/motion/brightness/static/idle/black-screen →
  `analysis.json`.
- **Phase 5A-5E — Gaming intelligence.** Highlight scoring
  (`highlight.json`), OCR (`ocr.json`), audio analysis (`audio.json`),
  signal fusion (`enriched_highlight.json`), AI decision
  (`edit_plan.json`).
- **Phase 6 — Automatic rendering.** Trims and concatenates the edit plan
  into a rendered MP4.
- **Phase 7 — Subtitle engine.** `subtitles.json` (7.1) + `.srt` sidecar.

## Phase 8 — Premium Desktop GUI (in progress)

A PySide6 desktop application over a new, permanent, Qt-free `gui_core`
application layer. Backend stays frozen. See `PHASE8_DESIGN.md`.

- **8A — `gui_core`.** Facade, event bus, plugin registry, commands,
  pipeline gating, immutable state, runner, structured logs (this step).
- **8B — Theme foundation.** Centralized Qt-free design tokens, dark
  futuristic neon theme, glassmorphism/shadow/blur/motion tokens,
  typography/spacing/radius scales, SVG icon infrastructure, DPI support, and
  a single-authority ThemeManager with a dark-only switching seam (this step).
- **8C — Widget library.** Built in verified sub-steps: 8C-1 infrastructure
  (base/styling/animation/effects) [verified, frozen], 8C-2 primitives
  (GlassCard, NeonButton, IconButton, SectionHeader) [verified, frozen],
  8C-3 information/progress widgets (StatusBadge, MetaLabel, ProgressBar,
  StatBlock) [verified, frozen], 8C-4 interactive widgets (ToggleSwitch,
  Checkbox, TextField) [verified, frozen]; 8C-5..8C-6 advanced widgets are
  next. See `PHASE8C_DESIGN.md`, `PHASE8C3_DESIGN.md`, `PHASE8C4_DESIGN.md`.
- **8D-8I — GUI.** Main window, dashboard, pipeline view, remaining pages,
  animations/polish, optimization.

## Historical Phase 5 design notes

The original design-only notes for Phase 5 are retained below for reference;
the phases above are now implemented. See `PHASE5_DESIGN.md`.

- **Kill detection** — detect elimination events (kill feed / on-screen
  cues) as candidate highlights.
- **HUD detection** — locate and interpret HUD regions (health, ammo,
  minimap) to focus later detectors.
- **OCR** — read text from HUD/kill feed (killstreaks, scores, names).
- **Audio analysis** — energy/onset detection, gunfire/explosion cues.
- **Voice excitement** — detect excited player commentary as a highlight
  signal.
- **Highlight ranking** — combine signals into a ranked highlight list
  (`highlight.json`).
- **AI decision pipeline** — Ollama reasons over the fused signals to
  propose which moments to keep and why.

Deliverable: `highlight.json` consumed by Phase 6.

## Phase 6 — Automatic FFmpeg Editing

Turn highlights into a rendered edit. Builds on `ffmpeg_service.py`.

- Cut clips around ranked highlights.
- Speed ramps and slow motion around peak moments.
- Zoom / punch-in on action.
- Transitions between clips.
- Background music mixing and ducking.
- Consume an `edit_plan.json` produced by the AI decision pipeline.

Deliverable: a rendered highlight reel.

## Phase 7 — Subtitle Engine

- Whisper (local) transcription of commentary.
- Word-by-word highlighting and timing.
- Emoji / gaming-styled subtitles.
- Burn-in or sidecar subtitle output.

## Phase 8 — GUI

- Timeline view of scenes/highlights.
- Drag & drop clip arrangement.
- Export presets.
- Batch processing of multiple videos.
- Reuses the analyzer/editor as a backend; replaces `VideoPicker`/CLI.

## Guiding constraints (all phases)

- Fully local; no cloud AI.
- Windows 11 target; Ryzen 7 5700G / 16 GB baseline.
- Never rewrite working modules; extend the architecture.
- Production-quality Python: type hints, docstrings, logging, tests.
