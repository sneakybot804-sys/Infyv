"""Tests for immutable ProjectState and its sole mutator StateStore (Qt-free)."""
from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from gui_core.artifacts import ArtifactKind, ArtifactResolver
from gui_core.events import Event, EventBus
from gui_core.state import ProjectState, StateStore


def test_project_state_is_frozen() -> None:
    state = ProjectState()
    with pytest.raises(dataclasses.FrozenInstanceError):
        state.video_path = Path("x.mp4")  # type: ignore[misc]


def test_select_video_creates_new_snapshot_and_event(tmp_path: Path) -> None:
    bus = EventBus()
    events: list[str] = []
    bus.subscribe(Event.VideoSelected, lambda m: events.append(m.payload["video_path"]))
    store = StateStore(bus, ArtifactResolver(tmp_path))

    before = store.state
    after = store.select_video(tmp_path / "clip.mp4")

    assert before is not after
    assert before.video_path is None
    assert after.video_path == tmp_path / "clip.mp4"
    assert events == [str(tmp_path / "clip.mp4")]


def test_select_video_discovers_artifacts(tmp_path: Path) -> None:
    (tmp_path / "clip_analysis.json").write_text("{}", encoding="utf-8")
    bus = EventBus()
    store = StateStore(bus, ArtifactResolver(tmp_path))
    state = store.select_video(tmp_path / "clip.mp4")
    assert {a.kind for a in state.artifacts} == {ArtifactKind.ANALYSIS}


def test_update_setting_publishes_settings_changed(tmp_path: Path) -> None:
    bus = EventBus()
    seen: list[tuple] = []
    bus.subscribe(Event.SettingsChanged, lambda m: seen.append((m.payload["key"], m.payload["value"])))
    store = StateStore(bus, ArtifactResolver(tmp_path))
    store.update_setting("theme", "dark")
    assert seen == [("theme", "dark")]
    assert store.state.settings["theme"] == "dark"


def test_refresh_artifacts_without_video_is_noop(tmp_path: Path) -> None:
    bus = EventBus()
    store = StateStore(bus, ArtifactResolver(tmp_path))
    assert store.refresh_artifacts().artifacts == ()
