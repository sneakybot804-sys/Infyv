"""Phase 7: configuration for the Subtitle Engine.

The subtitle engine is an **independent producer**: it extracts audio from the
ORIGINAL source video, transcribes it via a pluggable backend, and writes
``subtitles.json`` (schema ``7.1``) plus an optional ``.srt`` sidecar. Every
tunable lives here so no formatting or segmentation value is hardcoded in the
logic (Open/Closed Principle), mirroring ``OcrConfig`` and ``AudioConfig``.

Scope (Phase 7): transcript -> deterministic cues -> subtitles.json + SRT.
No styling, burn-in, emoji, karaoke effects or rendering (deferred).

No transcription library is a dependency of this project. The default backend
is a dependency-free placeholder; a real ASR backend (e.g. Whisper) can be
added later behind the same Protocol without changing the public API.
"""
from __future__ import annotations

from dataclasses import dataclass


class SubtitleError(RuntimeError):
    """Raised when subtitle configuration or transcription fails.

    Mirrors the ``OcrError`` / ``AudioAnalyzerError`` pattern: fail loud,
    normalized, and logged before raising.
    """


@dataclass(frozen=True)
class SubtitleConfig:
    """Fully configurable settings for subtitle generation."""

    # --- Backend selection ---
    # Default is the dependency-free placeholder (empty transcript). A real
    # ASR backend can be registered and named here later.
    backend: str = "placeholder"
    # Preferred language hint (None => let the backend decide / autodetect).
    language: str | None = None
    # Request word-level timings when the backend supports them.
    word_timestamps: bool = True

    # --- Cue segmentation / formatting ---
    max_line_chars: int = 42          # wrap text to this many chars per line
    max_lines_per_cue: int = 2        # at most this many lines per cue
    min_cue_seconds: float = 0.8      # pad cues shorter than this
    max_cue_seconds: float = 6.0      # split/limit cues longer than this
    # Merge consecutive words/segments separated by <= this gap into one cue.
    max_gap_merge_seconds: float = 0.3

    # --- Output ---
    emit_json: bool = True
    emit_srt: bool = True

    def validate(self) -> None:
        """Validate ranges and output selection."""
        if not self.backend.strip():
            raise SubtitleError("backend must not be empty.")
        if self.max_line_chars <= 0:
            raise SubtitleError("max_line_chars must be positive.")
        if self.max_lines_per_cue <= 0:
            raise SubtitleError("max_lines_per_cue must be positive.")
        if self.min_cue_seconds <= 0.0:
            raise SubtitleError("min_cue_seconds must be positive.")
        if self.max_cue_seconds <= self.min_cue_seconds:
            raise SubtitleError("max_cue_seconds must be greater than min_cue_seconds.")
        if self.max_gap_merge_seconds < 0.0:
            raise SubtitleError("max_gap_merge_seconds must be >= 0.")
        if not (self.emit_json or self.emit_srt):
            raise SubtitleError("at least one of emit_json / emit_srt must be True.")
