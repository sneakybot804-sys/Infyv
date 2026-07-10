"""Dev-only visual smoke test for the theme foundation.

This is **not** part of the application: it exists so the theme can be
inspected before any real window/widgets exist. It creates a QApplication,
applies the active (dark) theme via :class:`~gui.theme.manager.ThemeManager`,
shows a minimal empty window, and exits cleanly.

Run with:

    python -m gui.app_theme_preview

No pages, widgets, dashboard, or backend wiring are involved.
"""
from __future__ import annotations

import sys

from gui.theme.dpi import configure_high_dpi


def main() -> int:
    """Launch a themed empty window and run the Qt event loop."""
    configure_high_dpi()

    from PySide6.QtWidgets import QApplication, QWidget

    from gui.theme.manager import ThemeManager

    app = QApplication(sys.argv)

    manager = ThemeManager()
    manager.apply(app)

    window = QWidget()
    window.setWindowTitle("Theme Preview — Dark")
    window.resize(960, 600)
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
