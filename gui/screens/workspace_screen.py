"""Premium AI Gaming Video Editor workspace screen (Phase 8H, Milestone 1).

Shell only: a professional, dock-oriented editor layout composed from the
frozen widget library (:mod:`gui.widgets`). Additive -- it does not replace the
Phase 8D :func:`gui.screens.editor_screen.build_editor_screen`; both coexist.

Milestone 1 delivers static workspace regions and nothing more: a compact
toolbar strip, a left sidebar (Project / Media / Assets), a large center video
preview surface, a right inspector / AI panel, and a bottom timeline
placeholder. There is no timeline editing, AI logic, media browser, export
pipeline, or playback yet. The screen uses static/demo content, wires no
signals, and never touches :mod:`gui_core` or any backend.

Regions carry stable object names so later milestones and tests can locate them
without depending on layout internals. The only public entry point is
:func:`build_workspace_screen`; every other function is private.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from gui.theme.manager import ThemeManager
from gui.widgets import (
    GlassCard,
    IconButton,
    MetaLabel,
    NeonButton,
    SectionHeader,
    StatusBadge,
)


def build_workspace_screen(theme: ThemeManager) -> QWidget:
    """Build and return the premium editor workspace shell.

    Constructed without running a Qt event loop so it can be asserted
    headlessly in tests. All visual values come from the injected ``theme``;
    content is static/demo only and no signals are wired.

    Args:
        theme: The injected theme manager (sole source of visual values).

    Returns:
        The composed workspace shell as a :class:`QWidget`.
    """
    tokens = theme.tokens

    screen = QWidget()
    screen.setObjectName("WorkspaceScreen")
    screen.setWindowTitle("AI Gaming Video Editor \u2014 Workspace")

    root = QVBoxLayout(screen)
    root.setContentsMargins(
        tokens.spacing.md, tokens.spacing.md, tokens.spacing.md, tokens.spacing.md
    )
    root.setSpacing(tokens.spacing.md)

    root.addWidget(_build_toolbar_strip(theme))

    upper = QSplitter(Qt.Orientation.Horizontal, screen)
    upper.setObjectName("WorkspaceUpperSplitter")
    upper.setChildrenCollapsible(False)
    upper.addWidget(_build_sidebar(theme))
    upper.addWidget(_build_preview(theme))
    upper.addWidget(_build_inspector(theme))
    upper.setStretchFactor(0, 0)
    upper.setStretchFactor(1, 1)
    upper.setStretchFactor(2, 0)

    vertical = QSplitter(Qt.Orientation.Vertical, screen)
    vertical.setObjectName("WorkspaceVerticalSplitter")
    vertical.setChildrenCollapsible(False)
    vertical.addWidget(upper)
    vertical.addWidget(_build_timeline(theme))
    vertical.setStretchFactor(0, 1)
    vertical.setStretchFactor(1, 0)

    root.addWidget(vertical, 1)
    return screen


def _build_toolbar_strip(theme: ThemeManager) -> QWidget:
    """Build the compact in-screen toolbar row of icon actions (static)."""
    tokens = theme.tokens

    strip = QWidget()
    strip.setObjectName("WorkspaceToolbarStrip")
    layout = QHBoxLayout(strip)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(tokens.spacing.sm)

    # Only play.svg and spark.svg exist as icon assets today, so every tool
    # uses a verified icon; the tooltip carries the tool's meaning. Later
    # milestones can add dedicated icons without changing this structure.
    for icon_name, tip, accent in (
        ("spark", "Select", "cyan"),
        ("spark", "Cut", "cyan"),
        ("spark", "Crop", "cyan"),
        ("spark", "Text", "purple"),
        ("spark", "AI Enhance", "purple"),
    ):
        layout.addWidget(IconButton(theme, icon_name, accent=accent, tooltip=tip))

    layout.addStretch(1)

    layout.addWidget(IconButton(theme, "play", accent="cyan", tooltip="Play"))
    layout.addWidget(NeonButton(theme, "Export", variant="primary", accent="cyan"))
    return strip


def _panel_card(
    theme: ThemeManager, object_name: str, title: str, subtitle: str
) -> GlassCard:
    """Build a titled GlassCard panel with an empty, stretchable body."""
    tokens = theme.tokens

    card = GlassCard(theme, glow=None, elevation="medium")
    card.setObjectName(object_name)

    content = QWidget()
    layout = QVBoxLayout(content)
    layout.setContentsMargins(
        tokens.spacing.lg, tokens.spacing.lg, tokens.spacing.lg, tokens.spacing.lg
    )
    layout.setSpacing(tokens.spacing.md)

    header = SectionHeader(theme, title, subtitle=subtitle)
    header.set_divider(True)
    layout.addWidget(header)
    layout.addStretch(1)

    card.set_content(content)
    return card


def _build_sidebar(theme: ThemeManager) -> QWidget:
    """Build the left Project / Media / Assets sidebar (static placeholders)."""
    tokens = theme.tokens

    sidebar = QWidget()
    sidebar.setObjectName("WorkspaceSidebar")
    sidebar.setMinimumWidth(240)
    layout = QVBoxLayout(sidebar)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(tokens.spacing.md)

    layout.addWidget(
        _panel_card(theme, "WorkspaceProjectPanel", "Project", "Current session")
    )
    layout.addWidget(
        _panel_card(theme, "WorkspaceMediaPanel", "Media", "Imported clips")
    )
    layout.addWidget(
        _panel_card(theme, "WorkspaceAssetsPanel", "Assets", "Overlays & audio")
    )
    layout.addStretch(1)
    return sidebar


def _build_preview(theme: ThemeManager) -> QWidget:
    """Build the center video preview surface (static placeholder)."""
    tokens = theme.tokens

    preview = QWidget()
    preview.setObjectName("WorkspacePreview")
    layout = QVBoxLayout(preview)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(tokens.spacing.sm)

    card = GlassCard(theme, glow="cyan", elevation="high")
    card.setObjectName("WorkspacePreviewCard")
    content = QWidget()
    inner = QVBoxLayout(content)
    inner.setContentsMargins(
        tokens.spacing.lg, tokens.spacing.lg, tokens.spacing.lg, tokens.spacing.lg
    )
    inner.setSpacing(tokens.spacing.md)

    header = SectionHeader(theme, "Preview", subtitle="No clip loaded")
    header.set_divider(True)
    inner.addWidget(header)

    stage = QFrame(content)
    stage.setObjectName("WorkspacePreviewStage")
    stage.setFrameShape(QFrame.Shape.StyledPanel)
    stage.setMinimumHeight(280)
    stage_layout = QVBoxLayout(stage)
    stage_layout.setContentsMargins(0, 0, 0, 0)
    placeholder = QLabel("Video preview", stage)
    placeholder.setObjectName("WorkspacePreviewPlaceholder")
    placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
    placeholder.setFont(theme.font("caption"))
    stage_layout.addWidget(placeholder)
    inner.addWidget(stage, 1)

    card.set_content(content)
    layout.addWidget(card, 1)
    return preview


def _build_inspector(theme: ThemeManager) -> QWidget:
    """Build the right inspector / AI panel (static placeholders)."""
    tokens = theme.tokens

    inspector = QWidget()
    inspector.setObjectName("WorkspaceInspector")
    inspector.setMinimumWidth(280)
    layout = QVBoxLayout(inspector)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(tokens.spacing.md)

    ai_card = GlassCard(theme, glow="purple", elevation="medium")
    ai_card.setObjectName("WorkspaceAIPanel")
    ai_content = QWidget()
    ai_layout = QVBoxLayout(ai_content)
    ai_layout.setContentsMargins(
        tokens.spacing.lg, tokens.spacing.lg, tokens.spacing.lg, tokens.spacing.lg
    )
    ai_layout.setSpacing(tokens.spacing.md)
    ai_header = SectionHeader(theme, "AI Assistant", subtitle="Suggestions")
    ai_header.set_divider(True)
    ai_layout.addWidget(ai_header)
    ai_layout.addWidget(StatusBadge(theme, "Idle", status="info"))
    ai_layout.addWidget(MetaLabel(theme, "Model: local"))
    ai_layout.addStretch(1)
    ai_card.set_content(ai_content)
    layout.addWidget(ai_card, 1)

    props_card = _panel_card(
        theme, "WorkspacePropertiesPanel", "Properties", "Selection"
    )
    layout.addWidget(props_card, 1)
    return inspector


def _build_timeline(theme: ThemeManager) -> QWidget:
    """Build the bottom timeline placeholder (static; no editing yet)."""
    tokens = theme.tokens

    timeline = QWidget()
    timeline.setObjectName("WorkspaceTimeline")
    timeline.setMinimumHeight(160)
    layout = QVBoxLayout(timeline)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(tokens.spacing.sm)

    card = GlassCard(theme, glow=None, elevation="low")
    card.setObjectName("WorkspaceTimelineCard")
    content = QWidget()
    inner = QVBoxLayout(content)
    inner.setContentsMargins(
        tokens.spacing.lg, tokens.spacing.lg, tokens.spacing.lg, tokens.spacing.lg
    )
    inner.setSpacing(tokens.spacing.sm)

    header = SectionHeader(theme, "Timeline", subtitle="Milestone 1 placeholder")
    header.set_divider(True)
    inner.addWidget(header)

    track = QFrame(content)
    track.setObjectName("WorkspaceTimelineTrack")
    track.setFrameShape(QFrame.Shape.StyledPanel)
    track.setMinimumHeight(64)
    inner.addWidget(track, 1)

    card.set_content(content)
    layout.addWidget(card, 1)
    return timeline
