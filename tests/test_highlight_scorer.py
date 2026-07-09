"""Unit tests for the Phase 5A ``HighlightScorer``.

All tests use synthetic Phase 4A analysis dicts; no video, FFmpeg, Ollama,
audio or OCR is involved.
"""
from __future__ import annotations

import json

import pytest

from highlight_scorer import (
    HighlightReport,
    HighlightScorer,
    HighlightScorerError,
    HighlightScoringConfig,
)


def _scene(index, start, end, motion, brightness, static):
    return {
        "index": index,
        "start": start,
        "end": end,
        "duration": round(end - start, 3),
        "avg_motion": motion,
        "max_motion": motion,
        "avg_brightness": brightness,
        "avg_static": static,
    }


def _analysis(scenes, idle=None, black=None, video="C:/videos/clip.mp4"):
    return {
        "schema_version": "4a.1",
        "video": video,
        "metadata": {},
        "scenes": scenes,
        "idle_sections": idle or [],
        "black_screens": black or [],
    }


# --------------------------------------------------------------------- #
# Pure helpers
# --------------------------------------------------------------------- #
def test_normalize_clamps_between_0_and_1() -> None:
    assert HighlightScorer.normalize(0.0, 40.0) == 0.0
    assert HighlightScorer.normalize(40.0, 40.0) == 1.0
    assert HighlightScorer.normalize(80.0, 40.0) == 1.0  # clamped
    assert HighlightScorer.normalize(20.0, 40.0) == pytest.approx(0.5)
    assert HighlightScorer.normalize(10.0, 0.0) == 0.0  # bad reference


def test_overlap_ratio() -> None:
    spans = [{"start": 5.0, "end": 10.0}]
    assert HighlightScorer.overlap_ratio(0.0, 10.0, spans) == pytest.approx(0.5)
    assert HighlightScorer.overlap_ratio(5.0, 10.0, spans) == pytest.approx(1.0)
    assert HighlightScorer.overlap_ratio(11.0, 20.0, spans) == 0.0
    assert HighlightScorer.overlap_ratio(5.0, 5.0, spans) == 0.0


# --------------------------------------------------------------------- #
# Scoring behaviour
# --------------------------------------------------------------------- #
def test_score_is_normalized_0_to_100() -> None:
    scenes = [
        _scene(0, 0, 8, motion=200, brightness=255, static=0.0),
        _scene(1, 8, 16, motion=0, brightness=0, static=1.0),
    ]
    report = HighlightScorer().score_analysis(_analysis(scenes))
    for s in report.scenes:
        assert 0.0 <= s.score <= 100.0


def test_high_motion_outranks_low_motion() -> None:
    scenes = [
        _scene(0, 0, 8, motion=2, brightness=120, static=0.9),
        _scene(1, 8, 16, motion=40, brightness=120, static=0.1),
    ]
    report = HighlightScorer().score_analysis(_analysis(scenes))
    high = next(s for s in report.scenes if s.index == 1)
    low = next(s for s in report.scenes if s.index == 0)
    assert high.score > low.score
    assert high.rank < low.rank  # rank 1 is best


def test_idle_penalty_lowers_score() -> None:
    scene = _scene(0, 0, 10, motion=40, brightness=120, static=0.1)
    base = HighlightScorer().score_analysis(_analysis([scene]))
    idled = HighlightScorer().score_analysis(
        _analysis([scene], idle=[{"start": 0.0, "end": 10.0}])
    )
    assert idled.scenes[0].score < base.scenes[0].score


def test_black_screen_forces_ignore() -> None:
    scene = _scene(0, 0, 10, motion=40, brightness=5, static=0.1)
    report = HighlightScorer().score_analysis(
        _analysis([scene], black=[{"start": 0.0, "end": 9.0}])
    )
    assert report.scenes[0].classification == "Ignore"


def test_classification_buckets_present() -> None:
    scenes = [
        _scene(0, 0, 8, motion=60, brightness=200, static=0.0),
        _scene(1, 8, 16, motion=18, brightness=150, static=0.3),
        _scene(2, 16, 24, motion=1, brightness=10, static=0.99),
    ]
    report = HighlightScorer().score_analysis(_analysis(scenes))
    classes = {s.index: s.classification for s in report.scenes}
    assert classes[0] == "Excellent"
    assert classes[2] == "Ignore"
    valid = {"Excellent", "Good", "Average", "Ignore"}
    assert all(c in valid for c in classes.values())


def test_ranks_are_unique_and_sequential() -> None:
    scenes = [
        _scene(i, i * 8, i * 8 + 8, motion=i * 5, brightness=120, static=0.2)
        for i in range(5)
    ]
    report = HighlightScorer().score_analysis(_analysis(scenes))
    ranks = sorted(s.rank for s in report.scenes)
    assert ranks == [1, 2, 3, 4, 5]


def test_config_is_respected_no_magic_numbers() -> None:
    scene = _scene(0, 0, 8, motion=40, brightness=120, static=0.0)
    cfg = HighlightScoringConfig(
        motion_weight=0.0, brightness_weight=0.0, duration_weight=0.0
    )
    report = HighlightScorer(scoring_config=cfg).score_analysis(_analysis([scene]))
    assert report.scenes[0].score == 0.0


def test_invalid_thresholds_raise() -> None:
    with pytest.raises(HighlightScorerError):
        HighlightScorer(
            scoring_config=HighlightScoringConfig(
                excellent_threshold=10.0, good_threshold=20.0
            )
        )


# --------------------------------------------------------------------- #
# I/O and schema
# --------------------------------------------------------------------- #
def test_empty_scenes_produces_empty_report() -> None:
    report = HighlightScorer().score_analysis(_analysis([]))
    assert report.scenes == []
    assert report.schema_version == "5a.1"


def test_missing_scenes_key_raises() -> None:
    with pytest.raises(HighlightScorerError):
        HighlightScorer().score_analysis({"video": "x"})


def test_to_json_schema_keys() -> None:
    scene = _scene(0, 0, 8, motion=40, brightness=120, static=0.1)
    report = HighlightScorer().score_analysis(_analysis([scene]))
    data = json.loads(report.to_json())
    assert set(data) >= {"schema_version", "video", "scenes"}
    s0 = data["scenes"][0]
    assert set(s0) >= {
        "index", "start", "end", "duration", "score",
        "classification", "rank", "components",
    }


def test_score_file_and_score_to_file(tmp_path) -> None:
    from config import AppConfig, PathConfig

    app_config = AppConfig(paths=PathConfig(base_dir=tmp_path))

    analysis_path = tmp_path / "clip_analysis.json"
    scene = _scene(0, 0, 8, motion=40, brightness=120, static=0.1)
    analysis_path.write_text(json.dumps(_analysis([scene])), encoding="utf-8")

    scorer = HighlightScorer(app_config)
    report = scorer.score_file(analysis_path)
    assert isinstance(report, HighlightReport)

    first = scorer.score_to_file(analysis_path)
    second = scorer.score_to_file(analysis_path)
    assert first.exists() and second.exists()
    assert first != second  # never overwrites
    assert first.name == "clip_highlight.json"


def test_score_missing_file_raises() -> None:
    with pytest.raises(HighlightScorerError):
        HighlightScorer().score_file("nope_missing_123.json")
