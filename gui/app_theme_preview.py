"""Dev-only visual showcase for the theme + primitive widgets.

This is **not** part of the application. It creates a QApplication, applies
the active (dark) theme via :class:`~gui.theme.manager.ThemeManager`, and
shows a minimal showcase built from the reusable widget library (Phase 8C-2
primitives plus the 8C-3 information, 8C-4 interactive and 8C-5 advanced
interactive widgets) with dummy content.

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

    from gui.widgets import (
        Checkbox,
        Dropdown,
        IconButton,
        MetaLabel,
        NeonButton,
        ProgressBar,
        SectionHeader,
        SegmentedControl,
        Slider,
        StatBlock,
        StatusBadge,
        TextField,
        ToggleSwitch,
    )

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

    # ---- Phase 8C-3: information / progress widgets ----
    info = QHBoxLayout()
    info.setSpacing(tokens.spacing.md)
    info.addWidget(StatusBadge(theme, "Ready", status="success"))
    info.addWidget(StatusBadge(theme, "Running", status="info"))
    info.addWidget(StatusBadge(theme, "Warning", status="warning"))
    info.addWidget(StatusBadge(theme, "Error", status="error"))
    info.addWidget(MetaLabel(theme, "Metadata label", role="secondary"))
    info.addStretch(1)
    root.addWidget(
        _labeled_card(theme, "Status & Text", "StatusBadge / MetaLabel", None, info)
    )

    progress = QHBoxLayout()
    progress.setSpacing(tokens.spacing.md)
    determinate = ProgressBar(theme, value=0.65, accent="cyan")
    determinate.setFixedWidth(theme.tokens.spacing.xxl * 6)
    indeterminate = ProgressBar(theme, indeterminate=True, accent="purple")
    indeterminate.setFixedWidth(theme.tokens.spacing.xxl * 6)
    progress.addWidget(determinate)
    progress.addWidget(indeterminate)
    progress.addWidget(StatBlock(theme, "Scenes", "42", subtitle="detected"))
    progress.addWidget(StatBlock(theme, "Duration", "12:04"))
    progress.addStretch(1)
    root.addWidget(
        _labeled_card(theme, "Progress & Stats", "ProgressBar / StatBlock", None, progress)
    )

    # ---- Phase 8C-4: interactive widgets ----
    interactive = QHBoxLayout()
    interactive.setSpacing(tokens.spacing.md)
    interactive.addWidget(ToggleSwitch(theme, checked=True, accent="cyan"))
    interactive.addWidget(ToggleSwitch(theme, checked=False, accent="purple"))
    interactive.addWidget(Checkbox(theme, "Enable subtitles", checked=True))
    interactive.addWidget(Checkbox(theme, "Loop", accent="blue"))
    field = TextField(theme, text="my_clip", placeholder="Output name")
    field.setFixedWidth(theme.tokens.spacing.xxl * 6)
    interactive.addWidget(field)
    interactive.addStretch(1)
    root.addWidget(
        _labeled_card(
            theme,
            "Interactive",
            "ToggleSwitch / Checkbox / TextField",
            None,
            interactive,
        )
    )

    # ---- Phase 8C-5: advanced interactive widgets ----
    advanced = QHBoxLayout()
    advanced.setSpacing(tokens.spacing.md)
    dropdown = Dropdown(
        theme, items=["720p", "1080p", "1440p", "4K"], current=1, accent="cyan"
    )
    dropdown.setFixedWidth(theme.tokens.spacing.xxl * 5)
    advanced.addWidget(dropdown)
    slider = Slider(theme, minimum=0.0, maximum=1.0, value=0.5, accent="purple")
    slider.setFixedWidth(theme.tokens.spacing.xxl * 6)
    advanced.addWidget(slider)
    advanced.addWidget(
        SegmentedControl(theme, ["Day", "Week", "Month"], current=1, accent="blue")
    )
    advanced.addStretch(1)
    root.addWidget(
        _labeled_card(
            theme,
            "Advanced",
            "Dropdown / Slider / SegmentedControl",
            None,
            advanced,
        )
    )

    root.addStretch(1)
    return window


def main() -> int:
    """Launch the themed component gallery and run the Qt event loop."""
    configure_high_dpi()

    from PySide6.QtWidgets import QApplication

    from gui.theme.manager import ThemeManager

    app = QApplication(sys.argv)

    theme = ThemeManager()
    theme.apply(app)

    window = build_gallery(theme)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
