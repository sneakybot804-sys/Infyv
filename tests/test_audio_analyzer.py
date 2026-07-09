"""Unit tests for the Phase 5C Audio Analyzer.

Dependency-light by default: a fake backend and a fake FFmpeg service let the
full orchestration be exercised without real audio libraries or FFmpeg. A
single real-FFmpeg integration test is included but auto-skips when FFmpeg /
the backend is unavailable.
"""
from __future__ import annotations

import importlib
import json

import numpy as np
import pytest

from audio_analyzer import AudioAnalyzer, SCHEMA_VERSION
from audio_backend import (
    AudioBlock,
    ExcitementResult,
    NumpyAudioBackend,
    RawEvent,
    RawExcitementPeak,
    TrackFeatures,
    available_backends,
    create_backend,
    register_backend,
)
from audio_config import (
    AudioAnalyzerError,
    AudioConfig,
    TrackRole,
    TrackSpec,
)


# --------------------------------------------------------------------- #
# Test doubles
# --------------------------------------------------------------------- #
class FakeFFmpeg:
    """Fake FFmpeg service: canned stream count and PCM blocks per stream."""

    def __init__(self, stream_signals):
        # stream_signals: dict[int, np.ndarray] mono float32 per stream index
        self._signals = stream_signals

    def count_audio_streams(self, media_path):
        return len(self._signals)

    def stream_pcm_blocks(self, media_path, *, sample_rate, stream_index, block_seconds):
        if stream_index not in self._signals:
            raise RuntimeError(f"no such stream {stream_index}")
        signal = self._signals[stream_index]
        block = max(int(round(block_seconds * sample_rate)), 1)
        for pos in range(0, signal.size, block):
            yield signal[pos : pos + block].astype(np.float32)


class FakeBackend:
    """Fake backend returning canned features/events, ignoring the signal."""

    name = "fake"

    def __init__(self):
        self._opts = None
        self._blocks = 0

    def start_track(self, sample_rate, options, /):
        self._opts = options
        self._blocks = 0

    def process_block(self, block, /):
        self._blocks += 1

    def finalize(self):
        events = [
            RawEvent(start=1.0, end=1.4, type="onset", energy=0.8, confidence=0.7),
            RawEvent(start=0.5, end=0.9, type="onset", energy=0.6, confidence=0.6),
            RawEvent(start=2.0, end=2.5, type="energy_peak", energy=0.9, confidence=0.9),
        ]
        excitement = None
        if self._opts is not None and self._opts.compute_excitement:
            excitement = ExcitementResult(
                hop_seconds=0.5,
                score_series=[0.1, 0.7, 0.9],
                peaks=[RawExcitementPeak(start=2.0, end=2.5, score=0.9)],
            )
        return TrackFeatures(
            hop_seconds=0.5,
            rms_series=[0.1, 0.5, 0.9],
            avg_rms=0.5,
            peak_rms=0.9,
            events=events,
            excitement=excitement,
        )


register_backend("fake", FakeBackend)


def _analyzer(stream_signals, audio_config=None):
    cfg = audio_config or AudioConfig(backend="fake")
    return AudioAnalyzer(
        audio_config=cfg,
        ffmpeg_service=FakeFFmpeg(stream_signals),
    )


def _sig(seconds=3.0, sr=16000):
    return np.zeros(int(seconds * sr), dtype=np.float32)


# --------------------------------------------------------------------- #
# Track detection priority (section 3.1)
# --------------------------------------------------------------------- #
def test_config_trackspec_wins():
    cfg = AudioConfig(
        backend="fake",
        tracks=(TrackSpec("mic", TrackRole.COMMENTARY, "video", 0),),
    )
    doc = _analyzer({0: _sig()}, cfg).analyze("clip.mp4")
    assert [t["name"] for t in doc["tracks"]] == ["mic"]
    assert doc["tracks"][0]["role"] == "commentary"


def test_two_streams_map_gameplay_commentary():
    doc = _analyzer({0: _sig(), 1: _sig()}).analyze("clip.mp4")
    roles = {t["name"]: t["role"] for t in doc["tracks"]}
    assert roles == {"gameplay": "gameplay", "commentary": "commentary"}


def test_three_plus_streams_ignore_extras():
    doc = _analyzer({0: _sig(), 1: _sig(), 2: _sig()}).analyze("clip.mp4")
    names = [t["name"] for t in doc["tracks"]]
    assert names == ["gameplay", "commentary"]
    assert all(t["stream_index"] in (0, 1) for t in doc["tracks"])


def test_one_stream_maps_gameplay_only():
    doc = _analyzer({0: _sig()}).analyze("clip.mp4")
    assert [t["name"] for t in doc["tracks"]] == ["gameplay"]
    assert doc["tracks"][0]["excitement"] is None


def test_no_audio_fails_loud():
    with pytest.raises(AudioAnalyzerError):
        _analyzer({}).analyze("clip.mp4")


# --------------------------------------------------------------------- #
# Excitement is role-gated
# --------------------------------------------------------------------- #
def test_excitement_only_for_commentary():
    doc = _analyzer({0: _sig(), 1: _sig()}).analyze("clip.mp4")
    gameplay = next(t for t in doc["tracks"] if t["name"] == "gameplay")
    commentary = next(t for t in doc["tracks"] if t["name"] == "commentary")
    assert gameplay["excitement"] is None
    assert commentary["excitement"] is not None
    assert "peaks" in commentary["excitement"]


# --------------------------------------------------------------------- #
# Deterministic event ids (section 5.1)
# --------------------------------------------------------------------- #
def test_event_ids_unique_format_and_ordered():
    doc = _analyzer({0: _sig()}).analyze("clip.mp4")
    events = doc["tracks"][0]["events"]
    ids = [e["id"] for e in events]
    assert len(ids) == len(set(ids))  # unique
    # onsets numbered in chronological order
    onsets = [e for e in events if e["type"] == "onset"]
    assert onsets[0]["id"] == "gameplay-onset-0001"
    assert onsets[0]["start"] <= onsets[1]["start"]
    assert onsets[1]["id"] == "gameplay-onset-0002"


def test_event_and_peak_ids_never_collide():
    doc = _analyzer({1: _sig()}, AudioConfig(
        backend="fake",
        tracks=(TrackSpec("commentary", TrackRole.COMMENTARY, "video", 1),),
    )).analyze("clip.mp4")
    track = doc["tracks"][0]
    event_ids = {e["id"] for e in track["events"]}
    peak_ids = {p["id"] for p in track["excitement"]["peaks"]}
    assert event_ids.isdisjoint(peak_ids)
    assert all("excitement_peak" in pid for pid in peak_ids)


def test_ids_deterministic_across_runs():
    a = _analyzer({0: _sig()}).analyze("clip.mp4")
    b = _analyzer({0: _sig()}).analyze("clip.mp4")
    assert [e["id"] for e in a["tracks"][0]["events"]] == [
        e["id"] for e in b["tracks"][0]["events"]
    ]


# --------------------------------------------------------------------- #
# Event vs excitement-peak field contract (section 5.0)
# --------------------------------------------------------------------- #
def test_event_and_peak_field_contract():
    doc = _analyzer({1: _sig()}, AudioConfig(
        backend="fake",
        tracks=(TrackSpec("commentary", TrackRole.COMMENTARY, "video", 1),),
    )).analyze("clip.mp4")
    track = doc["tracks"][0]
    event = track["events"][0]
    assert set(event) == {"id", "start", "end", "type", "energy", "confidence", "scene_index"}
    peak = track["excitement"]["peaks"][0]
    assert set(peak) == {"id", "start", "end", "score", "scene_index"}
    assert "score" not in event and "energy" not in peak


# --------------------------------------------------------------------- #
# Scene mapping (section 8.3)
# --------------------------------------------------------------------- #
def _write_analysis(tmp_path, video_name, scenes):
    path = tmp_path / "clip_analysis.json"
    path.write_text(json.dumps({
        "schema_version": "4a.1",
        "video": f"C:/videos/{video_name}",
        "scenes": scenes,
    }), encoding="utf-8")
    return path


def test_scene_mapping_half_open(tmp_path):
    analysis = _write_analysis(tmp_path, "clip.mp4", [
        {"index": 0, "start": 0.0, "end": 1.0},
        {"index": 1, "start": 1.0, "end": 3.0},
    ])
    doc = _analyzer({0: _sig()}).analyze("clip.mp4", analysis_path=analysis)
    by_start = {e["start"]: e["scene_index"] for e in doc["tracks"][0]["events"]}
    assert by_start[0.5] == 0     # inside scene 0
    assert by_start[1.0] == 1     # boundary -> later scene
    assert by_start[2.0] == 1


def test_scene_mapping_absent_analysis_is_null():
    doc = _analyzer({0: _sig()}).analyze("clip.mp4")
    assert all(e["scene_index"] is None for e in doc["tracks"][0]["events"])


def test_scene_mapping_video_mismatch_is_null(tmp_path):
    analysis = _write_analysis(tmp_path, "OTHER.mp4", [
        {"index": 0, "start": 0.0, "end": 3.0},
    ])
    doc = _analyzer({0: _sig()}).analyze("clip.mp4", analysis_path=analysis)
    assert all(e["scene_index"] is None for e in doc["tracks"][0]["events"])


def test_scene_mapping_empty_scene_list_is_null(tmp_path):
    analysis = _write_analysis(tmp_path, "clip.mp4", [])
    doc = _analyzer({0: _sig()}).analyze("clip.mp4", analysis_path=analysis)
    assert all(e["scene_index"] is None for e in doc["tracks"][0]["events"])


# --------------------------------------------------------------------- #
# Failure handling (section 8.5)
# --------------------------------------------------------------------- #
def test_partial_track_failure_emits_other_track():
    # Stream 1 raises inside streaming; stream 0 succeeds.
    class PartialFFmpeg(FakeFFmpeg):
        def stream_pcm_blocks(self, media_path, *, sample_rate, stream_index, block_seconds):
            if stream_index == 1:
                raise RuntimeError("corrupt commentary stream")
            yield from super().stream_pcm_blocks(
                media_path, sample_rate=sample_rate,
                stream_index=stream_index, block_seconds=block_seconds,
            )

    analyzer = AudioAnalyzer(
        audio_config=AudioConfig(backend="fake"),
        ffmpeg_service=PartialFFmpeg({0: _sig(), 1: _sig()}),
    )
    doc = analyzer.analyze("clip.mp4")
    assert [t["name"] for t in doc["tracks"]] == ["gameplay"]


def test_zero_length_stream_is_skipped_then_fails_when_none():
    # Single empty stream -> no analyzable track -> error.
    with pytest.raises(AudioAnalyzerError):
        _analyzer({0: np.zeros(0, dtype=np.float32)}).analyze("clip.mp4")


def test_max_track_seconds_guard():
    cfg = AudioConfig(backend="fake", max_track_seconds=0.1, block_seconds=0.05)
    with pytest.raises(AudioAnalyzerError):
        _analyzer({0: _sig(seconds=1.0)}, cfg).analyze("clip.mp4")


# --------------------------------------------------------------------- #
# Schema + I/O
# --------------------------------------------------------------------- #
def test_document_schema_shape():
    doc = _analyzer({0: _sig()}).analyze("clip.mp4")
    assert doc["schema_version"] == SCHEMA_VERSION
    assert set(doc) >= {"schema_version", "video", "backend", "tracks"}
    track = doc["tracks"][0]
    assert set(track) >= {
        "name", "role", "source", "stream_index",
        "source_sample_rate", "analysis_sample_rate", "duration",
        "features", "events", "excitement",
    }
    assert "sample_rate" not in track  # only the disambiguated pair exists
    assert track["analysis_sample_rate"] == 16000


def test_empty_events_serialize_as_list():
    class SilentBackend(FakeBackend):
        name = "silent"
        def finalize(self):
            return TrackFeatures(0.5, [], 0.0, 0.0, events=[], excitement=None)

    register_backend("silent", SilentBackend)
    doc = _analyzer({0: _sig()}, AudioConfig(backend="silent")).analyze("clip.mp4")
    assert doc["tracks"][0]["events"] == []


def test_analyze_to_file_never_overwrites(tmp_path):
    from config import AppConfig, PathConfig

    app_config = AppConfig(paths=PathConfig(base_dir=tmp_path))
    analyzer = AudioAnalyzer(
        app_config,
        audio_config=AudioConfig(backend="fake"),
        ffmpeg_service=FakeFFmpeg({0: _sig()}),
    )
    first = analyzer.analyze_to_file("clip.mp4")
    second = analyzer.analyze_to_file("clip.mp4")
    assert first.exists() and second.exists()
    assert first != second
    assert first.name == "clip_audio.json"


# --------------------------------------------------------------------- #
# Config validation (no magic numbers)
# --------------------------------------------------------------------- #
def test_config_validate_rejects_bad_values():
    with pytest.raises(AudioAnalyzerError):
        AudioConfig(target_sample_rate=0).validate()
    with pytest.raises(AudioAnalyzerError):
        AudioConfig(block_overlap_seconds=99.0, block_seconds=1.0).validate()
    with pytest.raises(AudioAnalyzerError):
        AudioConfig(onset_threshold=5.0).validate()


def test_config_validate_rejects_duplicate_track_names():
    with pytest.raises(AudioAnalyzerError):
        AudioConfig(tracks=(
            TrackSpec("dup", TrackRole.GAMEPLAY),
            TrackSpec("dup", TrackRole.COMMENTARY, stream_index=1),
        )).validate()


# --------------------------------------------------------------------- #
# NumpyAudioBackend feature math + streaming equivalence
# --------------------------------------------------------------------- #
def _feed(backend, signal, sr, block_seconds, opts):
    backend.start_track(sr, opts)
    block = max(int(block_seconds * sr), 1)
    total = 0
    for pos in range(0, signal.size, block):
        chunk = signal[pos : pos + block]
        backend.process_block(AudioBlock(chunk.astype(np.float32), total / sr))
        total += chunk.size
    return backend.finalize()


def _burst_signal(sr=16000):
    sig = np.zeros(3 * sr, dtype=np.float32)
    t = np.arange(sr) / sr
    sig[sr : 2 * sr] = 0.8 * np.sin(2 * np.pi * 220 * t).astype(np.float32)
    return sig


def test_numpy_backend_detects_loud_burst():
    cfg = AudioConfig(backend="numpy")
    opts = cfg.feature_options(compute_excitement=False)
    feats = _feed(NumpyAudioBackend(), _burst_signal(), 16000, 30.0, opts)
    assert 0.0 <= feats.peak_rms <= 1.0
    assert feats.peak_rms == pytest.approx(1.0, abs=1e-6)
    assert any(e.type == "onset" for e in feats.events)


def test_numpy_backend_streaming_equivalence():
    cfg = AudioConfig(backend="numpy")
    opts = cfg.feature_options(compute_excitement=False)
    signal = _burst_signal()
    single = _feed(NumpyAudioBackend(), signal, 16000, 30.0, opts)
    chunked = _feed(NumpyAudioBackend(), signal, 16000, 0.3, opts)
    assert single.rms_series == chunked.rms_series
    assert [(e.type, e.start) for e in single.events] == [
        (e.type, e.start) for e in chunked.events
    ]


def test_numpy_backend_silence_has_no_events():
    cfg = AudioConfig(backend="numpy")
    opts = cfg.feature_options(compute_excitement=False)
    feats = _feed(NumpyAudioBackend(), np.zeros(16000, dtype=np.float32), 16000, 30.0, opts)
    assert feats.events == []
    assert feats.peak_rms == 0.0


def test_numpy_backend_registered_by_default():
    assert "numpy" in available_backends()
    assert isinstance(create_backend("numpy"), NumpyAudioBackend)


# --------------------------------------------------------------------- #
# Decoupling guard: audio never imports scorer/analyzer/OCR
# --------------------------------------------------------------------- #
def test_audio_modules_are_decoupled():
    import audio_analyzer as mod_a
    import audio_backend as mod_b
    import audio_config as mod_c

    forbidden = {"highlight_scorer", "video_analyzer", "scene_detector"}
    for module in (mod_a, mod_b, mod_c):
        src_names = set(vars(module))
        assert forbidden.isdisjoint(src_names), (
            f"{module.__name__} must not import {forbidden & src_names}"
        )


# --------------------------------------------------------------------- #
# Optional real-FFmpeg integration (auto-skips)
# --------------------------------------------------------------------- #
@pytest.mark.skipif(
    importlib.util.find_spec("ffmpeg") is None,
    reason="ffmpeg-python not available",
)
def test_real_ffmpeg_stream_if_available(tmp_path):
    import shutil

    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg binary not installed")

    import ffmpeg as ffmpeg_lib
    from ffmpeg_service import FFmpegService

    # Generate a 2s mono tone WAV via ffmpeg's lavfi source.
    wav = tmp_path / "tone.wav"
    (
        ffmpeg_lib
        .input("sine=frequency=440:duration=2", f="lavfi")
        .output(str(wav), ac=1, ar=16000)
        .overwrite_output()
        .run(quiet=True)
    )

    analyzer = AudioAnalyzer(audio_config=AudioConfig(backend="numpy"))
    analyzer._ffmpeg = FFmpegService()
    doc = analyzer.analyze(str(wav))
    assert doc["tracks"][0]["analysis_sample_rate"] == 16000
    assert doc["tracks"][0]["duration"] > 1.5
