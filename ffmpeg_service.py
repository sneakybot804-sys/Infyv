"""FFmpeg service: metadata reading and core video operations.

Wraps the system FFmpeg binary via the ffmpeg-python package. This module
does not alter the Phase 1 architecture; it only adds a new service.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterator, Sequence

import ffmpeg  # ffmpeg-python
import numpy as np

from config import AppConfig, config
from logger import get_logger

logger = get_logger(__name__)


class FFmpegServiceError(RuntimeError):
    """Raised when an FFmpeg operation fails or input is invalid."""


@dataclass(frozen=True)
class VideoMetadata:
    """Structured metadata for a video file."""

    path: Path
    duration: float          # seconds
    width: int               # pixels
    height: int              # pixels
    fps: float               # frames per second
    codec: str
    size_bytes: int

    @property
    def resolution(self) -> str:
        return f"{self.width}x{self.height}"


class FFmpegService:
    """Thin, well-typed wrapper around common FFmpeg operations."""

    def __init__(self, app_config: AppConfig | None = None) -> None:
        self._config = app_config or config
        self._paths = self._config.paths
        self._metadata_cache: dict[Path, VideoMetadata] = {}
        self._cache_lock = __import__('threading').Lock()
        logger.info("Initialized FFmpegService")

    # ------------------------------------------------------------------ #
    # Metadata
    # ------------------------------------------------------------------ #
    def read_metadata(self, video_path: str | Path) -> VideoMetadata:
        """Read metadata (duration, resolution, FPS, codec) for a video."""
        path = self._validate_input(video_path)

        # Return cached metadata if available (thread-safe)
        with self._cache_lock:
            if path in self._metadata_cache:
                return self._metadata_cache[path]

        try:
            probe: dict[str, Any] = ffmpeg.probe(str(path))
        except ffmpeg.Error as exc:
            message = self._decode_stderr(exc)
            logger.error("ffprobe failed for %s: %s", path, message)
            raise FFmpegServiceError(f"Could not probe '{path}': {message}") from exc

        video_stream = self._first_video_stream(probe)

        duration = self._extract_duration(probe, video_stream)
        width = int(video_stream.get("width", 0))
        height = int(video_stream.get("height", 0))
        fps = self._extract_fps(video_stream)
        codec = str(video_stream.get("codec_name", "unknown"))
        size_bytes = int(probe.get("format", {}).get("size", 0))

        metadata = VideoMetadata(
            path=path,
            duration=duration,
            width=width,
            height=height,
            fps=fps,
            codec=codec,
            size_bytes=size_bytes,
        )
        logger.info(
            "Metadata for %s: %.2fs, %s, %.2f fps, %s",
            path.name,
            metadata.duration,
            metadata.resolution,
            metadata.fps,
            metadata.codec,
        )
        # Cache for subsequent calls (thread-safe)
        with self._cache_lock:
            self._metadata_cache[path] = metadata
        return metadata

    def detect_duration(self, video_path: str | Path) -> float:
        """Return the duration of a video in seconds."""
        return self.read_metadata(video_path).duration

    def detect_resolution(self, video_path: str | Path) -> tuple[int, int]:
        """Return the (width, height) of a video in pixels."""
        meta = self.read_metadata(video_path)
        return meta.width, meta.height

    def detect_fps(self, video_path: str | Path) -> float:
        """Return the frames-per-second of a video."""
        return self.read_metadata(video_path).fps

    # ------------------------------------------------------------------ #
    # Operations
    # ------------------------------------------------------------------ #
    def trim_video(
        self,
        video_path: str | Path,
        start: float,
        end: float,
        output_name: str | None = None,
    ) -> Path:
        """Trim a video between start and end (seconds)."""
        path = self._validate_input(video_path)

        if start < 0 or end <= start:
            raise FFmpegServiceError(
                f"Invalid trim range: start={start}, end={end}."
            )

        output = self._output_path(output_name or f"{path.stem}_trim.mp4")
        logger.info("Trimming %s [%.2f -> %.2f] -> %s", path.name, start, end, output.name)

        try:
            (
                ffmpeg
                .input(str(path), ss=start, to=end)
                .output(str(output), c="copy")
                .overwrite_output()
                .run(quiet=True)
            )
        except ffmpeg.Error as exc:
            self._raise_run_error("trim_video", exc)

        return output

    def merge_videos(
        self,
        video_paths: Sequence[str | Path],
        output_name: str = "merged.mp4",
    ) -> Path:
        """Concatenate multiple videos into one (re-encodes for compatibility)."""
        if len(video_paths) < 2:
            raise FFmpegServiceError("merge_videos requires at least two inputs.")

        paths = [self._validate_input(p) for p in video_paths]
        output = self._output_path(output_name)
        logger.info("Merging %d videos -> %s", len(paths), output.name)

        try:
            streams = []
            for p in paths:
                inp = ffmpeg.input(str(p))
                streams.extend([inp.video, inp.audio])

            joined = ffmpeg.concat(*streams, v=1, a=1).node
            out = ffmpeg.output(joined[0], joined[1], str(output))
            out.overwrite_output().run(quiet=True)
        except ffmpeg.Error as exc:
            self._raise_run_error("merge_videos", exc)

        return output

    def extract_audio(
        self,
        video_path: str | Path,
        output_name: str | None = None,
    ) -> Path:
        """Extract the audio track as an MP3 file."""
        path = self._validate_input(video_path)
        output = self._output_path(output_name or f"{path.stem}.mp3")
        logger.info("Extracting audio from %s -> %s", path.name, output.name)

        try:
            (
                ffmpeg
                .input(str(path))
                .output(str(output), vn=None, acodec="libmp3lame", **{"q:a": 2})
                .overwrite_output()
                .run(quiet=True)
            )
        except ffmpeg.Error as exc:
            self._raise_run_error("extract_audio", exc)

        return output

    # ------------------------------------------------------------------ #
    # Audio streaming (Phase 5C; additive, backward-compatible)
    # ------------------------------------------------------------------ #
    def count_audio_streams(self, media_path: str | Path) -> int:
        """Return the number of audio streams in a media file.

        Used by the Phase 5C analyzer for automatic track detection. Existing
        callers are unaffected.
        """
        path = self._validate_input(media_path)
        try:
            probe: dict[str, Any] = ffmpeg.probe(str(path))
        except ffmpeg.Error as exc:
            message = self._decode_stderr(exc)
            logger.error("ffprobe failed for %s: %s", path, message)
            raise FFmpegServiceError(
                f"Could not probe '{path}': {message}"
            ) from exc
        return sum(
            1
            for s in probe.get("streams", [])
            if s.get("codec_type") == "audio"
        )

    def stream_pcm_blocks(
        self,
        media_path: str | Path,
        *,
        sample_rate: int = 16000,
        stream_index: int = 0,
        block_seconds: float = 30.0,
    ) -> Iterator[np.ndarray]:
        """Yield mono float32 PCM blocks from one audio stream via a pipe.

        Decodes to mono at ``sample_rate`` and streams the raw PCM out of
        FFmpeg's stdout in bounded chunks, so no whole-track buffer and no
        temporary file are ever created (Phase 5C sections 8.1/8.4).

        Args:
            media_path: Source media file.
            sample_rate: Target (analysis) sample rate; mono.
            stream_index: Audio stream index within the source (0-based).
            block_seconds: Approximate seconds of audio per yielded block.

        Yields:
            1-D ``float32`` numpy arrays in the range [-1, 1].

        Raises:
            FFmpegServiceError: if the stream is missing or decoding fails.
        """
        path = self._validate_input(media_path)
        if sample_rate <= 0:
            raise FFmpegServiceError("sample_rate must be positive.")
        if block_seconds <= 0:
            raise FFmpegServiceError("block_seconds must be positive.")

        bytes_per_sample = 4  # float32 little-endian
        block_samples = max(int(round(block_seconds * sample_rate)), 1)
        chunk_bytes = block_samples * bytes_per_sample

        process = None
        try:
            process = (
                ffmpeg
                .input(str(path))
                .output(
                    "pipe:",
                    format="f32le",
                    acodec="pcm_f32le",
                    ac=1,
                    ar=sample_rate,
                    map=f"0:a:{stream_index}",
                    vn=None,
                )
                .global_args("-nostdin", "-loglevel", "error")
                .run_async(pipe_stdout=True, pipe_stderr=True)
            )
            while True:
                raw = process.stdout.read(chunk_bytes)
                if not raw:
                    break
                yield np.frombuffer(raw, dtype="<f4").astype(np.float32, copy=False)
            try:
                process.wait(timeout=30)
            except Exception:
                process.kill()
                process.wait()
            if process.returncode not in (0, None):
                stderr = process.stderr.read() if process.stderr else b""
                message = stderr.decode("utf-8", errors="replace").strip()
                raise FFmpegServiceError(
                    f"stream_pcm_blocks failed (stream {stream_index}): {message}"
                )
        except ffmpeg.Error as exc:  # pragma: no cover - defensive
            self._raise_run_error("stream_pcm_blocks", exc)
        finally:
            if process is not None:
                for pipe in (process.stdout, process.stderr):
                    try:
                        if pipe is not None:
                            pipe.close()
                    except Exception:  # pragma: no cover - best effort cleanup
                        pass
                if process.poll() is None:  # pragma: no cover - defensive
                    process.kill()
                    process.wait(timeout=10)

    def extract_frame_at(
        self,
        video_path: str | Path,
        timestamp: float,
    ) -> np.ndarray:
        """Decode a single BGR frame at ``timestamp`` (seconds) via a pipe.

        Additive, backward-compatible method used by the Phase 5B OCR
        extractor. Seeks to ``timestamp`` and returns exactly one decoded
        frame as an ``(H, W, 3)`` uint8 numpy array (BGR, matching OpenCV
        convention). No temporary file is created.

        Args:
            video_path: Source video file.
            timestamp: Seek time in seconds (>= 0).

        Returns:
            An ``(H, W, 3)`` uint8 BGR frame.

        Raises:
            FFmpegServiceError: if the timestamp is invalid, the video has no
                video stream, or decoding yields no frame.
        """
        path = self._validate_input(video_path)
        if timestamp < 0:
            raise FFmpegServiceError("timestamp must be >= 0.")

        # Use cached metadata instead of spawning redundant ffprobe
        meta = self.read_metadata(path)
        width = meta.width
        height = meta.height
        if width <= 0 or height <= 0:
            raise FFmpegServiceError(
                f"Invalid video dimensions for '{path}': {width}x{height}."
            )

        frame_bytes = width * height * 3
        try:
            raw, err = (
                ffmpeg
                .input(str(path), ss=timestamp)
                .output(
                    "pipe:",
                    format="rawvideo",
                    pix_fmt="bgr24",
                    vframes=1,
                )
                .global_args("-nostdin", "-loglevel", "error")
                .run(capture_stdout=True, capture_stderr=True)
            )
        except ffmpeg.Error as exc:
            self._raise_run_error("extract_frame_at", exc)

        if not raw or len(raw) < frame_bytes:
            message = err.decode("utf-8", errors="replace").strip() if err else ""
            raise FFmpegServiceError(
                f"No frame decoded at t={timestamp}s from '{path}'. {message}"
            )
        return (
            np.frombuffer(raw[:frame_bytes], dtype=np.uint8)
            .reshape((height, width, 3))
        )

    def extract_frames(
        self,
        video_path: str | Path,
        fps: float = 1.0,
        subdir: str | None = None,
    ) -> Path:
        """Extract frames as JPEG images at a given sampling rate."""
        path = self._validate_input(video_path)

        if fps <= 0:
            raise FFmpegServiceError(f"fps must be positive, got {fps}.")

        frames_dir = self._paths.output_dir / (subdir or f"{path.stem}_frames")
        frames_dir.mkdir(parents=True, exist_ok=True)
        pattern = str(frames_dir / "frame_%05d.jpg")
        logger.info("Extracting frames from %s at %.2f fps -> %s", path.name, fps, frames_dir)

        try:
            (
                ffmpeg
                .input(str(path))
                .output(pattern, vf=f"fps={fps}")
                .overwrite_output()
                .run(quiet=True)
            )
        except ffmpeg.Error as exc:
            self._raise_run_error("extract_frames", exc)

        return frames_dir

    def export_mp4(
        self,
        video_path: str | Path,
        output_name: str | None = None,
        crf: int = 23,
        preset: str = "medium",
    ) -> Path:
        """Re-encode a video to a standard H.264/AAC MP4."""
        path = self._validate_input(video_path)

        if not 0 <= crf <= 51:
            raise FFmpegServiceError(f"crf must be between 0 and 51, got {crf}.")

        output = self._output_path(output_name or f"{path.stem}_export.mp4")
        logger.info("Exporting %s -> %s (crf=%d, preset=%s)", path.name, output.name, crf, preset)

        try:
            (
                ffmpeg
                .input(str(path))
                .output(
                    str(output),
                    vcodec="libx264",
                    acodec="aac",
                    crf=crf,
                    preset=preset,
                    movflags="+faststart",
                )
                .overwrite_output()
                .run(quiet=True)
            )
        except ffmpeg.Error as exc:
            self._raise_run_error("export_mp4", exc)

        return output

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _validate_input(video_path: str | Path) -> Path:
        """Validate that the input path exists and is a file."""
        path = Path(video_path).expanduser().resolve()
        if not path.exists():
            raise FFmpegServiceError(f"Input file does not exist: {path}")
        if not path.is_file():
            raise FFmpegServiceError(f"Input path is not a file: {path}")
        return path

    def _output_path(self, name: str) -> Path:
        """Build a path inside the configured output directory."""
        self._paths.output_dir.mkdir(parents=True, exist_ok=True)
        return self._paths.output_dir / name

    @staticmethod
    def _first_video_stream(probe: dict[str, Any]) -> dict[str, Any]:
        """Return the first video stream from a probe result."""
        for stream in probe.get("streams", []):
            if stream.get("codec_type") == "video":
                return stream
        raise FFmpegServiceError("No video stream found in file.")

    @staticmethod
    def _extract_duration(
        probe: dict[str, Any], video_stream: dict[str, Any]
    ) -> float:
        """Resolve duration from format or stream data."""
        duration = probe.get("format", {}).get("duration")
        if duration is None:
            duration = video_stream.get("duration")
        try:
            return float(duration) if duration is not None else 0.0
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _extract_fps(video_stream: dict[str, Any]) -> float:
        """Parse FPS from the stream's frame-rate fraction (e.g. '30000/1001')."""
        rate = video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate")
        if not rate or rate == "0/0":
            return 0.0
        try:
            return float(Fraction(rate))
        except (ZeroDivisionError, ValueError):
            return 0.0

    @staticmethod
    def _decode_stderr(exc: ffmpeg.Error) -> str:
        """Decode FFmpeg stderr bytes into a readable string."""
        stderr = getattr(exc, "stderr", None)
        if isinstance(stderr, bytes):
            return stderr.decode("utf-8", errors="replace").strip()
        return str(exc)

    def _raise_run_error(self, operation: str, exc: ffmpeg.Error) -> None:
        """Log and re-raise an FFmpeg run failure as a service error."""
        message = self._decode_stderr(exc)
        logger.error("%s failed: %s", operation, message)
        raise FFmpegServiceError(f"{operation} failed: {message}") from exc
