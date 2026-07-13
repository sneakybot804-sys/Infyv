"""Media workspace screen: browser + interactive preview (Phase 8H, M2).

Composes the Milestone 2 widgets into an interactive media workspace, additive
to and independent of the Milestone 1 shell and the frozen Phase 8D editor
screen. Layout: a left :class:`MediaBrowser`, a center preview surface with a
:class:`TransportBar`, and a right static details / metadata panel for the
selected media.

Interaction is UI-only: selecting a media item updates the preview subtitle and
the details panel text. There is no timeline editing, AI logic, export
pipeline, real playback, or backend; :mod:`gui_core` is never touched.

Stable object names for later integration and tests:

* ``MediaWorkspaceScreen`` -- the root widget
* ``MediaWorkspacePreview`` -- the center preview surface
* ``MediaWorkspacePreviewStage`` -- the framed preview stage placeholder
* ``MediaWorkspaceDetails`` -- the right details / metadata panel

The only public entry point is :func:`build_media_workspace_screen`.
"""
from __future__ import annotations

from typing import List

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
from gui.widgets.clip_inspector import ClipInspector
from gui.widgets.glass_card import GlassCard
from gui.widgets.media_browser import MediaBrowser
from gui.widgets.meta_label import MetaLabel
from gui.widgets.section_header import SectionHeader
from gui.widgets.timeline import Timeline
from gui.widgets.transport_bar import TransportBar

#: Static/demo media used to seed the browser (no filesystem access).
_DEMO_ITEMS: List[str] = [
    "clip_01.mp4",
    "clip_02.mp4",
    "highlight_reel.mp4",
]


class _MediaWorkspace(QWidget):
    """Internal composite wiring the browser, preview and details together.

    Kept private; :func:`build_media_workspace_screen` is the only public
    entry point. Holds references to the child widgets it must update on
    selection so the wiring stays within the screen (UI-only state).
    """

    def __init__(self, theme: ThemeManager) -> None:
        super().__init__()
        self._theme = theme
        self.setObjectName("MediaWorkspaceScreen")
        self.setWindowTitle("AI Gaming Video Editor \u2014 Media")

        tokens = theme.tokens

        root = QVBoxLayout(self)
        root.setContentsMargins(
            tokens.spacing.md, tokens.spacing.md, tokens.spacing.md, tokens.spacing.md
        )
        root.setSpacing(tokens.spacing.md)

        self._browser = MediaBrowser(theme, items=list(_DEMO_ITEMS))
        self._preview_header = SectionHeader(
            theme, "Preview", subtitle="No clip selected"
        )
        self._detail_name = MetaLabel(theme, "Name: \u2014")
        self._detail_kind = MetaLabel(theme, "Type: \u2014")
        self._detail_status = MetaLabel(theme, "Status: no selection")

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setObjectName("MediaWorkspaceSplitter")
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._browser)
        splitter.addWidget(self._build_preview())
        splitter.addWidget(self._build_details())
        splitter.addWidget(self._build_inspector())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setStretchFactor(3, 0)
        root.addWidget(splitter, 1)

        # Bottom Timeline region (additive; below the splitter).
        root.addWidget(self._build_timeline())

        # Screen-level, UI-only wiring: media selection updates preview +
        # details; timeline clip selection updates the clip inspector.
        self._browser.selection_changed.connect(self._on_selection_changed)
        self._timeline.clip_selected.connect(self._on_clip_selected)
        # A drag-move updates the clip model without re-emitting clip_selected,
        # so refresh the inspector on clip_moved to keep it in sync.
        self._timeline.clip_moved.connect(self._on_clip_moved)

    # ------------------------------------------------------------------ #
    # Region builders
    # ------------------------------------------------------------------ #
    def _build_preview(self) -> QWidget:
        """Build the center preview surface (stage placeholder + transport)."""
        tokens = self._theme.tokens

        preview = QWidget()
        preview.setObjectName("MediaWorkspacePreview")
        layout = QVBoxLayout(preview)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(tokens.spacing.sm)

        card = GlassCard(self._theme, glow="cyan", elevation="high")
        card.setObjectName("MediaWorkspacePreviewCard")
        content = QWidget()
        inner = QVBoxLayout(content)
        inner.setContentsMargins(
            tokens.spacing.lg, tokens.spacing.lg, tokens.spacing.lg, tokens.spacing.lg
        )
        inner.setSpacing(tokens.spacing.md)

        self._preview_header.set_divider(True)
        inner.addWidget(self._preview_header)

        stage = QFrame(content)
        stage.setObjectName("MediaWorkspacePreviewStage")
        stage.setFrameShape(QFrame.Shape.StyledPanel)
        stage.setMinimumHeight(280)
        stage_layout = QVBoxLayout(stage)
        stage_layout.setContentsMargins(0, 0, 0, 0)
        placeholder = QLabel("Video preview", stage)
        placeholder.setObjectName("MediaWorkspacePreviewPlaceholder")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setFont(self._theme.font("caption"))
        stage_layout.addWidget(placeholder)
        inner.addWidget(stage, 1)

        self._transport = TransportBar(self._theme)
        inner.addWidget(self._transport)

        card.set_content(content)
        layout.addWidget(card, 1)
        return preview

    def _build_details(self) -> QWidget:
        """Build the right static details / metadata panel."""
        tokens = self._theme.tokens

        details = QWidget()
        details.setObjectName("MediaWorkspaceDetails")
        details.setMinimumWidth(260)
        layout = QVBoxLayout(details)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(tokens.spacing.md)

        card = GlassCard(self._theme, glow=None, elevation="medium")
        card.setObjectName("MediaWorkspaceDetailsCard")
        content = QWidget()
        inner = QVBoxLayout(content)
        inner.setContentsMargins(
            tokens.spacing.lg, tokens.spacing.lg, tokens.spacing.lg, tokens.spacing.lg
        )
        inner.setSpacing(tokens.spacing.sm)

        header = SectionHeader(self._theme, "Details", subtitle="Selected media")
        header.set_divider(True)
        inner.addWidget(header)
        inner.addWidget(self._detail_name)
        inner.addWidget(self._detail_kind)
        inner.addWidget(self._detail_status)
        inner.addStretch(1)

        card.set_content(content)
        layout.addWidget(card, 1)
        return details

    def _build_inspector(self) -> QWidget:
        """Build the right ClipInspector region (UI-only, read-only).

        Separate from the media details panel: this reflects the *selected
        timeline clip*, not the selected media item.
        """
        tokens = self._theme.tokens

        region = QWidget()
        region.setObjectName("MediaWorkspaceInspector")
        region.setMinimumWidth(260)
        layout = QVBoxLayout(region)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(tokens.spacing.md)

        card = GlassCard(self._theme, glow=None, elevation="medium")
        card.setObjectName("MediaWorkspaceInspectorCard")
        content = QWidget()
        inner = QVBoxLayout(content)
        inner.setContentsMargins(
            tokens.spacing.lg, tokens.spacing.lg, tokens.spacing.lg, tokens.spacing.lg
        )
        inner.setSpacing(tokens.spacing.sm)

        self._clip_inspector = ClipInspector(self._theme)
        inner.addWidget(self._clip_inspector)
        inner.addStretch(1)

        card.set_content(content)
        layout.addWidget(card, 1)
        return region

    def _build_timeline(self) -> QWidget:
        """Build the bottom Timeline region (UI-only; static demo clips)."""
        tokens = self._theme.tokens

        region = QWidget()
        region.setObjectName("MediaWorkspaceTimeline")
        region.setMinimumHeight(180)
        layout = QVBoxLayout(region)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(tokens.spacing.sm)

        card = GlassCard(self._theme, glow=None, elevation="low")
        card.setObjectName("MediaWorkspaceTimelineCard")
        content = QWidget()
        inner = QVBoxLayout(content)
        inner.setContentsMargins(
            tokens.spacing.lg, tokens.spacing.lg, tokens.spacing.lg, tokens.spacing.lg
        )
        inner.setSpacing(tokens.spacing.sm)

        header = SectionHeader(self._theme, "Timeline", subtitle="Preview only")
        header.set_divider(True)
        inner.addWidget(header)

        self._timeline = Timeline(
            self._theme, duration=60.0, tracks=["Video 1", "Audio 1"]
        )
        self._timeline.set_clips(
            [
                {"track": 0, "start": 0.0, "length": 12.0, "label": "Intro"},
                {"track": 0, "start": 12.0, "length": 20.0, "label": "Gameplay"},
                {"track": 1, "start": 0.0, "length": 32.0, "label": "Music"},
            ]
        )
        inner.addWidget(self._timeline, 1)

        card.set_content(content)
        layout.addWidget(card, 1)
        return region

    # ------------------------------------------------------------------ #
    # UI-only wiring
    # ------------------------------------------------------------------ #
    def _on_selection_changed(self, index: int) -> None:
        """Update the preview subtitle and details from the selection.

        UI-only: reflects the browser's current item. A cleared selection
        (``index == -1``) resets to the empty state. No media is opened.
        """
        item = self._browser.current_item()
        if item is None:
            self._preview_header.set_subtitle("No clip selected")
            self._detail_name.set_text("Name: \u2014")
            self._detail_kind.set_text("Type: \u2014")
            self._detail_status.set_text("Status: no selection")
            return
        self._preview_header.set_subtitle(item)
        self._detail_name.set_text(f"Name: {item}")
        self._detail_kind.set_text("Type: video/mp4")
        self._detail_status.set_text("Status: ready")

    def _on_clip_selected(self, index: int) -> None:
        """Update the clip inspector from the timeline selection (UI-only).

        Reflects the timeline's currently selected clip; a cleared selection
        (``index == -1``) returns the inspector to its empty state.
        """
        self._clip_inspector.show_clip(self._timeline.selected_clip())

    def _on_clip_moved(self, index: int, new_track: int) -> None:
        """Refresh the clip inspector after a timeline clip is moved (UI-only).

        A drag-move changes the clip's track without changing the selection
        index (so :attr:`clip_selected` is not re-emitted); re-show the
        currently selected clip so the inspector reflects its new track.
        """
        self._clip_inspector.show_clip(self._timeline.selected_clip())


def build_media_workspace_screen(theme: ThemeManager) -> QWidget:
    """Build and return the interactive media workspace screen.

    Constructed without running a Qt event loop so it can be asserted
    headlessly in tests. All visual values come from the injected ``theme``;
    interaction is UI-only (selection updates preview/details) and no backend
    is involved.

    Args:
        theme: The injected theme manager (sole source of visual values).

    Returns:
        The composed media workspace as a :class:`QWidget`.
    """
    return _MediaWorkspace(theme)
