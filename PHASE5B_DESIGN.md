# Phase 5B Design — HUD Text Extraction (OCR)

**Status: design only. No code. Awaiting approval before implementation.**

Phase 5B adds a **completely independent** OCR stage that extracts on-screen
text from gameplay frames and writes its own artifact, `ocr.json`. It is
**not** integrated into the Highlight Scorer. A later, separate phase (the
Signal Fusion Engine) combines the independent artifacts.

## 1. Objectives

- Extract raw on-screen **text, timestamp, confidence, and region** from a
  small set of frames.
- Produce a standalone `ocr.json` artifact and nothing else.
- Stay **fully decoupled**: the Highlight Scorer remains unaware of OCR.
- Remain **game-agnostic**: never interpret text, never assume a game.
- Keep the OCR engine **pluggable** behind a Protocol.
- Run acceptably on the CPU-only baseline (Ryzen 7 5700G, 16 GB).

### Non-goals (explicitly out of scope for 5B)
- No integration with `HighlightScorer` (it stays unchanged and unaware).
- No signal fusion (that is its own later phase).
- No text interpretation (no "this means a kill").
- No game-specific logic.
- No editing, rendering, Ollama, or audio.

## 2. Architecture

OCR is a **parallel branch** off `analysis.json`. The Highlight Scorer and
the OCR Engine are siblings that never call each other; each emits its own
artifact. A future Signal Fusion Engine reads both.

```
Gameplay Video
        │
        ▼
Video Analyzer
        │
        ▼
analysis.json
        │
        ├──────────────┐
        ▼              ▼
Highlight Scorer     OCR Engine
        │              │
        ▼              ▼
highlight.json      ocr.json
        └──────┬───────┘
               ▼
Signal Fusion Engine   (separate future phase)
               ▼
enriched_highlight.json
```

**Key rule:** the Highlight Scorer is never modified for OCR. OCR produces
`ocr.json` only. Fusion happens elsewhere, later, by reading artifacts.

### 2.1 Modules introduced in Phase 5B

| Module | Responsibility |
| --- | --- |
| `ocr_engine.py` | `OcrEngine` **Protocol** + concrete `TesseractOcrEngine`. Turns an image (numpy array) into raw text results. Swappable. |
| `hud_text_extractor.py` | Orchestrator: samples frames (per-scene, via a shared sampler), applies configurable regions of interest (ROIs), calls the engine, aggregates, and writes `ocr.json`. |
| `ocr_config.py` (or a dataclass in the extractor) | `OcrConfig`: engine selection, ROIs, sampling density, preprocessing, thresholds. No magic numbers. |

The Signal Fusion Engine (`signal_fusion.py`) is **not** part of 5B; it is
documented here only to show where OCR fits.

### 2.2 Module dependency diagram

```
                 +-------------------+
                 |   config.py       |
                 |   logger.py       |
                 +---------+---------+
                           ^
                           | (config, logging)
        +------------------+------------------+
        |                                     |
+-------v---------+                   +--------v--------+
| hud_text_       |  uses (Protocol)  |   ocr_engine.py |
| extractor.py    +------------------>|  OcrEngine      |
|                 |                   |  (Protocol)     |
| - sampling      |                   |   ^             |
| - ROI crop      |                   |   | implements  |
| - aggregation   |                   | +-+------------+|
| - writes        |                   | | Tesseract    ||
|   ocr.json      |                   | | (default)    ||
+-------+---------+                   | +--------------+|
        |                             +-----------------+
        | reads (scene bounds)
        v
   analysis.json  (Phase 4A artifact; read-only)

NOTE: no arrow ever points from hud_text_extractor or ocr_engine to
highlight_scorer.py. They are fully decoupled.
```

Dependency direction: `hud_text_extractor` → `ocr_engine` (via Protocol) →
`config`/`logger`. Nothing depends on `highlight_scorer`, and
`highlight_scorer` depends on nothing new. No cycles.

## 3. Input / Output

### Input
- Video path.
- Phase 4A `analysis.json` (read-only) for **scene bounds** so OCR runs on a
  few representative frames per scene instead of the whole video.
- `OcrConfig` (engine, ROIs, sampling, preprocessing, thresholds).

### Output: `ocr.json` (own artifact, never overwritten)

Written to `output/<video_name>_ocr.json`. Proposed schema `5b.1`:

```json
{
  "schema_version": "5b.1",
  "video": "C:/path/to/videos/clip.mp4",
  "engine": "tesseract",
  "detections": [
    {
      "scene_index": 3,
      "timestamp": 64.0,
      "region": "top_right",
      "text": "TRIPLE KILL",
      "confidence": 0.88,
      "bbox": { "x": 0.72, "y": 0.08, "w": 0.25, "h": 0.05 }
    }
  ]
}
```

Field meaning (raw extraction only — **no interpretation**):

| Field | Type | Meaning |
| --- | --- | --- |
| `engine` | string | Backend that produced the results. |
| `detections[].scene_index` | int | Phase 4A scene the frame belongs to. |
| `detections[].timestamp` | float (s) | Frame time. |
| `detections[].region` | string | Named ROI (config label, not a game concept). |
| `detections[].text` | string | Raw recognized text. |
| `detections[].confidence` | float 0..1 | Engine confidence. |
| `detections[].bbox` | object | Normalized 0..1 location. |

The `region` label is a **generic ROI name** from config (e.g. `top_right`),
not a game-specific meaning like "kill feed".

## 4. OcrEngine Protocol (pluggable backends)

```
class OcrEngine(Protocol):
    name: str
    def recognize(self, image: NDArray, /) -> list[OcrResult]: ...

# OcrResult: text, confidence, bbox (normalized)
```

- **Default backend:** `TesseractOcrEngine` (local, CPU-friendly, permissive
  license, easy Windows install via the Tesseract binary).
- **Future optional backends** (added later without touching the extractor):
  - `RapidOcrEngine` (ONNXRuntime; light, decent CPU speed).
  - `EasyOcrEngine` (accurate; heavy, GPU-preferred).
  - `PaddleOcrEngine` (accurate; heavy deps).
- Engine chosen via `OcrConfig`; extractor depends only on the Protocol
  (Dependency Inversion). Tests inject a fake engine.

## 5. No game assumptions / no interpretation

- OCR extracts `text, timestamp, confidence, region` and stops.
- It never decides what text *means* (no kills, no scores, no events).
- ROIs are generic, config-defined rectangles with neutral labels.
- Any game meaning is assigned later by adapters (section 8) or fusion,
  never inside OCR.

## 6. Performance impact

OCR is much heavier per frame than Phase 4A differencing. All mitigations
are config-driven:

- **Per-scene sampling:** OCR only 1–2 frames per scene → cost scales with
  scene count, not video length.
- **ROI cropping:** OCR only small configured rectangles, not full frames.
- **Skip low-value scenes:** optionally skip scenes marked idle/black in
  `analysis.json`.
- **Preprocessing:** grayscale/threshold/upscale crops for accuracy.
- GPU backends are an optional future accelerator; the CPU path (Tesseract)
  stays the default and must remain viable on the Ryzen 5700G.

Expected added runtime: seconds-to-minutes depending on scene count and ROI
size. OCR is an **optional stage**, off unless requested.

## 7. Risks

| Risk | Mitigation |
| --- | --- |
| Poor accuracy on stylized game fonts / motion blur | ROIs + preprocessing + swappable engine. |
| Game-specificity creep | ROIs are config profiles; OCR never interprets; adapters live outside OCR. |
| Tesseract system-binary install friction on Windows | Document setup; fail gracefully with a clear error (mirror FFmpeg pattern); OCR optional. |
| CPU latency regressions | Per-scene sampling, ROI crops, skip low-value scenes, config toggle. |
| Sampling-loop duplication with Phase 4A | Reuse a shared `media_io` sampler (TECHNICAL_DEBT) rather than copying. |
| Coupling drift over time | Architectural rule: no dependency from OCR → scorer; enforced in review. |

## 8. Future plugin architecture (game-specific adapters)

Game-specific behaviour is added **outside** OCR, so new games never modify
the OCR engine or extractor.

```
            ocr.json  (generic: text/timestamp/confidence/region)
                 │
                 ▼
        +--------------------+
        |  GameAdapter        |   <-- Protocol / plugin registry
        |  (interpretation)   |
        +----------+----------+
            ^   ^   ^   ^
            |   |   |   |  (register by game id; discovered dynamically)
     Valorant CS2 PUBG ...  each maps generic detections -> game events
                 │
                 ▼
     (feeds the Signal Fusion Engine / higher phases)
```

- **`GameAdapter` Protocol:** `interpret(ocr: OcrDocument) -> GameSignals`.
- **Plugin registry:** adapters register by game id; the pipeline selects an
  adapter by config, defaulting to a **no-op passthrough** (fully generic).
- Adapters are the *only* place game meaning exists. OCR, the scorer, and
  fusion stay generic.
- Adding Valorant/CS2/PUBG later = add a new adapter module + registry
  entry. Zero changes to `ocr_engine.py` or `hud_text_extractor.py`.

## 9. Signal Fusion Engine (separate future phase — context only)

Not part of 5B. Documented so OCR's role is clear:

- Reads `highlight.json` + `ocr.json` (+ future `audio.json`).
- Produces `enriched_highlight.json`.
- **Does not modify** the Highlight Scorer, OCR, or audio modules — it only
  consumes their artifacts.
- This is where OCR text (optionally via a game adapter) can raise/lower a
  highlight's confidence — keeping every producer module independent.

## 10. Sequence diagrams

### 10.1 OCR extraction (Phase 5B)

```
User/CLI        HudTextExtractor      analysis.json     OcrEngine        ocr.json
   |                  |                    |                |               |
   | run OCR(video)   |                    |                |               |
   |----------------->|                    |                |               |
   |                  | read scene bounds  |                |               |
   |                  |------------------->|                |               |
   |                  |<-- scenes ---------|                |               |
   |                  |                    |                |               |
   |          loop over selected scenes/frames               |             |
   |                  |  sample frame + crop ROI             |             |
   |                  |------------------------------------->| recognize() |
   |                  |<-- [text,conf,bbox] -----------------|             |
   |                  |  aggregate detection                 |             |
   |                  |                                      |             |
   |                  | write ocr.json (never overwrite)     |             |
   |                  |------------------------------------------------->  |
   |<-- path ---------|                                                    |
```

Note: no interaction with the Highlight Scorer anywhere in this sequence.

### 10.2 Full pipeline with future fusion (context)

```
VideoAnalyzer -> analysis.json
     |                |
     |     +----------+-----------+
     |     |                      |
     v     v                      v
 HighlightScorer            HudTextExtractor -> OcrEngine
     |                            |
     v                            v
 highlight.json                ocr.json
     |                            |
     +-------------+--------------+
                   v
         SignalFusionEngine   (separate phase; reads artifacts only)
                   v
         enriched_highlight.json
```

## 11. Test strategy

- **Unit, engine-free:** inject a **fake `OcrEngine`** returning canned
  results; test ROI mapping, per-scene assignment, aggregation, schema, and
  never-overwrite I/O.
- **Preprocessing:** deterministic transforms on synthetic numpy images
  (grayscale/threshold/upscale) with asserted outputs.
- **Config:** engine selection, ROIs, sampling density, skip rules all
  honored; no magic numbers.
- **Decoupling guard:** a test/asserts that the OCR modules do **not**
  import `highlight_scorer`, protecting the independence rule.
- **Adapter passthrough:** default no-op adapter leaves detections
  unchanged.
- **Optional integration (skippable):** render a synthetic frame with known
  text via OpenCV `putText`, run real Tesseract, assert recovery; auto-skip
  when Tesseract is not installed so unit/CI runs stay dependency-free.
- **Regression:** existing Phase 4A and 5A tests must pass unchanged
  (proves nothing coupled into the scorer).

## 12. Open questions for approval

1. Artifact name/location confirmed as `output/<video>_ocr.json`?
2. ROIs as **static config profiles** for 5B (automatic HUD-region
   detection deferred to a later refinement) — acceptable?
3. Schema id `5b.1` for `ocr.json` acceptable?

**No implementation will begin until this design is approved.**
