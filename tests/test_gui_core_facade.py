"""End-to-end tests through ApplicationFacade only (Qt-free, fakes)."""
from __future__ import annotations

from pathlib import Path

import pytest

from gui_core import (
    ApplicationFacade,
    Event,
    PhaseGatedError,
    ProjectNotLoadedError,
    UnknownPhaseError,
)
from gui_core.registry import PhaseId


class _FakeProducer:
    def __init__(self, output, method_name):
        self._output = output
        setattr(self, method_name, lambda *a, **k: self._write())

    def _write(self):
        Path(self._output).write_text("{}", encoding="utf-8")
        return self._output


class _FakeProducers:
    def __init__(self, out: Path) -> None:
        self._out = out

    def analysis(self):
        return _FakeProducer(self._out / "clip_analysis.json", "analyze_to_file")

    def highlight(self):
        return _FakeProducer(self._out / "clip_highlight.json", "score_to_file")

    def ocr(self):
        return _FakeProducer(self._out / "clip_ocr.json", "extract_to_file")

    def audio(self):
        return _FakeProducer(self._out / "clip_audio.json", "analyze_to_file")

    def fusion(self):
        return _FakeProducer(self._out / "clip_enriched_highlight.json", "fuse_to_file")

    def decision(self):
        return _FakeProducer(self._out / "clip_edit_plan.json", "decide_to_file")

    def render(self):
        return _FakeProducer(self._out / "clip_reel.mp4", "render_files")

    def subtitles(self):
        return _FakeProducer(self._out / "clip_subtitles.json", "transcribe_to_file")


class _Paths:
    def __init__(self, out: Path) -> None:
        self.output_dir = out


class _Config:
    def __init__(self, out: Path) -> None:
        self.paths = _Paths(out)


def _facade(tmp_path: Path) -> ApplicationFacade:
    return ApplicationFacade(_Config(tmp_path), producers=_FakeProducers(tmp_path))


def test_run_phase_requires_selected_video(tmp_path: Path) -> None:
    with pytest.raises(ProjectNotLoadedError):
        _facade(tmp_path).run_phase(PhaseId.ANALYSIS.value)


def test_unknown_phase_raises(tmp_path: Path) -> None:
    facade = _facade(tmp_path)
    facade.select_video(tmp_path / "clip.mp4")
    with pytest.raises(UnknownPhaseError):
        facade.run_phase("does_not_exist")


def test_blocked_phase_raises_gated(tmp_path: Path) -> None:
    facade = _facade(tmp_path)
    facade.select_video(tmp_path / "clip.mp4")
    with pytest.raises(PhaseGatedError):
        facade.run_phase(PhaseId.FUSION.value)


def test_available_phases_reflect_gating(tmp_path: Path) -> None:
    facade = _facade(tmp_path)
    facade.select_video(tmp_path / "clip.mp4")
    ids = {p.id for p in facade.available_phases()}
    assert PhaseId.ANALYSIS.value in ids
    assert PhaseId.FUSION.value not in ids


def test_end_to_end_run_unlocks_next_phase(tmp_path: Path) -> None:
    facade = _facade(tmp_path)
    facade.select_video(tmp_path / "clip.mp4")

    result = facade.run_phase(PhaseId.ANALYSIS.value)
    assert result.success is True
    # After analysis, highlight becomes available.
    assert PhaseId.HIGHLIGHT.value in {p.id for p in facade.available_phases()}
    # Artifact state was refreshed on the facade.
    assert any(a.path.name == "clip_analysis.json" for a in facade.artifacts())


def test_events_are_observable_via_facade(tmp_path: Path) -> None:
    facade = _facade(tmp_path)
    facade.select_video(tmp_path / "clip.mp4")
    seen: list[Event] = []
    facade.subscribe(Event.PhaseCompleted, lambda m: seen.append(m.event))
    facade.run_phase(PhaseId.ANALYSIS.value)
    assert Event.PhaseCompleted in seen


def test_subscribe_replay_synchronizes_video_selection(tmp_path: Path) -> None:
    facade = _facade(tmp_path)
    facade.select_video(tmp_path / "clip.mp4")
    received: list[str] = []
    facade.subscribe(
        Event.VideoSelected,
        lambda m: received.append(m.payload["video_path"]),
        replay=True,
    )
    assert received == [str(tmp_path / "clip.mp4")]


def test_settings_round_trip(tmp_path: Path) -> None:
    facade = _facade(tmp_path)
    facade.update_settings("theme", "midnight")
    assert facade.settings()["theme"] == "midnight"
