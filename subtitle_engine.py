"""Phase 7: Subtitle Engine -- independent producer of ``subtitles.json``.

Extracts audio from the ORIGINAL source video (via ``FFmpegService``),
transcribes it through a pluggable :class:`TranscriptBackend`, and turns the
raw transcript into deterministic cues written as ``subtitles.json`` (schema
``7.1``) plus an optional ``.srt`` sidecar.

Hard boundaries (Phase 7):
- **Independent producer.** Input is the original video only; the engine
  consumes no other artifact and imports no Phase 4/5/6 producer or the
  editor. It produces subtitle artifacts and nothing else.
- **Deterministic.** Cue segmentation/formatting is a pure function of the
  transcript and config; ids are stable (``cue-0001``...).
- **No fabricated subtitles.** The default backend returns an empty
  transcript, so the default output has ``cues: []``.
- **No magic numbers.** All segmentation/formatting tunables live in
  :class:`SubtitleConfig`.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from config import AppConfig, config
from logger import get_logger
from subtitle_backend import (
    TranscriptBackend,
    TranscriptResult,
    TranscriptSegment,
    Word,
    create_backend,
)
from subtitle_config import SubtitleConfig, SubtitleError

logger = get_logger(__name__)

SCHEMA_VERSION = "7.1"


@dataclass
class SubtitleCue:
    """A single, formatted subtitle cue."""

    id: str
    start: float
    end: float
    text: str  # may contain newlines (one per wrapped line)
    words: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class SubtitleDocument:
    """Complete subtitle document, serializable to ``subtitles.json``."""

    video: str
    language: str | None
    backend: str
    cues: list[SubtitleCue] = field(default_factory=list)
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "video": self.video,
            "language": self.language,
            "backend": self.backend,
            "cues": [
                {
                    "id": c.id,
                    "start": c.start,
                    "end": c.end,
                    "text": c.text,
                    "words": list(c.words),
                }
                for c in self.cues
            ],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def to_srt(self) -> str:
        """Render the cues as an SRT document (empty string when no cues)."""
        blocks: list[str] = []
        for i, cue in enumerate(self.cues, start=1):
            blocks.append(
                f"{i}\n"
                f"{_srt_timestamp(cue.start)} --> {_srt_timestamp(cue.end)}\n"
                f"{cue.text}\n"
            )
        return "\n".join(blocks)


def _srt_timestamp(seconds: float) -> str:
    """Format seconds as an SRT timestamp ``HH:MM:SS,mmm``."""
    if seconds < 0:
        seconds = 0.0
    total_ms = int(round(seconds * 1000))
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, millis = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


class SubtitleEngine:
    """Transcribe a video's audio into ``subtitles.json`` (7.1) + optional SRT."""

    def __init__(
        self,
        app_config: AppConfig | None = None,
        subtitle_config: SubtitleConfig | None = None,
        ffmpeg_service: Any | None = None,
        backend: TranscriptBackend | None = None,
    ) -> None:
        """Create the engine.

        Args:
            app_config: Shared application config (paths).
            subtitle_config: Backend selection and cue formatting tunables.
            ffmpeg_service: Object exposing ``extract_audio``. Injectable for
                tests; the real ``FFmpegService`` is built lazily.
            backend: Transcript backend. Injectable for tests; resolved from
                the registry by ``subtitle_config.backend`` when omitted.
        """
        self._config = app_config or config
        self._subtitle = subtitle_config or SubtitleConfig()
        self._subtitle.validate()
        self._ffmpeg = ffmpeg_service
        self._backend = backend
        logger.info(
            "Initialized SubtitleEngine (backend=%s)", self._subtitle.backend
        )

    # ------------------------------------------------------------------ #
    # Lazy dependencies (kept out of unit tests)
    # ------------------------------------------------------------------ #
    def _ffmpeg_service(self) -> Any:
        if self._ffmpeg is None:
            from ffmpeg_service import FFmpegService

            self._ffmpeg = FFmpegService(self._config)
        return self._ffmpeg

    def _transcript_backend(self) -> TranscriptBackend:
        if self._backend is None:
            self._backend = create_backend(self._subtitle.backend)
        return self._backend

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def transcribe(self, video: str | Path) -> SubtitleDocument:
        """Transcribe ``video`` and return a subtitle document."""
        video = str(video)
        audio_path = self._ffmpeg_service().extract_audio(video)
        try:
            result = self._transcript_backend().transcribe(
                audio_path,
                language=self._subtitle.language,
                word_timestamps=self._subtitle.word_timestamps,
            )
        finally:
            self._cleanup(audio_path)

        cues = self._build_cues(result)
        backend_name = getattr(self._transcript_backend(), "name", self._subtitle.backend)
        return SubtitleDocument(
            video=video,
            language=result.language,
            backend=backend_name,
            cues=cues,
        )

    def transcribe_to_file(
        self, video: str | Path, output_name: str | None = None
    ) -> list[Path]:
        """Transcribe and write ``<stem>_subtitles.json`` and/or ``<stem>.srt``.

        Existing files are never overwritten. Returns the written paths.
        """
        document = self.transcribe(video)
        out_dir = self._config.paths.output_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        stem = Path(str(video)).stem

        written: list[Path] = []
        if self._subtitle.emit_json:
            base = output_name or f"{stem}_subtitles.json"
            path = self._unique_path(out_dir, base)
            path.write_text(json.dumps(document.to_dict(), indent=2), encoding="utf-8")
            written.append(path)
        if self._subtitle.emit_srt:
            path = self._unique_path(out_dir, f"{stem}.srt")
            path.write_text(document.to_srt(), encoding="utf-8")
            written.append(path)
        logger.info("Wrote %d subtitle artifact(s) for %s", len(written), stem)
        return written

    # ------------------------------------------------------------------ #
    # Deterministic cue building
    # ------------------------------------------------------------------ #
    def _build_cues(self, result: TranscriptResult) -> list[SubtitleCue]:
        """Turn a raw transcript into deterministic, formatted cues."""
        groups = self._group_segments(result.segments)
        cues: list[SubtitleCue] = []
        for i, seg in enumerate(groups, start=1):
            text = self._wrap_text(seg.text.strip())
            if not text:
                continue
            start, end = self._clamp_bounds(seg.start, seg.end)
            cues.append(
                SubtitleCue(
                    id=f"cue-{len(cues) + 1:04d}",
                    start=round(start, 3),
                    end=round(end, 3),
                    text=text,
                    words=self._words_json(seg.words),
                )
            )
        return cues

    def _group_segments(
        self, segments: list[TranscriptSegment]
    ) -> list[TranscriptSegment]:
        """Merge adjacent segments within the gap/duration limits.

        Merges consecutive segments separated by <= ``max_gap_merge_seconds``
        as long as the combined duration stays <= ``max_cue_seconds``.
        Deterministic: input order is preserved.
        """
        cfg = self._subtitle
        merged: list[TranscriptSegment] = []
        for seg in segments:
            if not merged:
                merged.append(self._copy_segment(seg))
                continue
            cur = merged[-1]
            gap = seg.start - cur.end
            combined = seg.end - cur.start
            if (
                0.0 <= gap <= cfg.max_gap_merge_seconds
                and combined <= cfg.max_cue_seconds
            ):
                cur.text = f"{cur.text} {seg.text}".strip()
                cur.end = seg.end
                cur.words = list(cur.words) + list(seg.words)
            else:
                merged.append(self._copy_segment(seg))
        return merged

    @staticmethod
    def _copy_segment(seg: TranscriptSegment) -> TranscriptSegment:
        return TranscriptSegment(
            text=seg.text.strip(),
            start=seg.start,
            end=seg.end,
            words=list(seg.words),
        )

    def _clamp_bounds(self, start: float, end: float) -> tuple[float, float]:
        """Enforce min/max cue duration deterministically."""
        cfg = self._subtitle
        start = max(float(start), 0.0)
        end = float(end)
        if end < start:
            end = start
        duration = end - start
        if duration < cfg.min_cue_seconds:
            end = start + cfg.min_cue_seconds
        elif duration > cfg.max_cue_seconds:
            end = start + cfg.max_cue_seconds
        return start, end

    def _wrap_text(self, text: str) -> str:
        """Greedy word-wrap to max_line_chars x max_lines_per_cue.

        Lines beyond ``max_lines_per_cue`` are dropped from the displayed
        text (the words remain in the ``words`` list for later phases).
        """
        cfg = self._subtitle
        if not text:
            return ""
        words = text.split()
        lines: list[str] = []
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if len(candidate) <= cfg.max_line_chars or not current:
                current = candidate
            else:
                lines.append(current)
                current = word
                if len(lines) >= cfg.max_lines_per_cue:
                    break
        if current and len(lines) < cfg.max_lines_per_cue:
            lines.append(current)
        return "\n".join(lines[: cfg.max_lines_per_cue])

    def _words_json(self, words: list[Word]) -> list[dict[str, Any]]:
        """Serialize words when word timestamps are enabled, else empty."""
        if not self._subtitle.word_timestamps:
            return []
        return [
            {
                "text": w.text,
                "start": round(float(w.start), 3),
                "end": round(float(w.end), 3),
                "confidence": round(float(w.confidence), 6),
            }
            for w in words
        ]

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _cleanup(audio_path: Any) -> None:
        """Best-effort removal of the temporary extracted audio file."""
        try:
            Path(str(audio_path)).unlink(missing_ok=True)
        except OSError as exc:  # pragma: no cover - best effort
            logger.warning("Could not remove temp audio %s: %s", audio_path, exc)

    @staticmethod
    def _unique_path(directory: Path, base_name: str) -> Path:
        """Return a path in ``directory`` that does not already exist."""
        candidate = directory / base_name
        if not candidate.exists():
            return candidate
        stem = Path(base_name).stem
        suffix = Path(base_name).suffix
        counter = 1
        while True:
            candidate = directory / f"{stem}_{counter}{suffix}"
            if not candidate.exists():
                return candidate
            counter += 1
