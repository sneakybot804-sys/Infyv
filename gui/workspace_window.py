"""Executable launcher and QMainWindow host for the Phase 8H media workspace.

Separate from the permanent Phase 8E launcher (:mod:`gui.application`), which
continues to open the old host window unchanged. This module makes the new
media workspace runnable on its own:

    python -m gui.workspace_window

It configures high-DPI, creates the :class:`QApplication`, applies the dark
theme via :class:`~gui.theme.manager.ThemeManager`, builds the workspace host,
shows it, and runs the Qt event loop.

:func:`build_workspace_window` returns a :class:`QMainWindow` host: the
MediaWorkspaceScreen (from
:func:`gui.screens.media_workspace_screen.build_media_workspace_screen`) is set
as the central widget, and the host adds a menu bar, a main toolbar, left /
right / bottom docks, and a status bar. No backend and no
:class:`gui_core.ApplicationFacade` are wired here.

Stable object names for integration and tests:

* ``WorkspaceMainToolbar`` -- the top toolbar
* ``WorkspaceLeftDock`` / ``WorkspaceRightDock`` / ``WorkspaceBottomDock``
  -- the dock widgets
"""
from __future__ import annotations

import sys

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QDockWidget,
    QMainWindow,
    QToolBar,
    QWidget,
)

from gui.theme.dpi import configure_high_dpi
from gui.theme.manager import ThemeManager


def build_workspace_window(theme: ThemeManager) -> QMainWindow:
    """Build and return the Phase 8H media workspace as a QMainWindow host.

    The MediaWorkspaceScreen is the central widget; the host adds a menu bar, a
    main toolbar (``WorkspaceMainToolbar``), left / right / bottom docks
    (``WorkspaceLeftDock`` / ``WorkspaceRightDock`` / ``WorkspaceBottomDock``),
    and a status bar showing ``"Ready"``.

    Args:
        theme: The injected :class:`~gui.theme.manager.ThemeManager`.

    Returns:
        The composed workspace host as a :class:`QMainWindow`.
    """
    from gui.screens.media_workspace_screen import build_media_workspace_screen

    tokens = theme.tokens
    colors = tokens.colors

    window = QMainWindow()
    window.setObjectName("WorkspaceMainWindow")
    window.setWindowTitle("AI Gaming Video Editor \u2014 Workspace")
    # Premium desktop proportions (visual only; no behavior change).
    window.resize(1600, 960)
    window.setMinimumSize(1120, 700)
    # Animated, nestable docks with a consistent tabbed look, so the docks
    # read as first-class panels rather than floating palettes.
    window.setDockOptions(
        QMainWindow.DockOption.AnimatedDocks
        | QMainWindow.DockOption.AllowNestedDocks
        | QMainWindow.DockOption.AllowTabbedDocks
    )

    # Central content: the frozen media workspace screen. The host names the
    # central-widget instance WorkspaceScreen (the embedded screen keeps its
    # own frozen object name internally).
    central = build_media_workspace_screen(theme)
    central.setObjectName("WorkspaceScreen")
    window.setCentralWidget(central)

    # Menu bar with the top-level menus.
    menu_bar = window.menuBar()
    for title in ("File", "Edit", "View", "AI", "Help"):
        menu_bar.addMenu(title)

    # Main toolbar: fixed desktop chrome (not a floating/movable palette),
    # flat document mode, a consistent icon size and text-beside-icon buttons
    # for a professional, labelled toolbar. Populated with grouped, inert
    # placeholder actions separated by toolbar separators; the actions are not
    # wired to any slot, so behavior is unchanged. Premium hover/pressed/focus
    # styling is supplied globally by the theme QSS.
    toolbar = QToolBar("Main", window)
    toolbar.setObjectName("WorkspaceMainToolbar")
    toolbar.setMovable(False)
    toolbar.setFloatable(False)
    toolbar.setIconSize(QSize(18, 18))
    toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)

    # Grouped, inert placeholder actions (import / edit / history / output /
    # settings). Separators create professional visual grouping. None of these
    # are connected, so the workspace stays functionally identical.
    _toolbar_groups = (
        (("Import", "ToolbarActionImport"),),
        (("Cut", "ToolbarActionCut"), ("Split", "ToolbarActionSplit")),
        (("Undo", "ToolbarActionUndo"), ("Redo", "ToolbarActionRedo")),
        (("Export", "ToolbarActionExport"),),
        (("Settings", "ToolbarActionSettings"),),
    )
    for group_index, group in enumerate(_toolbar_groups):
        if group_index:
            toolbar.addSeparator()
        for text, name in group:
            action = QAction(text, window)
            action.setObjectName(name)
            toolbar.addAction(action)

    window.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

    # Docks: left / right / bottom. Uniform, professional dock features so
    # each reads as a first-class desktop panel; object names and titles are
    # unchanged.
    dock_features = (
        QDockWidget.DockWidgetFeature.DockWidgetMovable
        | QDockWidget.DockWidgetFeature.DockWidgetFloatable
        | QDockWidget.DockWidgetFeature.DockWidgetClosable
    )
    left_dock = QDockWidget("Library", window)
    left_dock.setObjectName("WorkspaceLeftDock")
    left_dock.setFeatures(dock_features)
    left_dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
    left_dock.setWidget(QWidget(left_dock))
    window.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, left_dock)

    right_dock = QDockWidget("Inspector", window)
    right_dock.setObjectName("WorkspaceRightDock")
    right_dock.setFeatures(dock_features)
    right_dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
    right_dock.setWidget(QWidget(right_dock))
    window.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, right_dock)

    bottom_dock = QDockWidget("Timeline", window)
    bottom_dock.setObjectName("WorkspaceBottomDock")
    bottom_dock.setFeatures(dock_features)
    bottom_dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
    bottom_dock.setWidget(QWidget(bottom_dock))
    window.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, bottom_dock)

    # Status bar: a professional desktop edge (size grip) and the frozen
    # "Ready" message.
    window.statusBar().setSizeGripEnabled(True)
    window.statusBar().showMessage("Ready")

    # Premium shell chrome: a window-level, object-name-scoped, token-derived
    # QSS block layered on top of the global theme QSS. Framed main-window
    # surface, glass dock title bars, a denser toolbar rhythm and a glassy
    # status bar with a subtle top divider. No hardcoded colors.
    window.setStyleSheet(
        f"#WorkspaceMainWindow {{ background: {colors.background_base}; }} "
        f"#WorkspaceMainWindow::separator {{ background: {colors.border}; "
        f"width: {tokens.spacing.xxs}px; height: {tokens.spacing.xxs}px; }} "
        f"QDockWidget {{ color: {colors.text_secondary}; "
        f"titlebar-close-icon: none; titlebar-normal-icon: none; }} "
        f"QDockWidget::title {{ background: {colors.surface_elevated}; "
        f"color: {colors.accent_cyan}; "
        f"border: 1px solid {colors.glass_border}; "
        f"border-top-left-radius: {tokens.radius.md}px; "
        f"border-top-right-radius: {tokens.radius.md}px; "
        f"padding: {tokens.spacing.xs}px {tokens.spacing.md}px; }} "
        f"#WorkspaceMainToolbar {{ background: {colors.surface}; "
        f"border: none; border-bottom: 1px solid {colors.border}; "
        f"spacing: {tokens.spacing.xs}px; "
        f"padding: {tokens.spacing.xxs}px {tokens.spacing.sm}px; }} "
        f"QStatusBar {{ background: {colors.surface}; "
        f"color: {colors.text_muted}; "
        f"border-top: 1px solid {colors.border}; }} "
        f"QStatusBar::item {{ border: none; }}"
    )

    return window


def main() -> int:
    """Launch the media workspace window and run the Qt event loop."""
    configure_high_dpi()

    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    theme = ThemeManager()
    theme.apply(app)

    window = build_workspace_window(theme)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
