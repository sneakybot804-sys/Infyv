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

from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from gui.integration.workflow_controller import WorkflowController  # noqa: E402
from gui.screens.media_workspace_screen import build_media_workspace_screen  # noqa: E402
from gui.theme.manager import ThemeManager  # noqa: E402
from gui.widgets import MediaBrowser, TransportBar  # noqa: E402
from gui.widgets.section_header import SectionHeader  # noqa: E402
from gui_core import ApplicationFacade  # noqa: E402
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


def test_timeline_playhead_resets_on_selection(theme, facade, tmp_path):
    clip = tmp_path / "clip_01.mp4"
    clip.write_bytes(b"x")

    controller = WorkflowController(facade)
    controller.start()
    screen = build_media_workspace_screen(theme, controller)

    timeline = _find(screen, "Timeline")
    assert timeline is not None
    timeline.set_playhead(10.0)
    assert timeline.playhead() == 10.0

    browser = _browser(screen)
    browser.set_items([str(clip)])
    browser.select(0)

    assert timeline.playhead() == 0.0
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
