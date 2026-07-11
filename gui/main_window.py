"""The permanent application host window (Phase 8E).

This module provides the minimal application shell: a :class:`QMainWindow`
whose central widget is the Phase 8D editor screen. The shell is intentionally
bare -- it establishes the permanent host and nothing more. It adds no menu
bar, toolbar, status bar, dock widgets, navigation, routing or additional
screens, wires no signals, and never touches :mod:`gui_core` or any backend.

The window class is an internal implementation detail; the only public
construction entry point is :func:`build_main_window`, consistent with the
repository's ``build_*`` pattern (``build_gallery`` / ``build_editor_screen``).
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import QMainWindow, QWidget

from gui.screens import build_editor_screen
from gui.theme.manager import ThemeManager

#: The visible window title owned by the shell (the child screen's own window
#: title is inert once it is hosted as a central widget).
_WINDOW_TITLE = "AI Gaming Video Editor"


class _MainWindow(QMainWindow):
    """Internal shell window hosting the editor screen as its central widget.

    Args:
        theme: The injected theme manager (sole source of visual values),
            passed straight through to the composed editor screen.
        parent: Optional Qt parent.
    """

    def __init__(self, theme: ThemeManager, *, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("MainWindow")
        self.setWindowTitle(_WINDOW_TITLE)
        self.setCentralWidget(build_editor_screen(theme))
        self.resize(720, 900)


def build_main_window(theme: ThemeManager) -> QMainWindow:
    """Build and return the permanent application host window.

    The window is constructed without running a Qt event loop so it can be
    asserted headlessly in tests. All visual values come from the injected
    ``theme``; no signals are wired and no backend is involved.

    Args:
        theme: The injected theme manager (sole source of visual values).

    Returns:
        The composed shell as a :class:`QMainWindow` hosting the editor screen.
    """
    return _MainWindow(theme)
