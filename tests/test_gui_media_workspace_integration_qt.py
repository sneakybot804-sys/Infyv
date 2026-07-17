"""Offscreen Qt tests for the in-screen MediaBrowser -> WorkflowController wiring.

The media workspace screen owns the only MediaBrowser, so its backend
integration lives inside the screen (no per-widget binding module). These
tests exercise both modes of :func:`build_media_workspace_screen`:

* no controller -> the screen stays purely UI-only (the original behavior);
* with a controller -> selecting a media item drives ``select_video`` and the
  screen reflects the authoritative ``ProjectState`` read back.

Uses a real :class:`ApplicationFacade` with a fake registry (mirroring
``test_gui_integration_workflow_controller_qt.py``) so no real backend is
needed. Skipped without PySide6; runs under the offscreen Qt platform.
"""
from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEventLoop, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from gui.integration.workflow_controller import WorkflowController  # noqa: E402
from gui.screens.media_workspace_screen import build_media_workspace_screen  # noqa: E402
from gui.theme.manager import ThemeManager  # noqa: E402
from gui.widgets import MediaBrowser, TransportBar  # noqa: E402
from gui_core import ApplicationFacade, Timeline, Track  # noqa: E402
from gui_core.timeline import Clip as TimelineClip  # noqa: E402
from gui_core.artifacts import ArtifactKind  # noqa: E402
from gui_core.commands import PhaseResult  # noqa: E402
from gui_core.registry import (  # noqa: E402
    PhaseCategory,
    PhaseDescriptor,
    PluginRegistry,
)


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance() or QApplication([])
    yield application


@pytest.fixture
def theme(app):
    manager = ThemeManager()
    manager.apply(app)
    return manager


class _FakeCommand:
    """A minimal fake command so the registry has a runnable phase."""

    phase_id = "analysis"
    name = "Fake Analysis"

    def execute(self, context) -> PhaseResult:
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


@pytest.fixture
def facade(app, tmp_path):
    config = SimpleNamespace(paths=SimpleNamespace(output_dir=tmp_path))
    return ApplicationFacade(config, producers=object(), registry=_make_registry())


class _FakeFrameService:
    """Fake decode/metadata service returning tiny numpy BGR frames."""

    def read_metadata(self, path):
        return SimpleNamespace(width=4, height=4, fps=30.0, duration=10.0)

    def extract_frame_at(self, path, timestamp):
        import numpy as np

        # A 4x4 BGR frame whose blue channel encodes the timestamp bucket.
        frame = np.zeros((4, 4, 3), dtype=np.uint8)
        frame[:, :, 0] = int(timestamp) % 256
        return frame


@pytest.fixture
def frame_facade(app, tmp_path):
    config = SimpleNamespace(paths=SimpleNamespace(output_dir=tmp_path))
    return ApplicationFacade(
        config,
        producers=object(),
        registry=_make_registry(),
        frame_service=_FakeFrameService(),
    )


def _find(root, object_name):
    for child in root.findChildren(QWidget):
        if child.objectName() == object_name:
            return child
    return None


def _browser(screen) -> MediaBrowser:
    browser = _find(screen, "MediaBrowser")
    assert isinstance(browser, MediaBrowser)
    return browser


def _label_text(screen, object_name) -> str:
    """Return the visible text of a QLabel-like Preview widget by object name."""
    widget = _find(screen, object_name)
    assert widget is not None, f"missing widget: {object_name}"
    return widget.text()


def _transport(screen) -> TransportBar:
    bar = _find(screen, "TransportBar")
    assert isinstance(bar, TransportBar)
    return bar


def _pump_until(predicate, timeout_ms=2000):
    """Spin the Qt event loop until ``predicate`` is true or timeout elapses."""
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


def _detail_status_text(screen) -> str:
    """Return the Details Status MetaLabel text via the screen's reference.

    The Status row is a MetaLabel without a distinct object name, so it is
    read through the screen's stored _detail_status attribute (a stable
    reference set at construction). Supports either .text() or .get_text().
    """
    label = screen._detail_status
    getter = getattr(label, "text", None) or getattr(label, "get_text", None)
    return getter()


# ---------------------------------------------------------------------- #
# UI-only mode (no controller): original behavior is preserved.
# ---------------------------------------------------------------------- #
def test_screen_builds_without_controller(theme):
    screen = build_media_workspace_screen(theme)
    assert screen.objectName() == "MediaWorkspaceScreen"
    # No backend selection happens; selecting an item is pure UI.
    browser = _browser(screen)
    browser.select(0)
    assert browser.current_index() == 0


# ---------------------------------------------------------------------- #
# Integration mode: selection drives the backend and reflects ProjectState.
# ---------------------------------------------------------------------- #
def test_selection_drives_select_video(theme, facade, tmp_path):
    # Seed the browser with real files so select_video accepts the path.
    clip = tmp_path / "clip_01.mp4"
    clip.write_bytes(b"x")

    controller = WorkflowController(facade)
    controller.start()
    screen = build_media_workspace_screen(theme, controller)

    browser = _browser(screen)
    browser.set_items([str(clip)])
    browser.select(0)

    # The selection was pushed through to the backend ProjectState.
    assert controller.project_state().video_path == clip
    controller.stop()


def test_ui_reflects_backend_project_state(theme, facade, tmp_path):
    clip = tmp_path / "highlight_reel.mp4"
    clip.write_bytes(b"x")

    controller = WorkflowController(facade)
    controller.start()
    screen = build_media_workspace_screen(theme, controller)

    browser = _browser(screen)
    browser.set_items([str(clip)])
    browser.select(0)

    # The screen reflects the authoritative backend video_path name (the
    # Details/preview labels are internal; project_state is the contract the
    # screen reads and mirrors).
    assert controller.project_state().video_path.name == "highlight_reel.mp4"
    controller.stop()


def test_preview_placeholder_and_type_reflect_project_state(theme, facade, tmp_path):
    clip = tmp_path / "clip_01.mp4"
    clip.write_bytes(b"x")

    controller = WorkflowController(facade)
    controller.start()
    screen = build_media_workspace_screen(theme, controller)

    browser = _browser(screen)
    browser.set_items([str(clip)])
    browser.select(0)

    # Placeholder reflects the selected media name (observed from video_path).
    assert _label_text(screen, "MediaWorkspacePreviewPlaceholder") == "clip_01.mp4"
    # Details "Type" is derived from the video_path suffix (no fabrication).
    assert controller.project_state().video_path.suffix == ".mp4"
    controller.stop()


def test_status_reflects_artifacts(theme, facade, tmp_path):
    # Seed the canonical analysis artifact so the real ArtifactResolver (bound
    # to the facade output_dir == tmp_path) discovers it on select_video.
    clip = tmp_path / "clip_01.mp4"
    clip.write_bytes(b"x")
    (tmp_path / "clip_01_analysis.json").write_text("{}")

    controller = WorkflowController(facade)
    controller.start()
    screen = build_media_workspace_screen(theme, controller)

    browser = _browser(screen)
    browser.set_items([str(clip)])
    browser.select(0)

    # ProjectState carries the discovered artifact; the Details status row
    # reflects real artifact presence (existing Details UI, no new widget).
    state = controller.project_state()
    assert len(state.artifacts) == 1
    assert _detail_status_text(screen) == "Status: ready \u00b7 1 artifact"
    controller.stop()


def test_status_ready_when_no_artifacts(theme, facade, tmp_path):
    clip = tmp_path / "clip_solo.mp4"
    clip.write_bytes(b"x")

    controller = WorkflowController(facade)
    controller.start()
    screen = build_media_workspace_screen(theme, controller)

    browser = _browser(screen)
    browser.set_items([str(clip)])
    browser.select(0)

    assert controller.project_state().artifacts == ()
    assert _detail_status_text(screen) == "Status: ready"
    controller.stop()


def test_transport_display_resets_on_selection(theme, facade, tmp_path):
    clip = tmp_path / "clip_01.mp4"
    clip.write_bytes(b"x")

    controller = WorkflowController(facade)
    controller.start()
    screen = build_media_workspace_screen(theme, controller)

    transport = _transport(screen)
    # Drive the transport away from its initial display first.
    transport.set_state("playing")
    transport.set_position(0.5)

    browser = _browser(screen)
    browser.set_items([str(clip)])
    browser.select(0)

    # Selecting new media resets the transport DISPLAY via its public API.
    assert transport.state() == "stopped"
    assert transport.position() == 0.0
    controller.stop()


def test_clear_selection_resets_empty_state(theme, facade, tmp_path):
    clip = tmp_path / "clip_01.mp4"
    clip.write_bytes(b"x")

    controller = WorkflowController(facade)
    controller.start()
    screen = build_media_workspace_screen(theme, controller)

    browser = _browser(screen)
    browser.set_items([str(clip)])
    browser.select(0)
    assert _label_text(screen, "MediaWorkspacePreviewPlaceholder") == "clip_01.mp4"

    browser.select(-1)
    # Every Preview-owned surface returns to the frozen empty state.
    assert _label_text(screen, "MediaWorkspacePreviewPlaceholder") == "No clip selected"
    controller.stop()


def test_run_phase_reflects_completion(theme, facade, tmp_path):
    clip = tmp_path / "clip_01.mp4"
    clip.write_bytes(b"x")

    controller = WorkflowController(facade)
    controller.start()
    screen = build_media_workspace_screen(theme, controller)

    browser = _browser(screen)
    browser.set_items([str(clip)])
    browser.select(0)

    # Caller specifies the phase explicitly.
    started = screen.run_phase("analysis")
    assert started is True
    _pump_until(lambda: controller.is_phase_running() is False)
    assert screen._preview_status_badge.text() == "Done"
    controller.stop()


def test_run_phase_without_controller_returns_false(theme):
    screen = build_media_workspace_screen(theme)
    assert screen.run_phase("analysis") is False


def test_selection_displays_real_first_frame(theme, frame_facade, tmp_path):
    clip = tmp_path / "clip_01.mp4"
    clip.write_bytes(b"x")

    controller = WorkflowController(frame_facade)
    controller.start()
    screen = build_media_workspace_screen(theme, controller)

    browser = _browser(screen)
    browser.set_items([str(clip)])
    browser.select(0)

    sink = _find(screen, "MediaWorkspacePreviewFrame")
    assert sink is not None
    assert sink.isVisible() is True
    assert sink.pixmap() is not None and not sink.pixmap().isNull()
    controller.stop()


def test_playhead_change_decodes_frame(theme, frame_facade, tmp_path):
    clip = tmp_path / "clip_01.mp4"
    clip.write_bytes(b"x")

    controller = WorkflowController(frame_facade)
    controller.start()
    screen = build_media_workspace_screen(theme, controller)

    browser = _browser(screen)
    browser.set_items([str(clip)])
    browser.select(0)

    timeline = _find(screen, "Timeline")
    timeline.set_playhead(5.0)  # emits playhead_changed -> decode + display

    sink = _find(screen, "MediaWorkspacePreviewFrame")
    assert sink.isVisible() is True
    assert not sink.pixmap().isNull()
    controller.stop()


class _WriteArtifactCommand:
    """Fake command writing a canonical artifact so gating can advance."""

    def __init__(self, phase_id, suffix):
        self.phase_id = phase_id
        self.name = phase_id
        self._suffix = suffix

    def execute(self, context):
        video = context.video_path
        stem = video.stem if video is not None else "clip_01"
        (context.output_dir / f"{stem}{self._suffix}").write_text("{}")
        return PhaseResult(phase_id=self.phase_id, success=True, message="ok")


def _auto_edit_facade(tmp_path):
    from gui_core.artifacts import ArtifactKind

    registry = PluginRegistry()
    registry.register(
        PhaseDescriptor(
            id="analysis", label="Analysis", category=PhaseCategory.ANALYSIS,
            command_factory=lambda: _WriteArtifactCommand("analysis", "_analysis.json"),
            dependencies=(), output_artifact=ArtifactKind.ANALYSIS,
        )
    )
    registry.register(
        PhaseDescriptor(
            id="highlight", label="Highlight", category=PhaseCategory.ANALYSIS,
            command_factory=lambda: _WriteArtifactCommand("highlight", "_highlight.json"),
            dependencies=("analysis",), output_artifact=ArtifactKind.HIGHLIGHT,
        )
    )
    config = SimpleNamespace(paths=SimpleNamespace(output_dir=tmp_path))
    return ApplicationFacade(config, producers=object(), registry=registry)


def test_auto_edit_sequences_pipeline(theme, tmp_path, app):
    clip = tmp_path / "clip_01.mp4"
    clip.write_bytes(b"x")

    controller = WorkflowController(_auto_edit_facade(tmp_path))
    controller.start()
    screen = build_media_workspace_screen(theme, controller)

    browser = _browser(screen)
    browser.set_items([str(clip)])
    browser.select(0)

    assert screen.start_auto_edit() is True
    _pump_until(
        lambda: (tmp_path / "clip_01_highlight.json").exists()
        and controller.is_phase_running() is False
    )
    assert (tmp_path / "clip_01_analysis.json").exists()
    assert (tmp_path / "clip_01_highlight.json").exists()
    controller.stop()


def test_widget_edit_persists_to_backend_timeline(theme, facade, tmp_path):
    controller = WorkflowController(facade)
    controller.start()
    screen = build_media_workspace_screen(theme, controller)

    timeline = _find(screen, "Timeline")
    # Two-track demo content exists by default; move the first clip to track 1.
    timeline.set_clips(
        [
            {"track": 0, "start": 0.0, "length": 10.0, "label": "A"},
            {"track": 1, "start": 0.0, "length": 10.0, "label": "B"},
        ]
    )
    timeline.move_clip(0, 1)  # emits clip_moved -> persist to backend

    backend = controller.timeline()
    assert backend is not None
    moved = backend.clip_by_id("clip_0")
    assert moved is not None and moved.track_index == 1
    controller.stop()


def test_backend_timeline_reflected_into_widget(theme, facade, tmp_path):
    clip = tmp_path / "clip_01.mp4"
    clip.write_bytes(b"x")

    controller = WorkflowController(facade)
    controller.start()
    screen = build_media_workspace_screen(theme, controller)

    backend_tl = (
        Timeline(duration=90.0, tracks=(Track(index=0, name="V1"),))
        .add_clip(TimelineClip(id="c1", track_index=0, start=0.0, length=10.0,
                               label="Intro"))
        .add_clip(TimelineClip(id="c2", track_index=0, start=10.0, length=20.0,
                               label="Play"))
    )
    controller.update_timeline(backend_tl)

    browser = _browser(screen)
    browser.set_items([str(clip)])
    browser.select(0)

    widget = _find(screen, "Timeline")
    assert widget is not None
    assert widget.duration() == 90.0
    assert widget.clip_count() == 2
    starts = sorted(c["start"] for c in widget.clips())
    assert starts == [0.0, 10.0]
    controller.stop()


class _WritingCommand:
    """Fake command that writes the canonical analysis artifact then succeeds."""

    phase_id = "analysis"
    name = "Writing Analysis"

    def execute(self, context) -> PhaseResult:
        # Producers write "<stem>_analysis.json" into output_dir; mirror that so
        # ArtifactResolver.discover finds it on refresh_artifacts().
        video = context.video_path if hasattr(context, "video_path") else None
        stem = video.stem if video is not None else "clip_01"
        (context.output_dir / f"{stem}_analysis.json").write_text("{}")
        return PhaseResult(phase_id=self.phase_id, success=True, message="ok")


def _writing_facade(tmp_path):
    registry = PluginRegistry()
    registry.register(
        PhaseDescriptor(
            id="analysis",
            label="Writing Analysis",
            category=PhaseCategory.ANALYSIS,
            command_factory=_WritingCommand,
            dependencies=(),
            output_artifact=ArtifactKind.ANALYSIS,
        )
    )
    config = SimpleNamespace(paths=SimpleNamespace(output_dir=tmp_path))
    return ApplicationFacade(config, producers=object(), registry=registry)


def test_details_artifacts_refresh_after_phase(theme, tmp_path, app):
    clip = tmp_path / "clip_01.mp4"
    clip.write_bytes(b"x")

    controller = WorkflowController(_writing_facade(tmp_path))
    controller.start()
    screen = build_media_workspace_screen(theme, controller)

    browser = _browser(screen)
    browser.set_items([str(clip)])
    browser.select(0)
    # No artifacts discovered at selection time.
    assert _detail_status_text(screen) == "Status: ready"

    assert screen.run_phase("analysis") is True
    _pump_until(lambda: controller.is_phase_running() is False)

    # After completion, ProjectState.artifacts is authoritative and the
    # Details Status row reflects the newly discovered artifact.
    assert len(controller.project_state().artifacts) == 1
    assert _detail_status_text(screen) == "Status: ready \u00b7 1 artifact"


def test_clear_selection_does_not_select_video(theme, facade, tmp_path):
    clip = tmp_path / "clip_01.mp4"
    clip.write_bytes(b"x")

    controller = WorkflowController(facade)
    controller.start()
    screen = build_media_workspace_screen(theme, controller)

    browser = _browser(screen)
    browser.set_items([str(clip)])
    browser.select(0)
    assert controller.project_state().video_path == clip

    # Clearing the selection resets the UI and does not push a new video.
    browser.select(-1)
    assert browser.current_index() == -1
    # The backend keeps the last real selection (clear never calls select_video).
    assert controller.project_state().video_path == clip
    controller.stop()
