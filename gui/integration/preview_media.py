"""PreviewMediaSource: a thin, failure-tolerant media bridge for previews.

Integration Milestone 2. Screens never import backend modules directly
(:mod:`gui.screens` stays backend-free by dependency injection); this small
adapter lives in the integration layer instead and wraps the two existing
backend services relevant to previewing:

* :class:`video_picker.VideoPicker` -- discovers real video files in the
  configured ``videos`` directory;
* :class:`ffmpeg_service.FFmpegService` -- decodes a single first frame
  (``extract_frame_at``) and reads duration metadata (``read_metadata``).

No backend logic is rewritten here: every method delegates to those services
and only converts their results into GUI-friendly types (a ``QImage`` frame,
a ``HH:MM:SS:FF``-style timecode string).

Everything is failure-tolerant by design: when the backend imports fail
(missing ffmpeg/numpy), the videos directory is empty, or a decode raises,
the accessors return ``None`` / ``[]`` so a hosting screen can silently keep
its placeholder art. No exception ever escapes to the caller.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtGui import QImage


def _format_timecode(seconds: float, fps: float) -> str:
    """Render ``seconds`` as an ``HH:MM:SS:FF`` editorial timecode."""
    seconds = max(0.0, float(seconds))
    fps = fps if fps > 0 else 30.0
    whole = int(seconds)
    frames = int(round((seconds - whole) * fps)) % max(1, int(round(fps)))
    hours, rem = divmod(whole, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}:{frames:02d}"


class PreviewMediaSource:
    """Discover real media and decode preview frames via existing services.

    All heavy imports (``video_picker`` / ``ffmpeg_service``, which pull in
    numpy + ffmpeg) are deferred to first use so merely constructing the
    source is cheap and safe in test/CI environments without those packages.
    """

    def __init__(self) -> None:
        self._picker = None            # lazy video_picker.VideoPicker
        self._ffmpeg = None            # lazy ffmpeg_service.FFmpegService
        self._backend_ok: Optional[bool] = None
        self._paths: Dict[str, Path] = {}

    # ------------------------------------------------------------------ #
    # Lazy backend construction (never raises)
    # ------------------------------------------------------------------ #
    def _ensure_backend(self) -> bool:
        """Import and construct the backend services once; report success."""
        if self._backend_ok is not None:
            return self._backend_ok
        try:
            from ffmpeg_service import FFmpegService
            from video_picker import VideoPicker

            self._picker = VideoPicker()
            self._ffmpeg = FFmpegService()
            self._backend_ok = True
        except Exception:
            self._backend_ok = False
        return self._backend_ok

    # ------------------------------------------------------------------ #
    # Discovery
    # ------------------------------------------------------------------ #
    def list_items(self) -> List[str]:
        """Return the display names of real videos found on disk.

        Returns an empty list when the backend is unavailable or the
        configured ``videos`` directory has no video files.
        """
        if not self._ensure_backend():
            return []
        try:
            paths = self._picker.list_videos()
        except Exception:
            return []
        self._paths = {path.name: path for path in paths}
        return [path.name for path in paths]

    def path_for(self, name: str) -> Optional[Path]:
        """Return the full path for a previously listed display name."""
        return self._paths.get(name)

    # ------------------------------------------------------------------ #
    # Preview data (delegates to FFmpegService; never raises)
    # ------------------------------------------------------------------ #
    def load_first_frame(self, name: str) -> Optional[QImage]:
        """Decode and return the first frame of ``name`` as a ``QImage``.

        Delegates to the existing ``FFmpegService.extract_frame_at`` (BGR
        numpy frame) and converts to ``QImage``. Returns ``None`` on any
        failure so the caller can keep its placeholder rendering.
        """
        path = self._paths.get(name)
        if path is None or not self._ensure_backend():
            return None
        try:
            frame = self._ffmpeg.extract_frame_at(path, 0.0)
            height, width = frame.shape[:2]
            image = QImage(
                frame.tobytes(),
                width,
                height,
                width * 3,
                QImage.Format.Format_BGR888,
            )
            # Detach from the numpy buffer before it goes out of scope.
            return image.copy()
        except Exception:
            return None

    def duration_timecode(self, name: str) -> Optional[str]:
        """Return ``name``'s duration as an ``HH:MM:SS:FF`` timecode string.

        Delegates to the existing ``FFmpegService.read_metadata``. Returns
        ``None`` on any failure.
        """
        path = self._paths.get(name)
        if path is None or not self._ensure_backend():
            return None
        try:
            meta = self._ffmpeg.read_metadata(path)
            return _format_timecode(meta.duration, meta.fps)
        except Exception:
            return None
