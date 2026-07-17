"""Offscreen Qt tests for the Phase 8E application shell.

Builds the host window headlessly (no event loop) via the single public
constructor and asserts the shell contract: it hosts the studio workspace
screen and stays bare (no toolbars, dock widgets, populated menu or status
bar -- the studio screen paints its own chrome). Skipped entirely when PySide6
is unavailable, matching the Phase 8B/8C/8D convention. Runs under the
``offscreen`` Qt platform.
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
)

from gui.main_window import build_main_window  # noqa: E402
from gui.theme.manager import ThemeManager  # noqa: E402


@pytest.fixture(scope="module")
def app():
    """Provide a single QApplication for the module."""
    application = QApplication.instance() or QApplication([])
    yield application


@pytest.fixture
def theme(app):
    """Provide an applied ThemeManager (dark theme)."""
    manager = ThemeManager()
    manager.apply(app)
    return manager


def test_build_returns_main_window(theme):
    window = build_main_window(theme)
    assert isinstance(window, QMainWindow)


def test_central_widget_is_studio_screen(theme):
    window = build_main_window(theme)
    central = window.centralWidget()
    assert central is not None
    assert central.objectName() == "StudioScreen"


def test_window_title(theme):
    window = build_main_window(theme)
    assert window.windowTitle() == "AI Gaming Video Editor"


def test_no_toolbars(theme):
    window = build_main_window(theme)
    assert window.findChildren(QToolBar) == []


def test_no_dock_widgets(theme):
    window = build_main_window(theme)
    assert window.findChildren(QDockWidget) == []


def test_menu_bar_not_populated(theme):
    window = build_main_window(theme)
    menu_bar = window.menuBar()
    # A bare shell adds no menus/actions (the studio screen paints its own).
    assert menu_bar.actions() == []


def test_status_bar_not_populated(theme):
    window = build_main_window(theme)
    # No status message has been set by the shell.
    assert window.statusBar().currentMessage() == ""


def test_studio_regions_present(theme):
    window = build_main_window(theme)
    central = window.centralWidget()
    for name in (
        "StudioMenuBar",
        "StudioToolbar",
        "StudioSidebar",
        "StudioPreviewStage",
        "StudioTransport",
        "StudioTimeline",
        "StudioRightPanel",
        "StudioStatusBar",
    ):
        assert central.findChild(object, name) is not None, name


def test_main_window_class_is_private():
    import gui.main_window as mw

    public = [n for n in vars(mw) if not n.startswith("_") and n[0].isupper()]
    # No public class is exported from the module (the window class is
    # private); imported Qt/theme symbols that are classes are excluded by
    # module origin.
    local_public_classes = [
        n
        for n in public
        if getattr(vars(mw)[n], "__module__", "") == mw.__name__
    ]
    assert local_public_classes == []
