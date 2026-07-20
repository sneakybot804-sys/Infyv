"""Offscreen Qt tests for the Phase 8H Milestone 1 premium workspace shell.

Builds the new workspace screen and its host window headlessly (no event loop)
and asserts the Milestone 1 shell contract (regions + dock-based chrome).
Additive and independent of the frozen Phase 8D/8E tests. Skipped when PySide6
is unavailable; runs under the ``offscreen`` Qt platform.
"""
from __future__ import annotations

import os

import pytest

pytest.importorskip("PySide6")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QDockWidget,
    QMainWindow,
    QToolBar,
    QWidget,
)

from gui.screens.workspace_screen import build_workspace_screen  # noqa: E402
from gui.theme.manager import ThemeManager  # noqa: E402
from gui.workspace_window import build_workspace_window  # noqa: E402


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance() or QApplication([])
    yield application


@pytest.fixture
def theme(app):
    manager = ThemeManager()
    manager.apply(app)
    return manager


def _find(root, object_name):
    for child in root.findChildren(QWidget):
        if child.objectName() == object_name:
            return child
    return None


def test_screen_build_returns_widget(theme):
    screen = build_workspace_screen(theme)
    assert isinstance(screen, QWidget)
    assert screen.objectName() == "WorkspaceScreen"


def test_screen_has_all_regions(theme):
    screen = build_workspace_screen(theme)
    for name in (
        "WorkspaceToolbarStrip",
        "WorkspaceSidebar",
        "WorkspacePreview",
        "WorkspaceInspector",
        "WorkspaceTimeline",
    ):
        assert _find(screen, name) is not None, f"missing region: {name}"


def test_sidebar_has_project_media_assets(theme):
    screen = build_workspace_screen(theme)
    sidebar = _find(screen, "WorkspaceSidebar")
    for name in (
        "WorkspaceProjectPanel",
        "WorkspaceMediaPanel",
        "WorkspaceAssetsPanel",
    ):
        assert _find(sidebar, name) is not None, f"missing sidebar panel: {name}"


def test_inspector_has_ai_and_properties(theme):
    screen = build_workspace_screen(theme)
    inspector = _find(screen, "WorkspaceInspector")
    assert _find(inspector, "WorkspaceAIPanel") is not None
    assert _find(inspector, "WorkspacePropertiesPanel") is not None


def test_preview_has_stage(theme):
    screen = build_workspace_screen(theme)
    assert _find(screen, "WorkspacePreviewStage") is not None


def test_timeline_placeholder_present(theme):
    screen = build_workspace_screen(theme)
    assert _find(screen, "WorkspaceTimelineTrack") is not None


def test_window_build_returns_main_window(theme):
    window = build_workspace_window(theme)
    assert isinstance(window, QMainWindow)


def test_window_central_is_workspace_screen(theme):
    window = build_workspace_window(theme)
    central = window.centralWidget()
    assert central is not None
    assert central.objectName() == "WorkspaceScreen"


def test_window_menu_bar_populated(theme):
    window = build_workspace_window(theme)
    titles = [a.text() for a in window.menuBar().actions()]
    assert titles == ["File", "Edit", "View", "AI", "Help"]


def test_window_has_toolbar(theme):
    window = build_workspace_window(theme)
    toolbars = window.findChildren(QToolBar)
    assert any(t.objectName() == "WorkspaceMainToolbar" for t in toolbars)


def test_window_has_three_docks(theme):
    window = build_workspace_window(theme)
    names = {d.objectName() for d in window.findChildren(QDockWidget)}
    assert {
        "WorkspaceLeftDock",
        "WorkspaceRightDock",
        "WorkspaceBottomDock",
    } <= names


def test_window_status_bar_has_message(theme):
    window = build_workspace_window(theme)
    assert window.statusBar().currentMessage() == "Ready"


def test_workspace_window_class_is_private():
    import gui.workspace_window as ww

    local_public_classes = [
        n
        for n in vars(ww)
        if not n.startswith("_")
        and n[0].isupper()
        and getattr(vars(ww)[n], "__module__", "") == ww.__name__
    ]
    assert local_public_classes == []
