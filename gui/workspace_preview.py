"""Dev-only launcher for the Milestone 2 media workspace screen.

This is the correct entry point for previewing the NavigationSidebar and
the full media workspace layout. It mirrors the pattern of
:mod:`gui.app_editor_preview` but mounts :func:`build_media_workspace_screen`
instead of the Phase 8D editor screen.

Run with:

    python -m gui.workspace_preview

No backend, no :mod:`gui_core`, no navigation beyond the workspace itself.
"""
from __future__ import annotations

import sys

from gui.theme.dpi import configure_high_dpi


def main() -> int:
    """Launch the media workspace screen and run the Qt event loop."""
    configure_high_dpi()

    from PySide6.QtWidgets import QApplication

    from gui.screens.media_workspace_screen import build_media_workspace_screen
    from gui.theme.manager import ThemeManager

    app = QApplication(sys.argv)

    theme = ThemeManager()
    theme.apply(app)

    window = build_media_workspace_screen(theme)
    window.resize(1600, 900)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
