"""Tests for Timeline integration into StateStore / ApplicationFacade."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from gui_core.artifacts import ArtifactResolver
from gui_core.events import Event, EventBus
from gui_core.facade import ApplicationFacade
from gui_core.state import StateStore
from gui_core.timeline import Clip, Timeline, Track


def _timeline() -> Timeline:
    return Timeline(
        duration=30.0,
        tracks=(Track(index=0, name="V1"),),
    ).add_clip(Clip(id="c1", track_index=0, start=0.0, length=5.0))


def test_statestore_update_timeline_publishes_replayable(tmp_path):
    bus = EventBus()
    store = StateStore(bus, ArtifactResolver(tmp_path))

    received = []
    bus.subscribe(Event.TimelineChanged, lambda m: received.append(m))

    tl = _timeline()
    state = store.update_timeline(tl)
    assert state.timeline == tl
    assert store.state.timeline == tl
    assert len(received) == 1
    assert received[0].payload["timeline"]["duration"] == 30.0

    # Replayable: a late subscriber synchronizes immediately.
    late = []
    bus.subscribe(Event.TimelineChanged, lambda m: late.append(m), replay=True)
    assert len(late) == 1


def test_facade_timeline_roundtrip(tmp_path):
    config = SimpleNamespace(paths=SimpleNamespace(output_dir=tmp_path))
    facade = ApplicationFacade(config, producers=object(), registry=None)
    # registry=None triggers built-in registration; safe for a read/write test.
    assert facade.timeline() is None
    tl = _timeline()
    facade.update_timeline(tl)
    assert facade.timeline() == tl
    assert facade.project_state().timeline == tl
