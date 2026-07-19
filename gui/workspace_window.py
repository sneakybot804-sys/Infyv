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
    QLabel,
    QMainWindow,
    QToolBar,
    QWidget,
)

from gui.theme.dpi import configure_high_dpi
from gui.theme.manager import ThemeManager

# Win32 non-client hit-test codes for frameless edge resizing.
_HTLEFT = 10
_HTRIGHT = 11
_HTTOP = 12
_HTTOPLEFT = 13
_HTTOPRIGHT = 14
_HTBOTTOM = 15
_HTBOTTOMLEFT = 16
_HTBOTTOMRIGHT = 17
_WM_NCHITTEST = 0x0084
_RESIZE_MARGIN = 6


class _FramelessWorkspaceWindow(QMainWindow):
    """Frameless :class:`QMainWindow` with native edge-resize hit testing.

    The window chrome (title bar, menu strip, controls) is drawn by the
    embedded widgets; this subclass only removes the OS frame and restores
    native resize behavior on Windows via ``WM_NCHITTEST``. It adds no
    application behavior.
    """

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowSystemMenuHint
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint
        )

    def nativeEvent(self, event_type, message):  # noqa: N802 (Qt override)
        """Map cursor position to resize edges so the frameless window resizes.

        Falls back to the default handling for every non-hit-test message and
        on any non-Windows platform.
        """
        if event_type == "windows_generic_MSG" and not self.isMaximized():
            try:
                import ctypes
                from ctypes import wintypes

                msg = ctypes.wintypes.MSG.from_address(int(message))
                if msg.message == _WM_NCHITTEST:
                    hit = self._hit_test_edge()
                    if hit is not None:
                        return True, hit
            except Exception:  # pragma: no cover - platform/ctypes guard
                return super().nativeEvent(event_type, message)
        return super().nativeEvent(event_type, message)

    def _hit_test_edge(self):
        """Return the HT* edge code under the cursor, or None for the interior."""
        from PySide6.QtGui import QCursor

        pos = self.mapFromGlobal(QCursor.pos())
        x, y = pos.x(), pos.y()
        w, h = self.width(), self.height()
        m = _RESIZE_MARGIN
        left, right = x <= m, x >= w - m
        top, bottom = y <= m, y >= h - m
        if top and left:
            return _HTTOPLEFT
        if top and right:
            return _HTTOPRIGHT
        if bottom and left:
            return _HTBOTTOMLEFT
        if bottom and right:
            return _HTBOTTOMRIGHT
        if left:
            return _HTLEFT
        if right:
            return _HTRIGHT
        if top:
            return _HTTOP
        if bottom:
            return _HTBOTTOM
        return None


def _build_production_controller():
    """Construct the real backend WorkflowController for the workspace.

    Reuses the existing production seam end to end: the shared ``config``
    (config.py), :class:`gui_core.ApplicationFacade` (which lazily builds the
    real FFmpegService and registers the built-in phases), and
    :class:`gui.integration.workflow_controller.WorkflowController`.

    Failure-tolerant: any backend construction error returns ``None`` so the
    window still opens UI-only (the screen's no-controller mode) instead of
    crashing at launch. No new backend architecture is invented here.
    """
    try:
        from config import config as app_config
        from gui.integration.workflow_controller import WorkflowController
        from gui_core import ApplicationFacade

        app_config.ensure_directories()
        facade = ApplicationFacade(app_config)
        controller = WorkflowController(facade)
        controller.start()
        return controller
    except Exception:  # pragma: no cover - environment-dependent guard
        return None


def build_workspace_window(theme: ThemeManager, controller=None) -> QMainWindow:
    """Build and return the Phase 8H media workspace as a QMainWindow host.

    The MediaWorkspaceScreen is the central widget; the host is a frameless
    desktop window whose chrome (custom title bar + main toolbar (
    ``WorkspaceMainToolbar``) + status bar showing ``"Ready"``) is drawn by
    embedded widgets. The frozen menu bar (``File`` / ``Edit`` / ``View`` /
    ``AI`` / ``Help``) and the left / right / bottom docks
    (``WorkspaceLeftDock`` / ``WorkspaceRightDock`` / ``WorkspaceBottomDock``)
    are still present for integration/tests, but hidden in favor of the
    in-screen premium regions.

    Args:
        theme: The injected :class:`~gui.theme.manager.ThemeManager`.
        controller: Optional :class:`~gui.integration.workflow_controller.
            WorkflowController`. When provided it is injected into the
            central MediaWorkspaceScreen (full backend wiring); when omitted
            the screen builds UI-only exactly as before, so every existing
            caller/test is unaffected.

    Returns:
        The composed workspace host as a :class:`QMainWindow`.
    """
    from gui.screens.media_workspace_screen import build_media_workspace_screen
    from gui.widgets.title_bar import TitleBar

    tokens = theme.tokens
    colors = tokens.colors

    window = _FramelessWorkspaceWindow()
    window.setObjectName("WorkspaceMainWindow")
    window.setWindowTitle("AI Gaming Video Editor \u2014 Media")
    # Full-HD desktop proportions (visual only; no behavior change).
    window.resize(1920, 1080)
    window.setMinimumSize(1280, 800)
    # Suppress the toolbar/dock right-click toggle menu (hidden chrome).
    window.setContextMenuPolicy(Qt.ContextMenuPolicy.PreventContextMenu)
    # Animated, nestable docks with a consistent tabbed look, so the docks
    # read as first-class panels rather than floating palettes.
    window.setDockOptions(
        QMainWindow.DockOption.AnimatedDocks
        | QMainWindow.DockOption.AllowNestedDocks
        | QMainWindow.DockOption.AllowTabbedDocks
    )

    # Central content: the frozen media workspace screen. The host names the
    # central-widget instance WorkspaceScreen (the embedded screen keeps its
    # own frozen object name internally). The optional controller is passed
    # through unchanged (None keeps the original UI-only construction).
    central = build_media_workspace_screen(theme, controller)
    central.setObjectName("WorkspaceScreen")
    window.setCentralWidget(central)

    # Menu bar with the top-level menus. Kept populated for integration/tests
    # but collapsed to zero height: the visible menu strip lives in the custom
    # title bar.
    menu_bar = window.menuBar()
    for title in ("File", "Edit", "View", "AI", "Help"):
        menu_bar.addMenu(title)
    menu_bar.setMaximumHeight(0)

    # Custom frameless title bar mounted as the first top toolbar row, then a
    # toolbar break so the main toolbar sits on the second row. Using a toolbar
    # host (rather than setMenuWidget) leaves the central widget and the real
    # menu bar untouched.
    title_bar = TitleBar(theme)
    # Wire the title-bar global actions to the screen's existing behaviors
    # (no new architecture: Import opens the screen's import dialog, Export
    # runs the existing render phase, AI Assistant starts the existing Auto
    # Edit sequencer). Buttons are looked up by their frozen object names;
    # a missing button simply stays unwired.
    from PySide6.QtWidgets import QToolButton as _QTB

    _actions = {
        "WorkspaceImportAction": getattr(central, "_on_import_requested", None),
        "WorkspaceExportAction": getattr(central, "export", None),
        "WorkspaceAIAssistant": getattr(central, "start_auto_edit", None),
    }
    for _name, _slot in _actions.items():
        if _slot is None:
            continue
        _btn = title_bar.findChild(_QTB, _name)
        if _btn is not None:
            _btn.clicked.connect(lambda _=False, s=_slot: s())
    title_host = QToolBar("TitleBar", window)
    title_host.setObjectName("WorkspaceTitleBarHost")
    title_host.setMovable(False)
    title_host.setFloatable(False)
    title_host.addWidget(title_bar)
    window.addToolBar(Qt.ToolBarArea.TopToolBarArea, title_host)
    window.addToolBarBreak(Qt.ToolBarArea.TopToolBarArea)

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

    _populate_main_toolbar(window, toolbar, theme)

    # Wire the toolbar's project/AI actions to the screen's real behaviors
    # (the toolbar itself stays hidden chrome; QActions still fire from any
    # future surfacing and from tests). Lookup by frozen object name.
    _toolbar_slots = {
        "ToolbarActionNew": getattr(central, "new_project", None),
        "ToolbarActionOpen": getattr(central, "open_project", None),
        "ToolbarActionSave": getattr(central, "save_project", None),
        "ToolbarActionImport": getattr(central, "_on_import_requested", None),
        "ToolbarActionAnalyze": (
            (lambda: central.run_phase("analysis"))
            if hasattr(central, "run_phase") else None
        ),
        "ToolbarActionAutoCut": getattr(central, "start_auto_edit", None),
        "ToolbarActionBeatSync": (
            (lambda: central.run_phase("audio"))
            if hasattr(central, "run_phase") else None
        ),
        "ToolbarActionRender": getattr(central, "export", None),
    }
    for _action in toolbar.actions():
        _slot = _toolbar_slots.get(_action.objectName())
        if _slot is not None:
            _action.triggered.connect(lambda _=False, s=_slot: s())

    window.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)
    # The NEXUS reference has a single-row header: every global action lives
    # in the custom title bar, so the legacy labelled toolbar is kept (frozen
    # object name + populated actions for integration/tests) but hidden.
    toolbar.setVisible(False)

    # Docks: left / right / bottom. Present for integration/tests but hidden;
    # the visible regions come from the central screen. Native dock title bars
    # are removed with an empty title widget.
    dock_features = (
        QDockWidget.DockWidgetFeature.DockWidgetMovable
        | QDockWidget.DockWidgetFeature.DockWidgetFloatable
        | QDockWidget.DockWidgetFeature.DockWidgetClosable
    )
    for title, name, area in (
        ("Library", "WorkspaceLeftDock", Qt.DockWidgetArea.LeftDockWidgetArea),
        ("Inspector", "WorkspaceRightDock", Qt.DockWidgetArea.RightDockWidgetArea),
        ("Timeline", "WorkspaceBottomDock", Qt.DockWidgetArea.BottomDockWidgetArea),
    ):
        dock = QDockWidget(title, window)
        dock.setObjectName(name)
        dock.setFeatures(dock_features)
        dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        dock.setTitleBarWidget(QWidget(dock))
        dock.setWidget(QWidget(dock))
        window.addDockWidget(area, dock)
        dock.hide()

    # Status bar: the frozen "Ready" message on the left, plus premium
    # right-aligned readouts (permanent widgets survive showMessage).
    status = window.statusBar()
    status.setSizeGripEnabled(True)
    status.showMessage("Ready")
    _populate_status_bar(status, colors, tokens)

    # Premium shell chrome: a window-level, object-name-scoped, token-derived
    # QSS block layered on top of the global theme QSS.
    window.setStyleSheet(
        f"#WorkspaceMainWindow {{ background: {colors.background_base}; "
        f"border: 1px solid {colors.border}; }} "
        f"#WorkspaceTitleBarHost {{ background: {colors.background_base}; "
        f"border: none; padding: 0px; spacing: 0px; }} "
        f"#WorkspaceTitleBarHost::separator {{ width: 0px; height: 0px; }} "
        f"#WorkspaceMainToolbar {{ background: {colors.surface}; "
        f"border: none; border-bottom: 1px solid {colors.border}; "
        f"spacing: {tokens.spacing.xxs}px; "
        f"padding: {tokens.spacing.xs}px {tokens.spacing.sm}px; }} "
        f"#WorkspaceMainToolbar::separator {{ width: 1px; "
        f"background: {colors.border}; margin: {tokens.spacing.xs}px "
        f"{tokens.spacing.sm}px; }} "
        f"QStatusBar {{ background: {colors.background_base}; "
        f"color: {colors.text_muted}; "
        f"border-top: 1px solid {colors.border}; }} "
        f"QStatusBar::item {{ border: none; }} "
        f"QStatusBar QLabel {{ background: transparent; "
        f"color: {colors.text_muted}; }}"
    )

    return window


def _populate_main_toolbar(
    window: QMainWindow, toolbar: QToolBar, theme: ThemeManager
) -> None:
    """Fill the main toolbar with grouped, inert, icon-labelled actions.

    Icons come from the theme icon loader; every action is unconnected, so the
    workspace stays functionally identical. The ``AI Analyze`` action is shown
    checked to mirror the reference's active tool.
    """
    from PySide6.QtWidgets import QComboBox, QSizePolicy, QToolButton

    c = theme.tokens.colors
    icon = theme.icons.icon

    # (label, icon-name, object-name) grouped by separators.
    groups = (
        (
            ("New", "file-plus", "ToolbarActionNew"),
            ("Open", "folder-open", "ToolbarActionOpen"),
            ("Save", "save", "ToolbarActionSave"),
        ),
        (
            ("Import", "download", "ToolbarActionImport"),
            ("Record", "disc", "ToolbarActionRecord"),
        ),
        (
            ("AI Analyze", "sparkles", "ToolbarActionAnalyze"),
            ("Auto Cut", "scissors", "ToolbarActionAutoCut"),
            ("Beat Sync", "activity", "ToolbarActionBeatSync"),
            ("AI Render", "wand", "ToolbarActionRender"),
        ),
    )
    for group_index, group in enumerate(groups):
        if group_index:
            toolbar.addSeparator()
        for text, icon_name, name in group:
            action = QAction(text, window)
            action.setObjectName(name)
            try:
                action.setIcon(icon(icon_name, c.text_secondary, 18))
            except Exception:  # pragma: no cover - icon optional
                pass
            if name == "ToolbarActionAnalyze":
                action.setCheckable(True)
                action.setChecked(True)
                try:
                    action.setIcon(icon(icon_name, c.accent_blue, 18))
                except Exception:  # pragma: no cover
                    pass
            toolbar.addAction(action)

    # Aspect-ratio dropdown (decorative).
    toolbar.addSeparator()
    aspect = QComboBox(window)
    aspect.setObjectName("ToolbarAspectRatio")
    aspect.addItems(["16:9", "9:16", "1:1", "4:3", "21:9"])
    aspect.setFixedWidth(84)
    toolbar.addWidget(aspect)

    # Small icon-only view actions after the aspect combo, matching the
    # reference toolbar (decorative, unconnected — append-only).
    for icon_name, name, tip in (
        ("camera", "ToolbarActionSnapshot", "Snapshot"),
        ("layout-template", "ToolbarActionGridView", "Grid"),
        ("monitor", "ToolbarActionExpandView", "Expand"),
    ):
        action = QAction("", window)
        action.setObjectName(name)
        action.setToolTip(tip)
        try:
            action.setIcon(icon(icon_name, c.text_secondary, 18))
        except Exception:  # pragma: no cover - icon optional
            pass
        toolbar.addAction(action)

    # Right-aligned Export button.
    spacer = QWidget(window)
    spacer.setObjectName("ToolbarSpacer")
    spacer.setSizePolicy(
        QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
    )
    toolbar.addWidget(spacer)

    export = QToolButton(window)
    export.setObjectName("ToolbarExportButton")
    export.setText("  Export  ")
    export.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
    export.setCursor(Qt.CursorShape.PointingHandCursor)
    # Real action: run the existing render phase via the central screen's
    # export() helper (gated by the pipeline; no-op without a controller).
    central = window.centralWidget()
    if central is not None and hasattr(central, "export"):
        export.clicked.connect(lambda _=False: central.export())
    try:
        export.setIcon(icon("download", c.text_on_accent, 16))
        export.setIconSize(QSize(16, 16))
    except Exception:  # pragma: no cover
        pass
    export.setStyleSheet(
        f"#ToolbarExportButton {{ color: {c.text_on_accent}; "
        f"font-weight: 700; padding: {theme.tokens.spacing.xs}px "
        f"{theme.tokens.spacing.lg}px; border-radius: {theme.tokens.radius.md}px; "
        f"background: qlineargradient(x1:0, y1:0, x2:0, y2:1, "
        f"stop:0 {c.accent_blue}, stop:1 {c.accent_purple}); }} "
        f"#ToolbarExportButton:hover {{ background: {c.accent_blue}; }}"
    )
    toolbar.addWidget(export)


def _populate_status_bar(status, colors, tokens) -> None:
    """Add the premium right-aligned status readouts (permanent widgets)."""
    def _chip(text: str, *, accent: str | None = None) -> QLabel:
        label = QLabel(text)
        label.setObjectName("WorkspaceStatusChip")
        color = accent or colors.text_muted
        label.setStyleSheet(
            f"color: {color}; background: transparent; "
            f"padding: 0px {tokens.spacing.sm}px; font-size: 11px;"
        )
        return label

    status.addPermanentWidget(_chip("Project: Valorant Montage"))
    status.addPermanentWidget(_chip("Timeline: Main Edit"))
    status.addPermanentWidget(_chip("00:02:18:09  total duration"))
    status.addPermanentWidget(_chip("Saved 2 minutes ago", accent=colors.success))
    status.addPermanentWidget(_chip("NVIDIA RTX 4070 Ti"))
    status.addPermanentWidget(_chip("VRAM 9.2 / 12 GB"))
    dot = QLabel("\u25cf")
    dot.setStyleSheet(
        f"color: {colors.success}; background: transparent; "
        f"padding-right: {tokens.spacing.md}px; font-size: 10px;"
    )
    status.addPermanentWidget(dot)


def main() -> int:
    """Launch the media workspace window and run the Qt event loop.

    Production path: builds the real backend WorkflowController (facade over
    config + FFmpegService + the built-in phase registry) and injects it into
    the workspace so every wired control performs real actions. Falls back to
    UI-only when backend construction fails.
    """
    configure_high_dpi()

    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    theme = ThemeManager()
    theme.apply(app)

    controller = _build_production_controller()
    window = build_workspace_window(theme, controller)
    window.show()
    try:
        return app.exec()
    finally:
        if controller is not None:
            controller.stop()


if __name__ == "__main__":
    raise SystemExit(main())
