"""Executable launcher for the Phase 8H media workspace.

Separate from the permanent Phase 8E launcher (:mod:`gui.application`), which
continues to open the old host window unchanged. This module makes the new
media workspace runnable on its own:

    python -m gui.workspace_window

It configures high-DPI, creates the QApplication, applies the dark theme via
:class:`~gui.theme.manager.ThemeManager`, builds the workspace, shows it, and
runs the Qt event loop.

The workspace's public builder is
:func:`gui.screens.media_workspace_screen.build_media_workspace_screen`, which
returns the ``MediaWorkspaceScreen`` widget. :func:`build_workspace_window` is
a thin wrapper over it. No backend and no :class:`gui_core.ApplicationFacade`
are wired here.
"""
from __future__ import annotations

import sys

from gui.theme.dpi import configure_high_dpi


def build_workspace_window(theme):
    """Build and return the Phase 8H media workspace widget.

    Thin wrapper over
    :func:`gui.screens.media_workspace_screen.build_media_workspace_screen`;
    the returned widget can be shown directly as a top-level window.

    Args:
        theme: The injected :class:`~gui.theme.manager.ThemeManager`.

    Returns:
        The composed media workspace as a ``QWidget``.
    """
    from gui.screens.media_workspace_screen import build_media_workspace_screen

    return build_media_workspace_screen(theme)


def main() -> int:
    """Launch the media workspace window and run the Qt event loop."""
    configure_high_dpi()

    from PySide6.QtWidgets import QApplication

    from gui.theme.manager import ThemeManager

    app = QApplication(sys.argv)

    theme = ThemeManager()
    theme.apply(app)

    window = build_workspace_window(theme)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
