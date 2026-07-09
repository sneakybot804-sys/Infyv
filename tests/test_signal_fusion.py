"""Unit tests for the Phase 5D Signal Fusion Engine.

Dependency-light: fusion is a pure JSON consumer, so all tests use synthetic
artifact dicts. No video, FFmpeg, OCR engine or audio backend is involved.
"""
from __future__ import annotations

import json

import pytest

from signal_fusion import SCHEMA_VERSION, SignalFusionEngine
from signal_fusion_config import FusionConfig, FusionError


# --------------------------------------------------------------------- #
# Synthetic artifact builders (real 5a.1 / 5b.1 / 5c.1 shapes)
# --------------------------------------------------------------------- #
def _highlight(scenes, video="C:/videos/clip.mp4"):
    return {"schema_version": "5a.1", "video": video, "scenes": scenes}


def _scene(index, start, end, score, classification="Average"):
    return {
        "index": index,
        "start": start,
        "end": end,
        "duration": round(end - start, 3),
        "score": score,
        "classification": classification,
        "rank": 0,
    }


def _ocr(detections, video="C:/videos/clip.mp4"):
    return {"schema_version": "5b.1", "video": video, "engine": "fake",
            "detections": detections}


def _det(scene_index, text, confidence, region="top_right"):
    return {
        "id": f"{region}-0001",
        "scene_index": scene_index,
        "timestamp": 1.0,
        "region": region,
        "text": text,
        "confidence": confidence,
        "bbox": {"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.1},
    }


def _audio(events=None, peaks=None, video="C:/videos/clip.mp4"):
    track = {
        "name": "commentary",
        "role": "commentary",
        "events": events or [],
        "excitement": (
            {"hop_seconds": 0.5, "score_series": [], "peaks": peaks}
            if peaks is not None
            else None
        ),
    }
    return {"schema_version": "5c.1", "video": video, "backend": "fake",
            "tracks": [track]}


def _event(scene_index, energy, type="energy_peak"):
    return {"id": f"commentary-{type}-0001", "start": 1.0, "end": 1.4,
            "type": type, "energy": energy, "confidence": 0.8,
            "scene_index": scene_index}


def _peak(scene_index, score):
    return {"id": "commentary-excitement_peak-0001", "start": 1.0, "end": 1.5,
            "score": score, "scene_index": scene_index}


def _engine(fusion_config=None, app_config=None):
    return SignalFusionEngine(app_config=app_config, fusion_config=fusion_config)


# --------------------------------------------------------------------- #
# Weight application
# --------------------------------------------------------------------- #
def test_base_only_weight_maps_score_to_output_scale():
    # Only the base signal is weighted; a 5A score of 50 -> 0.5 -> 50.0.
    cfg = FusionConfig(
        base_highlight_weight=1.0,
        ocr_weight=0.0,
        audio_energy_weight=0.0,
        voice_excitement_weight=0.0,
    )
    report = _engine(cfg).fuse(_highlight([_scene(0, 0, 8, score=50.0)]))
    assert report.scenes[0].score == pytest.approx(50.0)
    assert report.scenes[0].signals.base_highlight == pytest.approx(0.5)


def test_ocr_signal_raises_fused_score():
    cfg = FusionConfig(
        base_highlight_weight=1.0,
        ocr_weight=1.0,
        audio_energy_weight=0.0,
        voice_excitement_weight=0.0,
    )
    base = _highlight([_scene(0, 0, 8, score=40.0)])
    without = _engine(cfg).fuse(base)
    with_ocr = _engine(cfg).fuse(base, ocr=_ocr([_det(0, "KILL", 1.0)]))
    # base 0.4 alone -> 40; adding OCR 1.0 with equal weight -> (0.4+1.0)/2=0.7 -> 70.
    assert without.scenes[0].score == pytest.approx(40.0)
    assert with_ocr.scenes[0].score == pytest.approx(70.0)


def test_voice_excitement_signal_contributes():
    cfg = FusionConfig(
        base_highlight_weight=1.0, ocr_weight=0.0,
        audio_energy_weight=0.0, voice_excitement_weight=1.0,
    )
    base = _highlight([_scene(0, 0, 8, score=20.0)])
    fused = _engine(cfg).fuse(base, audio=_audio(peaks=[_peak(0, 0.8)]))
    # (0.2 + 0.8)/2 = 0.5 -> 50.
    assert fused.scenes[0].score == pytest.approx(50.0)
    assert fused.scenes[0].signals.voice_excitement == pytest.approx(0.8)


# --------------------------------------------------------------------- #
# Scene alignment (highlight.index == ocr/audio scene_index)
# --------------------------------------------------------------------- #
def test_signals_align_by_scene_index():
    cfg = FusionConfig(
        base_highlight_weight=1.0, ocr_weight=1.0,
        audio_energy_weight=0.0, voice_excitement_weight=0.0,
    )
    highlight = _highlight([_scene(0, 0, 4, 40.0), _scene(1, 4, 8, 40.0)])
    ocr = _ocr([_det(1, "ACE", 1.0)])  # only scene 1 has OCR
    report = _engine(cfg).fuse(highlight, ocr=ocr)
    by_index = {s.index: s for s in report.scenes}
    assert by_index[0].signals.ocr == 0.0
    assert by_index[1].signals.ocr == pytest.approx(1.0)
    assert by_index[1].ocr == ["ACE"]


def test_max_confidence_used_when_multiple_detections_in_scene():
    cfg = FusionConfig(ocr_weight=1.0, audio_energy_weight=0.0,
                       voice_excitement_weight=0.0)
    ocr = _ocr([_det(0, "a", 0.3), _det(0, "b", 0.9), _det(0, "c", 0.5)])
    report = _engine(cfg).fuse(_highlight([_scene(0, 0, 8, 0.0)]), ocr=ocr)
    assert report.scenes[0].signals.ocr == pytest.approx(0.9)
    assert report.scenes[0].ocr == ["a", "b", "c"]


# --------------------------------------------------------------------- #
# Missing-artifact degradation (never fatal for ocr/audio)
# --------------------------------------------------------------------- #
def test_missing_ocr_and_audio_are_zero_not_fatal():
    report = _engine().fuse(_highlight([_scene(0, 0, 8, 50.0)]))
    s = report.scenes[0]
    assert s.signals.ocr == 0.0
    assert s.signals.audio_energy == 0.0
    assert s.signals.voice_excitement == 0.0
    assert report.sources["ocr"] == {"available": False, "schema_version": None}
    assert report.sources["audio"] == {"available": False, "schema_version": None}
    assert report.sources["highlight"]["available"] is True


def test_missing_highlight_is_fatal():
    with pytest.raises(FusionError):
        _engine().fuse({"schema_version": "5a.1", "video": "x"})  # no 'scenes'


def test_sources_report_available_schema_versions():
    report = _engine().fuse(
        _highlight([_scene(0, 0, 8, 10.0)]),
        ocr=_ocr([]),
        audio=_audio(events=[]),
    )
    assert report.sources["ocr"] == {"available": True, "schema_version": "5b.1"}
    assert report.sources["audio"] == {"available": True, "schema_version": "5c.1"}


# --------------------------------------------------------------------- #
# Null scene_index handling
# --------------------------------------------------------------------- #
def test_null_scene_index_contributes_to_no_scene():
    cfg = FusionConfig(ocr_weight=1.0, audio_energy_weight=1.0,
                       voice_excitement_weight=1.0)
    highlight = _highlight([_scene(0, 0, 8, 0.0)])
    ocr = _ocr([_det(None, "floating", 1.0)])
    audio = _audio(events=[_event(None, 1.0)], peaks=[_peak(None, 1.0)])
    report = _engine(cfg).fuse(highlight, ocr=ocr, audio=audio)
    s = report.scenes[0]
    assert s.signals.ocr == 0.0
    assert s.signals.audio_energy == 0.0
    assert s.signals.voice_excitement == 0.0
    assert s.ocr == []


# --------------------------------------------------------------------- #
# Deterministic ranking
# --------------------------------------------------------------------- #
def test_ranking_is_by_score_desc_then_index():
    highlight = _highlight([
        _scene(0, 0, 4, 20.0),
        _scene(1, 4, 8, 80.0),
        _scene(2, 8, 12, 50.0),
    ])
    report = _engine().fuse(highlight)
    order = [(s.index, s.rank) for s in report.scenes]
    assert order == [(1, 1), (2, 2), (0, 3)]


def test_ranking_tie_break_by_index_is_deterministic():
    highlight = _highlight([
        _scene(2, 8, 12, 50.0),
        _scene(0, 0, 4, 50.0),
        _scene(1, 4, 8, 50.0),
    ])
    a = _engine().fuse(highlight)
    b = _engine().fuse(highlight)
    assert [s.index for s in a.scenes] == [0, 1, 2]
    assert [s.index for s in a.scenes] == [s.index for s in b.scenes]
    assert [s.rank for s in a.scenes] == [1, 2, 3]


# --------------------------------------------------------------------- #
# top_n behaviour
# --------------------------------------------------------------------- #
def test_top_n_none_keeps_all():
    highlight = _highlight([_scene(i, i * 4, i * 4 + 4, i * 10.0) for i in range(5)])
    report = _engine(FusionConfig(top_n=None)).fuse(highlight)
    assert len(report.scenes) == 5


def test_top_n_limits_to_highest_ranked():
    highlight = _highlight([_scene(i, i * 4, i * 4 + 4, i * 10.0) for i in range(5)])
    report = _engine(FusionConfig(top_n=2)).fuse(highlight)
    assert len(report.scenes) == 2
    # Highest scores are indices 4 (40) and 3 (30).
    assert [s.index for s in report.scenes] == [4, 3]
    assert [s.rank for s in report.scenes] == [1, 2]


# --------------------------------------------------------------------- #
# Schema shape
# --------------------------------------------------------------------- #
def test_document_schema_shape():
    report = _engine().fuse(
        _highlight([_scene(0, 0, 8, 90.0)]),
        ocr=_ocr([_det(0, "HELLO", 0.9)]),
    )
    doc = report.to_dict()
    assert doc["schema_version"] == SCHEMA_VERSION
    assert set(doc) == {"schema_version", "video", "sources", "scenes"}
    assert set(doc["sources"]) == {"highlight", "ocr", "audio"}
    scene = doc["scenes"][0]
    assert set(scene) == {
        "index", "start", "end", "duration", "score",
        "classification", "rank", "signals", "ocr",
    }
    assert set(scene["signals"]) == {
        "base_highlight", "ocr", "audio_energy", "voice_excitement"
    }
    # Round-trips as JSON.
    assert json.loads(report.to_json())["schema_version"] == SCHEMA_VERSION


def test_empty_scenes_serialize_as_list():
    report = _engine().fuse(_highlight([]))
    assert report.to_dict()["scenes"] == []


# --------------------------------------------------------------------- #
# Never-overwrite output (isolated config; no global singleton mutation)
# --------------------------------------------------------------------- #
def test_fuse_to_file_never_overwrites(tmp_path):
    from config import AppConfig, PathConfig

    app_config = AppConfig(paths=PathConfig(base_dir=tmp_path))
    out_dir = app_config.paths.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    video = "C:/videos/clip.mp4"
    (out_dir / "clip_highlight.json").write_text(
        json.dumps(_highlight([_scene(0, 0, 8, 60.0)], video=video)),
        encoding="utf-8",
    )

    engine = SignalFusionEngine(app_config)
    first = engine.fuse_to_file(video)
    second = engine.fuse_to_file(video)
    assert first.exists() and second.exists()
    assert first != second
    assert first.name == "clip_enriched_highlight.json"


def test_fuse_files_auto_discovers_optional_artifacts(tmp_path):
    from config import AppConfig, PathConfig

    app_config = AppConfig(paths=PathConfig(base_dir=tmp_path))
    out_dir = app_config.paths.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    video = "C:/videos/clip.mp4"
    (out_dir / "clip_highlight.json").write_text(
        json.dumps(_highlight([_scene(0, 0, 8, 40.0)], video=video)),
        encoding="utf-8",
    )
    (out_dir / "clip_ocr.json").write_text(
        json.dumps(_ocr([_det(0, "WIN", 1.0)], video=video)), encoding="utf-8"
    )
    # No audio artifact on disk -> audio signal absent, not fatal.

    cfg = FusionConfig(base_highlight_weight=1.0, ocr_weight=1.0,
                       audio_energy_weight=0.0, voice_excitement_weight=0.0)
    report = SignalFusionEngine(app_config, cfg).fuse_files(video)
    assert report.sources["ocr"]["available"] is True
    assert report.sources["audio"]["available"] is False
    assert report.scenes[0].score == pytest.approx(70.0)  # (0.4+1.0)/2*100


def test_fuse_files_missing_highlight_raises(tmp_path):
    from config import AppConfig, PathConfig

    app_config = AppConfig(paths=PathConfig(base_dir=tmp_path))
    app_config.paths.output_dir.mkdir(parents=True, exist_ok=True)
    with pytest.raises(FusionError):
        SignalFusionEngine(app_config).fuse_files("C:/videos/missing.mp4")


# --------------------------------------------------------------------- #
# Config validation (no magic numbers)
# --------------------------------------------------------------------- #
def test_config_validate_rejects_bad_values():
    with pytest.raises(FusionError):
        FusionConfig(base_highlight_weight=-1.0).validate()
    with pytest.raises(FusionError):
        FusionConfig(
            base_highlight_weight=0.0, ocr_weight=0.0,
            audio_energy_weight=0.0, voice_excitement_weight=0.0,
        ).validate()
    with pytest.raises(FusionError):
        FusionConfig(base_score_reference=0.0).validate()
    with pytest.raises(FusionError):
        FusionConfig(top_n=0).validate()
    with pytest.raises(FusionError):
        FusionConfig(excellent_threshold=10.0, good_threshold=20.0).validate()


def test_engine_construction_validates_config():
    with pytest.raises(FusionError):
        SignalFusionEngine(fusion_config=FusionConfig(top_n=-5))


# --------------------------------------------------------------------- #
# Producer/consumer decoupling guard
# --------------------------------------------------------------------- #
def test_fusion_modules_are_decoupled():
    import signal_fusion as mod_a
    import signal_fusion_config as mod_b

    forbidden = {
        "highlight_scorer", "video_analyzer", "audio_analyzer",
        "hud_text_extractor", "ocr_engine", "scene_detector",
    }
    for module in (mod_a, mod_b):
        src_names = set(vars(module))
        assert forbidden.isdisjoint(src_names), (
            f"{module.__name__} must not import {forbidden & src_names}"
        )


def test_fusion_does_not_mutate_input_artifacts():
    highlight = _highlight([_scene(0, 0, 8, 50.0)])
    ocr = _ocr([_det(0, "X", 0.9)])
    audio = _audio(events=[_event(0, 0.7)], peaks=[_peak(0, 0.6)])
    snapshot = json.dumps([highlight, ocr, audio], sort_keys=True)
    _engine().fuse(highlight, ocr=ocr, audio=audio)
    assert json.dumps([highlight, ocr, audio], sort_keys=True) == snapshot
