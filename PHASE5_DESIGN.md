# Phase 5 Design — Gaming Intelligence

**Design only. No code.** This document specifies *what* Phase 5 builds and
*how the pieces fit*, so implementation can proceed in small, testable MRs.

Phase 5 turns the generic `analysis.json` (Phase 4A) into **game-aware**
understanding, producing a ranked `highlight.json` (see `JSON_SCHEMA.md`)
for the Phase 6 editor.

## Design constraints

- Fully local; CPU-first on Ryzen 7 5700G / 16 GB, GPU optional.
- **Do not modify** `video_analyzer.py` (keep it generic). Phase 5 detectors
  are **new modules** that consume `analysis.json` and/or sampled frames.
- Each detector: own config dataclass, own error type, dataclass output with
  `schema_version`, unit tests with synthetic fixtures.
- Detectors are **independent and composable**; the ranker fuses them.

## Component overview

```
analysis.json ─┐
               ├─► Kill Detector ─────┐
 frames ───────┤                       │
               ├─► HUD Detector ──► OCR ┤
               │                       ├─► Highlight Ranker ─► highlight.json
 audio ────────┼─► Audio Analysis ─────┤            │
               └─► Voice Excitement ───┘            ▼
                                          AI Decision Pipeline (Ollama)
```

## 1. Kill Detection

- **Goal:** flag elimination events as highlight candidates with timestamps
  and confidence.
- **Inputs:** sampled frames (kill-feed / center-screen region), optionally
  audio onsets; `analysis.json` motion/brightness as priors.
- **Approach options (choose per game, keep behind an interface):**
  - Template / icon matching on the kill-feed region.
  - OCR of kill-feed text (see OCR component).
  - Lightweight learned classifier (optional GPU) on a cropped region.
- **Output:** `[{timestamp, confidence, source}]`.
- **Design notes:** HUD detection should provide the kill-feed region so the
  kill detector only processes a small crop (CPU-friendly).

## 2. HUD Detection

- **Goal:** locate persistent HUD regions (health, ammo, minimap, kill
  feed) to focus other detectors and reduce work.
- **Approach:** detect stable, low-motion overlay regions across time using
  the existing per-frame data (regions with low variance / persistent
  edges), plus optional per-game region templates.
- **Output:** named bounding boxes with confidence, ideally computed once
  per video (HUD position is stable).
- **Design notes:** HUD layout is game-specific; store profiles in config so
  new games are added without code changes.

## 3. OCR

- **Goal:** read text from HUD/kill-feed crops (killstreak banners, scores,
  player names, timers).
- **Approach:** local OCR engine (e.g. Tesseract) on small crops provided by
  HUD detection; never OCR the full frame (too slow).
- **Output:** `[{region, text, timestamp, confidence}]`.
- **Design notes:** pre-process crops (threshold/upscale) for accuracy;
  cache per-region results; throttle OCR frequency.

## 4. Audio Analysis

- **Goal:** extract audio-based highlight cues.
- **Inputs:** audio extracted via `FFmpegService.extract_audio`.
- **Features:** short-time energy / RMS, onset detection, spectral cues for
  gunfire/explosions.
- **Output:** time series + discrete events `[{start, end, type, energy}]`.
- **Design notes:** audio is cheap relative to video and a strong highlight
  signal; compute independently of the video detectors.

## 5. Voice Excitement

- **Goal:** detect excited player commentary (a strong "this was cool"
  signal).
- **Approach:** separate/assume a commentary track; measure pitch, loudness
  and speech-rate spikes; optionally a small local model.
- **Output:** excitement score time series + peaks.
- **Design notes:** keep decoupled from transcription (Phase 7 Whisper) —
  excitement is prosody, not words.

## 6. Highlight Ranking

- **Goal:** fuse all signals into a ranked list of highlight windows.
- **Approach:** normalize each signal to 0..1, combine with configurable
  weights into a score per candidate window, merge overlapping windows,
  sort by score.
- **Output:** `highlight.json` (`highlights[]` with `score`, `type`,
  per-signal `signals`, and any `ocr`).
- **Design notes:** weights live in config (OCP); ranking is deterministic
  and unit-testable with synthetic signal inputs.

## 7. AI Decision Pipeline

- **Goal:** use Ollama to reason over the ranked highlights and produce a
  coherent edit plan (which clips, order, pacing, why).
- **Inputs:** `highlight.json` + video metadata.
- **Approach:** structured prompt → LLM → validated `edit_plan.json`
  (Phase 6 consumes it). Reuse `GamingEditorAgent`/Ollama; add a new prompt
  module rather than changing agent logic.
- **Output:** `edit_plan.json` (see `JSON_SCHEMA.md`).
- **Design notes:** validate the LLM output against the schema; fall back to
  a deterministic top-N selection if the LLM output is invalid.

## Suggested implementation order (small MRs)

1. Audio analysis (cheap, high-signal, independent).
2. HUD detection (unlocks focused crops).
3. OCR (depends on HUD crops).
4. Kill detection (uses HUD + OCR + audio).
5. Voice excitement.
6. Highlight ranker (fuses 1–5 → `highlight.json`).
7. AI decision pipeline (`highlight.json` → `edit_plan.json`).

Each step ships with its own config, tests and schema updates, and must not
modify the Phase 4A generic analyzer.
