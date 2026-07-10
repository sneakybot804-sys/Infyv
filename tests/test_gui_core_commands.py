"""Tests for stateless phase commands using fake producers (Qt-free)."""
from __future__ import annotations

from pathlib import Path

import pytest

from gui_core.artifacts import ArtifactKind, ArtifactResolver
from gui_core.commands import (
    CommandContext,
    RunAnalysisCommand,
    RunHighlightCommand,
    RunRenderCommand,
    RunSubtitleCommand,
)
from gui_core.events import Event, EventBus
from gui_core.logs import CoreLogger


class _FakeProducer:
    def __init__(self, output, recorder, method_names):
        self._output = output
        self._recorder = recorder
        for name in method_names:
            setattr(self, name, self._make(name))

    def _make(self, name):
        def _call(*args, **kwargs):
            self._recorder.append((name, args, kwargs))
            return self._output
        return _call


class _FakeProducers:
    def __init__(self, tmp_path: Path, recorder: list) -> None:
        self._tmp = tmp_path
        self._rec = recorder

    def analysis(self):
        return _FakeProducer(self._tmp / "clip_analysis.json", self._rec, ["analyze_to_file"])

    def highlight(self):
        return _FakeProducer(self._tmp / "clip_highlight.json", self._rec, ["score_to_file"])

    def ocr(self):
        return _FakeProducer(self._tmp / "clip_ocr.json", self._rec, ["extract_to_file"])

    def audio(self):
        return _FakeProducer(self._tmp / "clip_audio.json", self._rec, ["analyze_to_file"])

    def fusion(self):
        return _FakeProducer(self._tmp / "clip_enriched_highlight.json", self._rec, ["fuse_to_file"])

    def decision(self):
        return _FakeProducer(self._tmp / "clip_edit_plan.json", self._rec, ["decide_to_file"])

    def render(self):
        return _FakeProducer(self._tmp / "clip_reel.mp4", self._rec, ["render_files"])

    def subtitles(self):
        srt = self._tmp / "clip.srt"
        return _FakeProducer([self._tmp / "clip_subtitles.json", srt], self._rec, ["transcribe_to_file"])


def _context(tmp_path: Path, recorder: list) -> CommandContext:
    bus = EventBus()
    return CommandContext(
        video_path=tmp_path / "clip.mp4",
        output_dir=tmp_path,
        producers=_FakeProducers(tmp_path, recorder),
        artifacts=ArtifactResolver(tmp_path),
        bus=bus,
        logger=CoreLogger("test", bus),
    )


def test_analysis_command_calls_producer(tmp_path: Path) -> None:
    rec: list = []
    result = RunAnalysisCommand().execute(_context(tmp_path, rec))
    assert result.success is True
    assert rec[0][0] == "analyze_to_file"
    assert result.outputs == [tmp_path / "clip_analysis.json"]


def test_highlight_command_passes_analysis_path(tmp_path: Path) -> None:
    rec: list = []
    RunHighlightCommand().execute(_context(tmp_path, rec))
    # score_to_file receives the analysis path derived from the video stem.
    name, args, _ = rec[0]
    assert name == "score_to_file"
    assert args[0] == tmp_path / "clip_analysis.json"


def test_render_emits_render_finished(tmp_path: Path) -> None:
    rec: list = []
    ctx = _context(tmp_path, rec)
    seen: list[Event] = []
    ctx.bus.subscribe(Event.RenderFinished, lambda m: seen.append(m.event))
    RunRenderCommand().execute(ctx)
    assert Event.RenderFinished in seen


def test_subtitles_returns_multiple_outputs(tmp_path: Path) -> None:
    rec: list = []
    result = RunSubtitleCommand().execute(_context(tmp_path, rec))
    assert len(result.outputs) == 2


def test_event_order_started_then_completed(tmp_path: Path) -> None:
    rec: list = []
    ctx = _context(tmp_path, rec)
    order: list[Event] = []
    for ev in (Event.PhaseStarted, Event.ArtifactCreated, Event.PhaseCompleted):
        ctx.bus.subscribe(ev, lambda m: order.append(m.event))
    RunAnalysisCommand().execute(ctx)
    assert order[0] == Event.PhaseStarted
    assert order[-1] == Event.PhaseCompleted
    assert Event.ArtifactCreated in order


def test_producer_error_is_normalized(tmp_path: Path) -> None:
    rec: list = []
    ctx = _context(tmp_path, rec)

    class _Boom(_FakeProducers):
        def analysis(self):
            producer = super().analysis()
            def _raise(*a, **k):
                raise RuntimeError("backend exploded")
            producer.analyze_to_file = _raise
            return producer

    ctx = CommandContext(
        video_path=tmp_path / "clip.mp4",
        output_dir=tmp_path,
        producers=_Boom(tmp_path, rec),
        artifacts=ArtifactResolver(tmp_path),
        bus=ctx.bus,
        logger=ctx.logger,
    )
    result = RunAnalysisCommand().execute(ctx)
    assert result.success is False
    assert "backend exploded" in result.message


def test_missing_video_is_reported_as_failure(tmp_path: Path) -> None:
    rec: list = []
    bus = EventBus()
    ctx = CommandContext(
        video_path=None,
        output_dir=tmp_path,
        producers=_FakeProducers(tmp_path, rec),
        artifacts=ArtifactResolver(tmp_path),
        bus=bus,
        logger=CoreLogger("test", bus),
    )
    result = RunAnalysisCommand().execute(ctx)
    assert result.success is False
