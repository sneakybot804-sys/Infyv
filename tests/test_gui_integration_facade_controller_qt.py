"""Offscreen Qt tests for the Phase 8F read-only FacadeController.

Constructs a real ApplicationFacade from a minimal fake app_config with an
injected fake producer bundle, wraps it in a FacadeController, and asserts the
frozen read-only contract: it subscribes only to the three persistent state
events (with replay), exposes read-only accessors, records latest snapshots,
and has no write/execution passthroughs. Skipped without PySide6; runs under
the offscreen platform.
"""
from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from gui.integration import FacadeController  # noqa: E402
from gui.integration import facade_controller as fc_module  # noqa: E402
from gui_core import ApplicationFacade, Event  # noqa: E402
from gui_core.registry import PluginRegistry, register_builtins  # noqa: E402


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance() or QApplication([])
    yield application


def _make_config(tmp_path: Path) -> SimpleNamespace:
    """Return a minimal app_config exposing only paths.output_dir."""
    return SimpleNamespace(paths=SimpleNamespace(output_dir=tmp_path))


def _make_facade(tmp_path: Path) -> ApplicationFacade:
    """Build a real facade with a fake producer bundle and builtins registry."""
    registry = PluginRegistry()
    register_builtins(registry)
    producers = object()  # never used: no phase is executed in read-only 8F
    return ApplicationFacade(_make_config(tmp_path), producers=producers, registry=registry)


@pytest.fixture
def facade(app, tmp_path):
    return _make_facade(tmp_path)


def test_construct_not_running(facade):
    controller = FacadeController(facade)
    assert controller.is_running() is False


def test_start_sets_running_and_stop_clears(facade):
    controller = FacadeController(facade)
    controller.start()
    assert controller.is_running() is True
    controller.stop()
    assert controller.is_running() is False


def test_start_is_idempotent(facade):
    controller = FacadeController(facade)
    controller.start()
    controller.start()  # must not raise or duplicate
    assert controller.is_running() is True
    controller.stop()


def test_stop_is_idempotent_before_start(facade):
    controller = FacadeController(facade)
    controller.stop()  # safe before start
    assert controller.is_running() is False


def test_read_only_accessors(facade):
    controller = FacadeController(facade)
    state = controller.project_state()
    assert state.video_path is None
    assert controller.settings() == {}
    assert controller.artifacts() == []
    # No video selected -> no runnable phases.
    assert controller.available_phases() == []
    assert controller.logs() == []


def test_latest_snapshots_start_none(facade):
    controller = FacadeController(facade)
    assert controller.latest_project_loaded() is None
    assert controller.latest_video_selected() is None
    assert controller.latest_settings_changed() is None


def test_replay_populates_latest_settings(app, tmp_path):
    # Seed a cached persistent event on the facade's bus *before* the
    # controller starts, so replay=True delivers it immediately on start().
    facade = _make_facade(tmp_path)
    facade.update_settings("quality", "1080p")  # publishes SettingsChanged
    controller = FacadeController(facade)
    controller.start()
    message = controller.latest_settings_changed()
    assert message is not None
    assert message.event is Event.SettingsChanged
    assert message.payload.get("key") == "quality"
    controller.stop()


def test_stop_stops_updates(app, tmp_path):
    facade = _make_facade(tmp_path)
    controller = FacadeController(facade)
    controller.start()
    controller.stop()
    facade.update_settings("quality", "4K")  # published after unsubscribe
    assert controller.latest_settings_changed() is None


def test_no_write_or_execution_passthroughs(facade):
    controller = FacadeController(facade)
    for name in (
        "open_project",
        "select_video",
        "update_settings",
        "run_phase",
        "cancel_phase",
    ):
        assert not hasattr(controller, name)


def test_only_persistent_events_are_referenced():
    # The module must reference only the three persistent events and none of
    # the volatile ones by name.
    persistent = {"ProjectLoaded", "VideoSelected", "SettingsChanged"}
    volatile = {
        "LogMessage",
        "PhaseStarted",
        "PhaseProgress",
        "PhaseCompleted",
        "ArtifactCreated",
        "RenderFinished",
    }
    events = set(fc_module._PERSISTENT_EVENTS)
    names = {e.name for e in events}
    assert names == persistent
    assert not (names & volatile)
