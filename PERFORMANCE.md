# Performance

**Target hardware:** Ryzen 7 5700G (8c/16t APU), 16 GB RAM, CPU-only
(no discrete GPU assumed). Windows 11.

Guiding principle for Phase 4A: **performance over perfect accuracy**.

## Where time goes

1. **Video decoding** (OpenCV `VideoCapture.read`) — dominant cost on long,
   high-FPS videos.
2. **LLM inference** (Ollama) — dominant cost for edit-plan generation on
   CPU (see benchmark in `PROJECT_STATUS.md`).
3. **Per-frame analysis** (differencing, mean) — small after downscaling.

## CPU optimization

- **Frame differencing, not optical flow.** Motion is a single `absdiff` +
  `mean` on a downscaled grayscale frame — far cheaper than Farneback flow.
- **Downscale before analysis.** Frames are resized to `analysis_width`
  (default 320 px) so per-frame cost is roughly constant regardless of
  source resolution.
- **Sub-sampling.** Only ~`sample_fps` (default 4) frames per second are
  analyzed, independent of source FPS.
- **Single-pass aggregation.** Per-scene metrics are bucketed in one ordered
  pass (O(scenes + samples)), avoiding quadratic cost on many scene cuts.
- **Model choice.** Smaller Ollama models (`qwen2.5:3b`, `gemma3:4b`) are
  recommended over `qwen3:8b` for acceptable latency on this CPU.

## Memory optimization

- **Streaming decode.** Frames are read and released one at a time; only the
  previous grayscale frame is retained for differencing. Peak memory is
  independent of video length.
- **Compact samples.** Only small `FrameMetrics` dataclasses are retained,
  not frames. A 3h video at `sample_fps=4` is ~43k lightweight records.
- **No frame buffering** across the whole video.

## Long video optimization (1–3 hours)

- Sub-sampling + downscaling keep analysis cost bounded.
- Single-pass scene aggregation prevents quadratic blow-up.
- Periodic `debug` progress logging every 1000 samples for visibility.
- **Known cost:** every frame is still decoded even though most are skipped;
  decoding is the runtime floor for long high-FPS sources. This is a
  deliberate trade-off (sequential decode is more reliable than per-frame
  seeking with `CAP_PROP_POS_FRAMES`).

### Future long-video ideas (not implemented)
- Optional hardware-accelerated decode (see GPU section).
- Chunked/parallel decode of independent segments.
- Coarse first pass to skip long idle/black spans before fine analysis.

## Future GPU acceleration

All GPU work is **future / optional**; the baseline must remain CPU-only.

- **Decode:** FFmpeg hardware decoders (NVDEC / AMD AMF / QSV) or OpenCV
  built with CUDA to offload the dominant decode cost.
- **LLM:** Ollama with a supported GPU dramatically improves tokens/sec vs
  the CPU benchmark; keep model choice in `config.py`.
- **Whisper (Phase 7):** GPU greatly accelerates transcription.
- **Detectors (Phase 5):** any CNN-based kill/HUD detection benefits from a
  GPU; keep such detectors behind an interface so CPU fallbacks remain.

Guideline: introduce GPU paths as **optional accelerators behind feature
detection**, never as a hard requirement.
