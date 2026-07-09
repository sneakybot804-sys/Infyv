"""Unit tests for the Phase 4A generic ``VideoAnalyzer``.

The pure metric functions are tested directly with numpy arrays, and the
full pipeline is tested against small synthetic videos with an injected
fake metadata reader (so tests do not depend on FFmpeg).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest

from video_analyzer import (
    GenericAnalysisConfig,
    VideoAnalyzer,
    VideoAnalyzerError,
)


@dataclass
class _FakeMetadata:
    """Minimal stand-in matching the fields the analyzer reads."""

    path: Path
    duration: float
    width: int
    height: int
    fps: float
    codec: str
    size_bytes: int


class _FakeMetadataReader:
    """Fake MetadataReader returning fixed metadata (no FFmpeg needed)."""

    def __init__(self, duration: float, fps: float = 8.0) -> None:
        self._duration = duration
        self._fps = fps

    def read_metadata(self, video_path):  # type: ignore[no-untyped-def]
        return _FakeMetadata(
            path=Path(video_path),
            duration=self._duration,
            width=160,
            height=90,
            fps=self._fps,
            codec="mjpg",
            size_bytes=1234,
        )


# --------------------------------------------------------------------- #
# Pure metric functions
# --------------------------------------------------------------------- #
def test_compute_brightness_black_and_white() -> None:
    black = np.zeros((10, 10), dtype=np.uint8)
    white = np.full((10, 10), 255, dtype=np.uint8)
    assert VideoAnalyzer.compute_brightness(black) == 0.0
    assert VideoAnalyzer.compute_brightness(white) == 255.0


def test_compute_motion_none_and_identical_and_changed() -> None:
    frame = np.full((10, 10), 100, dtype=np.uint8)
    changed = np.full((10, 10), 150, dtype=np.uint8)
    # No previous frame => zero motion.
    assert VideoAnalyzer.compute_motion(None, frame) == 0.0
    # Identical frames => zero motion.
    assert VideoAnalyzer.compute_motion(frame, frame) == 0.0
    # Uniform +50 change => motion score of 50.
    assert VideoAnalyzer.compute_motion(frame, changed) == pytest.approx(50.0)


def test_compute_static_score_is_inverse_of_motion() -> None:
    assert VideoAnalyzer.compute_static_score(0.0) == 1.0
    high = VideoAnalyzer.compute_static_score(100.0)
    low_motion = VideoAnalyzer.compute_static_score(1.0)
    assert 0.0 < high < low_motion < 1.0


def test_compute_motion_shape_mismatch_returns_zero() -> None:
    small = np.full((10, 10), 100, dtype=np.uint8)
    big = np.full((20, 20), 200, dtype=np.uint8)
    # Differing shapes must not raise; motion is skipped for that transition.
    assert VideoAnalyzer.compute_motion(small, big) == 0.0


# --------------------------------------------------------------------- #
# Full pipeline against synthetic videos
# --------------------------------------------------------------------- #
def _analyzer(duration: float, fps: float = 8.0) -> VideoAnalyzer:
    return VideoAnalyzer(
        analysis_config=GenericAnalysisConfig(
            sample_fps=8.0,
            min_idle_seconds=1.0,
            min_black_seconds=0.5,
        ),
        metadata_reader=_FakeMetadataReader(duration=duration, fps=fps),
    )


def test_metadata_extraction(synthetic_video) -> None:
    video = synthetic_video([("static", 2.0)])
    analysis = _analyzer(duration=2.0).analyze(video)
    assert analysis.metadata.width == 160
    assert analysis.metadata.height == 90
    assert analysis.metadata.fps == 8.0
    assert analysis.metadata.duration == 2.0


def test_scene_detection_produces_at_least_one_scene(synthetic_video) -> None:
    video = synthetic_video([("static", 1.5), ("motion", 1.5)])
    analysis = _analyzer(duration=3.0).analyze(video)
    assert len(analysis.scenes) >= 1
    # Scenes cover the timeline in order.
    assert analysis.scenes[0].start == 0.0


def test_motion_and_brightness_scores_generated(synthetic_video) -> None:
    video = synthetic_video([("static", 1.0), ("motion", 2.0)])
    analysis = _analyzer(duration=3.0).analyze(video)
    # At least one scene shows real motion from the moving block.
    assert max(s.max_motion for s in analysis.scenes) > 5.0
    # Brightness is populated and within range.
    for scene in analysis.scenes:
        assert 0.0 <= scene.avg_brightness <= 255.0


def test_static_score_high_for_still_footage(synthetic_video) -> None:
    video = synthetic_video([("static", 2.0)])
    analysis = _analyzer(duration=2.0).analyze(video)
    assert analysis.scenes[0].avg_static > 0.5


def test_idle_detection(synthetic_video) -> None:
    video = synthetic_video([("static", 3.0)])
    analysis = _analyzer(duration=3.0).analyze(video)
    assert analysis.idle_sections, "expected an idle section for still footage"
    assert analysis.idle_sections[0].duration >= 1.0


def test_black_screen_detection(synthetic_video) -> None:
    video = synthetic_video([("black", 2.0), ("motion", 1.0)])
    analysis = _analyzer(duration=3.0).analyze(video)
    assert analysis.black_screens, "expected a black-screen section"
    assert analysis.black_screens[0].start == 0.0


def test_motion_footage_is_not_flagged_idle(synthetic_video) -> None:
    video = synthetic_video([("motion", 3.0)])
    analysis = _analyzer(duration=3.0).analyze(video)
    total_idle = sum(s.duration for s in analysis.idle_sections)
    assert total_idle == 0.0


# --------------------------------------------------------------------- #
# JSON output and file safety
# --------------------------------------------------------------------- #
def test_to_json_roundtrip_schema(synthetic_video) -> None:
    import json

    video = synthetic_video([("motion", 1.0)])
    analysis = _analyzer(duration=1.0).analyze(video)
    data = json.loads(analysis.to_json())
    for key in ("schema_version", "video", "metadata", "scenes",
                "idle_sections", "black_screens"):
        assert key in data


def test_analyze_to_file_never_overwrites(synthetic_video, tmp_path, monkeypatch) -> None:
    from config import config as app_config

    monkeypatch.setattr(type(app_config.paths), "base_dir", tmp_path, raising=False)
    video = synthetic_video([("static", 1.0)])

    analyzer = _analyzer(duration=1.0)
    first = analyzer.analyze_to_file(video)
    second = analyzer.analyze_to_file(video)

    assert first.exists()
    assert second.exists()
    assert first != second


def test_missing_input_raises() -> None:
    with pytest.raises(VideoAnalyzerError):
        _analyzer(duration=1.0).analyze("does_not_exist_12345.mp4")
