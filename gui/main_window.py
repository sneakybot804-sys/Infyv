"""The permanent application host window (Phase 8E).

This module provides the minimal application shell: a :class:`QMainWindow`
whose central widget is the full studio workspace screen. The shell is
intentionally bare -- it establishes the permanent host and nothing more. It
adds no menu bar, toolbar, status bar, dock widgets, navigation, routing or
additional screens (the studio screen paints its own chrome), wires no
signals, and never touches :mod:`gui_core` or any backend.

The window class is an internal implementation detail; the only public
construction entry point is :func:`build_main_window`, consistent with the
repository's ``build_*`` pattern (``build_gallery`` / ``build_studio_screen``).
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import QMainWindow, QWidget

from gui.screens.media_workspace_screen import build_media_workspace_screen
from gui.theme.manager import ThemeManager

#: The visible window title owned by the shell (the child screen's own window
#: title is inert once it is hosted as a central widget).
_WINDOW_TITLE = "AI Gaming Video Editor"


def _build_backend_controller():
    """Build the live backend controller for the production editor.

    Constructs the existing, Qt-free ``ApplicationFacade`` over the shared
    app ``config`` and wraps it in the interactive ``WorkflowController`` that
    the media workspace consumes for real playback (decode / metadata /
    audio), timeline persistence and phase execution. No new architecture is
    introduced -- only the existing constructors are used.

    Failure-tolerant: if the backend cannot be built (e.g. missing optional
    dependencies in a headless/CI environment), returns ``None`` so the
    caller can still launch the real editor in UI-only mode rather than the
    legacy studio mockup.
    """
    try:
        from config import config
        from gui.integration.workflow_controller import WorkflowController
        from gui_core import ApplicationFacade

        facade = ApplicationFacade(config)
        controller = WorkflowController(facade)
        controller.start()
        return controller
    except Exception:
        return None


class _MainWindow(QMainWindow):
    """Internal shell window hosting the real Media Workspace editor.

    Args:
        theme: The injected theme manager (sole source of visual values),
            passed straight through to the composed workspace screen.
        parent: Optional Qt parent.
    """

    def __init__(self, theme: ThemeManager, *, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("MainWindow")
        self.setWindowTitle(_WINDOW_TITLE)
        # The single production editor: the real Media Workspace, driven by a
        # live backend controller (real playback / metadata / audio / phases).
        self._controller = _build_backend_controller()
        self.setCentralWidget(
            build_media_workspace_screen(theme, self._controller)
        )
        self.resize(1536, 960)

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        """Tear the backend controller down cleanly on window close."""
        controller = getattr(self, "_controller", None)
        if controller is not None:
            try:
                controller.stop()
            except Exception:
                pass
        super().closeEvent(event)


def build_main_window(theme: ThemeManager) -> QMainWindow:
    """Build and return the permanent application host window.

    The window is constructed without running a Qt event loop so it can be
    asserted headlessly in tests. All visual values come from the injected
    ``theme``; no signals are wired and no backend is involved.

    Args:
        theme: The injected theme manager (sole source of visual values).

    Returns:
        The composed shell as a :class:`QMainWindow` hosting the studio screen.
    """
    return _MainWindow(theme)
