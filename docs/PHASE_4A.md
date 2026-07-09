# Phase 4A - Generic Video Analysis

Phase 4A adds **generic, game-agnostic** video analysis. It inspects a video
and produces a JSON summary of its structure and activity. It performs **no**
game-specific detection, **no** editing and **no** rendering; those belong to
later phases.

## Scope

Implemented:

- Video picker (GUI dialog with CLI fallback)
- Metadata (duration, resolution, FPS, codec, size)
- Scene detection (content-based)
- Motion score (frame differencing)
- Brightness
- Static score
- Idle detection
- Black-screen detection
- `output/<video_name>_analysis.json` (never overwrites existing files)

Explicitly **out of scope** (Phase 5+): kill/HUD detection, OCR, voice
excitement, highlight scoring, cutting, speed ramps, transitions, subtitles,
GUI timeline.

## Architecture

Phase 4A only **extends** the existing modular architecture; no completed
module (`agent.py`, `ffmpeg_service.py`, `scene_detector.py`, `config.py`,
`logger.py`) is modified.

| Component | Responsibility |
| --- | --- |
| `video_picker.py` (`VideoPicker`) | Select a video via Tkinter dialog or CLI fallback. |
| `video_analyzer.py` (`VideoAnalyzer`) | Produce the generic analysis and JSON. |
| `ffmpeg_service.py` (`FFmpegService`) | **Reused** for metadata via the `MetadataReader` protocol. |
| PySceneDetect | Content-based scene boundaries. |
| OpenCV | Frame sampling + differencing for motion/brightness. |
| `app.py` | Minimal menu entry to run the analyze flow. |

SOLID notes:

- **SRP:** picking, analysis and metadata are separate units.
- **DIP:** `VideoAnalyzer` depends on a `MetadataReader` *protocol*, not on
  the concrete `FFmpegService`; tests inject a fake reader.
- **OCP:** thresholds live in `GenericAnalysisConfig`; behaviour is tuned by
  configuration, not by editing logic.

## Data flow

```
VideoPicker.pick()
        |
        v
   video path
        |
        v
VideoAnalyzer.analyze(path)
   |-- MetadataReader.read_metadata(path)      -> metadata
   |-- PySceneDetect                            -> scene spans
   |-- OpenCV sample loop (every Nth frame)     -> FrameMetrics[]
   |       motion  = mean|frame_t - frame_{t-1}|
   |       bright  = mean(gray)
   |       static  = 1 / (1 + motion)
   |-- aggregate per scene                      -> SceneMetrics[]
   |-- merge idle runs (motion < threshold)     -> idle_sections
   |-- merge black runs (bright <= threshold)   -> black_screens
        |
        v
VideoAnalysis.to_json() -> output/<name>_analysis.json
```

## JSON schema (`schema_version: "4a.1"`)

```json
{
  "schema_version": "4a.1",
  "video": "C:/.../videos/clip.mp4",
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

Units:

- `motion_score` / `avg_motion` / `max_motion`: mean absolute per-pixel
  difference between consecutive sampled grayscale frames (0..255).
- `brightness` / `avg_brightness`: mean pixel value (0..255).
- `static_score` / `avg_static`: `1 / (1 + motion)` (1.0 = perfectly still).

## Performance considerations

Target hardware: **Ryzen 7 5700G, 16 GB RAM, CPU-only.**

- **Frame differencing, not optical flow.** Motion is a single `absdiff` +
  `mean`, which is dramatically cheaper than Farneback optical flow and is
  sufficient for generic activity detection.
- **Downscaling.** Frames are resized to `analysis_width` (default 320 px)
  before analysis, cutting per-frame cost by an order of magnitude.
- **Sub-sampling.** Only ~`sample_fps` (default 4) frames per second are
  analyzed, independent of source FPS.
- **Single pass, streaming.** Frames are read and released one at a time; peak
  memory stays low regardless of video length.

All thresholds are in `GenericAnalysisConfig`, so accuracy/speed can be tuned
without code changes.

## Extension points for Phase 5 (Gaming Intelligence)

Phase 4A is deliberately a clean base to build on:

- Add a game-specific analyzer that **consumes** this `analysis.json` (kills,
  HUD, OCR, voice excitement, highlight scoring) instead of re-decoding video.
- The `FrameMetrics` sampling loop is the natural hook for extra per-frame
  signals (e.g. HUD region crops, template matches); add fields to
  `FrameMetrics` rather than changing existing ones.
- Bump `schema_version` when the JSON shape changes so downstream consumers
  can adapt safely.
- Keep game logic in new modules; do not add heuristics here (this module
  must stay generic).

## Testing

`tests/test_video_analyzer.py` covers metadata, scene detection, motion,
brightness, static score, idle detection, black-screen detection, JSON schema
and the never-overwrite file behaviour. Videos are generated synthetically at
runtime (OpenCV), and metadata is provided by an injected fake reader, so the
suite needs no binary fixtures and no FFmpeg install.

Run:

```bash
pytest -q
```
