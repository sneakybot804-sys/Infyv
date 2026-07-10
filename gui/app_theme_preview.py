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


def _labeled_card(theme, title, subtitle, badge, body_layout):
    """Build a GlassCard whose content is a header plus a body layout.

    Helper local to the gallery; not part of the widget library.
    """
    from PySide6.QtWidgets import QVBoxLayout, QWidget

    from gui.widgets import GlassCard, SectionHeader

    tokens = theme.tokens
    card = GlassCard(theme, glow="cyan")
    content = QWidget()
    layout = QVBoxLayout(content)
    layout.setContentsMargins(
        tokens.spacing.lg, tokens.spacing.lg, tokens.spacing.lg, tokens.spacing.lg
    )
    layout.setSpacing(tokens.spacing.md)

    header = SectionHeader(theme, title, subtitle=subtitle)
    if badge:
        header.set_badge(badge, accent="purple")
    header.set_divider(True)
    layout.addWidget(header)
    layout.addLayout(body_layout)
    card.set_content(content)
    return card


def build_gallery(theme) -> "QWidget":
    """Build and return the component-gallery window for ``theme``.

    Extracted from :func:`main` so the widget tree can be constructed (and
    asserted) headlessly in tests without running the Qt event loop.
    """
    from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

    from gui.widgets import IconButton, NeonButton, SectionHeader

    tokens = theme.tokens

    window = QWidget()
    window.setWindowTitle("Component Gallery - Dark")
    window.resize(1040, 720)

    root = QVBoxLayout(window)
    m = tokens.spacing.xxl
    root.setContentsMargins(m, m, m, m)
    root.setSpacing(tokens.spacing.xl)

    # Page title.
    title = SectionHeader(
        theme,
        "Component Gallery",
        subtitle="Premium primitive widgets - Phase 8C-2",
    )
    title.set_badge("dark", accent="cyan")
    root.addWidget(title)

    # Buttons card.
    buttons = QHBoxLayout()
    buttons.setSpacing(tokens.spacing.md)
    for label, variant, accent in (
        ("Primary", "primary", "blue"),
        ("Secondary", "secondary", "cyan"),
        ("Ghost", "ghost", "purple"),
    ):
        b = NeonButton(theme, label, variant=variant, accent=accent)
        b.setFixedWidth(theme.tokens.spacing.xxl * 5)
        buttons.addWidget(b)
    disabled = NeonButton(theme, "Disabled", variant="secondary")
    disabled.setEnabled(False)
    disabled.setFixedWidth(theme.tokens.spacing.xxl * 5)
    buttons.addWidget(disabled)
    buttons.addStretch(1)
    root.addWidget(
        _labeled_card(theme, "Buttons", "NeonButton variants", "4", buttons)
    )

    # Icon buttons card.
    icons = QHBoxLayout()
    icons.setSpacing(tokens.spacing.md)
    icons.addWidget(IconButton(theme, "play", tooltip="Play", accent="cyan"))
    icons.addWidget(
        IconButton(theme, "spark", tooltip="Sparkle", accent="purple", checkable=True)
    )
    icons.addWidget(IconButton(theme, "play", tooltip="Blue", accent="blue"))
    icons.addStretch(1)
    root.addWidget(
        _labeled_card(theme, "Icon Buttons", "IconButton states", None, icons)
    )

    # States card: disabled + loading examples.
    states = QHBoxLayout()
    states.setSpacing(tokens.spacing.md)
    disabled_btn = NeonButton(theme, "Disabled", variant="secondary")
    disabled_btn.setEnabled(False)
    disabled_btn.setFixedWidth(theme.tokens.spacing.xxl * 5)
    loading_btn = NeonButton(theme, "Saving", variant="primary", accent="cyan")
    loading_btn.set_loading(True)
    loading_btn.setFixedWidth(theme.tokens.spacing.xxl * 5)
    states.addWidget(disabled_btn)
    states.addWidget(loading_btn)
    states.addStretch(1)
    root.addWidget(
        _labeled_card(theme, "States", "Disabled and loading", None, states)
    )

    root.addStretch(1)
    return window


def _debug_checkpoint(window, label: str) -> None:
    """TEMPORARY: log widget counts / visibility / effects at a checkpoint."""
    from gui.widgets import GlassCard, IconButton, NeonButton, SectionHeader

    print(f"[gallery] checkpoint {label}")
    for widget_type in (GlassCard, NeonButton, IconButton, SectionHeader):
        found = window.findChildren(widget_type)
        print(f"[gallery]   {widget_type.__name__}: count={len(found)}")
        for i, w in enumerate(found):
            has_effect = w.graphicsEffect() is not None
            print(
                f"[gallery]     #{i} visible={w.isVisible()} "
                f"effect={has_effect}"
            )


def main() -> int:
    """Launch the themed component gallery and run the Qt event loop."""
    configure_high_dpi()

    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from gui.theme.manager import ThemeManager

    app = QApplication(sys.argv)

    theme = ThemeManager()
    theme.apply(app)

    window = build_gallery(theme)
    print("[gallery] build_gallery() returned")
    window.show()
    print("[gallery] show() called")

    # TEMPORARY checkpoints to trace the disappearance (remove after diagnosis).
    QTimer.singleShot(0, lambda: _debug_checkpoint(window, "t=0ms"))
    QTimer.singleShot(500, lambda: _debug_checkpoint(window, "t=500ms"))
    QTimer.singleShot(1500, lambda: _debug_checkpoint(window, "t=1500ms"))
    QTimer.singleShot(3000, lambda: _debug_checkpoint(window, "t=3000ms"))

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
