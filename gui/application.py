"""Permanent application launcher (Phase 8E).

This is the permanent entry point for the application host. It configures
high-DPI, creates the QApplication, applies the dark theme via
:class:`~gui.theme.manager.ThemeManager`, builds the host window via
:func:`gui.main_window.build_main_window`, and runs the Qt event loop.

Run with:

    python -m gui.application

The developer-only screen preview (``python -m gui.app_editor_preview``)
remains available and unchanged. This launcher wires no backend and no
:class:`gui_core.ApplicationFacade`; integration arrives in a later phase.
"""
from __future__ import annotations

import sys

from gui.theme.dpi import configure_high_dpi


def main() -> int:
    """Launch the application host window and run the Qt event loop."""
    configure_high_dpi()

    from PySide6.QtWidgets import QApplication

    from gui.main_window import build_main_window
    from gui.theme.manager import ThemeManager

    app = QApplication(sys.argv)

    theme = ThemeManager()
    theme.apply(app)

    window = build_main_window(theme)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
