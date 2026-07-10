"""Dev-only visual showcase for the theme + primitive widgets.

This is **not** part of the application. It creates a QApplication, applies
the active (dark) theme via :class:`~gui.theme.manager.ThemeManager`, and
shows a minimal showcase built ONLY from the Phase 8C-2 primitive widgets
(GlassCard, NeonButton, IconButton, SectionHeader) with dummy content.

Run with:

    python -m gui.app_theme_preview

No dashboard, sidebar, navigation, pages, timeline, video preview, or backend
wiring are involved.
"""
from __future__ import annotations

import sys

from gui.theme.dpi import configure_high_dpi


def main() -> int:
    """Launch the themed widget showcase and run the Qt event loop."""
    configure_high_dpi()

    from PySide6.QtWidgets import (
        QApplication,
        QHBoxLayout,
        QVBoxLayout,
        QWidget,
    )

    from gui.theme.manager import ThemeManager
    from gui.widgets import GlassCard, IconButton, NeonButton, SectionHeader

    app = QApplication(sys.argv)

    theme = ThemeManager()
    theme.apply(app)

    window = QWidget()
    window.setWindowTitle("Widget Showcase - Dark")
    window.resize(960, 600)

    root = QVBoxLayout(window)

    header = SectionHeader(
        theme, "Primitive Widgets", subtitle="Phase 8C-2 showcase"
    )
    header.set_action(NeonButton(theme, "Run", variant="primary", accent="cyan"))
    root.addWidget(header)

    # A glass card containing dummy button rows.
    card = GlassCard(theme, glow="purple")
    card_body = QWidget()
    body_layout = QVBoxLayout(card_body)

    button_row = QHBoxLayout()
    button_row.addWidget(NeonButton(theme, "Primary", variant="primary", accent="blue"))
    button_row.addWidget(NeonButton(theme, "Secondary", variant="secondary", accent="cyan"))
    button_row.addWidget(NeonButton(theme, "Ghost", variant="ghost", accent="purple"))
    body_layout.addLayout(button_row)

    icon_row = QHBoxLayout()
    icon_row.addWidget(IconButton(theme, "play", tooltip="Play", accent="cyan"))
    icon_row.addWidget(
        IconButton(theme, "spark", tooltip="Sparkle", accent="purple", checkable=True)
    )
    icon_row.addStretch(1)
    body_layout.addLayout(icon_row)

    card.set_content(card_body)
    root.addWidget(card)
    root.addStretch(1)

    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
