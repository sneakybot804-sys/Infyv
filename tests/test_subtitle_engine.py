"""Unit tests for the Phase 7 Subtitle Engine.

Dependency-light: a fake FFmpegService (returns a dummy audio path) and a
FakeTranscriptBackend (deterministic transcript, tests only) exercise the
whole engine without FFmpeg or any ASR library. The production default
PlaceholderTranscriptBackend returns an empty transcript and is checked too.
"""
from __future__ import annotations

import json

import pytest

from subtitle_backend import (
    TranscriptResult,
    TranscriptSegment,
    Word,
    available_backends,
    create_backend,
)
from subtitle_config import SubtitleConfig, SubtitleError
from subtitle_engine import SCHEMA_VERSION, SubtitleEngine, _srt_timestamp


# --------------------------------------------------------------------- #
# Fakes
# --------------------------------------------------------------------- #
class FakeFFmpeg:
    """Fake FFmpegService: records extract_audio calls, returns a dummy path."""

    def __init__(self, audio_path="C:/tmp/clip.mp3"):
        self._audio = audio_path
        self.calls: list[str] = []

    def extract_audio(self, video_path, output_name=None):
        self.calls.append(str(video_path))
        return self._audio


class FakeBackend:
    """Deterministic transcript backend for tests (not registered)."""

    name = "fake"

    def __init__(self, result: TranscriptResult):
        self._result = result
        self.calls = 0

    def transcribe(self, audio_path, /, *, language, word_timestamps):
        self.calls += 1
        return self._result


def _seg(text, start, end, words=None):
    return TranscriptSegment(text=text, start=start, end=end, words=words or [])


def _w(text, start, end, conf=1.0):
    return Word(text=text, start=start, end=end, confidence=conf)


def _engine(tmp_path, result, cfg=None):
    from config import AppConfig, PathConfig

    app_config = AppConfig(paths=PathConfig(base_dir=tmp_path))
    app_config.paths.output_dir.mkdir(parents=True, exist_ok=True)
    return SubtitleEngine(
        app_config,
        subtitle_config=cfg or SubtitleConfig(),
        ffmpeg_service=FakeFFmpeg(),
        backend=FakeBackend(result),
    ), app_config


# --------------------------------------------------------------------- #
# Default placeholder backend -> empty transcript -> cues: []
# --------------------------------------------------------------------- #
def test_placeholder_backend_is_registered_and_empty(tmp_path):
    assert "placeholder" in available_backends()
    backend = create_backend("placeholder")
    result = backend.transcribe("x.mp3", language=None, word_timestamps=True)
    assert result.segments == []


def test_default_engine_produces_no_cues(tmp_path):
    from config import AppConfig, PathConfig

    app_config = AppConfig(paths=PathConfig(base_dir=tmp_path))
    engine = SubtitleEngine(app_config, ffmpeg_service=FakeFFmpeg())  # default backend
    doc = engine.transcribe("C:/videos/clip.mp4")
    assert doc.cues == []
    assert doc.to_dict()["cues"] == []
    assert doc.to_srt() == ""


def test_unknown_backend_raises():
    with pytest.raises(SubtitleError):
        create_backend("does_not_exist_123")


# --------------------------------------------------------------------- #
# Cue grouping (gap merge) + duration clamping
# --------------------------------------------------------------------- #
def test_segments_within_gap_merge(tmp_path):
    result = TranscriptResult("en", [
        _seg("hello", 1.0, 2.0),
        _seg("world", 2.2, 3.0),  # gap 0.2 <= 0.3 -> merge
    ])
    cfg = SubtitleConfig(max_gap_merge_seconds=0.3, min_cue_seconds=0.1)
    engine, _ = _engine(tmp_path, result, cfg)
    doc = engine.transcribe("clip.mp4")
    assert len(doc.cues) == 1
    assert doc.cues[0].text == "hello world"
    assert doc.cues[0].start == 1.0 and doc.cues[0].end == 3.0


def test_segments_beyond_gap_do_not_merge(tmp_path):
    result = TranscriptResult("en", [
        _seg("hello", 1.0, 2.0),
        _seg("world", 5.0, 6.0),  # gap 3.0 > 0.3 -> separate
    ])
    cfg = SubtitleConfig(max_gap_merge_seconds=0.3, min_cue_seconds=0.1)
    engine, _ = _engine(tmp_path, result, cfg)
    doc = engine.transcribe("clip.mp4")
    assert len(doc.cues) == 2


def test_min_cue_duration_is_padded(tmp_path):
    result = TranscriptResult("en", [_seg("hi", 1.0, 1.1)])
    cfg = SubtitleConfig(min_cue_seconds=0.8, max_gap_merge_seconds=0.0)
    engine, _ = _engine(tmp_path, result, cfg)
    doc = engine.transcribe("clip.mp4")
    assert doc.cues[0].end == pytest.approx(1.8)  # 1.0 + 0.8


def test_max_cue_duration_is_capped(tmp_path):
    result = TranscriptResult("en", [_seg("long", 0.0, 30.0)])
    cfg = SubtitleConfig(max_cue_seconds=6.0, min_cue_seconds=0.5)
    engine, _ = _engine(tmp_path, result, cfg)
    doc = engine.transcribe("clip.mp4")
    assert doc.cues[0].end == pytest.approx(6.0)


# --------------------------------------------------------------------- #
# Line wrapping
# --------------------------------------------------------------------- #
def test_text_wraps_to_max_line_chars(tmp_path):
    result = TranscriptResult("en", [_seg("aaaa bbbb cccc", 0.0, 4.0)])
    cfg = SubtitleConfig(max_line_chars=9, max_lines_per_cue=2,
                         max_gap_merge_seconds=0.0)
    engine, _ = _engine(tmp_path, result, cfg)
    doc = engine.transcribe("clip.mp4")
    # "aaaa bbbb" (9 chars) on line 1, "cccc" on line 2.
    assert doc.cues[0].text == "aaaa bbbb\ncccc"


def test_lines_capped_at_max_lines_per_cue(tmp_path):
    result = TranscriptResult("en", [_seg("aa bb cc dd", 0.0, 4.0)])
    cfg = SubtitleConfig(max_line_chars=2, max_lines_per_cue=1,
                         max_gap_merge_seconds=0.0)
    engine, _ = _engine(tmp_path, result, cfg)
    doc = engine.transcribe("clip.mp4")
    assert doc.cues[0].text == "aa"  # only the first line kept


# --------------------------------------------------------------------- #
# Word timestamps on/off + deterministic ids
# --------------------------------------------------------------------- #
def test_word_timestamps_included_when_enabled(tmp_path):
    result = TranscriptResult("en", [
        _seg("go now", 1.0, 2.0, words=[_w("go", 1.0, 1.4), _w("now", 1.5, 2.0)]),
    ])
    cfg = SubtitleConfig(word_timestamps=True, min_cue_seconds=0.1)
    engine, _ = _engine(tmp_path, result, cfg)
    doc = engine.transcribe("clip.mp4")
    words = doc.cues[0].words
    assert [w["text"] for w in words] == ["go", "now"]
    assert set(words[0]) == {"text", "start", "end", "confidence"}


def test_word_timestamps_omitted_when_disabled(tmp_path):
    result = TranscriptResult("en", [
        _seg("go now", 1.0, 2.0, words=[_w("go", 1.0, 1.4)]),
    ])
    cfg = SubtitleConfig(word_timestamps=False, min_cue_seconds=0.1)
    engine, _ = _engine(tmp_path, result, cfg)
    doc = engine.transcribe("clip.mp4")
    assert doc.cues[0].words == []


def test_cue_ids_sequential_and_deterministic(tmp_path):
    result = TranscriptResult("en", [
        _seg("one", 0.0, 1.0), _seg("two", 5.0, 6.0), _seg("three", 10.0, 11.0),
    ])
    cfg = SubtitleConfig(max_gap_merge_seconds=0.0, min_cue_seconds=0.1)
    engine, _ = _engine(tmp_path, result, cfg)
    a = engine.transcribe("clip.mp4")
    ids = [c.id for c in a.cues]
    assert ids == ["cue-0001", "cue-0002", "cue-0003"]


# --------------------------------------------------------------------- #
# SRT formatting
# --------------------------------------------------------------------- #
def test_srt_timestamp_format():
    assert _srt_timestamp(0.0) == "00:00:00,000"
    assert _srt_timestamp(3.2) == "00:00:03,200"
    assert _srt_timestamp(3661.5) == "01:01:01,500"


def test_srt_document_structure(tmp_path):
    result = TranscriptResult("en", [
        _seg("hello", 1.0, 2.0), _seg("world", 5.0, 6.0),
    ])
    cfg = SubtitleConfig(max_gap_merge_seconds=0.0, min_cue_seconds=0.1)
    engine, _ = _engine(tmp_path, result, cfg)
    srt = engine.transcribe("clip.mp4").to_srt()
    assert "1\n00:00:01,000 --> 00:00:02,000\nhello" in srt
    assert "2\n00:00:05,000 --> 00:00:06,000\nworld" in srt


# --------------------------------------------------------------------- #
# Schema shape
# --------------------------------------------------------------------- #
def test_document_schema_shape(tmp_path):
    result = TranscriptResult("en", [_seg("hi there", 1.0, 2.0)])
    engine, _ = _engine(tmp_path, result, SubtitleConfig(min_cue_seconds=0.1))
    doc = engine.transcribe("C:/videos/clip.mp4").to_dict()
    assert doc["schema_version"] == SCHEMA_VERSION
    assert set(doc) == {"schema_version", "video", "language", "backend", "cues"}
    cue = doc["cues"][0]
    assert set(cue) == {"id", "start", "end", "text", "words"}
    assert json.loads(engine.transcribe("C:/videos/clip.mp4").to_json())[
        "schema_version"] == SCHEMA_VERSION


# --------------------------------------------------------------------- #
# File IO: emit toggles + never overwrite
# --------------------------------------------------------------------- #
def test_transcribe_to_file_writes_json_and_srt(tmp_path):
    result = TranscriptResult("en", [_seg("hi", 1.0, 2.0)])
    engine, app_config = _engine(tmp_path, result,
                                 SubtitleConfig(min_cue_seconds=0.1))
    outputs = engine.transcribe_to_file("C:/videos/clip.mp4")
    names = sorted(p.name for p in outputs)
    assert names == ["clip.srt", "clip_subtitles.json"]
    assert all(p.exists() for p in outputs)


def test_emit_toggles_respected(tmp_path):
    result = TranscriptResult("en", [_seg("hi", 1.0, 2.0)])
    cfg = SubtitleConfig(emit_json=True, emit_srt=False, min_cue_seconds=0.1)
    engine, _ = _engine(tmp_path, result, cfg)
    outputs = engine.transcribe_to_file("C:/videos/clip.mp4")
    assert [p.name for p in outputs] == ["clip_subtitles.json"]


def test_transcribe_to_file_never_overwrites(tmp_path):
    result = TranscriptResult("en", [_seg("hi", 1.0, 2.0)])
    engine, app_config = _engine(tmp_path, result,
                                 SubtitleConfig(emit_srt=False, min_cue_seconds=0.1))
    out_dir = app_config.paths.output_dir
    (out_dir / "clip_subtitles.json").write_text("existing", encoding="utf-8")
    outputs = engine.transcribe_to_file("C:/videos/clip.mp4")
    assert outputs[0].name != "clip_subtitles.json"
    assert (out_dir / "clip_subtitles.json").read_text(encoding="utf-8") == "existing"


# --------------------------------------------------------------------- #
# Config validation
# --------------------------------------------------------------------- #
def test_config_validate_rejects_bad_values():
    with pytest.raises(SubtitleError):
        SubtitleConfig(backend="").validate()
    with pytest.raises(SubtitleError):
        SubtitleConfig(max_line_chars=0).validate()
    with pytest.raises(SubtitleError):
        SubtitleConfig(min_cue_seconds=5.0, max_cue_seconds=1.0).validate()
    with pytest.raises(SubtitleError):
        SubtitleConfig(emit_json=False, emit_srt=False).validate()


def test_engine_construction_validates_config():
    with pytest.raises(SubtitleError):
        SubtitleEngine(subtitle_config=SubtitleConfig(max_line_chars=0),
                       ffmpeg_service=FakeFFmpeg())


# --------------------------------------------------------------------- #
# Decoupling guard
# --------------------------------------------------------------------- #
def test_subtitle_modules_are_decoupled_from_producers():
    import subtitle_engine as mod_a
    import subtitle_backend as mod_b
    import subtitle_config as mod_c

    forbidden = {
        "video_editor", "decision_agent", "signal_fusion", "highlight_scorer",
        "video_analyzer", "audio_analyzer", "hud_text_extractor",
        "ocr_engine", "scene_detector",
    }
    for module in (mod_a, mod_b, mod_c):
        src_names = set(vars(module))
        assert forbidden.isdisjoint(src_names), (
            f"{module.__name__} must not import {forbidden & src_names}"
        )
