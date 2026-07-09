"""Phase 6: automatic FFmpeg video editor -- renders ``edit_plan.json``.

A pure **consumer** that reads a Phase 5E ``edit_plan.json`` (schema ``5e.1``)
and renders a single highlight-reel MP4 by trimming each planned segment from
the source video and concatenating them in plan order.

Scope (minimum viable renderer): trim + concatenate + export. No transitions,
effects, zoom, music, subtitles or speed ramps (deferred to later phases).

Hard boundaries:
- **Pure consumer.** Reads the plan (and the source video) and writes one
  rendered file. No producer import, no producer mutation, no schema change.
- **Reuses FFmpegService (Option A).** Orchestrates the existing
  ``trim_video`` and ``merge_videos`` methods only; FFmpegService is not
  modified.
- **Injectable FFmpeg.** The service is dependency-injected so unit tests use
  a fake and never require the FFmpeg binary.
- **No magic numbers.** All encode settings and guards live in
  :class:`EditorConfig`.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from config import AppConfig, config
from editor_config import EditorConfig, EditorError
from logger import get_logger

logger = get_logger(__name__)

INPUT_SCHEMA_VERSION = "5e.1"


class VideoEditor:
    """Render an ``edit_plan.json`` (5e.1) into a single highlight reel."""

    def __init__(
        self,
        app_config: AppConfig | None = None,
        editor_config: EditorConfig | None = None,
        ffmpeg_service: Any | None = None,
    ) -> None:
        """Create the editor.

        Args:
            app_config: Shared application config (paths).
            editor_config: Encode settings and selection guards.
            ffmpeg_service: Object exposing ``trim_video`` and
                ``merge_videos``. Injectable for tests; the real
                ``FFmpegService`` is built lazily so unit tests never require
                the FFmpeg binary.
        """
        self._config = app_config or config
        self._editor = editor_config or EditorConfig()
        self._editor.validate()
        self._ffmpeg = ffmpeg_service or self._default_ffmpeg()
        logger.info(
            "Initialized VideoEditor (reencode=%s, codec=%s, crf=%d)",
            self._editor.reencode_segments,
            self._editor.video_codec,
            self._editor.crf,
        )

    @staticmethod
    def _default_ffmpeg() -> Any:
        """Lazily construct the real FFmpegService (kept out of unit tests)."""
        from ffmpeg_service import FFmpegService

        return FFmpegService()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def render(
        self,
        plan: dict[str, Any],
        source_video: str | Path | None = None,
    ) -> Path:
        """Render an in-memory edit plan dict into a single MP4.

        Args:
            plan: An ``edit_plan.json`` (5e.1) document.
            source_video: Source video path; falls back to the plan's
                ``source_video`` field when omitted.

        Returns:
            Path to the rendered reel (never overwrites an existing file).
        """
        self._validate_plan(plan)
        source = str(source_video) if source_video is not None else str(
            plan.get("source_video", "")
        )
        if not source:
            raise EditorError("No source video provided (arg or plan).")

        ranges = self._selected_ranges(plan)
        if not ranges:
            raise EditorError(
                "Edit plan has no renderable segments; refusing to render an "
                "empty video."
            )

        out_dir = self._config.paths.output_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        stem = Path(source).stem
        final_name = f"{stem}{self._editor.output_suffix}.{self._editor.container}"
        final_path = self._unique_path(out_dir, final_name)

        clips: list[Path] = []
        try:
            clips = self._trim_segments(source, ranges, stem)
            if len(clips) == 1:
                # merge_videos requires >= 2 inputs; a single clip IS the reel.
                clips[0].replace(final_path)
                clips = []  # ownership transferred; nothing to clean up
            else:
                self._ffmpeg.merge_videos(clips, output_name=final_path.name)
        except EditorError:
            raise
        except Exception as exc:  # normalize any FFmpeg/service failure
            raise EditorError(f"Rendering failed: {exc}") from exc
        finally:
            self._cleanup(clips)

        logger.info("Rendered reel (%d segment(s)) -> %s", len(ranges), final_path)
        return final_path

    def render_files(
        self,
        video: str | Path | None = None,
        *,
        plan_path: str | Path | None = None,
    ) -> Path:
        """Load an edit plan (auto-discovered or explicit) and render it.

        Auto-discovery uses the naming convention
        ``output/<stem>_edit_plan.json``. An explicit ``plan_path`` overrides
        discovery.
        """
        path = self._resolve_plan_path(video, plan_path)
        plan = self._read_plan(path)
        return self.render(plan, source_video=video)

    # ------------------------------------------------------------------ #
    # Segment handling
    # ------------------------------------------------------------------ #
    def _selected_ranges(self, plan: dict[str, Any]) -> list[tuple[float, float]]:
        """Return validated (start, end) ranges honoring the config guards."""
        segments = plan.get("segments", []) or []
        ranges: list[tuple[float, float]] = []
        for seg in segments:
            try:
                start = float(seg["start"])
                end = float(seg["end"])
            except (KeyError, TypeError, ValueError):
                logger.warning("Skipping segment with invalid bounds: %s", seg)
                continue
            if end - start < self._editor.min_segment_seconds:
                logger.warning(
                    "Skipping segment shorter than %.3fs: %s-%s",
                    self._editor.min_segment_seconds, start, end,
                )
                continue
            ranges.append((start, end))
            if len(ranges) >= self._editor.max_segments:
                logger.info("Reached max_segments=%d cap.", self._editor.max_segments)
                break
        return ranges

    def _trim_segments(
        self, source: str, ranges: list[tuple[float, float]], stem: str
    ) -> list[Path]:
        """Trim each range into an intermediate clip via FFmpegService."""
        clips: list[Path] = []
        for i, (start, end) in enumerate(ranges, start=1):
            clip_name = f"{stem}{self._editor.output_suffix}_part{i:04d}.{self._editor.container}"
            clip = self._ffmpeg.trim_video(
                source, start, end, output_name=clip_name
            )
            clips.append(Path(clip))
        return clips

    @staticmethod
    def _cleanup(clips: list[Path]) -> None:
        """Best-effort removal of intermediate clips."""
        for clip in clips:
            try:
                Path(clip).unlink(missing_ok=True)
            except OSError as exc:  # pragma: no cover - best effort
                logger.warning("Could not remove temp clip %s: %s", clip, exc)

    # ------------------------------------------------------------------ #
    # Validation / IO helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _validate_plan(plan: dict[str, Any]) -> None:
        """Validate the plan is a 5e.1 document with a segments list."""
        if not isinstance(plan, dict):
            raise EditorError("edit plan must be a JSON object.")
        version = plan.get("schema_version")
        if version != INPUT_SCHEMA_VERSION:
            raise EditorError(
                f"edit plan schema_version must be '{INPUT_SCHEMA_VERSION}', "
                f"got '{version}'."
            )
        if not isinstance(plan.get("segments"), list):
            raise EditorError("edit plan must contain a 'segments' list.")

    def _resolve_plan_path(
        self, video: str | Path | None, plan_path: str | Path | None
    ) -> Path:
        """Resolve the plan path from an explicit arg or naming convention."""
        if plan_path is not None:
            return Path(plan_path).expanduser()
        if video is None:
            raise EditorError(
                "An edit plan is required: provide 'plan_path' or a 'video' "
                "for auto-discovery."
            )
        stem = Path(str(video)).stem
        return self._config.paths.output_dir / f"{stem}_edit_plan.json"

    @staticmethod
    def _read_plan(path: Path) -> dict[str, Any]:
        """Read and parse an edit plan JSON file."""
        if not path.is_file():
            raise EditorError(f"Edit plan not found: {path}")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise EditorError(f"Could not read edit plan '{path}': {exc}") from exc
        if not isinstance(data, dict):
            raise EditorError(f"Edit plan '{path}' is not a JSON object.")
        return data

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
