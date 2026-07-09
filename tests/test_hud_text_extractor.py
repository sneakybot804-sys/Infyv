"""Unit tests for the Phase 5B HUD Text Extractor (OCR).

Dependency-light by default: a fake OcrEngine and a fake FFmpeg service let
the orchestration be exercised without Tesseract or real video. A single
real-Tesseract integration test is included but auto-skips when unavailable.
"""
from __future__ import annotations

import importlib
import json

import numpy as np
import pytest

from hud_text_extractor import HudTextExtractor, SCHEMA_VERSION
from ocr_config import DEFAULT_ROIS, OcrConfig, OcrError, Roi
from ocr_engine import (
    OcrResult,
    TesseractOcrEngine,
    available_engines,
    binarize,
    create_engine,
    register_engine,
    to_grayscale,
    upscale,
)


# --------------------------------------------------------------------- #
# Test doubles
# --------------------------------------------------------------------- #
class FakeFFmpeg:
    """Fake FFmpeg service returning a synthetic frame for any timestamp."""

    def __init__(self, width=320, height=180, max_time=None):
        self._w = width
        self._h = height
        self._max_time = max_time
        self.calls: list[float] = []

    def extract_frame_at(self, video_path, timestamp):
        self.calls.append(timestamp)
        if self._max_time is not None and timestamp > self._max_time:
            raise RuntimeError("past end of video")
        # Deterministic gradient frame (BGR uint8).
        frame = np.zeros((self._h, self._w, 3), dtype=np.uint8)
        frame[:, :, 0] = 200
        return frame


class FakeEngine:
    """Fake OCR engine: returns one canned result per crop it receives."""

    name = "fake"

    def __init__(self):
        self.crops_seen = 0

    def recognize(self, image, /):
        self.crops_seen += 1
        return [
            OcrResult(
                text="SCORE 12",
                confidence=0.9,
                bbox={"x": 0.1, "y": 0.2, "w": 0.5, "h": 0.3},
            )
        ]


register_engine("fake", FakeEngine)


def _single_roi_config(**kw):
    base = dict(
        engine="fake",
        rois=(Roi("top_right", 0.70, 0.0, 0.30, 0.15),),
        upscale=1.0,
        threshold=False,
        grayscale=False,
    )
    base.update(kw)
    return OcrConfig(**base)


def _extractor(ocr_config=None, ffmpeg=None):
    return HudTextExtractor(
        ocr_config=ocr_config or _single_roi_config(),
        ffmpeg_service=ffmpeg or FakeFFmpeg(),
    )


def _write_analysis(tmp_path, video_name, scenes, black=None, idle=None):
    path = tmp_path / "clip_analysis.json"
    path.write_text(json.dumps({
        "schema_version": "4a.1",
        "video": f"C:/videos/{video_name}",
        "scenes": scenes,
        "black_screens": black or [],
        "idle_sections": idle or [],
    }), encoding="utf-8")
    return path


# --------------------------------------------------------------------- #
# ROI-only behaviour + schema
# --------------------------------------------------------------------- #
def test_document_schema_shape(tmp_path):
    analysis = _write_analysis(tmp_path, "clip.mp4", [{"start": 0.0, "end": 4.0}])
    doc = _extractor().extract("clip.mp4", analysis_path=analysis)
    assert doc["schema_version"] == SCHEMA_VERSION
    assert set(doc) >= {"schema_version", "video", "engine", "detections"}
    det = doc["detections"][0]
    assert set(det) == {
        "id", "scene_index", "timestamp", "region", "text", "confidence", "bbox"
    }
    assert set(det["bbox"]) == {"x", "y", "w", "h"}


def test_bbox_converted_to_frame_space(tmp_path):
    # ROI at x=0.70,w=0.30; result bbox x=0.1,w=0.5 -> frame x=0.70+0.1*0.30
    analysis = _write_analysis(tmp_path, "clip.mp4", [{"start": 0.0, "end": 4.0}])
    doc = _extractor().extract("clip.mp4", analysis_path=analysis)
    bbox = doc["detections"][0]["bbox"]
    assert bbox["x"] == pytest.approx(0.73, abs=1e-6)
    assert bbox["w"] == pytest.approx(0.15, abs=1e-6)


def test_only_configured_rois_are_ocred(tmp_path):
    analysis = _write_analysis(tmp_path, "clip.mp4", [{"start": 0.0, "end": 4.0}])
    engine = FakeEngine()
    register_engine("count", lambda: engine)
    cfg = _single_roi_config(
        engine="count",
        rois=(Roi("a", 0.0, 0.0, 0.3, 0.2), Roi("b", 0.5, 0.5, 0.3, 0.2)),
        frames_per_scene=1,
    )
    HudTextExtractor(ocr_config=cfg, ffmpeg_service=FakeFFmpeg()).extract(
        "clip.mp4", analysis_path=analysis
    )
    # 1 scene x 1 frame x 2 ROIs = 2 crops, never the full frame.
    assert engine.crops_seen == 2


def test_empty_detections_serialize_as_list(tmp_path):
    class SilentEngine:
        name = "silent"
        def recognize(self, image, /):
            return []

    register_engine("silent", SilentEngine)
    analysis = _write_analysis(tmp_path, "clip.mp4", [{"start": 0.0, "end": 4.0}])
    doc = _extractor(_single_roi_config(engine="silent")).extract(
        "clip.mp4", analysis_path=analysis
    )
    assert doc["detections"] == []


def test_confidence_and_length_filtering(tmp_path):
    class LowConfEngine:
        name = "lowconf"
        def recognize(self, image, /):
            return [OcrResult("x", 0.1, {"x": 0, "y": 0, "w": 1, "h": 1})]

    register_engine("lowconf", LowConfEngine)
    analysis = _write_analysis(tmp_path, "clip.mp4", [{"start": 0.0, "end": 4.0}])
    cfg = _single_roi_config(engine="lowconf", min_confidence=0.5)
    doc = _extractor(cfg).extract("clip.mp4", analysis_path=analysis)
    assert doc["detections"] == []


# --------------------------------------------------------------------- #
# Deterministic ids
# --------------------------------------------------------------------- #
def test_ids_format_unique_and_deterministic(tmp_path):
    analysis = _write_analysis(
        tmp_path, "clip.mp4", [{"start": 0.0, "end": 4.0}, {"start": 4.0, "end": 8.0}]
    )
    doc = _extractor().extract("clip.mp4", analysis_path=analysis)
    ids = [d["id"] for d in doc["detections"]]
    assert len(ids) == len(set(ids))                 # unique
    assert ids[0] == "top_right-0001"
    assert all(i.startswith("top_right-") for i in ids)
    # Deterministic across runs
    doc2 = _extractor().extract("clip.mp4", analysis_path=analysis)
    assert [d["id"] for d in doc2["detections"]] == ids


# --------------------------------------------------------------------- #
# Scene mapping (identical to Phase 5C)
# --------------------------------------------------------------------- #
def test_scene_mapping_half_open(tmp_path):
    analysis = _write_analysis(
        tmp_path, "clip.mp4",
        [{"start": 0.0, "end": 2.0}, {"start": 2.0, "end": 6.0}],
    )
    # frames_per_scene=1 -> sample at scene midpoints (1.0 and 4.0)
    doc = _extractor(_single_roi_config(frames_per_scene=1)).extract(
        "clip.mp4", analysis_path=analysis
    )
    idx = {d["timestamp"]: d["scene_index"] for d in doc["detections"]}
    assert idx[1.0] == 0
    assert idx[4.0] == 1


def test_scene_mapping_absent_analysis_is_null():
    ff = FakeFFmpeg(max_time=25.0)
    doc = _extractor(ffmpeg=ff).extract("clip.mp4")  # no analysis path
    assert doc["detections"], "fallback sampling should still OCR frames"
    assert all(d["scene_index"] is None for d in doc["detections"])


def test_scene_mapping_video_mismatch_is_null(tmp_path):
    analysis = _write_analysis(tmp_path, "OTHER.mp4", [{"start": 0.0, "end": 4.0}])
    ff = FakeFFmpeg(max_time=25.0)
    doc = _extractor(ffmpeg=ff).extract("clip.mp4", analysis_path=analysis)
    assert all(d["scene_index"] is None for d in doc["detections"])


def test_skip_black_idle_scene(tmp_path):
    analysis = _write_analysis(
        tmp_path, "clip.mp4",
        [
            {"index": 0, "start": 0.0, "end": 2.0},
            {"index": 1, "start": 2.0, "end": 6.0},
        ],
        black=[{"start": 0.0, "end": 2.0}],
    )
    doc = _extractor(_single_roi_config(frames_per_scene=1, skip_black_idle=True)).extract(
        "clip.mp4", analysis_path=analysis
    )
    # Scene 0 fully black -> skipped; only the second scene sampled.
    times = sorted({d["timestamp"] for d in doc["detections"]})
    assert times == [4.0]
    # scene_index must be the ORIGINAL 4A index (1), not a re-based 0.
    assert all(d["scene_index"] == 1 for d in doc["detections"])


# --------------------------------------------------------------------- #
# I/O
# --------------------------------------------------------------------- #
def test_extract_to_file_never_overwrites(tmp_path):
    from config import AppConfig, PathConfig

    app_config = AppConfig(paths=PathConfig(base_dir=tmp_path))
    analysis = _write_analysis(tmp_path, "clip.mp4", [{"start": 0.0, "end": 4.0}])
    extractor = HudTextExtractor(
        app_config,
        ocr_config=_single_roi_config(),
        ffmpeg_service=FakeFFmpeg(),
    )
    first = extractor.extract_to_file("clip.mp4", analysis_path=analysis)
    second = extractor.extract_to_file("clip.mp4", analysis_path=analysis)
    assert first.exists() and second.exists()
    assert first != second
    assert first.name == "clip_ocr.json"


# --------------------------------------------------------------------- #
# Config / ROI validation
# --------------------------------------------------------------------- #
def test_config_validate_rejects_bad_values():
    with pytest.raises(OcrError):
        OcrConfig(rois=()).validate()
    with pytest.raises(OcrError):
        OcrConfig(frames_per_scene=0).validate()
    with pytest.raises(OcrError):
        OcrConfig(min_confidence=2.0).validate()


def test_roi_validation():
    with pytest.raises(OcrError):
        Roi("bad", 0.8, 0.0, 0.5, 0.2).validate()  # x+w > 1
    with pytest.raises(OcrError):
        Roi("bad", 0.0, 0.0, 0.0, 0.2).validate()   # zero width
    Roi("ok", 0.7, 0.0, 0.3, 0.15).validate()


def test_duplicate_roi_names_rejected():
    with pytest.raises(OcrError):
        OcrConfig(rois=(Roi("a", 0, 0, 0.3, 0.2), Roi("a", 0.5, 0.5, 0.3, 0.2))).validate()


def test_default_rois_are_valid():
    OcrConfig(rois=DEFAULT_ROIS).validate()


# --------------------------------------------------------------------- #
# Preprocessing math + engine registry
# --------------------------------------------------------------------- #
def test_to_grayscale_shape():
    img = np.zeros((4, 6, 3), dtype=np.uint8)
    gray = to_grayscale(img)
    assert gray.shape == (4, 6)
    assert to_grayscale(gray).shape == (4, 6)  # idempotent on gray


def test_binarize_is_zero_or_255():
    gray = np.array([[0, 128, 255]], dtype=np.uint8)
    out = binarize(gray)
    assert set(np.unique(out)).issubset({0, 255})


def test_upscale_doubles_dimensions():
    img = np.zeros((3, 5), dtype=np.uint8)
    out = upscale(img, 2.0)
    assert out.shape == (6, 10)
    assert upscale(img, 1.0).shape == (3, 5)


def test_tesseract_engine_registered_by_default():
    assert "tesseract" in available_engines()
    assert isinstance(create_engine("tesseract"), TesseractOcrEngine)


def test_unknown_engine_raises():
    with pytest.raises(OcrError):
        create_engine("does_not_exist_123")


# --------------------------------------------------------------------- #
# Config-driven tesseract_cmd (regression: no longer PATH-only)
# --------------------------------------------------------------------- #
def _install_fake_pytesseract(monkeypatch):
    """Insert a fake ``pytesseract`` module and return its inner namespace.

    Mirrors the real layout the engine touches:
    ``pytesseract.pytesseract.tesseract_cmd``. A sentinel default lets us
    assert whether the engine overwrote it or left it untouched.
    """
    import sys
    import types

    inner = types.SimpleNamespace(tesseract_cmd="__from_PATH__")
    fake = types.ModuleType("pytesseract")
    fake.pytesseract = inner
    monkeypatch.setitem(sys.modules, "pytesseract", fake)
    return inner


def test_tesseract_cmd_is_applied_when_set(monkeypatch):
    inner = _install_fake_pytesseract(monkeypatch)
    cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    engine = TesseractOcrEngine(cmd=cmd)
    # First use triggers lazy import + configuration.
    engine._lazy()
    assert inner.tesseract_cmd == cmd


def test_tesseract_cmd_none_preserves_path_behavior(monkeypatch):
    inner = _install_fake_pytesseract(monkeypatch)
    engine = TesseractOcrEngine()  # cmd defaults to None
    engine._lazy()
    # Engine must not touch tesseract_cmd: PATH discovery is preserved.
    assert inner.tesseract_cmd == "__from_PATH__"


def test_extractor_wires_config_tesseract_cmd(monkeypatch, tmp_path):
    inner = _install_fake_pytesseract(monkeypatch)
    cmd = "/opt/homebrew/bin/tesseract"
    cfg = _single_roi_config(engine="tesseract", tesseract_cmd=cmd)
    engine = create_engine(cfg.engine)
    # Simulate the extractor's wiring step, then force lazy configuration.
    if cfg.tesseract_cmd:
        engine._cmd = cfg.tesseract_cmd
    engine._lazy()
    assert inner.tesseract_cmd == cmd


# --------------------------------------------------------------------- #
# Decoupling guard
# --------------------------------------------------------------------- #
def test_ocr_modules_are_decoupled():
    import hud_text_extractor as mod_a
    import ocr_engine as mod_b
    import ocr_config as mod_c

    forbidden = {
        "highlight_scorer", "video_analyzer", "audio_analyzer", "scene_detector"
    }
    for module in (mod_a, mod_b, mod_c):
        assert forbidden.isdisjoint(set(vars(module))), (
            f"{module.__name__} must not import {forbidden & set(vars(module))}"
        )


# --------------------------------------------------------------------- #
# Optional real-Tesseract integration (auto-skips)
# --------------------------------------------------------------------- #
@pytest.mark.skipif(
    importlib.util.find_spec("pytesseract") is None
    or importlib.util.find_spec("cv2") is None,
    reason="pytesseract or OpenCV not available",
)
def test_real_tesseract_if_available():
    import shutil

    if shutil.which("tesseract") is None:
        pytest.skip("tesseract binary not installed")

    import cv2

    frame = np.full((120, 400, 3), 255, dtype=np.uint8)
    cv2.putText(frame, "HELLO", (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 2.0, (0, 0, 0), 4)

    class OneFrameFFmpeg:
        def extract_frame_at(self, video_path, timestamp):
            if timestamp > 1.0:
                raise RuntimeError("eof")
            return frame

    cfg = OcrConfig(
        engine="tesseract",
        rois=(Roi("full", 0.0, 0.0, 1.0, 1.0),),
        frames_per_scene=1,
        min_confidence=0.0,
    )
    extractor = HudTextExtractor(ocr_config=cfg, ffmpeg_service=OneFrameFFmpeg())
    doc = extractor.extract("clip.mp4")
    texts = " ".join(d["text"].upper() for d in doc["detections"])
    assert "HELLO" in texts
