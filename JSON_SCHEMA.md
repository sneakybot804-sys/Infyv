# JSON Schemas

All analysis artifacts are JSON with an explicit `schema_version`. Bump the
version whenever a shape changes so downstream consumers can adapt.

## analysis.json (Phase 4A) — `schema_version: "4a.1"`

Produced by `VideoAnalyzer`. Written to
`output/<video_name>_analysis.json` (never overwritten).

```json
{
  "schema_version": "4a.1",
  "video": "C:/path/to/videos/clip.mp4",
  "metadata": {
    "duration": 120.0,
    "width": 1920,
    "height": 1080,
    "fps": 60.0,
    "codec": "h264",
    "size_bytes": 52428800
  },
  "scenes": [
    {
      "index": 0,
      "start": 0.0,
      "end": 12.5,
      "duration": 12.5,
      "avg_motion": 8.42,
      "max_motion": 31.7,
      "avg_brightness": 96.3,
      "avg_static": 0.14
    }
  ],
  "idle_sections": [
    { "start": 40.0, "end": 46.0, "duration": 6.0 }
  ],
  "black_screens": [
    { "start": 0.0, "end": 1.5, "duration": 1.5 }
  ]
}
```

### Field reference

| Field | Type | Meaning |
| --- | --- | --- |
| `schema_version` | string | Schema identifier. |
| `video` | string | Absolute path to the analyzed video. |
| `metadata.duration` | float (s) | Total duration. |
| `metadata.width/height` | int (px) | Resolution. |
| `metadata.fps` | float | Frames per second. |
| `metadata.codec` | string | Video codec name. |
| `metadata.size_bytes` | int | File size in bytes. |
| `scenes[].index` | int | Scene order (0-based). |
| `scenes[].start/end/duration` | float (s) | Scene bounds. |
| `scenes[].avg_motion` | float 0..255 | Mean frame-difference motion. |
| `scenes[].max_motion` | float 0..255 | Peak motion in the scene. |
| `scenes[].avg_brightness` | float 0..255 | Mean brightness. |
| `scenes[].avg_static` | float 0..1 | Stillness = `1/(1+motion)`. |
| `idle_sections[]` | span | Low-motion spans ≥ `min_idle_seconds`. |
| `black_screens[]` | span | Dark spans ≥ `min_black_seconds`. |

Units: motion/brightness are 0..255 image-space values; static is 0..1.

## edit_plan.json (Phase 6, planned)

> Draft / not yet implemented. Shape subject to change; documented here to
> stabilize the interface between the AI decision pipeline and the editor.

```json
{
  "schema_version": "6.0-draft",
  "source_video": "C:/path/to/videos/clip.mp4",
  "output": "C:/path/to/output/clip_edit.mp4",
  "music": { "path": "assets/track.mp3", "gain_db": -6.0 },
  "segments": [
    {
      "start": 61.2,
      "end": 68.9,
      "reason": "triple kill",
      "effects": [
        { "type": "speed", "factor": 0.5, "start": 64.0, "end": 65.5 },
        { "type": "zoom", "factor": 1.3, "start": 64.0, "end": 65.5 }
      ],
      "transition_out": { "type": "crossfade", "duration": 0.4 }
    }
  ]
}
```

### Intended field reference

| Field | Type | Meaning |
| --- | --- | --- |
| `source_video` | string | Input video path. |
| `output` | string | Target render path. |
| `music` | object | Optional background track + gain. |
| `segments[].start/end` | float (s) | Clip bounds to keep. |
| `segments[].reason` | string | Why the AI kept this moment. |
| `segments[].effects[]` | list | Ordered effects (speed/zoom/slow-mo). |
| `segments[].transition_out` | object | Transition to the next segment. |

## highlight.json (Phase 5, planned)

> Draft / not yet implemented. Produced by the Phase 5 highlight ranker;
> consumed by the Phase 6 AI decision pipeline.

```json
{
  "schema_version": "5.0-draft",
  "video": "C:/path/to/videos/clip.mp4",
  "highlights": [
    {
      "start": 61.2,
      "end": 68.9,
      "score": 0.92,
      "type": "kill",
      "signals": {
        "kill": 0.95,
        "audio_energy": 0.80,
        "voice_excitement": 0.71,
        "motion": 0.66
      },
      "ocr": ["TRIPLE KILL"]
    }
  ]
}
```

### Intended field reference

| Field | Type | Meaning |
| --- | --- | --- |
| `highlights[].start/end` | float (s) | Highlight bounds. |
| `highlights[].score` | float 0..1 | Fused ranking score. |
| `highlights[].type` | string | Dominant highlight category. |
| `highlights[].signals` | object | Per-signal contributions (0..1). |
| `highlights[].ocr` | list[string] | OCR text captured in the window. |

## enriched_highlight.json (Phase 5D) — `schema_version: "5d.1"`

Produced by `SignalFusionEngine`. A pure consumer that fuses the frozen
Phase 5 artifacts at **scene level** into a ranked artifact. Written to
`output/<video_name>_enriched_highlight.json` (never overwritten). No
existing artifact is modified.

Inputs (aligned by scene index — `highlight.index` == `ocr`/`audio`
`scene_index`):
- `highlight.json` (`5a.1`) — **required** backbone. A missing highlight
  artifact raises `FusionError`.
- `ocr.json` (`5b.1`) — optional. Missing → the OCR signal contributes 0.
- `audio.json` (`5c.1`) — optional. Missing → the audio signals contribute 0.

Scores are exposed on the same **0..100** scale as Phase 5A.

```json
{
  "schema_version": "5d.1",
  "video": "C:/path/to/videos/clip.mp4",
  "sources": {
    "highlight": { "available": true, "schema_version": "5a.1" },
    "ocr":       { "available": true, "schema_version": "5b.1" },
    "audio":     { "available": false, "schema_version": null }
  },
  "scenes": [
    {
      "index": 3,
      "start": 61.2,
      "end": 68.9,
      "duration": 7.7,
      "score": 87.0,
      "classification": "Excellent",
      "rank": 1,
      "signals": {
        "base_highlight": 0.74,
        "ocr": 0.90,
        "audio_energy": 0.0,
        "voice_excitement": 0.0
      },
      "ocr": ["TRIPLE KILL"]
    }
  ]
}
```

### Field reference

| Field | Type | Meaning |
| --- | --- | --- |
| `schema_version` | string | Schema identifier (`5d.1`). |
| `video` | string | Path to the video (from the highlight artifact). |
| `sources.<name>.available` | bool | Whether that input artifact was present. |
| `sources.<name>.schema_version` | string\|null | Input artifact schema, or null if absent. |
| `scenes[].index` | int | Phase 4A scene index (backbone identity). |
| `scenes[].start/end/duration` | float (s) | Scene bounds (from the highlight artifact). |
| `scenes[].score` | float 0..100 | Fused score (0..1 internally, scaled to 0..100). |
| `scenes[].classification` | string | `Excellent`/`Good`/`Average`/`Ignore` (fused thresholds). |
| `scenes[].rank` | int | 1-based rank by fused score (deterministic). |
| `scenes[].signals` | object | Per-signal 0..1 contributions before weighting. |
| `scenes[].signals.base_highlight` | float 0..1 | Normalized Phase 5A score. |
| `scenes[].signals.ocr` | float 0..1 | Normalized max OCR confidence in the scene. |
| `scenes[].signals.audio_energy` | float 0..1 | Normalized max acoustic-event energy in the scene. |
| `scenes[].signals.voice_excitement` | float 0..1 | Normalized max commentary excitement peak in the scene. |
| `scenes[].ocr` | list[string] | OCR text captured in the scene (transparency). |

Notes:
- **Scene-level only.** Detections / events / peaks with a null
  `scene_index` contribute to no scene; time-window fusion is deferred.
- `top_n` in `FusionConfig` controls selection: `None` keeps all scenes, a
  positive integer keeps the top-N by fused score.

## Versioning policy

- `schema_version` is mandatory in every artifact.
- Additive fields → bump the minor version; consumers ignore unknown fields.
- Removed/renamed fields → bump the major version.
