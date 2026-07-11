"""Dev-only launcher for the Phase 8D AI Gaming Video Editor screen.

This is a thin runnable entry point, not application logic. It configures
high-DPI, creates a QApplication, applies the dark theme via
:class:`~gui.theme.manager.ThemeManager`, builds the first application screen
via :func:`gui.screens.build_editor_screen`, and runs the Qt event loop.

Run with:

    python -m gui.app_editor_preview

No navigation, sidebar, dashboard or backend wiring are involved.
"""
from __future__ import annotations

import sys

from gui.theme.dpi import configure_high_dpi


def main() -> int:
    """Launch the themed editor screen and run the Qt event loop."""
    configure_high_dpi()

    from PySide6.QtWidgets import QApplication

    from gui.screens import build_editor_screen
    from gui.theme.manager import ThemeManager

    app = QApplication(sys.argv)

    theme = ThemeManager()
    theme.apply(app)

    window = build_editor_screen(theme)
    window.resize(720, 900)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
