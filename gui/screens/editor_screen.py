"""First application screen: the AI Gaming Video Editor workspace.

A single, production-quality screen (Phase 8D) that composes the frozen widget
library into a realistic layout. It is intentionally not a dashboard: there is
no navigation, sidebar or multi-screen shell. It uses static/demo data only,
wires no signals, and never touches :mod:`gui_core` or any backend.

Input (editable form data) lives in a :class:`SettingsGroup` of
:class:`FormSection`s; output/status lives in a separate :class:`GlassCard`
("Export Status"), keeping input and output clearly separated. The only public
entry point is :func:`build_editor_screen`; every other function is private.
"""
from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout, QWidget

from gui.theme.manager import ThemeManager
from gui.widgets import (
    Checkbox,
    Dropdown,
    FormField,
    FormSection,
    GlassCard,
    NeonButton,
    ProgressBar,
    SectionHeader,
    SegmentedControl,
    SettingsGroup,
    Slider,
    StatusBadge,
    TextField,
)


def build_editor_screen(theme: ThemeManager) -> QWidget:
    """Build and return the AI Gaming Video Editor screen.

    The screen is constructed without running a Qt event loop so it can be
    asserted headlessly in tests. All visual values come from the injected
    ``theme``; data is static/demo only and no signals are wired.

    Args:
        theme: The injected theme manager (sole source of visual values).

    Returns:
        The fully composed screen as a :class:`QWidget`.
    """
    tokens = theme.tokens

    screen = QWidget()
    screen.setObjectName("EditorScreen")
    screen.setWindowTitle("AI Gaming Video Editor")

    root = QVBoxLayout(screen)
    margin = theme.tokens.spacing.xxl
    root.setContentsMargins(margin, margin, margin, margin)
    root.setSpacing(theme.tokens.spacing.xl)

    title = SectionHeader(theme, "AI Gaming Video Editor")
    title.set_divider(True)
    root.addWidget(title)

    settings = SettingsGroup(theme)
    settings.add_section(_build_project_section(theme))
    settings.add_section(_build_ai_options_section(theme))
    settings.add_section(_build_style_section(theme))
    settings.add_section(_build_intensity_section(theme))
    root.addWidget(settings)

    root.addWidget(_build_export_card(theme))
    root.addStretch(1)

    return screen


def _build_project_section(theme: ThemeManager) -> FormSection:
    """Build the 'Project Information' input section (static demo data)."""
    section = FormSection(theme, "Project Information")

    project_name = TextField(theme, text="my_clip", placeholder="Project name")
    section.add_field(FormField(theme, "Project Name", project_name))

    game = Dropdown(
        theme,
        items=["Valorant", "Fortnite", "Apex Legends", "Minecraft"],
        current=0,
        accent="cyan",
    )
    section.add_field(FormField(theme, "Game", game))

    quality = Dropdown(
        theme, items=["720p", "1080p", "1440p", "4K"], current=1, accent="cyan"
    )
    section.add_field(FormField(theme, "Output Quality", quality))

    return section


def _build_ai_options_section(theme: ThemeManager) -> FormSection:
    """Build the 'AI Options' input section of checkboxes (static demo data)."""
    section = FormSection(theme, "AI Options")
    for label, checked in (
        ("Auto Highlights", True),
        ("Auto Zoom", True),
        ("Meme Detection", True),
    ):
        box = Checkbox(theme, label, checked=checked, accent="cyan")
        section.add_field(FormField(theme, label, box))
    return section


def _build_style_section(theme: ThemeManager) -> FormSection:
    """Build the 'Editing Style' input section (SegmentedControl)."""
    section = FormSection(theme, "Editing Style")
    style = SegmentedControl(
        theme, ["Funny", "Cinematic", "Esports"], current=0, accent="purple"
    )
    section.add_field(FormField(theme, "Style", style))
    return section


def _build_intensity_section(theme: ThemeManager) -> FormSection:
    """Build the 'Intensity' input section (Slider)."""
    section = FormSection(theme, "Intensity")
    intensity = Slider(theme, minimum=0.0, maximum=1.0, value=0.5, accent="purple")
    section.add_field(FormField(theme, "Intensity", intensity))
    return section


def _build_export_card(theme: ThemeManager) -> GlassCard:
    """Build the 'Export Status' output card (outside the SettingsGroup).

    Status/output only: a StatusBadge, a ProgressBar and the primary action
    button live here. StatusBadge and ProgressBar are laid out directly (never
    wrapped in a FormField, which is for labelled form data only).
    """
    tokens = theme.tokens

    card = GlassCard(theme, glow="cyan")
    content = QWidget()
    layout = QVBoxLayout(content)
    layout.setContentsMargins(
        tokens.spacing.lg, tokens.spacing.lg, tokens.spacing.lg, tokens.spacing.lg
    )
    layout.setSpacing(tokens.spacing.md)

    header = SectionHeader(theme, "Export Status")
    header.set_divider(True)
    layout.addWidget(header)

    layout.addWidget(StatusBadge(theme, "Ready", status="success"))
    layout.addWidget(ProgressBar(theme, value=0.0, accent="cyan"))
    layout.addWidget(NeonButton(theme, "Generate Edit Plan", variant="primary", accent="cyan"))

    card.set_content(content)
    return card
