"""Phase 4A: generic, game-agnostic video analysis.

Produces a structured JSON summary of a video's activity using:
- ``FFmpegService`` (Phase 2) for metadata (reused, not duplicated),
- PySceneDetect for content-based scene boundaries,
- lightweight OpenCV frame differencing for motion / brightness / static
  scores, idle sections and black-screen detection.

Design goals for this module:
- **Generic only.** No game-specific heuristics (kills, HUD, OCR, ...).
  Those belong to Phase 5 and live elsewhere.
- **No editing / rendering.** This module is read-only with respect to
  video and never modifies existing project files.
- **Performance over perfect accuracy.** Frame differencing on downscaled
  grayscale frames is used deliberately instead of optical flow, to run
  comfortably on a Ryzen 7 5700G / 16GB CPU-only machine.
- **Unit-test friendly.** Pure metric functions are static and operate on
  plain numpy arrays, so they can be tested without any real video file.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol

import cv2
import numpy as np
from scenedetect import ContentDetector, SceneManager, open_video

from config import AppConfig, config
from ffmpeg_service import FFmpegService, VideoMetadata
from logger import get_logger

logger = get_logger(__name__)


class VideoAnalyzerError(RuntimeError):
    """Raised when generic video analysis fails or input is invalid."""


class MetadataReader(Protocol):
    """Minimal interface required from a metadata provider.

    Declared as a Protocol so tests can inject a fake reader and the
    analyzer does not hard-depend on the concrete ``FFmpegService``.
    """

    def read_metadata(self, video_path: str | Path) -> VideoMetadata:
        """Return structured metadata for ``video_path``."""
        ...


@dataclass(frozen=True)
class GenericAnalysisConfig:
    """Thresholds controlling generic analysis sensitivity.

    All values are intentionally simple and unit-less where possible so the
    behaviour is easy to reason about and test.
    """

    sample_fps: float = 4.0
    analysis_width: int = 320
    scene_threshold: float = 27.0
    # Motion score is the mean absolute per-pixel difference (0..255) between
    # consecutive sampled grayscale frames.
    motion_idle_threshold: float = 2.0
    min_idle_seconds: float = 4.0
    # Brightness is the mean pixel value (0..255).
    black_brightness_threshold: float = 10.0
    min_black_seconds: float = 0.5


@dataclass
class FrameMetrics:
    """Per-sample generic metrics for a single analyzed frame."""

    timestamp: float
    motion_score: float
    brightness: float
    static_score: float
    is_black: bool
    is_idle: bool


@dataclass
class SceneMetrics:
    """A detected scene span with aggregated generic metrics."""

    index: int
    start: float
    end: float
    duration: float
    avg_motion: float
    max_motion: float
    avg_brightness: float
    avg_static: float


@dataclass
class TimeSpan:
    """A contiguous time span (used for idle and black-screen sections)."""

    start: float
    end: float
    duration: float


@dataclass
class MetadataSummary:
    """Serializable subset of video metadata for the analysis JSON."""

    duration: float
    width: int
    height: int
    fps: float
    codec: str
    size_bytes: int

    @classmethod
    def from_metadata(cls, meta: VideoMetadata) -> "MetadataSummary":
        """Build a summary from a full ``VideoMetadata`` instance."""
        return cls(
            duration=round(meta.duration, 3),
            width=meta.width,
            height=meta.height,
            fps=round(meta.fps, 3),
            codec=meta.codec,
            size_bytes=meta.size_bytes,
        )


@dataclass
class VideoAnalysis:
    """Complete generic analysis, serializable to the Phase 4A JSON shape."""

    video: str
    metadata: MetadataSummary
    scenes: list[SceneMetrics] = field(default_factory=list)
    idle_sections: list[TimeSpan] = field(default_factory=list)
    black_screens: list[TimeSpan] = field(default_factory=list)
    schema_version: str = "4a.1"

    def to_dict(self) -> dict[str, Any]:
        """Return a plain-dict representation ready for JSON serialization."""
        return {
            "schema_version": self.schema_version,
            "video": self.video,
            "metadata": asdict(self.metadata),
            "scenes": [asdict(s) for s in self.scenes],
            "idle_sections": [asdict(s) for s in self.idle_sections],
            "black_screens": [asdict(b) for b in self.black_screens],
        }

    def to_json(self, indent: int = 2) -> str:
        """Return the analysis serialized as a JSON string."""
        return json.dumps(self.to_dict(), indent=indent)


class VideoAnalyzer:
    """Analyzes a video and produces a generic (game-agnostic) JSON summary."""

    def __init__(
        self,
        app_config: AppConfig | None = None,
        analysis_config: GenericAnalysisConfig | None = None,
        metadata_reader: MetadataReader | None = None,
    ) -> None:
        """Create an analyzer.

        Args:
            app_config: Shared application config (paths, etc.).
            analysis_config: Detection thresholds. Defaults are CPU-friendly.
            metadata_reader: Metadata provider. Defaults to ``FFmpegService``;
                injectable for testing.
        """
        self._config = app_config or config
        self._analysis = analysis_config or GenericAnalysisConfig()
        self._metadata_reader: MetadataReader = metadata_reader or FFmpegService(
            self._config
        )
        logger.info("Initialized VideoAnalyzer")

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def analyze(self, video_path: str | Path) -> VideoAnalysis:
        """Analyze a video and return a structured generic analysis."""
        path = self._validate_input(video_path)
        logger.info("Analyzing (generic) %s", path.name)

        metadata = self._metadata_reader.read_metadata(path)
        scene_spans = self._detect_scene_spans(path)
        samples = self._sample_metrics(path)

        scenes = self._aggregate_scenes(scene_spans, samples, metadata.duration)
        idle = self._merge_flagged_spans(
            samples,
            metadata.duration,
            flag=lambda m: m.is_idle,
            min_seconds=self._analysis.min_idle_seconds,
        )
        black = self._merge_flagged_spans(
            samples,
            metadata.duration,
            flag=lambda m: m.is_black,
            min_seconds=self._analysis.min_black_seconds,
        )

        analysis = VideoAnalysis(
            video=str(path),
            metadata=MetadataSummary.from_metadata(metadata),
            scenes=scenes,
            idle_sections=idle,
            black_screens=black,
        )
        logger.info(
            "Generic analysis complete: %d scenes, %d idle, %d black",
            len(scenes),
            len(idle),
            len(black),
        )
        return analysis

    def analyze_to_file(
        self, video_path: str | Path, output_name: str | None = None
    ) -> Path:
        """Analyze a video and write the JSON to ``output/<stem>_analysis.json``.

        Existing analysis files are never overwritten; a numeric suffix is
        added when a collision occurs.
        """
        analysis = self.analyze(video_path)
        out_dir = self._config.paths.output_dir
        out_dir.mkdir(parents=True, exist_ok=True)

        stem = Path(analysis.video).stem
        base_name = output_name or f"{stem}_analysis.json"
        output = self._unique_path(out_dir, base_name)

        output.write_text(analysis.to_json(), encoding="utf-8")
        logger.info("Wrote generic analysis JSON -> %s", output)
        return output

    # ------------------------------------------------------------------ #
    # Scene detection (PySceneDetect)
    # ------------------------------------------------------------------ #
    def _detect_scene_spans(self, path: Path) -> list[tuple[float, float]]:
        """Detect scene boundaries as (start, end) second pairs."""
        try:
            video = open_video(str(path))
            manager = SceneManager()
            manager.add_detector(
                ContentDetector(threshold=self._analysis.scene_threshold)
            )
            manager.detect_scenes(video, show_progress=False)
            scene_list = manager.get_scene_list()
        except Exception as exc:  # noqa: BLE001 - normalize to service error
            logger.error("Scene detection failed: %s", exc)
            raise VideoAnalyzerError(f"Scene detection failed: {exc}") from exc

        return [
            (self._to_seconds(start), self._to_seconds(end))
            for start, end in scene_list
        ]

    @staticmethod
    def _to_seconds(timecode: Any) -> float:
        """Convert a PySceneDetect FrameTimecode to seconds.

        Uses ``float(timecode)`` (the supported API) instead of the
        deprecated ``FrameTimecode.get_seconds()``. Falls back to
        ``get_seconds()`` only if float conversion is unavailable, so the
        analyzer works across PySceneDetect versions.
        """
        try:
            return float(timecode)
        except (TypeError, ValueError):  # pragma: no cover - version fallback
            return float(timecode.get_seconds())

    # ------------------------------------------------------------------ #
    # Frame sampling (OpenCV, frame differencing)
    # ------------------------------------------------------------------ #
    def _sample_metrics(self, path: Path) -> list[FrameMetrics]:
        """Sample frames and compute generic per-frame metrics."""
        capture = cv2.VideoCapture(str(path))
        if not capture.isOpened():
            raise VideoAnalyzerError(f"OpenCV could not open: {path}")

        try:
            fps = capture.get(cv2.CAP_PROP_FPS) or 0.0
            if fps <= 0:
                raise VideoAnalyzerError("Could not determine video FPS.")

            step = max(int(round(fps / self._analysis.sample_fps)), 1)
            samples = self._collect_samples(capture, fps, step)
        finally:
            capture.release()

        return samples

    def _collect_samples(
        self, capture: cv2.VideoCapture, fps: float, step: int
    ) -> list[FrameMetrics]:
        """Iterate frames at the sampling step and build frame metrics."""
        samples: list[FrameMetrics] = []
        prev_gray: np.ndarray | None = None
        frame_idx = 0

        while True:
            ok, frame = capture.read()
            if not ok:
                break

            if frame_idx % step == 0:
                gray = self._to_analysis_gray(frame, self._analysis.analysis_width)
                timestamp = round(frame_idx / fps, 3)
                samples.append(self._build_metrics(timestamp, prev_gray, gray))
                prev_gray = gray

                # Light progress signal for long (1-3h) videos.
                if len(samples) % 1000 == 0:
                    logger.debug("Analyzed %d samples (t=%.1fs)", len(samples), timestamp)

            frame_idx += 1

        return samples

    def _build_metrics(
        self, timestamp: float, prev_gray: np.ndarray | None, gray: np.ndarray
    ) -> FrameMetrics:
        """Compute all generic metrics for a single sampled frame."""
        cfg = self._analysis
        brightness = self.compute_brightness(gray)
        motion = self.compute_motion(prev_gray, gray)
        static = self.compute_static_score(motion)

        return FrameMetrics(
            timestamp=timestamp,
            motion_score=round(motion, 4),
            brightness=round(brightness, 4),
            static_score=round(static, 4),
            is_black=brightness <= cfg.black_brightness_threshold,
            is_idle=motion < cfg.motion_idle_threshold,
        )

    # ------------------------------------------------------------------ #
    # Pure metric functions (static, unit-test friendly)
    # ------------------------------------------------------------------ #
    @staticmethod
    def _to_analysis_gray(frame: np.ndarray, target_w: int) -> np.ndarray:
        """Downscale and grayscale a BGR frame for cheap analysis."""
        height, width = frame.shape[:2]
        if width > target_w and width > 0:
            scale = target_w / width
            frame = cv2.resize(frame, (target_w, max(int(height * scale), 1)))
        if frame.ndim == 3:
            return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return frame

    @staticmethod
    def compute_brightness(gray: np.ndarray) -> float:
        """Return mean brightness (0..255) of a grayscale frame."""
        return float(np.mean(gray))

    @staticmethod
    def compute_motion(
        prev_gray: np.ndarray | None, gray: np.ndarray
    ) -> float:
        """Return the motion score via mean absolute frame differencing.

        The score is the mean absolute per-pixel difference (0..255) between
        the previous and current grayscale frames. Returns ``0.0`` when there
        is no previous frame.
        """
        if prev_gray is None:
            return 0.0
        # Frame dimensions can change mid-stream (e.g. concatenated clips or
        # some capture cards). absdiff would raise on a shape mismatch, so
        # skip motion for that transition rather than aborting the analysis.
        if prev_gray.shape != gray.shape:
            return 0.0
        diff = cv2.absdiff(prev_gray, gray)
        return float(np.mean(diff))

    @staticmethod
    def compute_static_score(motion_score: float) -> float:
        """Return a 0..1 'stillness' score derived from the motion score.

        ``1.0`` means perfectly static; the score decays towards ``0.0`` as
        motion increases. Kept as a pure function of the motion score so it
        is trivially testable and consistent across the module.
        """
        if motion_score <= 0.0:
            return 1.0
        return float(1.0 / (1.0 + motion_score))

    # ------------------------------------------------------------------ #
    # Aggregation
    # ------------------------------------------------------------------ #
    def _aggregate_scenes(
        self,
        scene_spans: list[tuple[float, float]],
        samples: list[FrameMetrics],
        duration: float,
    ) -> list[SceneMetrics]:
        """Aggregate per-frame metrics into per-scene summaries.

        If PySceneDetect returns no scenes (e.g. a single continuous shot),
        the whole video is treated as one scene. Uses a single ordered pass
        over the samples (both scenes and samples are time-sorted) so cost is
        O(scenes + samples) rather than O(scenes * samples); this matters for
        long 1-3h videos with many scene cuts.
        """
        spans = scene_spans or [(0.0, duration)]
        buckets: list[list[FrameMetrics]] = [[] for _ in spans]

        sample_idx = 0
        n_samples = len(samples)
        for span_idx, (start, end) in enumerate(spans):
            # Skip samples that fall before this scene's start (e.g. gaps).
            while sample_idx < n_samples and samples[sample_idx].timestamp < start:
                sample_idx += 1
            while sample_idx < n_samples and samples[sample_idx].timestamp < end:
                buckets[span_idx].append(samples[sample_idx])
                sample_idx += 1

        scenes: list[SceneMetrics] = []
        for index, ((start, end), in_scene) in enumerate(zip(spans, buckets)):
            motions = [s.motion_score for s in in_scene]
            brights = [s.brightness for s in in_scene]
            statics = [s.static_score for s in in_scene]

            scenes.append(
                SceneMetrics(
                    index=index,
                    start=round(start, 3),
                    end=round(end, 3),
                    duration=round(end - start, 3),
                    avg_motion=round(_safe_mean(motions), 4),
                    max_motion=round(max(motions), 4) if motions else 0.0,
                    avg_brightness=round(_safe_mean(brights), 4),
                    avg_static=round(_safe_mean(statics), 4),
                )
            )
        return scenes

    def _merge_flagged_spans(
        self,
        samples: list[FrameMetrics],
        duration: float,
        flag: Callable[[FrameMetrics], bool],
        min_seconds: float,
    ) -> list[TimeSpan]:
        """Merge contiguous flagged samples into spans of a minimum length.

        Args:
            samples: Ordered per-frame metrics.
            duration: Total video duration, used to close a trailing run.
            flag: Predicate selecting samples that belong to a span.
            min_seconds: Minimum span length to keep.
        """
        spans: list[TimeSpan] = []
        run_start: float | None = None
        prev_ts = 0.0

        for sample in samples:
            if flag(sample) and run_start is None:
                run_start = sample.timestamp
            elif not flag(sample) and run_start is not None:
                self._append_span(spans, run_start, prev_ts, min_seconds)
                run_start = None
            prev_ts = sample.timestamp

        if run_start is not None:
            end = duration if duration > 0 else prev_ts
            self._append_span(spans, run_start, end, min_seconds)

        return spans

    @staticmethod
    def _append_span(
        spans: list[TimeSpan], start: float, end: float, min_len: float
    ) -> None:
        """Append a span if it meets the minimum length."""
        if end - start >= min_len:
            spans.append(
                TimeSpan(
                    start=round(start, 3),
                    end=round(end, 3),
                    duration=round(end - start, 3),
                )
            )

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _unique_path(directory: Path, base_name: str) -> Path:
        """Return a path in ``directory`` that does not already exist.

        Adds ``_1``, ``_2``, ... before the suffix on collision so previous
        analysis files are never overwritten.
        """
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

    @staticmethod
    def _validate_input(video_path: str | Path) -> Path:
        """Validate that the input path exists and is a file."""
        path = Path(video_path).expanduser().resolve()
        if not path.exists():
            raise VideoAnalyzerError(f"Input file does not exist: {path}")
        if not path.is_file():
            raise VideoAnalyzerError(f"Input path is not a file: {path}")
        return path


def _safe_mean(values: list[float]) -> float:
    """Return the mean of ``values`` or ``0.0`` for an empty list."""
    return float(np.mean(values)) if values else 0.0
