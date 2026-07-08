"""Gameplay scene analysis: scene changes, motion, highlights, idle sections.

Combines PySceneDetect (content-based scene cuts) with OpenCV frame analysis
(motion intensity, camera movement, brightness spikes) to produce a JSON
summary. This module is read-only with respect to video: it never edits
footage and never modifies existing project files.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from scenedetect import ContentDetector, SceneManager, open_video

from config import AppConfig, config
from logger import get_logger

logger = get_logger(__name__)


class SceneDetectorError(RuntimeError):
    """Raised when scene analysis fails or input is invalid."""


@dataclass(frozen=True)
class AnalysisConfig:
    """Thresholds controlling detection sensitivity."""

    sample_fps: float = 4.0
    scene_threshold: float = 27.0
    motion_analysis_width: int = 320
    high_motion_threshold: float = 6.0
    camera_move_threshold: float = 3.0
    explosion_brightness_jump: float = 40.0
    fast_movement_threshold: float = 9.0
    kill_motion_threshold: float = 7.5
    kill_brightness_jump: float = 25.0
    idle_motion_threshold: float = 1.0
    min_idle_seconds: float = 4.0


@dataclass
class Scene:
    """A detected scene span."""

    index: int
    start: float
    end: float
    duration: float


@dataclass
class Highlight:
    """A notable moment detected in the footage."""

    type: str
    timestamp: float
    score: float
    detail: str = ""


@dataclass
class BoringSection:
    """A long low-activity span."""

    start: float
    end: float
    duration: float


@dataclass
class _FrameSample:
    """Internal per-frame analysis result."""

    timestamp: float
    motion: float
    global_motion: float
    brightness: float


@dataclass
class AnalysisResult:
    """Complete analysis, serializable to the required JSON shape."""

    video: str
    duration: float
    fps: float
    scenes: list[Scene] = field(default_factory=list)
    highlights: list[Highlight] = field(default_factory=list)
    boring_sections: list[BoringSection] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "video": self.video,
            "duration": round(self.duration, 3),
            "fps": round(self.fps, 3),
            "scenes": [asdict(s) for s in self.scenes],
            "highlights": [asdict(h) for h in self.highlights],
            "boring_sections": [asdict(b) for b in self.boring_sections],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


class SceneDetector:
    """Analyzes a gameplay video and produces a JSON activity summary."""

    def __init__(
        self,
        app_config: AppConfig | None = None,
        analysis_config: AnalysisConfig | None = None,
    ) -> None:
        self._config = app_config or config
        self._analysis = analysis_config or AnalysisConfig()
        logger.info("Initialized SceneDetector")

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def analyze(self, video_path: str | Path) -> AnalysisResult:
        """Analyze a video and return a structured result."""
        path = self._validate_input(video_path)
        logger.info("Analyzing %s", path.name)

        scenes = self._detect_scenes(path)
        samples, duration, fps = self._analyze_frames(path)

        highlights = self._detect_highlights(samples)
        boring = self._detect_boring_sections(samples, duration)

        result = AnalysisResult(
            video=str(path),
            duration=duration,
            fps=fps,
            scenes=scenes,
            highlights=highlights,
            boring_sections=boring,
        )
        logger.info(
            "Analysis complete: %d scenes, %d highlights, %d boring sections",
            len(scenes),
            len(highlights),
            len(boring),
        )
        return result

    def analyze_to_json(self, video_path: str | Path) -> str:
        """Analyze a video and return the result as a JSON string."""
        return self.analyze(video_path).to_json()

    def analyze_to_file(
        self, video_path: str | Path, output_name: str | None = None
    ) -> Path:
        """Analyze a video and write the JSON result to the output directory."""
        result = self.analyze(video_path)
        out_dir = self._config.paths.output_dir
        out_dir.mkdir(parents=True, exist_ok=True)

        stem = Path(result.video).stem
        output = out_dir / (output_name or f"{stem}_analysis.json")
        output.write_text(result.to_json(), encoding="utf-8")
        logger.info("Wrote analysis JSON -> %s", output)
        return output

    # ------------------------------------------------------------------ #
    # Scene detection (PySceneDetect)
    # ------------------------------------------------------------------ #
    def _detect_scenes(self, path: Path) -> list[Scene]:
        """Detect scene boundaries using content-based detection."""
        try:
            video = open_video(str(path))
            manager = SceneManager()
            manager.add_detector(
                ContentDetector(threshold=self._analysis.scene_threshold)
            )
            manager.detect_scenes(video, show_progress=False)
            scene_list = manager.get_scene_list()
        except Exception as exc:
            logger.error("Scene detection failed: %s", exc)
            raise SceneDetectorError(f"Scene detection failed: {exc}") from exc

        scenes: list[Scene] = []
        for i, (start, end) in enumerate(scene_list):
            start_s = start.get_seconds()
            end_s = end.get_seconds()
            scenes.append(
                Scene(
                    index=i,
                    start=round(start_s, 3),
                    end=round(end_s, 3),
                    duration=round(end_s - start_s, 3),
                )
            )
        return scenes

    # ------------------------------------------------------------------ #
    # Frame analysis (OpenCV)
    # ------------------------------------------------------------------ #
    def _analyze_frames(
        self, path: Path
    ) -> tuple[list[_FrameSample], float, float]:
        """Sample frames and compute motion, camera movement and brightness."""
        capture = cv2.VideoCapture(str(path))
        if not capture.isOpened():
            raise SceneDetectorError(f"OpenCV could not open: {path}")

        try:
            fps = capture.get(cv2.CAP_PROP_FPS) or 0.0
            frame_count = capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0
            duration = frame_count / fps if fps > 0 else 0.0

            if fps <= 0:
                raise SceneDetectorError("Could not determine video FPS.")

            step = max(int(round(fps / self._analysis.sample_fps)), 1)
            samples = self._collect_samples(capture, fps, step)
        finally:
            capture.release()

        return samples, round(duration, 3), round(fps, 3)

    def _collect_samples(
        self, capture: cv2.VideoCapture, fps: float, step: int
    ) -> list[_FrameSample]:
        """Iterate frames at the sampling step and build frame samples."""
        samples: list[_FrameSample] = []
        prev_gray: np.ndarray | None = None
        frame_idx = 0

        while True:
            ok, frame = capture.read()
            if not ok:
                break

            if frame_idx % step == 0:
                gray = self._to_analysis_gray(frame)
                brightness = float(np.mean(gray))

                if prev_gray is not None:
                    motion, global_motion = self._optical_flow_metrics(
                        prev_gray, gray
                    )
                else:
                    motion, global_motion = 0.0, 0.0

                samples.append(
                    _FrameSample(
                        timestamp=round(frame_idx / fps, 3),
                        motion=motion,
                        global_motion=global_motion,
                        brightness=brightness,
                    )
                )
                prev_gray = gray

            frame_idx += 1

        return samples

    def _to_analysis_gray(self, frame: np.ndarray) -> np.ndarray:
        """Downscale and grayscale a frame for cheap motion analysis."""
        height, width = frame.shape[:2]
        target_w = self._analysis.motion_analysis_width
        if width > target_w:
            scale = target_w / width
            frame = cv2.resize(frame, (target_w, int(height * scale)))
        return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    @staticmethod
    def _optical_flow_metrics(
        prev_gray: np.ndarray, gray: np.ndarray
    ) -> tuple[float, float]:
        """Compute mean motion magnitude and global (camera) motion."""
        flow = cv2.calcOpticalFlowFarneback(
            prev_gray, gray, None,
            pyr_scale=0.5, levels=2, winsize=15,
            iterations=2, poly_n=5, poly_sigma=1.1, flags=0,
        )
        fx, fy = flow[..., 0], flow[..., 1]
        magnitude = np.sqrt(fx * fx + fy * fy)
        mean_motion = float(np.mean(magnitude))
        global_motion = float(np.sqrt(np.mean(fx) ** 2 + np.mean(fy) ** 2))
        return mean_motion, global_motion

    # ------------------------------------------------------------------ #
    # Heuristics
    # ------------------------------------------------------------------ #
    def _detect_highlights(self, samples: list[_FrameSample]) -> list[Highlight]:
        """Apply heuristics to flag notable moments."""
        cfg = self._analysis
        highlights: list[Highlight] = []

        for i, s in enumerate(samples):
            prev = samples[i - 1] if i > 0 else None
            brightness_jump = (s.brightness - prev.brightness) if prev else 0.0

            if (
                brightness_jump >= cfg.explosion_brightness_jump
                and s.motion >= cfg.high_motion_threshold
            ):
                highlights.append(
                    Highlight(
                        type="explosion",
                        timestamp=s.timestamp,
                        score=round(brightness_jump + s.motion, 2),
                        detail=f"brightness +{brightness_jump:.1f}, motion {s.motion:.1f}",
                    )
                )
                continue

            if (
                s.motion >= cfg.kill_motion_threshold
                and abs(brightness_jump) >= cfg.kill_brightness_jump
            ):
                highlights.append(
                    Highlight(
                        type="kill",
                        timestamp=s.timestamp,
                        score=round(s.motion + abs(brightness_jump), 2),
                        detail=f"motion {s.motion:.1f}, brightness d{brightness_jump:.1f}",
                    )
                )
                continue

            if s.motion >= cfg.fast_movement_threshold:
                highlights.append(
                    Highlight(
                        type="fast_movement",
                        timestamp=s.timestamp,
                        score=round(s.motion, 2),
                        detail=f"motion {s.motion:.1f}",
                    )
                )
                continue

            if s.global_motion >= cfg.camera_move_threshold:
                highlights.append(
                    Highlight(
                        type="camera_movement",
                        timestamp=s.timestamp,
                        score=round(s.global_motion, 2),
                        detail=f"global flow {s.global_motion:.1f}",
                    )
                )
                continue

            if s.motion >= cfg.high_motion_threshold:
                highlights.append(
                    Highlight(
                        type="motion",
                        timestamp=s.timestamp,
                        score=round(s.motion, 2),
                        detail=f"motion {s.motion:.1f}",
                    )
                )

        return highlights

    def _detect_boring_sections(
        self, samples: list[_FrameSample], duration: float
    ) -> list[BoringSection]:
        """Find contiguous low-motion spans longer than the idle threshold."""
        cfg = self._analysis
        boring: list[BoringSection] = []

        run_start: float | None = None
        prev_ts: float = 0.0

        for s in samples:
            is_idle = s.motion < cfg.idle_motion_threshold
            if is_idle and run_start is None:
                run_start = s.timestamp
            elif not is_idle and run_start is not None:
                self._append_boring(boring, run_start, prev_ts, cfg.min_idle_seconds)
                run_start = None
            prev_ts = s.timestamp

        if run_start is not None:
            end = duration if duration > 0 else prev_ts
            self._append_boring(boring, run_start, end, cfg.min_idle_seconds)

        return boring

    @staticmethod
    def _append_boring(
        boring: list[BoringSection], start: float, end: float, min_len: float
    ) -> None:
        """Append a boring section if it meets the minimum length."""
        if end - start >= min_len:
            boring.append(
                BoringSection(
                    start=round(start, 3),
                    end=round(end, 3),
                    duration=round(end - start, 3),
                )
            )

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _validate_input(video_path: str | Path) -> Path:
        """Validate that the input path exists and is a file."""
        path = Path(video_path).expanduser().resolve()
        if not path.exists():
            raise SceneDetectorError(f"Input file does not exist: {path}")
        if not path.is_file():
            raise SceneDetectorError(f"Input path is not a file: {path}")
        return path
