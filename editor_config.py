"""Phase 6: configuration for the automatic FFmpeg video editor.

The editor is a pure *consumer* of ``edit_plan.json`` (schema ``5e.1``) that
trims the planned segments from the source video and concatenates them into a
single rendered MP4. Every tunable lives here so no encode setting or
threshold is hardcoded in the logic (Open/Closed Principle), mirroring
``DecisionConfig``, ``FusionConfig``, ``OcrConfig`` and ``AudioConfig``.

Scope (Phase 6, minimum viable renderer): trim + concatenate + export only.
Transitions, effects, zoom, music, subtitles and speed ramps are out of scope
and deferred to later, additive phases.
"""
from __future__ import annotations

from dataclasses import dataclass


class EditorError(RuntimeError):
    """Raised when editor configuration or rendering fails.

    Mirrors the ``DecisionError`` / ``FusionError`` / ``FFmpegServiceError``
    pattern: fail loud, normalized, and logged before raising.
    """


@dataclass(frozen=True)
class EditorConfig:
    """Fully configurable settings for the minimum-viable renderer."""

    # --- Encode settings (applied on export / re-encode) ---
    # Re-encode trimmed segments for frame-accurate cuts and uniform codecs
    # (approved default). Stream-copy is intentionally not the default.
    reencode_segments: bool = True
    video_codec: str = "libx264"
    audio_codec: str = "aac"
    crf: int = 23
    preset: str = "medium"
    container: str = "mp4"

    # --- Segment selection guards ---
    # Skip degenerate/too-short clips; cap the number of rendered segments.
    min_segment_seconds: float = 0.1
    max_segments: int = 100

    # --- Output naming ---
    output_suffix: str = "_reel"

    def validate(self) -> None:
        """Validate encode settings and selection guards."""
        if not 0 <= self.crf <= 51:
            raise EditorError("crf must be between 0 and 51.")
        if not self.video_codec.strip():
            raise EditorError("video_codec must not be empty.")
        if not self.audio_codec.strip():
            raise EditorError("audio_codec must not be empty.")
        if not self.preset.strip():
            raise EditorError("preset must not be empty.")
        if not self.container.strip():
            raise EditorError("container must not be empty.")
        if self.min_segment_seconds <= 0.0:
            raise EditorError("min_segment_seconds must be positive.")
        if self.max_segments <= 0:
            raise EditorError("max_segments must be positive.")
        if not self.output_suffix.strip():
            raise EditorError("output_suffix must not be empty.")
