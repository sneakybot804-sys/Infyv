"""Qt-free video frame provider (PyAV-backed) for gui_core.

Phase 3 / Priority 1. The :class:`FrameProvider` owns **decoding only**: it
opens a media file with PyAV, reports metadata, and decodes frames either by
accurate seek (:meth:`FrameProvider.frame_at`) or sequentially
(:meth:`FrameProvider.next_frame`). It returns raw RGB24 :class:`VideoFrame`
value objects; converting to a Qt image is the UI's job, so ``gui_core`` stays
Qt-free.

PyAV is imported lazily inside the methods that need it, so importing
``gui_core`` (or running unrelated Qt-free tests) never imports PyAV. OpenCV is
not used for playback. FFmpeg CLI is reserved for final export elsewhere.

The provider is synchronous and owns no timer or thread; the front end owns
the playback timer and calls in. Errors are normalized to
:class:`FrameProviderError` (a :class:`~gui_core.errors.GuiCoreError`).

No Qt symbol is imported here.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from gui_core.errors import GuiCoreError


class FrameProviderError(GuiCoreError):
    """Raised when a media file cannot be opened or a frame cannot decode."""


@dataclass(frozen=True)
class VideoMetadata:
    """Immutable media metadata.

    Attributes:
        width: Frame width in pixels.
        height: Frame height in pixels.
        fps: Average frames per second (``> 0``; falls back to 30.0 if the
            container does not report a usable rate).
        duration: Duration in seconds (``0.0`` if unknown).
    """

    width: int
    height: int
    fps: float
    duration: float


@dataclass(frozen=True)
class VideoFrame:
    """An immutable decoded RGB24 frame.

    Attributes:
        width: Frame width in pixels.
        height: Frame height in pixels.
        data: Tightly packed RGB24 bytes (``len == width * height * 3``).
        pts_seconds: Presentation timestamp in seconds.
    """

    width: int
    height: int
    data: bytes
    pts_seconds: float


class FrameProvider:
    """Decode frames from a media file using PyAV (decoding only).

    Args:
        path: Path to the media file.

    Use :meth:`open` (or the context-manager protocol) before decoding, and
    :meth:`close` when done. The provider is not thread-safe; the caller
    serializes access (the UI drives it from one thread).
    """

    def __init__(self, path: str | Path) -> None:
        self._path = str(path)
        self._container = None
        self._stream = None
        self._metadata: Optional[VideoMetadata] = None

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    def open(self) -> "FrameProvider":
        """Open the container and select the first video stream.

        Raises:
            FrameProviderError: If PyAV is unavailable, the file cannot be
                opened, or it contains no video stream.
        """
        if self._container is not None:
            return self
        try:
            import av  # lazy import; PyAV is only needed for decoding
        except Exception as exc:  # pragma: no cover - import environment
            raise FrameProviderError(
                f"PyAV is required for video decoding: {exc}"
            ) from exc
        try:
            container = av.open(self._path)
        except Exception as exc:
            raise FrameProviderError(
                f"Could not open media {self._path!r}: {exc}"
            ) from exc
        video_streams = [s for s in container.streams if s.type == "video"]
        if not video_streams:
            container.close()
            raise FrameProviderError(f"No video stream in {self._path!r}.")
        stream = video_streams[0]
        # Decode on demand; let PyAV thread its own decoder.
        stream.thread_type = "AUTO"
        self._container = container
        self._stream = stream
        self._metadata = self._read_metadata(container, stream)
        return self

    def close(self) -> None:
        """Close the container. Idempotent."""
        if self._container is not None:
            try:
                self._container.close()
            except Exception:  # pragma: no cover - defensive
                pass
            self._container = None
            self._stream = None

    def __enter__(self) -> "FrameProvider":
        return self.open()

    def __exit__(self, *_exc) -> None:
        self.close()

    # ------------------------------------------------------------------ #
    # Metadata
    # ------------------------------------------------------------------ #
    @staticmethod
    def _read_metadata(container, stream) -> VideoMetadata:
        """Extract width/height/fps/duration from an open stream."""
        codec = stream.codec_context
        width = int(getattr(codec, "width", 0) or 0)
        height = int(getattr(codec, "height", 0) or 0)
        rate = stream.average_rate or stream.base_rate
        fps = float(rate) if rate else 30.0
        if fps <= 0.0:
            fps = 30.0
        # Prefer the stream duration; fall back to the container duration.
        duration = 0.0
        if stream.duration is not None and stream.time_base is not None:
            duration = float(stream.duration * stream.time_base)
        elif container.duration is not None:
            duration = float(container.duration) / 1_000_000.0  # AV_TIME_BASE
        return VideoMetadata(
            width=width, height=height, fps=fps, duration=max(0.0, duration)
        )

    def metadata(self) -> VideoMetadata:
        """Return the media metadata (opens the provider if needed)."""
        if self._metadata is None:
            self.open()
        assert self._metadata is not None
        return self._metadata

    def duration(self) -> float:
        """Return the media duration in seconds."""
        return self.metadata().duration

    def fps(self) -> float:
        """Return the media frame rate."""
        return self.metadata().fps

    # ------------------------------------------------------------------ #
    # Decoding
    # ------------------------------------------------------------------ #
    def _to_video_frame(self, av_frame) -> VideoFrame:
        """Convert a PyAV frame to an immutable RGB24 :class:`VideoFrame`."""
        rgb = av_frame.to_ndarray(format="rgb24")
        height, width = rgb.shape[0], rgb.shape[1]
        pts = 0.0
        if av_frame.pts is not None and av_frame.time_base is not None:
            pts = float(av_frame.pts * av_frame.time_base)
        return VideoFrame(
            width=int(width),
            height=int(height),
            data=rgb.tobytes(),
            pts_seconds=pts,
        )

    def next_frame(self) -> Optional[VideoFrame]:
        """Decode and return the next frame sequentially, or ``None`` at EOF.

        Raises:
            FrameProviderError: On a decode error.
        """
        if self._container is None:
            self.open()
        try:
            for frame in self._container.decode(self._stream):
                return self._to_video_frame(frame)
        except Exception as exc:
            raise FrameProviderError(f"Decode error: {exc}") from exc
        return None

    def frame_at(self, seconds: float) -> Optional[VideoFrame]:
        """Seek to ``seconds`` and return the nearest decoded frame.

        Performs an accurate seek: it seeks to the keyframe at/just before the
        target and decodes forward to the first frame whose pts is >= target
        (or the last decodable frame). Returns ``None`` only when no frame can
        be decoded (e.g. seeking past EOF on an empty stream).

        Raises:
            FrameProviderError: On a seek/decode error.
        """
        if self._container is None:
            self.open()
        target = max(0.0, float(seconds))
        stream = self._stream
        try:
            time_base = stream.time_base
            if time_base is not None:
                seek_pts = int(target / float(time_base))
                self._container.seek(
                    seek_pts, stream=stream, backward=True, any_frame=False
                )
            else:  # pragma: no cover - containers without a time base
                self._container.seek(int(target * 1_000_000))
            last: Optional[VideoFrame] = None
            for frame in self._container.decode(stream):
                vframe = self._to_video_frame(frame)
                last = vframe
                if vframe.pts_seconds >= target:
                    return vframe
            return last
        except Exception as exc:
            raise FrameProviderError(
                f"Seek/decode error at {target}s: {exc}"
            ) from exc
