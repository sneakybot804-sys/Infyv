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

## edit_plan.json (Phase 5E) — `schema_version: "5e.1"`

Produced by `DecisionAgent`. A pure consumer that reads
`enriched_highlight.json` (`5d.1`) and decides which scenes become clips,
either via a local Ollama model or a deterministic fallback. Written to
`output/<video_name>_edit_plan.json` (never overwritten). No producer
artifact is modified. The Phase 6 renderer consumes this schema unchanged.

Input:
- `enriched_highlight.json` (`5d.1`) — **required**. Missing → `DecisionError`.
- `analysis.json` (`4a.1`) — optional, used only for metadata context.

```json
{
  "schema_version": "5e.1",
  "source_video": "C:/path/to/videos/clip.mp4",
  "decision_source": "llm",
  "segments": [
    {
      "id": "segment-0001",
      "source_scene_index": 3,
      "start": 61.2,
      "end": 68.9,
      "score": 87.0,
      "reason": "score 87.0, Excellent"
    }
  ]
}
```

### Field reference

| Field | Type | Meaning |
| --- | --- | --- |
| `schema_version` | string | Schema identifier (`5e.1`). |
| `source_video` | string | Path to the video (from the enriched artifact). |
| `decision_source` | string | `"llm"` if the model produced the plan, `"fallback"` if the deterministic selection did. |
| `segments[].id` | string | Stable id (`segment-NNNN`). |
| `segments[].source_scene_index` | int | Phase 4A scene index the clip comes from. |
| `segments[].start/end` | float (s) | Clip bounds (scene bounds ± configured padding). |
| `segments[].score` | float 0..100 | Fused score carried from `enriched_highlight.json`. |
| `segments[].reason` | string | One short justification for keeping the clip. |

Notes:
- **Selection is configuration-driven** (`DecisionConfig`): a
  `FallbackStrategy` of `top_n`, `threshold` or `hybrid`, with
  `max_segments`, `top_n` and `min_score` caps.
- **LLM is best-effort.** The model response is validated against this
  schema; any failure (unreachable / invalid JSON / schema violation) falls
  back to the deterministic selection, so plan generation never hard-fails on
  an LLM problem.
- Segments may be padded (`pre_roll_seconds` / `post_roll_seconds`) and
  merged when adjacent (`merge_gap_seconds`), then re-numbered.

## subtitles.json (Phase 7) — `schema_version: "7.1"`

Produced by `SubtitleEngine`. An independent producer that extracts audio from
the ORIGINAL source video, transcribes it via a pluggable backend, and writes
deterministic cues. Written to `output/<video_name>_subtitles.json` (never
overwritten), with an optional `output/<video_name>.srt` sidecar. No other
artifact is consumed or modified.

The default `placeholder` backend returns an empty transcript, so the default
output has `cues: []`. No transcription library is a project dependency; a
real ASR backend can be registered later behind the same Protocol without a
schema or API change.

```json
{
  "schema_version": "7.1",
  "video": "C:/path/to/videos/clip.mp4",
  "language": "en",
  "backend": "placeholder",
  "cues": [
    {
      "id": "cue-0001",
      "start": 3.20,
      "end": 5.05,
      "text": "first line\nsecond line",
      "words": [
        { "text": "first", "start": 3.20, "end": 3.44, "confidence": 0.99 }
      ]
    }
  ]
}
```

### Field reference

| Field | Type | Meaning |
| --- | --- | --- |
| `schema_version` | string | Schema identifier (`7.1`). |
| `video` | string | Absolute path to the transcribed source video. |
| `language` | string\|null | Detected/-configured language, or null. |
| `backend` | string | Transcript backend that produced the cues. |
| `cues[].id` | string | Stable cue id (`cue-NNNN`). |
| `cues[].start/end` | float (s) | Cue timing (clamped to min/max cue duration). |
| `cues[].text` | string | Cue text; may contain `\n` for wrapped lines. |
| `cues[].words` | list | Per-word timings (empty when `word_timestamps` is off). |
| `cues[].words[].text` | string | Word text. |
| `cues[].words[].start/end` | float (s) | Word timing. |
| `cues[].words[].confidence` | float 0..1 | Backend confidence. |

Notes:
- **Deterministic.** Cue grouping (gap merge), duration clamping, line
  wrapping (`max_line_chars` x `max_lines_per_cue`) and ids are all a pure
  function of the transcript and `SubtitleConfig`.
- **SRT sidecar** uses standard `HH:MM:SS,mmm --> HH:MM:SS,mmm` timing and is
  empty when there are no cues. Styling, burn-in, emoji and karaoke effects
  are out of scope for Phase 7.

## Versioning policy

- `schema_version` is mandatory in every artifact.
- Additive fields → bump the minor version; consumers ignore unknown fields.
- Removed/renamed fields → bump the major version.
