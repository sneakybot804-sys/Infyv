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
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from gui.theme.manager import ThemeManager
from gui.widgets.clip_inspector import ClipInspector
from gui.widgets.dropdown import Dropdown
from gui.widgets.glass_card import GlassCard
from gui.widgets.media_browser import MediaBrowser
from gui.widgets.meta_label import MetaLabel
from gui.widgets.navigation_sidebar import NavigationSidebar
from gui.widgets.neon_button import NeonButton
from gui.widgets.section_header import SectionHeader
from gui.widgets.status_badge import StatusBadge
from gui.widgets.text_field import TextField
from gui.widgets.timeline import Timeline
from gui.widgets.toggle_switch import ToggleSwitch
from gui.widgets.transport_bar import TransportBar

# QScrollArea is imported lazily inside _build_details to keep the top-level
# import block minimal; see the local import there.

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

        # Surface hierarchy (visual-only): the application background sits
        # under the workspace surface behind the panels, so the app reads as
        # layered depth (App background -> workspace -> panel card -> content)
        # rather than a flat field of identical panels. Token-derived; no
        # hardcoded colors, no behavior change.
        self.setStyleSheet(
            f"#MediaWorkspaceScreen {{ background: {tokens.colors.background_base}; }} "
            f"#MediaWorkspaceScreen QSplitter::handle {{ "
            f"background: transparent; }}"
        )

        self._browser = MediaBrowser(theme, items=list(_DEMO_ITEMS))
        self._browser.setMinimumWidth(240)
        self._preview_header = SectionHeader(
            theme, "Preview", subtitle="No clip selected"
        )
        self._detail_name = MetaLabel(theme, "Name: \u2014")
        self._detail_kind = MetaLabel(theme, "Type: \u2014")
        self._detail_status = MetaLabel(theme, "Status: no selection")

        handle_width = tokens.spacing.xs

        # Right column: Details stacked over the Clip Inspector, like a pro
        # editor's metadata-over-inspector column (vertical split).
        right_column = QSplitter(Qt.Orientation.Vertical)
        right_column.setObjectName("MediaWorkspaceRightSplitter")
        right_column.setChildrenCollapsible(False)
        right_column.setHandleWidth(handle_width)
        # The lower pane tabs the Clip Inspector together with the AI
        # Assistant so the AI panel reuses the existing right-column space
        # without shrinking the Details or Inspector panels.
        right_tabs = QTabWidget()
        right_tabs.setObjectName("MediaWorkspaceRightTabs")
        right_tabs.addTab(self._build_inspector(), "Inspector")
        right_tabs.addTab(self._build_ai_assistant(), "AI")
        right_tabs.setStyleSheet(
            f"#MediaWorkspaceRightTabs::pane {{ border: none; }} "
            f"#MediaWorkspaceRightTabs QTabBar::tab {{ "
            f"background: {tokens.colors.surface}; "
            f"color: {tokens.colors.text_muted}; "
            f"border: 1px solid {tokens.colors.border}; "
            f"border-top-left-radius: {tokens.radius.sm}px; "
            f"border-top-right-radius: {tokens.radius.sm}px; "
            f"padding: {tokens.spacing.xs}px {tokens.spacing.md}px; "
            f"margin-right: {tokens.spacing.xxs}px; }} "
            f"#MediaWorkspaceRightTabs QTabBar::tab:selected {{ "
            f"color: {tokens.colors.accent_cyan}; "
            f"border: 1px solid {tokens.colors.accent_cyan}; }}"
        )

        right_column.addWidget(self._build_details())
        right_column.addWidget(right_tabs)
        right_column.setStretchFactor(0, 0)
        right_column.setStretchFactor(1, 1)
        right_column.setSizes([320, 520])

        # Top editing area: sidebar | large preview | right column.
        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setObjectName("MediaWorkspaceSplitter")
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(handle_width)
        self._sidebar = NavigationSidebar(self._theme)
        splitter.addWidget(self._sidebar)
        splitter.addWidget(self._browser)
        splitter.addWidget(self._build_preview())
        splitter.addWidget(right_column)
        splitter.setStretchFactor(0, 0)  # navigation rail
        splitter.setStretchFactor(1, 0)  # media browser
        splitter.setStretchFactor(2, 1)  # preview grows
        splitter.setStretchFactor(3, 0)  # right column
        splitter.setSizes([240, 260, 940, 300])

        # Outer vertical split: the editing area over a generous, resizable
        # Timeline region (the timeline is a first-class region, not a strip).
        main_split = QSplitter(Qt.Orientation.Vertical, self)
        main_split.setObjectName("MediaWorkspaceMainSplitter")
        main_split.setChildrenCollapsible(False)
        main_split.setHandleWidth(handle_width)
        main_split.addWidget(splitter)
        main_split.addWidget(self._build_timeline())
        main_split.setStretchFactor(0, 1)
        main_split.setStretchFactor(1, 0)
        main_split.setSizes([620, 300])
        root.addWidget(main_split, 1)

        # Screen-level, UI-only wiring: media selection updates preview +
        # details; timeline clip selection updates the clip inspector.
        self._browser.selection_changed.connect(self._on_selection_changed)
        self._timeline.clip_selected.connect(self._on_clip_selected)
        # A drag-move updates the clip model without re-emitting clip_selected,
        # so refresh the inspector on clip_moved to keep it in sync.
        self._timeline.clip_moved.connect(self._on_clip_moved)
        # A trim likewise updates start/length without re-emitting
        # clip_selected, so refresh the inspector on clip_trimmed too.
        self._timeline.clip_trimmed.connect(self._on_clip_trimmed)
        # Playback wiring (Milestone 9): the transport drives the timeline
        # playhead, and the timeline keeps the transport in sync.
        self._transport.play_requested.connect(self._timeline.play)
        self._transport.pause_requested.connect(self._timeline.pause)
        self._transport.stop_requested.connect(self._timeline.stop)
        self._timeline.playback_state_changed.connect(
            self._on_playback_state_changed
        )
        self._timeline.playhead_changed.connect(self._on_playhead_changed)

    # ------------------------------------------------------------------ #
    # Region builders
    # ------------------------------------------------------------------ #
    def _build_preview(self) -> QWidget:
        """Build the center preview surface (stage placeholder + transport)."""
        tokens = self._theme.tokens

        preview = QWidget()
        preview.setObjectName("MediaWorkspacePreview")
        preview.setMinimumWidth(420)
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

        # --- Phase 10F: viewer toolbar (decorative, wired to nothing) --- #
        viewer_toolbar = QWidget(content)
        viewer_toolbar.setObjectName("MediaWorkspaceViewerToolbar")
        vt_row = QHBoxLayout(viewer_toolbar)
        vt_row.setContentsMargins(
            tokens.spacing.sm, tokens.spacing.xs, tokens.spacing.sm, tokens.spacing.xs
        )
        vt_row.setSpacing(tokens.spacing.sm)
        zoom_dropdown = Dropdown(
            self._theme,
            items=["Fit", "25%", "50%", "100%", "200%"],
            current=0,
            accent="cyan",
        )
        zoom_dropdown.setObjectName("MediaWorkspaceViewerZoom")
        vt_row.addWidget(zoom_dropdown, 0)
        fit_btn = NeonButton(self._theme, "Fit", variant="ghost", accent="cyan")
        fit_btn.setObjectName("MediaWorkspaceViewerFit")
        vt_row.addWidget(fit_btn, 0)
        full_btn = NeonButton(self._theme, "100%", variant="ghost", accent="cyan")
        full_btn.setObjectName("MediaWorkspaceViewerHundred")
        vt_row.addWidget(full_btn, 0)
        vt_row.addStretch(1)
        safe_toggle = ToggleSwitch(self._theme, checked=False, accent="cyan")
        safe_toggle.setObjectName("MediaWorkspaceViewerSafeToggle")
        vt_row.addWidget(MetaLabel(self._theme, "Safe", role="muted", style="caption"), 0)
        vt_row.addWidget(safe_toggle, 0)
        grid_toggle = ToggleSwitch(self._theme, checked=False, accent="purple")
        grid_toggle.setObjectName("MediaWorkspaceViewerGridToggle")
        vt_row.addWidget(MetaLabel(self._theme, "Grid", role="muted", style="caption"), 0)
        vt_row.addWidget(grid_toggle, 0)
        shot_btn = NeonButton(
            self._theme, "Screenshot", variant="ghost", accent="cyan"
        )
        shot_btn.setObjectName("MediaWorkspaceViewerScreenshot")
        vt_row.addWidget(shot_btn, 0)
        fs_btn = NeonButton(
            self._theme, "Fullscreen", variant="ghost", accent="cyan"
        )
        fs_btn.setObjectName("MediaWorkspaceViewerFullscreen")
        vt_row.addWidget(fs_btn, 0)
        viewer_toolbar.setStyleSheet(
            f"#MediaWorkspaceViewerToolbar {{ "
            f"background: {tokens.colors.surface}; "
            f"border: 1px solid {tokens.colors.border}; "
            f"border-radius: {tokens.radius.md}px; }}"
        )
        inner.addWidget(viewer_toolbar)

        # Cinematic preview stage: a deep gradient backdrop with a soft glass
        # border, a glass HUD overlay (timecode + badges), a subtle safe-area
        # guide, and a centered premium empty state.
        stage = QFrame(content)
        stage.setObjectName("MediaWorkspacePreviewStage")
        stage.setFrameShape(QFrame.Shape.StyledPanel)
        stage.setMinimumHeight(360)
        c = tokens.colors
        stage_radius = tokens.radius.lg
        stage.setStyleSheet(
            f"#MediaWorkspacePreviewStage {{ "
            f"background: qlineargradient(x1:0, y1:0, x2:0, y2:1, "
            f"stop:0 {c.background_base}, stop:1 {c.background_deep}); "
            f"border: 1px solid {c.glass_border}; "
            f"border-radius: {stage_radius}px; }}"
        )
        stage_layout = QVBoxLayout(stage)
        stage_layout.setContentsMargins(
            tokens.spacing.md, tokens.spacing.md, tokens.spacing.md, tokens.spacing.md
        )
        stage_layout.setSpacing(tokens.spacing.sm)

        # Top glass HUD: timecode (left) + resolution / FPS / zoom badges
        # (right). Decorative chrome; additive object names only.
        hud = QWidget(stage)
        hud.setObjectName("MediaWorkspacePreviewHud")
        hud.setStyleSheet(
            f"#MediaWorkspacePreviewHud {{ "
            f"background: {c.glass_fill}; "
            f"border: 1px solid {c.glass_border}; "
            f"border-radius: {tokens.radius.md}px; }}"
        )
        hud_row = QHBoxLayout(hud)
        hud_row.setContentsMargins(
            tokens.spacing.md, tokens.spacing.xs, tokens.spacing.md, tokens.spacing.xs
        )
        hud_row.setSpacing(tokens.spacing.sm)

        timecode = QLabel("00:00:00:00", hud)
        timecode.setObjectName("MediaWorkspacePreviewTimecode")
        timecode.setFont(self._theme.font("mono"))
        timecode.setStyleSheet(
            f"#MediaWorkspacePreviewTimecode {{ color: {c.accent_cyan}; "
            f"background: transparent; }}"
        )
        hud_row.addWidget(timecode)
        hud_row.addStretch(1)

        badge_qss = (
            "{selector} { color: %s; background: %s; "
            "border: 1px solid %s; border-radius: %dpx; "
            "padding: %dpx %dpx; }"
            % (
                c.text_secondary,
                c.surface_overlay,
                c.glass_border,
                tokens.radius.sm,
                tokens.spacing.xxs,
                tokens.spacing.sm,
            )
        )
        for text, name in (
            ("1920\u00d71080", "MediaWorkspacePreviewResBadge"),
            ("30 fps", "MediaWorkspacePreviewFpsBadge"),
            ("100%", "MediaWorkspacePreviewZoomBadge"),
            ("Ready", "MediaWorkspacePreviewStatusBadge"),
        ):
            badge = QLabel(text, hud)
            badge.setObjectName(name)
            badge.setFont(self._theme.font("caption"))
            badge.setStyleSheet(
                badge_qss.replace("{selector}", f"#{name}")
            )
            hud_row.addWidget(badge)

        stage_layout.addWidget(hud)

        # Decorative viewer overlay guides: a rule-of-thirds / safe-area frame
        # and a center crosshair (subtle, wired to nothing).
        safe_area = QFrame(stage)
        safe_area.setObjectName("MediaWorkspacePreviewSafeArea")
        safe_area.setStyleSheet(
            f"#MediaWorkspacePreviewSafeArea {{ background: transparent; "
            f"border: 1px dashed {c.glass_border}; "
            f"border-radius: {tokens.radius.sm}px; }}"
        )
        crosshair = QFrame(safe_area)
        crosshair.setObjectName("MediaWorkspacePreviewCrosshair")
        crosshair.setFixedHeight(1)
        crosshair.setStyleSheet(
            f"#MediaWorkspacePreviewCrosshair {{ "
            f"background: {c.glass_border}; border: none; }}"
        )
        safe_layout = QVBoxLayout(safe_area)
        safe_layout.setContentsMargins(0, 0, 0, 0)
        safe_layout.addStretch(1)
        safe_layout.addWidget(crosshair)
        safe_layout.addStretch(1)
        stage_layout.addWidget(safe_area, 1)

        # Centered premium empty state (keeps the existing object name / type).
        stage_layout.addStretch(1)
        placeholder = QLabel("No clip selected", stage)
        placeholder.setObjectName("MediaWorkspacePreviewPlaceholder")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setFont(self._theme.font("h3"))
        placeholder.setStyleSheet(
            f"#MediaWorkspacePreviewPlaceholder {{ color: {c.text_muted}; "
            f"background: transparent; }}"
        )
        stage_layout.addWidget(placeholder)

        hint = QLabel("Select a clip to preview", stage)
        hint.setObjectName("MediaWorkspacePreviewHint")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setFont(self._theme.font("caption"))
        hint.setStyleSheet(
            f"#MediaWorkspacePreviewHint {{ color: {c.text_disabled}; "
            f"background: transparent; }}"
        )
        stage_layout.addWidget(hint)
        stage_layout.addStretch(2)

        inner.addWidget(stage, 1)

        self._transport = TransportBar(self._theme)
        inner.addWidget(self._transport)

        # --- Phase 10F: bottom player toolbar (decorative caption strip) --- #
        player_toolbar = QWidget(content)
        player_toolbar.setObjectName("MediaWorkspacePlayerToolbar")
        pt_row = QHBoxLayout(player_toolbar)
        pt_row.setContentsMargins(
            tokens.spacing.md, tokens.spacing.xs, tokens.spacing.md, tokens.spacing.xs
        )
        pt_row.setSpacing(tokens.spacing.md)
        for text, name in (
            ("00:00:00", "MediaWorkspacePlayerCurrentTime"),
            ("/ 00:00:32", "MediaWorkspacePlayerDuration"),
            ("Zoom 100%", "MediaWorkspacePlayerZoom"),
            ("Speed 1.0x", "MediaWorkspacePlayerSpeed"),
            ("Loop", "MediaWorkspacePlayerLoop"),
            ("Viewer: Ready", "MediaWorkspacePlayerStatus"),
            ("Quality: Full", "MediaWorkspacePlayerQuality"),
        ):
            detail = MetaLabel(self._theme, text, role="muted", style="caption")
            detail.setObjectName(name)
            pt_row.addWidget(detail, 0)
            if name == "MediaWorkspacePlayerDuration":
                pt_row.addStretch(1)
        player_toolbar.setStyleSheet(
            f"#MediaWorkspacePlayerToolbar {{ "
            f"background: {tokens.colors.surface}; "
            f"border: 1px solid {tokens.colors.border}; "
            f"border-radius: {tokens.radius.md}px; }}"
        )
        inner.addWidget(player_toolbar)

        # --- Phase 10F: viewer footer (decorative badge strip) --- #
        viewer_footer = QWidget(content)
        viewer_footer.setObjectName("MediaWorkspaceViewerFooter")
        vf_row = QHBoxLayout(viewer_footer)
        vf_row.setContentsMargins(0, 0, 0, 0)
        vf_row.setSpacing(tokens.spacing.xs)
        for text, status, name in (
            ("1920\u00d71080", "neutral", "MediaWorkspaceFooterResolution"),
            ("Rec.709", "neutral", "MediaWorkspaceFooterColorSpace"),
            ("Proxy Off", "warning", "MediaWorkspaceFooterProxy"),
            ("GPU Decode", "success", "MediaWorkspaceFooterGpu"),
        ):
            badge = StatusBadge(self._theme, text, status=status)
            badge.setObjectName(name)
            vf_row.addWidget(badge, 0)
        vf_row.addStretch(1)
        inner.addWidget(viewer_footer)

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

        # Secondary panel: a flatter elevation so the primary panels
        # (Preview / Inspector / AI / Timeline) read as the dominant surfaces.
        card = GlassCard(self._theme, glow=None, elevation="low")
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

        # --- Phase 10H: professional information dashboard (decorative) --- #
        # A scrollable body of read-only metadata sections. The three frozen
        # detail MetaLabels (self._detail_name / _detail_kind / _detail_status)
        # remain the General section's rows, so selection wiring is unchanged.
        from PySide6.QtWidgets import QScrollArea

        body = QScrollArea(details)
        body.setObjectName("MediaWorkspaceDetailsBody")
        body.setWidgetResizable(True)
        body.setFrameShape(QFrame.Shape.NoFrame)
        body_container = QWidget()
        body_container.setObjectName("MediaWorkspaceDetailsBodyContainer")
        body_layout = QVBoxLayout(body_container)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(tokens.spacing.md)

        def _section(title: str, rows) -> None:
            """Append a decorative metadata section (header + glass card).

            ``rows`` is a sequence of either an existing MetaLabel widget (kept
            as-is) or a (key, value) pair rendered as a new MetaLabel row.
            """
            sec_header = SectionHeader(self._theme, title)
            sec_header.setObjectName("MediaWorkspaceDetailsSection")
            sec_header.set_divider(True)
            body_layout.addWidget(sec_header)

            group = QFrame(body_container)
            group.setObjectName("MediaWorkspaceDetailsGroup")
            group.setFrameShape(QFrame.Shape.StyledPanel)
            group_layout = QVBoxLayout(group)
            group_layout.setContentsMargins(
                tokens.spacing.md, tokens.spacing.sm,
                tokens.spacing.md, tokens.spacing.sm,
            )
            group_layout.setSpacing(tokens.spacing.xxs)
            for row in rows:
                if isinstance(row, tuple):
                    label = MetaLabel(
                        self._theme,
                        f"{row[0]}: {row[1]}",
                        role="muted",
                        style="body_small",
                    )
                    label.setObjectName("MediaWorkspaceDetailsRow")
                    group_layout.addWidget(label)
                else:
                    group_layout.addWidget(row)
            body_layout.addWidget(group)

        # General reuses the frozen detail MetaLabels (unchanged identity).
        _section(
            "General",
            (self._detail_name, self._detail_kind, self._detail_status,
             ("Track", "\u2014")),
        )
        _section(
            "File",
            (("Size", "\u2014"), ("Created", "\u2014"), ("Modified", "\u2014")),
        )
        _section(
            "Video",
            (("Resolution", "1920\u00d71080"), ("FPS", "60"),
             ("Codec", "H.264"), ("Bitrate", "\u2014"),
             ("Frame Count", "\u2014")),
        )
        _section(
            "Audio",
            (("Channels", "Stereo"), ("Sample Rate", "48 kHz"),
             ("Codec", "AAC")),
        )
        _section(
            "Timeline",
            (("Duration", "00:00:00"), ("In", "\u2014"), ("Out", "\u2014")),
        )

        # AI Analysis: status badges instead of plain rows.
        ai_header = SectionHeader(self._theme, "AI Analysis")
        ai_header.setObjectName("MediaWorkspaceDetailsSection")
        ai_header.set_divider(True)
        body_layout.addWidget(ai_header)
        ai_group = QFrame(body_container)
        ai_group.setObjectName("MediaWorkspaceDetailsGroup")
        ai_group.setFrameShape(QFrame.Shape.StyledPanel)
        ai_layout = QVBoxLayout(ai_group)
        ai_layout.setContentsMargins(
            tokens.spacing.md, tokens.spacing.sm,
            tokens.spacing.md, tokens.spacing.sm,
        )
        ai_layout.setSpacing(tokens.spacing.xs)
        for text, status in (
            ("AI Status: Idle", "info"),
            ("Scene Count: 0", "neutral"),
            ("Highlight Count: 0", "neutral"),
            ("OCR: Off", "warning"),
            ("Audio Analysis: Off", "warning"),
        ):
            badge = StatusBadge(self._theme, text, status=status)
            badge.setObjectName("MediaWorkspaceDetailsAiBadge")
            ai_layout.addWidget(badge)
        body_layout.addWidget(ai_group)

        body_layout.addStretch(1)
        body.setWidget(body_container)
        inner.addWidget(body, 1)

        # Object-name-scoped, token-derived dashboard styling.
        c = tokens.colors
        body.setStyleSheet(
            f"#MediaWorkspaceDetailsBody {{ background: transparent; "
            f"border: none; }} "
            f"#MediaWorkspaceDetailsBodyContainer {{ background: transparent; }} "
            f"QScrollBar:vertical {{ background: transparent; "
            f"width: {tokens.spacing.sm}px; margin: 0px; }} "
            f"QScrollBar::handle:vertical {{ background: {c.surface_overlay}; "
            f"border-radius: {tokens.radius.sm}px; "
            f"min-height: {tokens.spacing.xl}px; }} "
            f"QScrollBar::handle:vertical:hover {{ background: {c.accent_cyan}; }} "
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ "
            f"height: 0px; }} "
            f"QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ "
            f"background: transparent; }}"
        )
        group_qss = (
            f"#MediaWorkspaceDetailsGroup {{ background: {c.surface_overlay}; "
            f"border: 1px solid {c.border}; "
            f"border-radius: {tokens.radius.md}px; }} "
            f"#MediaWorkspaceDetailsRow {{ background: transparent; }} "
            f"#MediaWorkspaceDetailsAiBadge {{ background: transparent; }}"
        )
        for grp in body_container.findChildren(QFrame):
            if grp.objectName() == "MediaWorkspaceDetailsGroup":
                grp.setStyleSheet(group_qss)

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

    def _build_ai_assistant(self) -> QWidget:
        """Build the right-side AI Assistant panel (UI-only placeholders).

        A decorative professional AI copilot panel: header, prompt field,
        suggested-action buttons, AI pipeline-status chips, recent tasks and
        smart recommendations. Every control is wired to nothing (no backend,
        no AI, no signals); new object names only.
        """
        tokens = self._theme.tokens
        c = tokens.colors

        region = QWidget()
        region.setObjectName("MediaWorkspaceAiAssistant")
        region.setMinimumWidth(260)
        layout = QVBoxLayout(region)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(tokens.spacing.md)

        card = GlassCard(self._theme, glow="purple", elevation="medium")
        card.setObjectName("MediaWorkspaceAiAssistantCard")
        content = QWidget()
        inner = QVBoxLayout(content)
        inner.setContentsMargins(
            tokens.spacing.lg, tokens.spacing.lg, tokens.spacing.lg, tokens.spacing.lg
        )
        inner.setSpacing(tokens.spacing.sm)

        header = SectionHeader(
            self._theme, "AI Assistant", subtitle="Smart editing copilot"
        )
        header.setObjectName("MediaWorkspaceAiHeader")
        header.set_badge("Beta", accent="purple")
        header.set_divider(True)
        inner.addWidget(header)

        # Prompt input + Ask affordance (placeholders; wired to nothing).
        self._ai_prompt = TextField(
            self._theme, placeholder="Ask the AI to edit\u2026"
        )
        self._ai_prompt.setObjectName("MediaWorkspaceAiPrompt")
        inner.addWidget(self._ai_prompt)
        ask = NeonButton(self._theme, "Ask AI", variant="primary", accent="purple")
        ask.setObjectName("MediaWorkspaceAiAsk")
        inner.addWidget(ask)

        # Suggested Actions grid of ghost buttons (decorative).
        actions_header = SectionHeader(self._theme, "Suggested Actions")
        actions_header.setObjectName("MediaWorkspaceAiSection")
        inner.addWidget(actions_header)
        actions_wrap = QWidget(content)
        actions_wrap.setObjectName("MediaWorkspaceAiActions")
        actions_grid = QVBoxLayout(actions_wrap)
        actions_grid.setContentsMargins(0, 0, 0, 0)
        actions_grid.setSpacing(tokens.spacing.xs)
        action_labels = (
            "Auto Edit", "Generate Highlights", "Generate Captions",
            "Clean Audio", "Create Thumbnail", "Smart Crop",
            "Remove Silence", "Enhance Voice", "Color Grade",
        )
        pair_row = None
        for index, label in enumerate(action_labels):
            if index % 2 == 0:
                pair_row = QHBoxLayout()
                pair_row.setContentsMargins(0, 0, 0, 0)
                pair_row.setSpacing(tokens.spacing.xs)
                actions_grid.addLayout(pair_row)
            btn = NeonButton(self._theme, label, variant="ghost", accent="cyan")
            btn.setObjectName("MediaWorkspaceAiAction")
            pair_row.addWidget(btn)
        inner.addWidget(actions_wrap)

        # AI Pipeline Status chips (decorative).
        status_header = SectionHeader(self._theme, "AI Pipeline Status")
        status_header.setObjectName("MediaWorkspaceAiSection")
        inner.addWidget(status_header)
        status_wrap = QWidget(content)
        status_wrap.setObjectName("MediaWorkspaceAiStatus")
        status_row = QVBoxLayout(status_wrap)
        status_row.setContentsMargins(0, 0, 0, 0)
        status_row.setSpacing(tokens.spacing.xxs)
        for text, status in (
            ("Highlight Detection: Idle", "info"),
            ("OCR: Idle", "neutral"),
            ("Audio Analysis: Idle", "neutral"),
            ("Subtitle Generator: Idle", "neutral"),
            ("Export Assistant: Idle", "warning"),
        ):
            badge = StatusBadge(self._theme, text, status=status)
            badge.setObjectName("MediaWorkspaceAiStatusBadge")
            status_row.addWidget(badge)
        inner.addWidget(status_wrap)

        # Recent AI Tasks + Smart Recommendations (decorative label rows).
        recent_header = SectionHeader(self._theme, "Recent AI Tasks")
        recent_header.setObjectName("MediaWorkspaceAiSection")
        inner.addWidget(recent_header)
        for text in (
            "\u2014 No tasks yet",
            "Highlights will appear here",
            "Captions will appear here",
        ):
            row = MetaLabel(self._theme, text, role="muted", style="body_small")
            row.setObjectName("MediaWorkspaceAiRecent")
            inner.addWidget(row)

        rec_header = SectionHeader(self._theme, "Smart Recommendations")
        rec_header.setObjectName("MediaWorkspaceAiSection")
        inner.addWidget(rec_header)
        for text in (
            "Try Auto Edit for a quick cut",
            "Generate captions for accessibility",
            "Clean audio to reduce background noise",
        ):
            row = MetaLabel(self._theme, text, role="muted", style="caption")
            row.setObjectName("MediaWorkspaceAiRecommendation")
            inner.addWidget(row)

        inner.addStretch(1)

        # Object-name-scoped, token-derived styling (glass sub-panels).
        for wrap in (actions_wrap, status_wrap):
            wrap.setStyleSheet(
                f"#{wrap.objectName()} {{ background: {c.surface_overlay}; "
                f"border: 1px solid {c.border}; "
                f"border-radius: {tokens.radius.md}px; }}"
            )

        card.set_content(content)
        layout.addWidget(card, 1)
        return region

    def _build_timeline(self) -> QWidget:
        """Build the bottom Timeline region (UI-only; static demo clips)."""
        tokens = self._theme.tokens

        region = QWidget()
        region.setObjectName("MediaWorkspaceTimeline")
        region.setMinimumHeight(220)
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

    def _on_clip_trimmed(self, index: int, start: float, length: float) -> None:
        """Refresh the clip inspector after a timeline clip is trimmed (UI-only).

        An edge trim changes the clip's start/length without changing the
        selection index (so :attr:`clip_selected` is not re-emitted); re-show
        the currently selected clip so the inspector reflects its new bounds.
        """
        self._clip_inspector.show_clip(self._timeline.selected_clip())

    def _on_playback_state_changed(self, state: str) -> None:
        """Mirror the timeline transport state onto the TransportBar (UI-only)."""
        self._transport.set_state(state)

    def _on_playhead_changed(self, seconds: float) -> None:
        """Reflect the timeline playhead on the TransportBar's seek position.

        Normalizes the playhead time to the timeline duration; set_position
        clamps and does not re-emit seek_requested, so there is no loop.
        """
        duration = self._timeline.duration()
        fraction = seconds / duration if duration > 0 else 0.0
        self._transport.set_position(fraction)


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
