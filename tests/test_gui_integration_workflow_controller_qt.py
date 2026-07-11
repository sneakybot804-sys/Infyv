"""Offscreen Qt tests for the Phase 8G-1 WorkflowController.

Uses a real ApplicationFacade with a fake producer bundle and a registry whose
single fake plugin returns a fake command, so the full run_phase path executes
without any real backend. Covers reads/writes delegation, background success
and failure, single-flight enforcement, lifecycle, and queued signal delivery.
Skipped without PySide6; offscreen platform.
"""
from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEventLoop, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from gui.integration.workflow_controller import WorkflowController  # noqa: E402
from gui_core import ApplicationFacade, Event  # noqa: E402
from gui_core.artifacts import ArtifactKind  # noqa: E402
from gui_core.commands import PhaseResult  # noqa: E402
from gui_core.registry import PhaseCategory, PhaseDescriptor, PluginRegistry  # noqa: E402


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance() or QApplication([])
    yield application


def _pump_until(predicate, timeout_ms=2000):
    loop = QEventLoop()
    timer = QTimer()
    timer.setInterval(10)
    timer.timeout.connect(lambda: loop.quit() if predicate() else None)
    timer.start()
    guard = QTimer()
    guard.setSingleShot(True)
    guard.timeout.connect(loop.quit)
    guard.start(timeout_ms)
    if not predicate():
        loop.exec()
    timer.stop()
    guard.stop()


class _FakeCommand:
    """A stateless fake command that publishes an ArtifactCreated + succeeds."""

    phase_id = "analysis"
    name = "Fake Analysis"

    def execute(self, context) -> PhaseResult:
        output = context.output_dir / "clip_analysis.json"
        context.bus.publish(
            Event.ArtifactCreated, {"phase_id": self.phase_id, "path": str(output)}
        )
        return PhaseResult(phase_id=self.phase_id, success=True, message="ok")


def _make_registry() -> PluginRegistry:
    registry = PluginRegistry()
    registry.register(
        PhaseDescriptor(
            id="analysis",
            label="Fake Analysis",
            category=PhaseCategory.ANALYSIS,
            command_factory=_FakeCommand,
            dependencies=(),
            output_artifact=ArtifactKind.ANALYSIS,
        )
    )
    return registry


def _make_facade(tmp_path: Path) -> ApplicationFacade:
    config = SimpleNamespace(paths=SimpleNamespace(output_dir=tmp_path))
    return ApplicationFacade(config, producers=object(), registry=_make_registry())


@pytest.fixture
def facade(app, tmp_path):
    return _make_facade(tmp_path)


def test_read_delegation(facade):
    controller = WorkflowController(facade)
    assert controller.project_state().video_path is None
    assert controller.settings() == {}
    assert controller.artifacts() == []
    assert controller.available_phases() == []
    assert controller.logs() == []


def test_lifecycle(facade):
    controller = WorkflowController(facade)
    assert controller.is_running() is False
    controller.start()
    assert controller.is_running() is True
    controller.stop()
    assert controller.is_running() is False


def test_write_delegation(facade, tmp_path):
    controller = WorkflowController(facade)
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"x")
    controller.select_video(video)
    assert controller.project_state().video_path == video
    controller.set_setting("quality", "1080p")
    assert controller.settings().get("quality") == "1080p"


def test_run_phase_success_emits_completed(facade, tmp_path):
    controller = WorkflowController(facade)
    controller.start()
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"x")
    controller.select_video(video)

    results = {}
    controller.phase_completed.connect(lambda r: results.update(result=r))
    started = controller.run_phase("analysis")
    assert started is True
    _pump_until(lambda: "result" in results)
    assert results["result"].success is True
    assert controller.is_phase_running() is False
    controller.stop()


def test_run_phase_failure_emits_failed(facade, tmp_path):
    controller = WorkflowController(facade)
    controller.start()
    # No video selected -> facade.run_phase raises ProjectNotLoadedError.
    messages = {}
    controller.phase_failed.connect(lambda m: messages.update(message=m))
    started = controller.run_phase("analysis")
    assert started is True
    _pump_until(lambda: "message" in messages)
    assert messages["message"]
    assert controller.is_phase_running() is False
    controller.stop()


def test_single_flight(facade, tmp_path):
    controller = WorkflowController(facade)
    controller.start()
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"x")
    controller.select_video(video)

    first = controller.run_phase("analysis")
    second = controller.run_phase("analysis")
    assert first is True
    assert second is False  # rejected while the first is in flight
    _pump_until(lambda: controller.is_phase_running() is False)
    controller.stop()


def test_artifact_created_signal(facade, tmp_path):
    controller = WorkflowController(facade)
    controller.start()
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"x")
    controller.select_video(video)

    artifacts = []
    controller.artifact_created.connect(lambda m: artifacts.append(m))
    controller.run_phase("analysis")
    _pump_until(lambda: controller.is_phase_running() is False)
    assert any(m.event is Event.ArtifactCreated for m in artifacts)
    controller.stop()


def test_no_excluded_methods(facade):
    controller = WorkflowController(facade)
    for name in ("open_project", "cancel_phase"):
        assert not hasattr(controller, name)
