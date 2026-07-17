"""Media workspace screen: browser + interactive preview (Phase 8H, M2).

Composes the Milestone 2 widgets into an interactive media workspace, additive
to and independent of the Milestone 1 shell and the frozen Phase 8D editor
screen. Layout: a left :class:`MediaBrowser`, a center preview surface with a
:class:`TransportBar`, and a right static details / metadata panel for the
selected media.

Interaction is UI-only by default: selecting a media item updates the preview
subtitle and the details panel text. There is no timeline editing, AI logic,
export pipeline or real playback.

Backend integration is optional and lives in this screen (the sole owner of
the MediaBrowser). When a :class:`~gui.integration.workflow_controller.
WorkflowController` is injected, the browser's ``selection_changed`` drives
``controller.select_video`` and the screen reflects the authoritative
``ProjectState`` read back from the controller. When no controller is given
the screen stays purely UI-only and never touches :mod:`gui_core`.

Stable object names for later integration and tests:

* ``MediaWorkspaceScreen`` -- the root widget
* ``MediaWorkspacePreview`` -- the center preview surface
* ``MediaWorkspacePreviewStage`` -- the framed preview stage placeholder
* ``MediaWorkspaceDetails`` -- the right details / metadata panel

The only public entry point is :func:`build_media_workspace_screen`.
"""
from __future__ import annotations

from typing import List

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPixmap
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
from gui.widgets.dropdown import Dropdown
from gui.widgets.glass_card import GlassCard
from gui.widgets.media_browser import MediaBrowser
from gui.widgets.meta_label import MetaLabel
from gui.widgets.navigation_sidebar import NavigationSidebar
from PySide6.QtWidgets import QGridLayout, QScrollArea, QSizePolicy
from gui.widgets.neon_button import NeonButton
from gui.widgets.progress_bar import ProgressBar
from gui.widgets.section_header import SectionHeader
from gui.widgets.slider import Slider
from gui.widgets.status_badge import StatusBadge
from gui.widgets.text_field import TextField
from gui.widgets.timeline import Timeline
from gui.widgets.toggle_switch import ToggleSwitch
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

    Args:
        theme: Injected theme manager (sole source of visual values).
        controller: Optional interactive workflow controller. When provided,
            the screen becomes the integration point that owns its
            MediaBrowser: browser selection drives ``select_video`` and the
            screen reflects the ``ProjectState`` read back from the controller.
            When ``None`` the screen stays purely UI-only (``gui_core`` is
            never touched), preserving the original behavior for every
            existing caller and test.
    """

    def __init__(self, theme: ThemeManager, controller=None) -> None:
        super().__init__()
        self._theme = theme
        # Optional backend surface. None keeps the screen UI-only; when set it
        # is the single interactive write/read surface (WorkflowController).
        self._controller = controller
        # Selected media path for real playback frame decoding (None until a
        # backend video selection resolves). Decoding is owned by the backend
        # FFmpegService via the controller; the screen only requests frames.
        self._media_path = None
        # Qt Multimedia audio layer (created lazily on first play). Kept None
        # when QtMultimedia is unavailable so the screen stays video-only.
        self._audio_player = None
        self._audio_output = None
        self._audio_loaded_for = None
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

        # MediaBrowser: fully constructed with all frozen APIs and signals
        # intact. Parented to the screen but hidden (the same pattern as the
        # Details / Inspector / AI hosts below): it is intentionally NOT in
        # the splitter, so its zero-size hidden slot can never corrupt the
        # sidebar's geometry, yet as a proper child it remains discoverable
        # via findChildren and its selection_changed wiring stays live. A
        # future milestone surfaces it when the Media nav item is activated.
        self._browser = MediaBrowser(theme, items=list(_DEMO_ITEMS))
        self._browser.setParent(self)
        self._browser.setVisible(False)
        self._browser.setMinimumWidth(240)
        self._preview_header = SectionHeader(
            theme, "Preview", subtitle="No clip selected"
        )
        self._detail_name = MetaLabel(theme, "Name: \u2014")
        self._detail_kind = MetaLabel(theme, "Type: \u2014")
        self._detail_status = MetaLabel(theme, "Status: no selection")

        handle_width = tokens.spacing.xs

        # Right column (unified stream): a single, seamless top-to-bottom
        # scroll region replacing the previous Details-over-(Inspector/AI
        # tabs) splitter. The nested layers were crushing vertical space and
        # clipping against the timeline bounds; a single master QScrollArea
        # gives one uniform stream instead.
        #
        # IMPORTANT (wiring preservation): the frozen Details labels
        # (_detail_name/_kind/_status) and the ClipInspector / AI panels are
        # still constructed here so every existing signal handler
        # (_on_selection_changed, _on_clip_selected/_moved/_trimmed) keeps a
        # live target. The Details / Inspector / AI panels are built and
        # parented to this screen but hidden, so their child widgets (notably
        # self._clip_inspector) stay alive and connected without appearing in
        # the visible stream.
        self._details_host = self._build_details()
        self._details_host.setParent(self)
        self._details_host.setVisible(False)
        self._inspector_host = self._build_inspector()
        self._inspector_host.setParent(self)
        self._inspector_host.setVisible(False)
        self._ai_host = self._build_ai_assistant()
        self._ai_host.setParent(self)
        self._ai_host.setVisible(False)

        right_column = self._build_right_stream()
        right_column.setObjectName("MediaWorkspaceRightColumn")
        # Hard width cap: prevents the right column from absorbing surplus
        # horizontal space when the window is maximised on a wide monitor.
        right_column.setFixedWidth(300)

        # Top editing area: sidebar | preview | right column.
        # The MediaBrowser is intentionally NOT added to this splitter in M2
        # (see comment above); it remains a hidden child of the screen so its
        # absence never creates an ambiguous zero-size slot that corrupts the
        # sidebar.
        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setObjectName("MediaWorkspaceSplitter")
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(handle_width)

        self._sidebar = NavigationSidebar(self._theme)
        # Fixed horizontal / Expanding vertical: the sidebar never shrinks
        # below its setFixedWidth(240) and always fills the vertical space.
        # setFixedWidth here mirrors the value set inside NavigationSidebar
        # itself; the redundant call on the outer widget ensures the splitter
        # geometry engine sees the constraint at the pane level too.
        self._sidebar.setFixedWidth(240)
        self._sidebar.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding
        )
        splitter.addWidget(self._sidebar)
        splitter.addWidget(self._build_preview())
        splitter.addWidget(right_column)
        splitter.setCollapsible(0, False)  # sidebar must never collapse
        splitter.setCollapsible(1, False)  # preview must never collapse
        splitter.setCollapsible(2, False)  # right column must never collapse
        splitter.setStretchFactor(0, 0)    # sidebar: fixed at 240px
        splitter.setStretchFactor(1, 1)    # preview: absorbs ALL spare space
        splitter.setStretchFactor(2, 0)    # right column: fixed at 300px
        # setSizes is a one-time layout hint. The true constraints are the
        # setFixedWidth calls on sidebar (240px) and right_column (300px);
        # those survive maximise / resize events where setSizes does not.
        splitter.setSizes([240, 1380, 300])

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

        # Screen-level wiring: media selection updates preview + details;
        # timeline clip selection updates the clip inspector. When a
        # WorkflowController is injected, selection additionally drives the
        # backend via _on_selection_changed (see below); otherwise it stays
        # UI-only. The single connection covers both modes.
        self._browser.selection_changed.connect(self._on_selection_changed)

        # Phase-execution integration: observe the controller's phase
        # lifecycle signals and reflect run state into the existing Preview
        # HUD status label. Connected only when a controller is present, so
        # UI-only construction is unaffected. Delivery is on the GUI thread
        # (the controller uses queued connections for background outcomes).
        if self._controller is not None:
            self._controller.phase_started.connect(self._on_phase_started)
            self._controller.phase_completed.connect(self._on_phase_completed)
            self._controller.phase_failed.connect(self._on_phase_failed)
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
        # Audio playback (Qt Multimedia), connected additively to the same
        # transport signals so audio follows the existing controls and stays
        # synchronized to the timeline playhead (no second playback clock).
        self._transport.play_requested.connect(self._on_audio_play)
        self._transport.pause_requested.connect(self._on_audio_pause)
        self._transport.stop_requested.connect(self._on_audio_stop)
        self._transport.seek_requested.connect(self._on_audio_seek)
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
        # Layout: [Zoom dropdown] ----stretch---- [Safe | toggle] [Grid | toggle]
        #         [Screenshot] [Fullscreen]
        # The Fit and 100% NeonButtons that previously sat next to the dropdown
        # duplicated its own "Fit" and "100%" options and caused the double-Fit
        # visual artifact. Removed; the dropdown is the sole zoom control.
        viewer_toolbar = QWidget(content)
        viewer_toolbar.setObjectName("MediaWorkspaceViewerToolbar")
        viewer_toolbar.setMinimumHeight(36)
        vt_row = QHBoxLayout(viewer_toolbar)
        vt_row.setContentsMargins(
            tokens.spacing.sm, tokens.spacing.sm, tokens.spacing.sm, tokens.spacing.sm
        )
        vt_row.setSpacing(tokens.spacing.sm)

        # Left group: zoom preset selector.
        zoom_dropdown = Dropdown(
            self._theme,
            items=["Fit", "25%", "50%", "100%", "200%"],
            current=0,
            accent="cyan",
        )
        zoom_dropdown.setObjectName("MediaWorkspaceViewerZoom")
        vt_row.addWidget(zoom_dropdown, 0)

        # Single stretch pushes the right group to the far right.
        vt_row.addStretch(1)

        # Right group: overlay toggles then action buttons.
        vt_row.addWidget(
            MetaLabel(self._theme, "Safe", role="muted", style="caption"), 0
        )
        safe_toggle = ToggleSwitch(self._theme, checked=False, accent="cyan")
        safe_toggle.setObjectName("MediaWorkspaceViewerSafeToggle")
        vt_row.addWidget(safe_toggle, 0)

        vt_row.addWidget(
            MetaLabel(self._theme, "Grid", role="muted", style="caption"), 0
        )
        grid_toggle = ToggleSwitch(self._theme, checked=False, accent="purple")
        grid_toggle.setObjectName("MediaWorkspaceViewerGridToggle")
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
            # Keep a reference to the status badge so the phase-execution
            # observer can reflect run state. Object name / style / layout
            # are unchanged; only the text is updated later.
            if name == "MediaWorkspacePreviewStatusBadge":
                self._preview_status_badge = badge
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
        # Keep a reference so the ProjectState observer can refresh the empty
        # state / selected-media text. Object name, style and layout position
        # are unchanged; only the text is updated later.
        self._preview_placeholder = placeholder
        stage_layout.addWidget(placeholder)

        # Frame sink: a minimal image surface for decoded playback frames.
        # Hidden until show_frame() is called; stacked with the placeholder
        # inside the existing stage (no layout redesign, additive only).
        self._preview_frame = QLabel(stage)
        self._preview_frame.setObjectName("MediaWorkspacePreviewFrame")
        self._preview_frame.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_frame.setStyleSheet(
            "#MediaWorkspacePreviewFrame { background: transparent; }"
        )
        self._preview_frame.setVisible(False)
        stage_layout.addWidget(self._preview_frame, 1)

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
        details.setMaximumWidth(300)
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
        body = QScrollArea(details)
        body.setObjectName("MediaWorkspaceDetailsBody")
        body.setWidgetResizable(True)
        body.setFrameShape(QFrame.Shape.NoFrame)
        body_container = QWidget()
        body_container.setObjectName("MediaWorkspaceDetailsBodyContainer")
        body_layout = QVBoxLayout(body_container)
        # Right margin gives section headers and group cards 8px of breathing
        # room away from the scrollbar track so content never sits flush.
        body_layout.setContentsMargins(0, 0, tokens.spacing.sm, 0)
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

    def _build_right_stream(self) -> QWidget:
        """Build the unified single-scroll right column (UI-only stream).

        A master :class:`QScrollArea` hosts one vertical stream: an AI
        Assistant header with an inline Export action, a two-column grid of AI
        tool cards, collapsible Properties accordions (Transform / Audio) and
        a Background Tasks monitor. Every control is decorative and wired to
        nothing; all visual values derive from theme tokens. This replaces the
        old nested Details/Inspector/AI splitter in the visible view path
        while the frozen detail labels + inspector remain live off-screen for
        the existing selection wiring.
        """
        tokens = self._theme.tokens
        c = tokens.colors
        r = tokens.radius
        s = tokens.spacing

        master_scroll = QScrollArea()
        master_scroll.setObjectName("MediaWorkspaceRightStream")
        master_scroll.setWidgetResizable(True)
        master_scroll.setFrameShape(QFrame.Shape.NoFrame)
        master_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        master_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        master_scroll.setStyleSheet(
            f"#MediaWorkspaceRightStream {{ background: transparent; "
            f"border: none; }} "
            f"QScrollBar:vertical {{ background: transparent; "
            f"width: {s.sm}px; margin: 0px; }} "
            f"QScrollBar::handle:vertical {{ background: {c.surface_overlay}; "
            f"border-radius: {r.sm}px; min-height: {s.xl}px; }} "
            f"QScrollBar::handle:vertical:hover {{ background: {c.accent_blue}; }} "
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ "
            f"height: 0px; border: none; background: none; }} "
            f"QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ "
            f"background: transparent; }}"
        )

        content = QWidget()
        content.setObjectName("UnifiedRightSidebarContent")
        content.setStyleSheet(
            f"#UnifiedRightSidebarContent {{ background: transparent; }}"
        )
        stream = QVBoxLayout(content)
        stream.setContentsMargins(s.sm, s.md, s.sm, s.md)
        stream.setSpacing(s.lg)

        # ---- Header: title + inline Export action ---- #
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(s.sm)
        header_title = MetaLabel(
            self._theme, "AI ASSISTANT", role="muted", style="caption"
        )
        header_title.setObjectName("MediaWorkspaceRightStreamHeader")
        header_row.addWidget(header_title, 0)
        header_row.addStretch(1)
        export_btn = NeonButton(
            self._theme, "Export", variant="primary", accent="blue"
        )
        export_btn.setObjectName("MediaWorkspaceRightStreamExport")
        header_row.addWidget(export_btn, 0)
        stream.addLayout(header_row)

        # ---- Section 1: two-column AI tool card grid ---- #
        ai_grid = QGridLayout()
        ai_grid.setHorizontalSpacing(s.sm)
        ai_grid.setVerticalSpacing(s.sm)
        ai_grid.setContentsMargins(0, 0, 0, 0)
        ai_tools = (
            ("Auto Edit", "Create edit automatically"),
            ("Highlight Detection", "Find best moments"),
            ("Funny Moment", "Detect funny moments"),
            ("Beat Sync", "Sync to music beat"),
            ("Subtitle Generator", "Auto generate subtitles"),
            ("Thumbnail Generator", "Create thumbnails"),
            ("Script Assistant", "Generate video scripts"),
            ("Voice Cleanup", "Enhance voice quality"),
        )
        card_qss = (
            f"QFrame#MediaWorkspaceAiToolCard {{ "
            f"background: {c.surface}; "
            f"border: 1px solid {c.border}; "
            f"border-radius: {r.md}px; }} "
            f"QFrame#MediaWorkspaceAiToolCard:hover {{ "
            f"border: 1px solid {c.accent_purple}; "
            f"background: {c.surface_elevated}; }}"
        )
        # Compact, ultra-tight "AI" chip styling (token-derived). Scoped to
        # this screen so the frozen StatusBadge widget is untouched; using a
        # MetaLabel keeps padding minimal so the chip never hogs the row.
        chip_qss = (
            f"#MediaWorkspaceAiToolBadge {{ "
            f"color: {c.accent_cyan}; "
            f"background: {c.surface_overlay}; "
            f"border: 1px solid {c.border}; "
            f"border-radius: {r.sm}px; "
            f"padding: 0px {s.xxs}px; }}"
        )
        for idx, (title, desc) in enumerate(ai_tools):
            card = QFrame()
            card.setObjectName("MediaWorkspaceAiToolCard")
            card.setFrameShape(QFrame.Shape.StyledPanel)
            # Adaptive height: allow two title lines + a description without
            # truncation. A raised floor keeps single-line cards uniform, and
            # MinimumExpanding lets a wrapped title grow the card instead of
            # clipping ("Highlight Det...").
            card.setMinimumHeight(72)
            card.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.MinimumExpanding,
            )
            card.setStyleSheet(card_qss)
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(s.sm, s.sm, s.sm, s.sm)
            # Real vertical breathing room between the title row and the
            # description so the two never bleed into each other.
            card_layout.setSpacing(s.xxs)

            # Title row: the title MAY wrap to a second line (multi-word tools
            # like "Highlight Detection") and takes the flexible space; the
            # compact AI chip is pinned to the top-right so it never steals
            # width from the title.
            title_row = QHBoxLayout()
            title_row.setContentsMargins(0, 0, 0, 0)
            title_row.setSpacing(s.xs)
            title_lbl = QLabel(title, card)
            title_lbl.setObjectName("MediaWorkspaceAiToolTitle")
            title_lbl.setFont(self._theme.font("caption"))
            title_lbl.setWordWrap(True)
            title_lbl.setTextInteractionFlags(
                Qt.TextInteractionFlag.NoTextInteraction
            )
            title_lbl.setStyleSheet(
                f"#MediaWorkspaceAiToolTitle {{ color: {c.text_primary}; "
                f"background: transparent; }}"
            )
            title_lbl.setSizePolicy(
                QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred
            )
            title_row.addWidget(title_lbl, 1)
            badge = QLabel("AI", card)
            badge.setObjectName("MediaWorkspaceAiToolBadge")
            badge.setFont(self._theme.font("caption"))
            badge.setStyleSheet(chip_qss)
            badge.setSizePolicy(
                QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
            )
            title_row.addWidget(
                badge,
                0,
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop,
            )
            card_layout.addLayout(title_row)

            desc_lbl = MetaLabel(
                self._theme, desc, role="muted", style="caption"
            )
            desc_lbl.setObjectName("MediaWorkspaceAiToolDesc")
            # Let the description wrap freely and claim the height it needs.
            desc_lbl.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
            )
            card_layout.addWidget(desc_lbl)
            card_layout.addStretch(1)

            # Top-align each cell so an uneven (two-line) card in one column
            # does not vertically stretch its single-line neighbour.
            ai_grid.addWidget(
                card, idx // 2, idx % 2, Qt.AlignmentFlag.AlignTop
            )
        ai_grid.setColumnStretch(0, 1)
        ai_grid.setColumnStretch(1, 1)
        stream.addLayout(ai_grid)

        # ---- Section 2: collapsible Properties accordions ---- #
        props_header = SectionHeader(self._theme, "Properties")
        props_header.setObjectName("MediaWorkspaceRightStreamSection")
        props_header.set_divider(True)
        stream.addWidget(props_header)

        transform_acc = self._build_stream_accordion("Transform")
        # X / Y coordinate rows with axis-prefixed numeric fields; Scale
        # exposes a proportional-lock "Link" affordance matching the mock.
        transform_acc.add_axis_row("Scale", "100.0%", "100.0%", linked=True)
        transform_acc.add_axis_row("Position", "0.0", "0.0")
        stream.addWidget(transform_acc)

        audio_acc = self._build_stream_accordion("Audio")
        # Single horizontal slider + one matching numeric field (not a dual
        # input) so Audio reads as a level control, per the reference. The
        # value is shown in decibels (0.0 dB) to match premium editor tools.
        audio_acc.add_slider_row(
            "Volume",
            Slider(self._theme, minimum=0.0, maximum=200.0, value=100.0, accent="blue"),
            "0.0 dB",
        )
        stream.addWidget(audio_acc)

        # ---- Section 3: Background Tasks monitor ---- #
        tasks_header = SectionHeader(self._theme, "Background Tasks")
        tasks_header.setObjectName("MediaWorkspaceRightStreamSection")
        tasks_header.set_divider(True)
        stream.addWidget(tasks_header)

        stream.addWidget(
            self._build_stream_task(
                "AI Analyzing", "Analyzing audio & video\u2026", 0.78, "cyan"
            )
        )
        stream.addWidget(
            self._build_stream_task(
                "Generating Thumbnails", "Creating thumbnails\u2026", 0.65, "purple"
            )
        )

        stream.addStretch(1)
        master_scroll.setWidget(content)
        return master_scroll

    def _build_stream_accordion(self, title: str) -> "_StreamAccordion":
        """Return a themed collapsible accordion frame for the right stream."""
        return _StreamAccordion(self._theme, title)

    def _build_stream_task(
        self, title: str, subtitle: str, fraction: float, accent: str
    ) -> QWidget:
        """Build one Background Tasks monitor row (label + ProgressBar).

        UI-only and decorative; ``fraction`` is a static 0..1 progress value
        and ``accent`` selects the ProgressBar accent. No backend is involved.
        """
        tokens = self._theme.tokens
        s = tokens.spacing

        row = QWidget()
        row.setObjectName("MediaWorkspaceBackgroundTask")
        row.setStyleSheet(
            f"#MediaWorkspaceBackgroundTask {{ background: transparent; }}"
        )
        layout = QVBoxLayout(row)
        layout.setContentsMargins(0, s.xxs, 0, s.xxs)
        layout.setSpacing(s.xxs)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(s.sm)
        title_lbl = MetaLabel(
            self._theme, title, role="primary", style="body_small"
        )
        top.addWidget(title_lbl, 0)
        top.addStretch(1)
        pct_lbl = MetaLabel(
            self._theme, f"{int(round(fraction * 100))}%", role="muted", style="caption"
        )
        top.addWidget(pct_lbl, 0)
        layout.addLayout(top)

        sub_lbl = MetaLabel(self._theme, subtitle, role="muted", style="caption")
        layout.addWidget(sub_lbl)

        layout.addWidget(ProgressBar(self._theme, value=fraction, accent=accent))
        return row

    def _build_inspector(self) -> QWidget:
        """Build the right ClipInspector region (UI-only, read-only).

        Separate from the media details panel: this reflects the *selected
        timeline clip*, not the selected media item.
        """
        tokens = self._theme.tokens

        region = QWidget()
        region.setObjectName("MediaWorkspaceInspector")
        region.setMinimumWidth(260)
        region.setMaximumWidth(300)
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

        Reflects the browser's current item. A cleared selection
        (``index == -1``) resets to the empty state; no media is opened.

        When a :class:`WorkflowController` is injected this is also the
        integration point: the selected item is pushed to the backend via
        ``controller.select_video`` and the authoritative ``ProjectState`` is
        read back and reflected in the UI. With no controller the method is
        pure UI (the original behavior), so every existing caller/test is
        unaffected.
        """
        item = self._browser.current_item()
        if item is None:
            self._show_empty_preview()
            return

        # UI-only path (no backend): reflect the browser item directly.
        if self._controller is None:
            self._preview_header.set_subtitle(item)
            self._detail_name.set_text(f"Name: {item}")
            self._detail_kind.set_text("Type: video/mp4")
            self._detail_status.set_text("Status: ready")
            self._preview_placeholder.setText(item)
            return

        # Integration path: push the selection to the backend, then reflect
        # the authoritative ProjectState read back from the controller. A
        # failed select_video (e.g. a missing path) must never crash the UI
        # thread, so it degrades to an explicit error state.
        self._reflect_selected_video(item)

    def _show_empty_preview(self) -> None:
        """Reset every Preview-owned surface to its empty state (no selection).

        Preserves the frozen empty-state text/object names; only text is set.
        """
        self._preview_header.set_subtitle("No clip selected")
        self._preview_placeholder.setText("No clip selected")
        self._detail_name.set_text("Name: \u2014")
        self._detail_kind.set_text("Type: \u2014")
        self._detail_status.set_text("Status: no selection")

    # ------------------------------------------------------------------ #
    # Real playback frame pipeline (decode via FFmpegService; display here)
    # ------------------------------------------------------------------ #
    def _decode_and_show(self, seconds: float) -> None:
        """Decode the frame at ``seconds`` via the backend and display it.

        Best-effort: requires a controller and a selected media path. Decoding
        is owned by the backend FFmpegService (via the controller); any decode
        failure is swallowed so playback/seek never crashes the UI thread.
        """
        if self._controller is None or self._media_path is None:
            return
        try:
            frame = self._controller.decode_frame(self._media_path, seconds)
        except Exception:
            return
        if frame is not None:
            self.show_frame(frame)

    def show_frame(self, bgr) -> None:
        """Display a decoded ``(H, W, 3)`` uint8 BGR ndarray in the preview.

        Converts BGR -> RGB, wraps as a QImage/QPixmap and shows it in the
        frame sink, hiding the empty-state placeholder while a frame is shown.
        Silently ignores malformed frames.
        """
        try:
            height, width = int(bgr.shape[0]), int(bgr.shape[1])
            if height <= 0 or width <= 0:
                return
            rgb = bgr[:, :, ::-1]  # BGR -> RGB
            buffer = rgb.tobytes()
            image = QImage(buffer, width, height, 3 * width, QImage.Format.Format_RGB888)
            # Copy so the QImage does not alias the temporary buffer.
            pixmap = QPixmap.fromImage(image.copy())
        except Exception:
            return
        target = self._preview_frame.size()
        if target.width() > 0 and target.height() > 0:
            pixmap = pixmap.scaled(
                target,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        self._preview_placeholder.setVisible(False)
        self._preview_frame.setPixmap(pixmap)
        self._preview_frame.setVisible(True)

    def clear_frame(self) -> None:
        """Hide the frame sink and restore the empty-state placeholder."""
        self._preview_frame.clear()
        self._preview_frame.setVisible(False)
        self._preview_placeholder.setVisible(True)

    # ------------------------------------------------------------------ #
    # Audio playback (Qt Multimedia; synchronized to the timeline playhead)
    # ------------------------------------------------------------------ #
    def _ensure_audio_player(self):
        """Create the QMediaPlayer/QAudioOutput lazily; return the player.

        Returns ``None`` when Qt Multimedia is unavailable (the screen then
        stays video-only). Idempotent.
        """
        if self._audio_player is not None:
            return self._audio_player
        try:
            from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
        except Exception:
            return None
        self._audio_player = QMediaPlayer(self)
        self._audio_output = QAudioOutput(self)
        self._audio_player.setAudioOutput(self._audio_output)
        return self._audio_player

    def _ensure_audio_loaded(self) -> bool:
        """Extract (once) and load the audio track for the selected media.

        Returns whether a player is ready with the current media's audio.
        Reuses the backend FFmpegService.extract_audio via the controller.
        Best-effort: any failure leaves the screen video-only.
        """
        if self._controller is None or self._media_path is None:
            return False
        player = self._ensure_audio_player()
        if player is None:
            return False
        if self._audio_loaded_for == self._media_path:
            return True
        try:
            from PySide6.QtCore import QUrl

            audio_path = self._controller.extract_audio(self._media_path)
            player.setSource(QUrl.fromLocalFile(str(audio_path)))
            self._audio_loaded_for = self._media_path
            return True
        except Exception:
            return False

    def _on_audio_play(self) -> None:
        """Start/resume audio playback (loads the track on first play)."""
        if self._ensure_audio_loaded():
            self._audio_player.play()

    def _on_audio_pause(self) -> None:
        """Pause audio playback if a player exists."""
        if self._audio_player is not None:
            self._audio_player.pause()

    def _on_audio_stop(self) -> None:
        """Stop audio playback (and rewind) if a player exists."""
        if self._audio_player is not None:
            self._audio_player.stop()

    def _on_audio_seek(self, fraction: float) -> None:
        """Seek audio to ``fraction`` of the timeline duration (ms position)."""
        if self._audio_player is None:
            return
        duration = self._timeline.duration()
        self._audio_player.setPosition(int(max(0.0, fraction) * duration * 1000))

    def _reset_audio_for_new_media(self) -> None:
        """Stop audio and invalidate the cached track for a new selection."""
        if self._audio_player is not None:
            self._audio_player.stop()
        self._audio_loaded_for = None

    def _reflect_selected_video(self, item: str) -> None:
        """Drive ``select_video`` and reflect the controller's ProjectState.

        Integration-only helper (called when a WorkflowController is present).
        Reuses the controller's existing write (``select_video``) and read
        (``project_state``) surface; it invents no new backend API and mutates
        no frozen component. The authoritative ``ProjectState`` snapshot is
        then observed by :meth:`_reflect_preview`.
        """
        try:
            self._controller.select_video(item)
            state = self._controller.project_state()
        except Exception as exc:  # backend rejected the selection
            self._preview_header.set_subtitle(item)
            self._preview_placeholder.setText(item)
            self._detail_name.set_text(f"Name: {item}")
            self._detail_kind.set_text("Type: video/mp4")
            self._detail_status.set_text(f"Status: error \u2014 {exc}")
            return
        self._reflect_preview(state, fallback_name=item)

    def _reflect_preview(self, state, fallback_name: str) -> None:
        """Observe an immutable ``ProjectState`` snapshot into Preview-owned UI.

        Pure observer: reads only fields ``ProjectState`` genuinely exposes
        (``video_path`` and ``artifacts``) and updates only existing
        Preview-owned widgets (title/subtitle, placeholder, empty state and
        the existing Details metadata rows). It stores no state, creates no
        widget, and never becomes a source of truth.

        Metadata not exposed by the current architecture (duration, fps,
        resolution, codec, thumbnails, first-frame rendering) is deliberately
        left unchanged: none of it lives in ``ProjectState`` or on
        ``WorkflowController``, so fabricating it is out of scope. The
        decorative HUD badges are therefore intentionally not touched.

        The TransportBar DISPLAY is reset to its initial state for the newly
        selected media using only its existing public API; no playback logic
        is added and it remains the single playback-state owner.
        """
        video_path = getattr(state, "video_path", None)
        if video_path is None:
            self._media_path = None
            self.clear_frame()
            self._show_empty_preview()
            return

        # Title / subtitle / placeholder from the authoritative video_path.
        display = getattr(video_path, "name", None) or fallback_name
        self._preview_header.set_subtitle(display)
        self._preview_placeholder.setText(display)

        # Record the media path and show the first real frame (t=0). A new
        # selection invalidates any previously loaded audio track.
        self._media_path = video_path
        self._reset_audio_for_new_media()
        self._decode_and_show(0.0)

        # Details metadata derived directly from ProjectState (no fabrication).
        self._detail_name.set_text(f"Name: {display}")
        suffix = getattr(video_path, "suffix", "") or ""
        kind = suffix.lstrip(".").lower()
        self._detail_kind.set_text(f"Type: {kind}" if kind else "Type: \u2014")
        self._detail_status.set_text(self._artifact_status(state))

        # Reset the transport DISPLAY for the new selection via public API
        # only. TransportBar stays the single playback-state owner.
        self._transport.set_state("stopped")
        self._transport.set_position(0.0)

        # Reflect the authoritative backend Timeline (if any) into the
        # existing Timeline widget via its public API only.
        self._reflect_timeline()

    def _reflect_timeline(self) -> None:
        """Reflect the backend Timeline into the existing Timeline widget.

        Observer-only: reads ``controller.timeline()`` and maps it into the
        frozen Timeline widget through its existing public API
        (``set_duration`` / ``add_track`` / ``set_clips``). The backend
        ``ProjectState.timeline`` remains the single source of truth; the
        widget stores only view state. When there is no controller or no
        backend timeline, the widget's current (demo) content is left
        untouched -- no backend data is fabricated.

        Markers are not reflected: the Timeline widget exposes no marker API,
        and adding one would redesign a reusable widget (out of scope).
        """
        if self._controller is None:
            return
        try:
            timeline = self._controller.timeline()
        except Exception:
            return
        if timeline is None:
            return
        # Duration first so clip bounds validate against the new span.
        self._timeline.set_duration(timeline.duration)
        # Extend widget tracks to cover the backend track indices (never
        # remove existing lanes; the widget owns its lane view state).
        needed = max((t.index for t in timeline.tracks), default=-1) + 1
        while self._timeline.track_count() < needed:
            self._timeline.add_track(f"Track {self._timeline.track_count() + 1}")
        self._timeline.set_clips(
            [
                {
                    "track": clip.track_index,
                    "start": clip.start,
                    "length": clip.length,
                    "label": clip.label or (clip.source or ""),
                }
                for clip in timeline.clips
            ]
        )

    # ------------------------------------------------------------------ #
    # Phase execution integration (observe + trigger; controller APIs only)
    # ------------------------------------------------------------------ #
    def run_phase(self, phase_id: str) -> bool:
        """Run an explicitly specified backend phase (screen helper).

        The caller chooses the target phase; the screen never selects backend
        behavior implicitly. Forwards to the controller's existing
        ``run_phase`` (which enforces single-flight and returns whether the
        run started). Returns ``False`` when there is no controller.
        """
        if self._controller is None:
            return False
        return self._controller.run_phase(phase_id)

    def _set_phase_status(self, text: str) -> None:
        """Reflect phase run state into the existing Preview HUD status label."""
        badge = getattr(self, "_preview_status_badge", None)
        if badge is not None:
            badge.setText(text)

    def _on_phase_started(self, phase_id: str) -> None:
        """Observer: a background phase run began."""
        self._set_phase_status(f"Running: {phase_id}")

    def _on_phase_completed(self, result) -> None:
        """Observer: a phase run finished; reflect success/failure + artifacts.

        ``ApplicationFacade.run_phase`` refreshes discovered artifacts before
        returning, so ``project_state().artifacts`` is authoritative here. Re-
        read the state and refresh the existing Details Status row via the
        existing formatter. ``artifact_created`` is not observed for this,
        because its information is already represented by the refreshed
        ``ProjectState.artifacts`` (avoiding a duplicate update).
        """
        success = bool(getattr(result, "success", False))
        self._set_phase_status("Done" if success else "Failed")
        if self._controller is None:
            return
        try:
            state = self._controller.project_state()
        except Exception:
            return
        self._detail_status.set_text(self._artifact_status(state))

    def _on_phase_failed(self, message: str) -> None:
        """Observer: a phase run raised; reflect the failure."""
        self._set_phase_status("Failed")

    @staticmethod
    def _artifact_status(state) -> str:
        """Summarize ``ProjectState.artifacts`` for the existing Status row.

        Kept terse to match the existing UI ("Status: ready"). Reports only
        real artifact presence derived directly from the state's ``artifacts``
        tuple; creates no new artifact widget and adds no fabricated detail.
        """
        count = len(tuple(getattr(state, "artifacts", ()) or ()))
        if count == 0:
            return "Status: ready"
        noun = "artifact" if count == 1 else "artifacts"
        return f"Status: ready \u00b7 {count} {noun}"

    def _on_clip_selected(self, index: int) -> None:
        """Update the clip inspector from the timeline selection (UI-only).

        Reflects the timeline's currently selected clip; a cleared selection
        (``index == -1``) returns the inspector to its empty state.
        """
        self._clip_inspector.show_clip(self._timeline.selected_clip())

    def _persist_timeline_to_backend(self) -> None:
        """Persist the Timeline widget's current model into the backend.

        Maps the widget's tracks/clips into a validated gui_core.Timeline and
        calls controller.update_timeline (publishing TimelineChanged), so the
        backend ProjectState.timeline follows the widget edits. No-op without
        a controller; best-effort on validation errors (an invalid transient
        edit must never crash the UI thread).
        """
        if self._controller is None:
            return
        try:
            from gui_core import Timeline, Track
            from gui_core.timeline import Clip as BackendClip

            names = self._timeline.tracks()
            tracks = tuple(
                Track(index=i, name=name) for i, name in enumerate(names)
            )
            duration = float(self._timeline.duration())
            backend = Timeline(duration=duration, tracks=tracks)
            for i, clip in enumerate(self._timeline.clips()):
                backend = backend.add_clip(
                    BackendClip(
                        id=f"clip_{i}",
                        track_index=int(clip.get("track", 0)),
                        start=float(clip.get("start", 0.0)),
                        length=float(clip.get("length", 0.0)),
                        label=str(clip.get("label", "")),
                    )
                )
            self._controller.update_timeline(backend)
        except Exception:
            return

    def _on_clip_moved(self, index: int, new_track: int) -> None:
        """Refresh the clip inspector after a timeline clip is moved (UI-only).

        A drag-move changes the clip's track without changing the selection
        index (so :attr:`clip_selected` is not re-emitted); re-show the
        currently selected clip so the inspector reflects its new track, then
        persist the widget's model into the backend Timeline.
        """
        self._clip_inspector.show_clip(self._timeline.selected_clip())
        self._persist_timeline_to_backend()

    def _on_clip_trimmed(self, index: int, start: float, length: float) -> None:
        """Refresh the clip inspector after a timeline clip is trimmed (UI-only).

        An edge trim changes the clip's start/length without changing the
        selection index (so :attr:`clip_selected` is not re-emitted); re-show
        the currently selected clip so the inspector reflects its new bounds,
        then persist the widget's model into the backend Timeline.
        """
        self._clip_inspector.show_clip(self._timeline.selected_clip())
        self._persist_timeline_to_backend()

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
        # Real playback: decode and display the frame at the new playhead. The
        # Timeline widget's own timer drives playhead_changed as playback
        # advances, so this reuses the existing timer (no second owner).
        self._decode_and_show(seconds)


class _StreamAccordion(QWidget):
    """A minimal collapsible section for the unified right stream (UI-only).

    Composes a header row (chevron + title) with a token-styled content frame
    that holds labeled control rows. The chevron toggles the local visibility
    of the content frame only; it is wired to no logic and touches no backend.
    """

    _CHEVRON_EXPANDED = "\u25be"
    _CHEVRON_COLLAPSED = "\u25b8"

    def __init__(self, theme: ThemeManager, title: str) -> None:
        super().__init__()
        self._theme = theme
        self._expanded = True
        self._grid_row = 0
        tokens = theme.tokens
        c = tokens.colors
        r = tokens.radius
        s = tokens.spacing

        self.setObjectName("MediaWorkspaceStreamAccordion")
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(s.xxs)

        self._toggle = NeonButton(
            theme, f"{self._CHEVRON_EXPANDED}  {title}", variant="ghost", accent="cyan"
        )
        self._toggle.setObjectName("MediaWorkspaceStreamAccordionToggle")
        self._title = title
        self._toggle.clicked.connect(self._on_toggle)
        column.addWidget(self._toggle)

        self._content = QFrame(self)
        self._content.setObjectName("MediaWorkspaceStreamAccordionContent")
        self._content.setFrameShape(QFrame.Shape.StyledPanel)
        self._content.setStyleSheet(
            f"#MediaWorkspaceStreamAccordionContent {{ "
            f"background: {c.surface}; "
            f"border: 1px solid {c.border}; "
            f"border-radius: {r.md}px; }}"
        )
        # Shared unified grid: EVERY property row places its widgets into the
        # SAME columns so Scale, Position and Volume align on identical column
        # boundaries like one clean table.
        #
        # Axis rows stack X over Y vertically (two grid rows each) so each
        # coordinate field gets the FULL column width inside the narrow 300px
        # sidebar instead of being squeezed side-by-side:
        #
        #   col 0 (name, spans 2 rows)   col 1 (expanding)   col 2
        #   [Name                     ]  [X <field>       ]  [Link (spans 2)]
        #                                [Y <field>       ]
        #
        # Slider rows use one grid row: name (col 0), slider (col 1), value
        # field (col 2).
        self._grid = QGridLayout(self._content)
        self._grid.setContentsMargins(s.md, s.sm, s.md, s.sm)
        self._grid.setHorizontalSpacing(s.sm)
        self._grid.setVerticalSpacing(s.xs)
        # col 0 = name (content width), col 1 = fields (absorbs spare width),
        # col 2 = fixed outer-right tracking column (Link / value field).
        self._grid.setColumnStretch(0, 0)
        self._grid.setColumnStretch(1, 1)
        self._grid.setColumnStretch(2, 0)
        column.addWidget(self._content)

    def _axis_block(self, axis: str, value: str) -> QWidget:
        """Build an ``[axis-label | field]`` metric block that fills its cell.

        The field expands to the full column width -- the vertical X-over-Y
        stack gives each coordinate the whole column -- so no fixed width is
        imposed here.
        """
        s = self._theme.tokens.spacing
        block = QWidget(self._content)
        block.setObjectName("MediaWorkspaceStreamAxisGroup")
        b_layout = QHBoxLayout(block)
        b_layout.setContentsMargins(0, 0, 0, 0)
        b_layout.setSpacing(s.xs)
        axis_lbl = MetaLabel(self._theme, axis, role="disabled", style="caption")
        b_layout.addWidget(axis_lbl, 0, Qt.AlignmentFlag.AlignVCenter)
        field = TextField(self._theme, text=value)
        field.setObjectName("MediaWorkspaceStreamAxisField")
        field.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        b_layout.addWidget(field, 1)
        return block

    def add_row(self, label: str, control: QWidget) -> None:
        """Append a simple labeled control spanning the metric columns."""
        name = MetaLabel(self._theme, label, role="muted", style="body_small")
        self._grid.addWidget(
            name, self._grid_row, 0,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        )
        control.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self._grid.addWidget(control, self._grid_row, 1, 1, 2)
        self._grid_row += 1

    def add_axis_row(
        self,
        label: str,
        value_x: str,
        value_y: str,
        *,
        linked: bool = False,
    ) -> None:
        """Append an X / Y coordinate row into the shared grid.

        Columns: 0 = name (left), 1 = X block, 2 = Y block, 3 = optional
        "Link" ghost button on the outer-right boundary. Because every axis
        row uses these same columns, Scale and Position align exactly.
        UI-only / decorative.
        """
        top = self._grid_row
        bottom = self._grid_row + 1

        name = MetaLabel(self._theme, label, role="muted", style="body_small")
        # Name spans both coordinate rows, anchored top-left.
        self._grid.addWidget(
            name, top, 0, 2, 1,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
        )
        # X on the top grid row, Y directly beneath -- each field now fills
        # the full column-1 width (fixes the horizontal squish).
        self._grid.addWidget(self._axis_block("X", value_x), top, 1)
        self._grid.addWidget(self._axis_block("Y", value_y), bottom, 1)
        if linked:
            link = NeonButton(
                self._theme, "Link", variant="ghost", accent="cyan"
            )
            link.setObjectName("MediaWorkspaceStreamAxisLink")
            link.setSizePolicy(
                QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
            )
            # Link spans both rows on the outer-right column, centered against
            # the X/Y stack.
            self._grid.addWidget(
                link, top, 2, 2, 1,
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            )
        self._grid_row += 2

    def add_slider_row(
        self, label: str, control: QWidget, value: str
    ) -> None:
        """Append a single-slider row into the shared grid.

        Columns: 0 = name (left), 1 = the stretching horizontal slider,
        2 = one standalone value field on the outer-right boundary. Shares
        the axis rows' column boundaries so the name and the trailing value
        align with the Transform rows above. UI-only / decorative.
        """
        name = MetaLabel(self._theme, label, role="muted", style="body_small")
        self._grid.addWidget(
            name, self._grid_row, 0,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        )
        control.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self._grid.addWidget(control, self._grid_row, 1)
        field = TextField(self._theme, text=value)
        field.setObjectName("MediaWorkspaceStreamNumericField")
        field.setFixedWidth(64)
        field.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._grid.addWidget(
            field, self._grid_row, 2,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        )
        self._grid_row += 1

    def _on_toggle(self) -> None:
        """Flip the local expanded state (no external effect)."""
        self._expanded = not self._expanded
        self._content.setVisible(self._expanded)
        chevron = (
            self._CHEVRON_EXPANDED if self._expanded else self._CHEVRON_COLLAPSED
        )
        self._toggle.set_text(f"{chevron}  {self._title}")


def build_media_workspace_screen(theme: ThemeManager, controller=None) -> QWidget:
    """Build and return the interactive media workspace screen.

    Constructed without running a Qt event loop so it can be asserted
    headlessly in tests. All visual values come from the injected ``theme``.

    Args:
        theme: The injected theme manager (sole source of visual values).
        controller: Optional :class:`~gui.integration.workflow_controller.
            WorkflowController`. When omitted the screen is purely UI-only
            (selection updates preview/details, no backend). When provided the
            screen becomes the integration point for its MediaBrowser:
            selecting a media item drives ``controller.select_video`` and the
            screen reflects the ``ProjectState`` read back from the controller.

    Returns:
        The composed media workspace as a :class:`QWidget`.
    """
    return _MediaWorkspace(theme, controller)
