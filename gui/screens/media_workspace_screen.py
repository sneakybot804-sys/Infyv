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

import collections
from typing import List, Optional

from PySide6.QtCore import (
    QAbstractAnimation,
    QMutex,
    QMutexLocker,
    QPropertyAnimation,
    QThread,
    QTimer,
    Qt,
    Signal,
)
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication,
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
from gui.widgets.effects import apply_glow  # noqa: F401  (kept: screen-level glow helper)
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


class _FrameDecoder(QThread):
    """Background video frame decoder using ONE persistent ffmpeg pipe.

    Spawns a single long-lived ffmpeg process streaming raw BGR frames
    sequentially (no per-frame subprocess, no per-frame seek), buffering up
    to ``max_frames`` ndarrays. The main thread pulls frames from the deque
    on each play tick — real-time playback at the video's native frame rate.

    Signals:
        error(str): Emitted when decoding fails (GUI thread via queued conn).
    """

    error = Signal(str)

    def __init__(self, controller, media_path, fps: float = 30.0,
                 max_frames: int = 8, start_at: float = 0.0, parent=None):
        super().__init__(parent)
        self._controller = controller
        self._media_path = media_path
        self._fps = max(1.0, float(fps))
        self._max_frames = max(2, int(max_frames))
        self._queue: collections.deque = collections.deque(maxlen=self._max_frames)
        self._mutex = QMutex()
        self._stop = False
        self._start_at = max(0.0, float(start_at))
        self._seek_to: Optional[float] = None
        self._proc = None

    def run(self):
        """Stream frames from one persistent ffmpeg pipe until stopped."""
        import subprocess

        import numpy as np

        # Probe once for dimensions (backend metadata; no per-frame probe).
        try:
            meta = self._controller.media_metadata(self._media_path)
            width = int(getattr(meta, "width", 0) or 0)
            height = int(getattr(meta, "height", 0) or 0)
        except Exception as exc:
            self.error.emit(f"metadata failed: {exc}")
            return
        if width <= 0 or height <= 0:
            self.error.emit("invalid video dimensions")
            return
        frame_bytes = width * height * 3
        start = self._start_at

        while not self._stop:
            # (Re)spawn the streaming pipe at `start` seconds.
            cmd = [
                "ffmpeg", "-nostdin", "-loglevel", "error",
                "-ss", f"{start:.3f}",
                "-i", str(self._media_path),
                "-f", "rawvideo", "-pix_fmt", "bgr24",
                "pipe:1",
            ]
            try:
                self._proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    bufsize=frame_bytes * 4,
                )
            except Exception as exc:
                self.error.emit(f"ffmpeg spawn failed: {exc}")
                return

            restart = False
            while not self._stop:
                # Seek request: kill the pipe and respawn at the new time.
                with QMutexLocker(self._mutex):
                    if self._seek_to is not None:
                        start = self._seek_to
                        self._seek_to = None
                        self._queue.clear()
                        restart = True
                # Back-pressure: wait while the buffer is full.
                if not restart and len(self._queue) >= self._max_frames:
                    self.msleep(5)
                    continue
                if restart:
                    break
                raw = self._proc.stdout.read(frame_bytes)
                if not raw or len(raw) < frame_bytes:
                    # End of stream.
                    self._stop = True
                    break
                frame = np.frombuffer(raw, dtype=np.uint8).reshape(
                    (height, width, 3)
                ).copy()
                with QMutexLocker(self._mutex):
                    self._queue.append(frame)

            self._kill_proc()
            if not restart:
                break

    def _kill_proc(self):
        proc = self._proc
        self._proc = None
        if proc is not None:
            try:
                proc.kill()
                proc.wait(timeout=2)
            except Exception:
                pass

    # -- Thread-safe API (called from GUI thread) --
    def seek(self, seconds: float):
        with QMutexLocker(self._mutex):
            self._seek_to = float(seconds)

    def precache(self, seconds: float):
        self.seek(seconds)

    def pop(self):
        with QMutexLocker(self._mutex):
            return self._queue.popleft() if self._queue else None

    def clear(self):
        with QMutexLocker(self._mutex):
            self._queue.clear()

    def stop_decoding(self):
        self._stop = True
        self._kill_proc()


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
        # Auto Edit sequencing state (over the existing gated pipeline).
        self._auto_edit_active = False
        self._auto_edit_attempted = set()
        # Imported-media name -> full path map used when no PreviewMediaSource
        # is active (e.g. UI-only mode with drag & drop).
        self._imported_paths = {}
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
        #
        # Media discovery (backend integration): when a controller is present
        # the browser is seeded with REAL videos from the configured videos
        # directory via the existing PreviewMediaSource (VideoPicker +
        # FFmpegService seam). UI-only construction keeps the demo seed so
        # every existing caller/test is unaffected.
        self._media_source = None
        items = list(_DEMO_ITEMS)
        if controller is not None:
            try:
                from gui.integration.preview_media import PreviewMediaSource

                self._media_source = PreviewMediaSource()
                real_items = self._media_source.list_items()
                if real_items:
                    items = real_items
            except Exception:
                self._media_source = None
        self._browser = MediaBrowser(theme, items=items)
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
        right_column.setFixedWidth(345)

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
        # below its fixed two-column width and always fills the vertical
        # space. setFixedWidth here mirrors the value set inside
        # NavigationSidebar itself; the redundant call on the outer widget
        # ensures the splitter geometry engine sees the constraint too.
        self._sidebar.setFixedWidth(NavigationSidebar.TOTAL_WIDTH)
        self._sidebar.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding
        )
        splitter.addWidget(self._sidebar)
        splitter.addWidget(self._build_preview())
        splitter.addWidget(right_column)
        splitter.setCollapsible(0, False)  # sidebar must never collapse
        splitter.setCollapsible(1, False)  # preview must never collapse
        splitter.setCollapsible(2, False)  # right column must never collapse
        splitter.setStretchFactor(0, 0)    # sidebar: fixed two-column width
        splitter.setStretchFactor(1, 1)    # preview: absorbs ALL spare space
        splitter.setStretchFactor(2, 0)    # right column: fixed at 345px
        # setSizes is a one-time layout hint. The true constraints are the
        # setFixedWidth calls on sidebar and right_column (345px);
        # those survive maximise / resize events where setSizes does not.
        splitter.setSizes([NavigationSidebar.TOTAL_WIDTH, 1245, 345])

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
        # Taller default timeline region: 7 pro-NLE lanes (34px each) plus
        # toolbar / ruler / playhead need ~380px to read like the reference.
        main_split.setSizes([580, 380])
        root.addWidget(main_split, 1)

        # Screen-level wiring: media selection updates preview + details;
        # timeline clip selection updates the clip inspector. When a
        # WorkflowController is injected, selection additionally drives the
        # backend via _on_selection_changed (see below); otherwise it stays
        # UI-only. The single connection covers both modes.
        self._browser.selection_changed.connect(self._on_selection_changed)
        # Import: the browser's existing import_requested signal opens a real
        # file dialog and appends the chosen videos (backend path when a
        # controller is present; harmless UI-only append otherwise).
        self._browser.import_requested.connect(self._on_import_requested)
        # Drag & drop media import onto the whole workspace.
        self.setAcceptDrops(True)
        # Thumbnails: decode first frames for the browser rows lazily (one
        # per timer tick, off the critical path) via the existing
        # PreviewMediaSource decode seam. No-op when no real media source.
        self._start_thumbnail_loading()

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
        # Transport seek scrubber drives the timeline playhead (single
        # playback clock); audio seek is already connected above.
        self._transport.seek_requested.connect(self._on_transport_seek)
        # Loop: replay from 0 when playback reaches the end with loop on.
        self._timeline.playback_finished.connect(self._on_playback_finished)
        # Frame-step / shuttle buttons on the transport (looked up by their
        # frozen object names; wiring-only, no layout or naming change).
        self._wire_transport_buttons()
        # Viewer toolbar: zoom / screenshot / fullscreen (existing controls).
        self._wire_viewer_toolbar()
        # Timeline editing tools: the existing toolbar glyphs and track-header
        # controls perform real edits (split/delete/duplicate/zoom/markers/
        # lock/mute/solo) against the widget model, persisted to the backend
        # Timeline via the existing update_timeline path.
        self._wire_timeline_tools()
        self._wire_track_header_controls()
        self._wire_edit_shortcuts()
        # History baseline: the pristine clip model, so the first edit's
        # pre-state is known and undoable.
        self._last_clips_snapshot = self._timeline.clips()
        # Project system: current project path + periodic autosave.
        self._project_path = None
        self._start_autosave()
        # Sidebar project actions: "+ New Project" creates a fresh project;
        # recent rows open the matching saved project when one exists (looked
        # up by row name against the persisted recents index).
        self._wire_sidebar_projects()
        # Sidebar navigation: show the MediaBrowser when "Media" is active
        # (index 2), hide it for any other nav item. The browser is always
        # a child of the screen (not in the splitter), so hiding/showing it
        # never corrupts splitter geometry.
        self._sidebar.navigation_changed.connect(self._on_nav_changed)
        self._nav_media_index = 2  # "Media" in _NAV_ITEMS
        # AI orchestration: build the AIManager + AIController (ai_core
        # pipeline). Failure-tolerant — without keys/network the controller
        # still constructs; individual requests then report their errors
        # through request_failed.
        self._ai_controller = None
        if controller is not None:
            try:
                from ai_core import AIManager
                from gui.integration.ai_controller import AIController

                manager = AIManager(
                    controller=controller,
                    view_state=self._ai_view_state,
                )
                self._ai_controller = AIController(manager, parent=self)
                self._ai_controller.request_started.connect(
                    self._on_ai_request_started
                )
                self._ai_controller.request_completed.connect(
                    self._on_ai_request_completed
                )
                self._ai_controller.request_failed.connect(
                    self._on_ai_request_failed
                )
            except Exception:
                self._ai_controller = None

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
            self._theme, "Screenshot", variant="ghost", accent="cyan",
            icon_name="camera",
        )
        shot_btn.setObjectName("MediaWorkspaceViewerScreenshot")
        vt_row.addWidget(shot_btn, 0)

        fs_btn = NeonButton(
            self._theme, "Fullscreen", variant="ghost", accent="cyan",
            icon_name="monitor",
        )
        fs_btn.setObjectName("MediaWorkspaceViewerFullscreen")
        vt_row.addWidget(fs_btn, 0)

        viewer_toolbar.setStyleSheet(
            f"#MediaWorkspaceViewerToolbar {{ "
            f"background: {tokens.colors.surface}; "
            f"border: 1px solid {tokens.colors.border}; "
            f"border-radius: {tokens.radius.md}px; }}"
        )
        # Reference layout places this editing strip BELOW the video stage
        # (after the transport controls), so it is inserted further down —
        # right after ``self._transport`` (visual reorder only; same widgets,
        # names and signals).

        # Cinematic preview stage: a deep gradient backdrop with a soft glass
        # border, a glass HUD overlay (timecode + badges), a subtle safe-area
        # guide, and a centered premium empty state.
        stage = QFrame(content)
        stage.setObjectName("MediaWorkspacePreviewStage")
        stage.setFrameShape(QFrame.Shape.StyledPanel)
        stage.setMinimumHeight(360)
        c = tokens.colors
        stage_radius = tokens.radius.lg
        # Cinematic backdrop: a deep multi-stop gradient with faint purple /
        # blue color hints so the empty viewer reads like a lit stage, not a
        # dead panel (visual-only).
        stage.setStyleSheet(
            f"#MediaWorkspacePreviewStage {{ "
            f"background: qlineargradient(x1:0, y1:0, x2:1, y2:1, "
            f"stop:0 {c.background_base}, "
            f"stop:0.35 #100A1E, "
            f"stop:0.55 #16102A, "
            f"stop:0.75 #100A1E, "
            f"stop:1 {c.background_deep}); "
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
        timecode.setMinimumWidth(
            timecode.fontMetrics().horizontalAdvance("00:00:00:00") + 8
        )
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
        # A glowing gradient play tile above the placeholder text so the empty
        # viewer looks intentional and premium (decorative, additive name).
        play_tile = QLabel(stage)
        play_tile.setObjectName("MediaWorkspacePreviewPlayTile")
        tile_side = 64
        glyph_side = 26
        play_tile.setFixedSize(tile_side, tile_side)
        play_tile.setAlignment(Qt.AlignmentFlag.AlignCenter)
        play_tile.setPixmap(
            self._theme.icons.icon(
                "play", c.text_primary, glyph_side
            ).pixmap(glyph_side, glyph_side)
        )
        play_tile.setStyleSheet(
            f"#MediaWorkspacePreviewPlayTile {{ "
            f"background: qlineargradient(x1:0, y1:0, x2:1, y2:1, "
            f"stop:0 {c.accent_blue}, stop:1 {c.accent_purple}); "
            f"border: 2px solid {c.glass_highlight}; "
            f"border-radius: {tile_side // 2}px; }}"
        )
        stage_layout.addWidget(
            play_tile, 0, Qt.AlignmentFlag.AlignHCenter
        )
        # Kept as an attribute so show_frame()/clear_frame() can hide the
        # decorative tile while a real decoded frame is displayed. Clicking
        # it selects the first media item (if none selected) and starts
        # playback — the empty-state play button behaves like a play button.
        self._preview_play_tile = play_tile
        self._register_click(play_tile, self._on_play_tile_clicked)
        stage_layout.addSpacing(tokens.spacing.sm)
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

        # Editing toolbar sits under the transport row, matching the
        # reference (toolbar built above, before the stage).
        inner.addWidget(viewer_toolbar)

        # --- Phase 10F: bottom player toolbar (decorative caption strip) --- #
        player_toolbar = QWidget(content)
        player_toolbar.setObjectName("MediaWorkspacePlayerToolbar")
        pt_row = QHBoxLayout(player_toolbar)
        pt_row.setContentsMargins(
            tokens.spacing.md, tokens.spacing.xs, tokens.spacing.md, tokens.spacing.xs
        )
        pt_row.setSpacing(tokens.spacing.md)
        for text, name in (
            ("00:00:42:16", "MediaWorkspacePlayerCurrentTime"),
            ("/ 00:02:15:08", "MediaWorkspacePlayerDuration"),
            ("Zoom 100%", "MediaWorkspacePlayerZoom"),
            ("Speed 1.0x", "MediaWorkspacePlayerSpeed"),
            ("Loop", "MediaWorkspacePlayerLoop"),
            ("Viewer: Ready", "MediaWorkspacePlayerStatus"),
            ("Quality: Full", "MediaWorkspacePlayerQuality"),
        ):
            # Timecode readouts render in mono with a cyan current-time so
            # the row reads like a pro NLE player bar; other captions stay
            # muted (visual-only; names and texts unchanged).
            if name in (
                "MediaWorkspacePlayerCurrentTime",
                "MediaWorkspacePlayerDuration",
            ):
                detail = MetaLabel(self._theme, text, role="muted", style="mono")
                if name == "MediaWorkspacePlayerCurrentTime":
                    detail.setStyleSheet(
                        f"color: {tokens.colors.accent_cyan}; "
                        f"background: transparent;"
                    )
            else:
                detail = MetaLabel(
                    self._theme, text, role="muted", style="caption"
                )
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

        # ---- Header: NEXUS inspector tab strip (decorative pills) ---- #
        # The reference panel is headed by four uppercase tabs; "AI STUDIO"
        # is active (gradient pill), the rest are quiet captions. Purely
        # visual -- the stream below always shows every section.
        tab_row = QHBoxLayout()
        tab_row.setContentsMargins(0, 0, 0, 0)
        tab_row.setSpacing(s.xxs)
        for tab_text, active in (
            ("AI STUDIO", True),
            ("PROPERTIES", False),
            ("EFFECTS", False),
            ("INSPECTOR", False),
        ):
            tab = QLabel(tab_text)
            tab.setObjectName(
                "MediaWorkspaceRightTabActive" if active
                else "MediaWorkspaceRightTab"
            )
            tab.setFont(self._theme.font("caption"))
            tab.setAlignment(Qt.AlignmentFlag.AlignCenter)
            # Minimum width based on longest tab text so labels never clip.
            tab.setMinimumWidth(
                tab.fontMetrics().horizontalAdvance(tab_text) + 2 * s.xs + 4
            )
            if active:
                tab.setStyleSheet(
                    f"#MediaWorkspaceRightTabActive {{ "
                    f"color: {c.text_primary}; font-weight: 700; "
                    f"background: qlineargradient(x1:0, y1:0, x2:1, y2:1, "
                    f"stop:0 {c.accent_blue}, stop:1 {c.accent_purple}); "
                    f"border: 1px solid {c.glass_highlight}; "
                    f"border-radius: {r.sm}px; "
                    f"padding: {s.xxs + 1}px {s.xs}px; }}"
                )
            else:
                tab.setStyleSheet(
                    f"#MediaWorkspaceRightTab {{ "
                    f"color: {c.text_muted}; font-weight: 600; "
                    f"background: transparent; "
                    f"border: 1px solid transparent; "
                    f"border-radius: {r.sm}px; "
                    f"padding: {s.xxs + 1}px {s.xs}px; }}"
                )
            tab.setSizePolicy(
                QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed
            )
            tab_row.addWidget(tab, 1)
        stream.addLayout(tab_row)

        # ---- Section 1: three-column AI tool card grid ---- #
        ai_grid = QGridLayout()
        ai_grid.setHorizontalSpacing(s.xs)
        ai_grid.setVerticalSpacing(s.xs)
        ai_grid.setContentsMargins(0, 0, 0, 0)
        ai_tools = (
            ("Auto Edit", "wand"),
            ("Highlight Detection", "sparkles"),
            ("Funny Moment", "zap"),
            ("Beat Sync", "activity"),
            ("Subtitle Generator", "type"),
            ("Thumbnail Generator", "image"),
            ("Script Writer", "bot"),
            ("Voice Cleanup", "mic"),
            ("Scene Enhance", "spark"),
        )
        # Card title -> registered backend phase id (gui_core registry).
        # Only real phases are mapped; "Auto Edit" runs the full gated
        # pipeline via the existing sequencer. Titles with no backend phase
        # report honestly instead of fabricating behavior.
        ai_phase_map = {
            "Highlight Detection": "highlight",
            "Funny Moment": "fusion",
            "Beat Sync": "audio",
            "Subtitle Generator": "subtitles",
            "Script Writer": "decision",
            "Voice Cleanup": "audio",
            "Scene Enhance": "analysis",
        }
        card_qss = (
            f"QFrame#MediaWorkspaceAiToolCard {{ "
            f"background: qlineargradient(x1:0, y1:0, x2:0, y2:1, "
            f"stop:0 {c.surface_elevated}, stop:1 {c.surface}); "
            f"border: 1px solid {c.glass_border}; "
            f"border-radius: {r.md}px; }} "
            f"QFrame#MediaWorkspaceAiToolCard:hover {{ "
            f"border: 1px solid {c.accent_purple}; "
            f"background: qlineargradient(x1:0, y1:0, x2:0, y2:1, "
            f"stop:0 {c.surface_overlay}, stop:1 {c.surface_elevated}); }}"
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
        for idx, (title, icon_name) in enumerate(ai_tools):
            card = QFrame()
            card.setObjectName("MediaWorkspaceAiToolCard")
            card.setFrameShape(QFrame.Shape.StyledPanel)
            # Wire the card to its backend phase (or the Auto Edit
            # sequencer). Availability/gating stays owned by the pipeline:
            # _run_ai_tool re-checks available_phases() at click time.
            if title == "Auto Edit":
                self._register_click(card, self.start_auto_edit)
            elif title in ai_phase_map:
                self._register_click(
                    card,
                    lambda p=ai_phase_map[title], t=title: self._run_ai_tool(t, p),
                )
            else:
                # No backend phase exists (e.g. Thumbnail Generator): report
                # honestly on click rather than fabricating behavior.
                self._register_click(
                    card,
                    lambda t=title: self._detail_status.set_text(
                        f"{t}: no backend phase available"
                    ),
                )
            # Reference cards: square-ish tiles, icon stacked above a small
            # centered title (which may wrap to two lines).
            card.setMinimumHeight(88)
            # Ignored horizontal policy: the three grid columns split the
            # fixed 345px panel evenly instead of the cards' content minimums
            # forcing the scroll content wider than the panel (which squeezed
            # and overflowed the whole sidebar).
            card.setSizePolicy(
                QSizePolicy.Policy.Ignored,
                QSizePolicy.Policy.MinimumExpanding,
            )
            card.setStyleSheet(card_qss)
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(s.xs, s.xs, s.xs, s.xs)
            card_layout.setSpacing(s.xxs)

            # Badge row: tiny "AI" chip pinned top-right, per the reference.
            badge_row = QHBoxLayout()
            badge_row.setContentsMargins(0, 0, 0, 0)
            badge_row.setSpacing(0)
            badge_row.addStretch(1)
            badge = QLabel("AI", card)
            badge.setObjectName("MediaWorkspaceAiToolBadge")
            badge.setFont(self._theme.font("caption"))
            badge.setStyleSheet(chip_qss)
            badge.setSizePolicy(
                QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
            )
            badge_row.addWidget(badge, 0)
            card_layout.addLayout(badge_row)

            # Gradient icon tile, horizontally centered above the title.
            tile = QLabel(card)
            tile.setObjectName("MediaWorkspaceAiToolIcon")
            tile_side = 30
            icon_side = 15
            tile.setFixedSize(tile_side, tile_side)
            tile.setAlignment(Qt.AlignmentFlag.AlignCenter)
            tile.setPixmap(
                self._theme.icons.icon(
                    icon_name, c.text_primary, icon_side
                ).pixmap(icon_side, icon_side)
            )
            tile.setStyleSheet(
                f"#MediaWorkspaceAiToolIcon {{ "
                f"background: qlineargradient(x1:0, y1:0, x2:1, y2:1, "
                f"stop:0 {c.accent_blue}, stop:1 {c.accent_purple}); "
                f"border: 1px solid {c.glass_highlight}; "
                f"border-radius: {r.sm + 2}px; }}"
            )
            card_layout.addWidget(
                tile, 0, Qt.AlignmentFlag.AlignHCenter
            )

            title_lbl = QLabel(title, card)
            title_lbl.setObjectName("MediaWorkspaceAiToolTitle")
            title_lbl.setFont(self._theme.font("caption"))
            title_lbl.setWordWrap(True)
            title_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            title_lbl.setTextInteractionFlags(
                Qt.TextInteractionFlag.NoTextInteraction
            )
            title_lbl.setStyleSheet(
                f"#MediaWorkspaceAiToolTitle {{ color: {c.text_primary}; "
                f"background: transparent; }}"
            )
            title_lbl.setSizePolicy(
                QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
            )
            card_layout.addWidget(title_lbl)
            card_layout.addStretch(1)

            # Top-align each cell so an uneven (two-line) card in one column
            # does not vertically stretch its single-line neighbour.
            ai_grid.addWidget(
                card, idx // 3, idx % 3, Qt.AlignmentFlag.AlignTop
            )
        ai_grid.setColumnStretch(0, 1)
        ai_grid.setColumnStretch(1, 1)
        ai_grid.setColumnStretch(2, 1)
        stream.addLayout(ai_grid)

        # ---- Section 2: collapsible Properties accordions ---- #
        props_header = SectionHeader(self._theme, "PROPERTIES")
        props_header.setObjectName("MediaWorkspaceRightStreamSection")
        props_header.set_divider(True)
        self._style_stream_header(props_header, accent=True)
        # Trailing ✕ close glyph like the reference (decorative).
        props_close = QLabel(props_header)
        props_close.setObjectName("MediaWorkspacePropertiesClose")
        close_side = 12
        props_close.setPixmap(
            self._theme.icons.icon("x", c.text_muted, close_side)
            .pixmap(close_side, close_side)
        )
        props_close.setStyleSheet(
            "#MediaWorkspacePropertiesClose { background: transparent; }"
        )
        props_header.set_action(props_close)
        stream.addWidget(props_header)

        # Sub-tab pill strip (Transform active), matching the reference's
        # Transform / Video / Audio / Speed selector. Decorative only.
        subtab_row = QHBoxLayout()
        subtab_row.setContentsMargins(0, 0, 0, 0)
        subtab_row.setSpacing(s.xxs)
        for sub_text, sub_active in (
            ("Transform", True), ("Video", False),
            ("Audio", False), ("Speed", False),
        ):
            pill = QLabel(sub_text)
            pill.setObjectName(
                "MediaWorkspacePropsSubTabActive" if sub_active
                else "MediaWorkspacePropsSubTab"
            )
            pill.setFont(self._theme.font("caption"))
            pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
            if sub_active:
                pill.setStyleSheet(
                    f"#MediaWorkspacePropsSubTabActive {{ "
                    f"color: {c.text_primary}; font-weight: 600; "
                    f"background: rgba(168, 85, 247, 0.22); "
                    f"border: 1px solid rgba(168, 85, 247, 0.55); "
                    f"border-radius: {r.sm}px; "
                    f"padding: {s.xxs}px {s.xs}px; }}"
                )
            else:
                pill.setStyleSheet(
                    f"#MediaWorkspacePropsSubTab {{ "
                    f"color: {c.text_muted}; "
                    f"background: {c.surface}; "
                    f"border: 1px solid {c.border}; "
                    f"border-radius: {r.sm}px; "
                    f"padding: {s.xxs}px {s.xs}px; }}"
                )
            pill.setSizePolicy(
                QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed
            )
            subtab_row.addWidget(pill, 1)
        stream.addLayout(subtab_row)

        transform_acc = self._build_stream_accordion("Transform")
        # X / Y coordinate rows with axis-prefixed numeric fields; Scale
        # exposes a proportional-lock "Link" affordance matching the mock.
        transform_acc.add_axis_row("Position", "960.0", "540.0")
        transform_acc.add_axis_row("Scale", "100.0%", "100.0%", linked=True)
        self._prop_rotation = Slider(
            self._theme, minimum=-180.0, maximum=180.0, value=0.0,
            accent="blue",
        )
        transform_acc.add_slider_row(
            "Rotation",
            self._prop_rotation,
            "0.0°",
            reset=True,
        )
        transform_acc.add_axis_row("Anchor Point", "0.0", "0.0")
        self._prop_opacity = Slider(
            self._theme, minimum=0.0, maximum=100.0, value=100.0,
            accent="blue",
        )
        transform_acc.add_slider_row(
            "Opacity",
            self._prop_opacity,
            "100%",
            reset=True,
        )
        stream.addWidget(transform_acc)
        # Property wiring: every slider writes through the controller's
        # existing set_setting (SettingsChanged on the backend bus). The
        # axis fields are wired after the accordion exists (below).
        self._prop_rotation.value_changed.connect(
            lambda v: self._on_property_changed("clip.rotation", round(v, 1))
        )
        self._prop_opacity.value_changed.connect(
            lambda v: self._on_property_changed("clip.opacity", round(v, 1))
        )
        self._wire_transform_fields(transform_acc)

        # ---- Section 3: EFFECTS (5) checkbox + toggle list ---- #
        effects_header = SectionHeader(self._theme, "EFFECTS (5)")
        effects_header.setObjectName("MediaWorkspaceRightStreamSection")
        effects_header.set_divider(True)
        self._style_stream_header(effects_header, accent=True)
        stream.addWidget(effects_header)

        effects_card = QFrame()
        effects_card.setObjectName("MediaWorkspaceEffectsList")
        effects_card.setFrameShape(QFrame.Shape.StyledPanel)
        effects_card.setStyleSheet(
            f"#MediaWorkspaceEffectsList {{ "
            f"background: {c.surface}; "
            f"border: 1px solid {c.border}; "
            f"border-radius: {r.md}px; }}"
        )
        effects_col = QVBoxLayout(effects_card)
        effects_col.setContentsMargins(s.sm, s.xs, s.sm, s.xs)
        effects_col.setSpacing(s.xs)
        for fx_name, fx_on in (
            ("Glow", True),
            ("Camera Shake", True),
            ("RGB Split", True),
            ("Gaussian Blur", False),
            ("Chromatic Aberration", True),
        ):
            fx_row = QHBoxLayout()
            fx_row.setContentsMargins(0, 0, 0, 0)
            fx_row.setSpacing(s.xs)
            check = QLabel("✓" if fx_on else "", effects_card)
            check.setObjectName("MediaWorkspaceEffectCheck")
            check_side = 15
            check.setFixedSize(check_side, check_side)
            check.setAlignment(Qt.AlignmentFlag.AlignCenter)
            if fx_on:
                check.setStyleSheet(
                    f"#MediaWorkspaceEffectCheck {{ "
                    f"color: {c.text_primary}; font-size: 9px; "
                    f"background: qlineargradient(x1:0, y1:0, x2:1, y2:1, "
                    f"stop:0 {c.accent_blue}, stop:1 {c.accent_purple}); "
                    f"border: 1px solid {c.glass_highlight}; "
                    f"border-radius: 4px; }}"
                )
            else:
                check.setStyleSheet(
                    f"#MediaWorkspaceEffectCheck {{ "
                    f"background: {c.surface_overlay}; "
                    f"border: 1px solid {c.border}; "
                    f"border-radius: 4px; }}"
                )
            fx_row.addWidget(check, 0, Qt.AlignmentFlag.AlignVCenter)
            fx_lbl = MetaLabel(
                self._theme, fx_name,
                role="primary" if fx_on else "muted",
                style="body_small",
            )
            fx_row.addWidget(fx_lbl, 1)
            fx_toggle = ToggleSwitch(
                self._theme, checked=fx_on, accent="blue"
            )
            fx_toggle.setObjectName("MediaWorkspaceEffectToggle")
            # Wire the toggle to the backend settings store (existing
            # set_setting seam). NOTE: the repository has no backend effect
            # renderers (no glow/blur/rgb-split/shake/aberration pipeline);
            # only the enabled-state persists. Reported as a genuine gap.
            fx_key = "effect." + fx_name.lower().replace(" ", "_")
            fx_toggle.toggled.connect(
                lambda on, k=fx_key: self._on_property_changed(k, bool(on))
            )
            fx_row.addWidget(fx_toggle, 0, Qt.AlignmentFlag.AlignVCenter)
            effects_col.addLayout(fx_row)
        stream.addWidget(effects_card)

        # ---- Section 4: RENDER QUEUE (2 tasks) ---- #
        export_header = SectionHeader(self._theme, "RENDER QUEUE")
        export_header.setObjectName("MediaWorkspaceRightStreamSection")
        export_header.set_divider(True)
        self._style_stream_header(export_header, accent=True)
        queue_count = MetaLabel(
            self._theme, "2 Tasks", role="muted", style="caption"
        )
        queue_count.setObjectName("MediaWorkspaceRenderQueueCount")
        export_header.set_action(queue_count)
        stream.addWidget(export_header)
        self._render_queue_count = queue_count

        self._render_task_row = self._build_stream_task(
            "Valorant Montage 4K",
            "4K \u00b7 60fps \u00b7 H.265 \u00b7 80 Mbps",
            0.62,
            "blue",
            thumb=True,
            eta="Remaining: 00:02:48",
            highlight=True,
        )
        stream.addWidget(self._render_task_row)
        self._render_task_row2 = self._build_stream_task(
            "YouTube Short Teaser",
            "1080p \u00b7 60fps \u00b7 H.264",
            0.0,
            "purple",
            thumb=True,
            pct_text="Waiting",
        )
        stream.addWidget(self._render_task_row2)

        # ---- Section 5: BACKGROUND TASKS (3 slim rows) ---- #
        tasks_header = SectionHeader(self._theme, "BACKGROUND TASKS")
        tasks_header.setObjectName("MediaWorkspaceRightStreamSection")
        tasks_header.set_divider(True)
        self._style_stream_header(tasks_header, accent=True)
        tasks_count = MetaLabel(
            self._theme, "3 Tasks", role="muted", style="caption"
        )
        tasks_count.setObjectName("MediaWorkspaceBackgroundTasksCount")
        tasks_header.set_action(tasks_count)
        stream.addWidget(tasks_header)
        self._bg_tasks_count = tasks_count

        self._bg_task_rows = {}
        for phase_key, title, subtitle, frac, icon in (
            ("analysis", "AI Scene Analysis",
             "Analyzing gameplay footage\u2026", 0.75, "bot"),
            ("subtitles", "Auto Subtitle Generation",
             "Transcribing voice track\u2026", 0.48, "type"),
            ("audio", "Voice Cleanup",
             "Removing background noise\u2026", 0.32, "mic"),
        ):
            row = self._build_stream_task(
                title, subtitle, frac, "cyan", icon=icon,
                icon_color=c.success,
            )
            self._bg_task_rows[phase_key] = row
            stream.addWidget(row)

        stream.addStretch(1)
        master_scroll.setWidget(content)
        return master_scroll

    def _build_stream_accordion(self, title: str) -> "_StreamAccordion":
        """Return a themed collapsible accordion frame for the right stream."""
        return _StreamAccordion(self._theme, title)

    def _style_stream_header(
        self, header: SectionHeader, *, accent: bool = False
    ) -> None:
        """Restyle a right-stream SectionHeader title as a compact caption.

        Visual-only: the reference panel renders its section titles as small
        uppercase blue captions ("PROPERTIES" / "EXPORT QUEUE" / ...), not
        h2 headings. This tweaks only the title QLabel's font and color on
        the already-built header (no SectionHeader API/behaviour change).
        """
        c = self._theme.tokens.colors
        color = c.accent_blue if accent else c.text_muted
        for label in header.findChildren(QLabel):
            if label.text() == header.title():
                label.setFont(self._theme.font("caption"))
                # Ensure section header title is never clipped by giving it
                # a minimum width based on its own text metrics.
                label.setMinimumWidth(
                    label.fontMetrics().horizontalAdvance(label.text()) + 8
                )
                label.setStyleSheet(
                    f"color: {color}; background: transparent; "
                    f"font-weight: 700; letter-spacing: 1px;"
                )
                break

    def _build_stream_task(
        self, title: str, subtitle: str, fraction: float, accent: str,
        *, thumb: bool = False, icon: Optional[str] = None,
        icon_color: Optional[str] = None, eta: Optional[str] = None,
        highlight: bool = False, pct_text: Optional[str] = None,
    ) -> QWidget:
        """Build one Background Tasks monitor row (label + ProgressBar).

        UI-only and decorative; ``fraction`` is a static 0..1 progress value
        and ``accent`` selects the ProgressBar accent. ``thumb`` adds a small
        gradient clip-thumbnail tile on the left (Render Queue rows);
        ``icon`` adds a rounded icon tile instead (Background Tasks rows),
        tinted with ``icon_color``; ``eta`` renders a trailing accent-colored
        ETA next to the percentage; ``highlight`` wraps the row in an
        accent-bordered card (the reference's active render job);
        ``pct_text`` overrides the trailing percent label (e.g. "Waiting").
        No backend is involved.
        """
        tokens = self._theme.tokens
        c = tokens.colors
        s = tokens.spacing

        row = QWidget()
        # Ignored horizontal policy: rows fit the fixed panel width instead
        # of their content minimums widening the scroll content (same fix as
        # the AI card grid).
        row.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        row.setObjectName(
            "MediaWorkspaceBackgroundTaskActive" if highlight
            else "MediaWorkspaceBackgroundTask"
        )
        if highlight:
            row.setStyleSheet(
                f"#MediaWorkspaceBackgroundTaskActive {{ "
                f"background: rgba(168, 85, 247, 0.10); "
                f"border: 1px solid rgba(168, 85, 247, 0.45); "
                f"border-radius: {tokens.radius.md}px; }}"
            )
        else:
            row.setStyleSheet(
                f"#MediaWorkspaceBackgroundTask {{ background: transparent; }}"
            )
        outer = QHBoxLayout(row)
        pad_h = s.sm if highlight else 0
        outer.setContentsMargins(pad_h, s.xs if highlight else s.xxs,
                                 pad_h, s.xs if highlight else s.xxs)
        outer.setSpacing(s.sm)

        if thumb:
            tile = QLabel(row)
            tile.setObjectName("MediaWorkspaceTaskThumb")
            tile.setFixedSize(44, 32)
            tile.setStyleSheet(
                f"#MediaWorkspaceTaskThumb {{ "
                f"background: qlineargradient(x1:0, y1:0, x2:1, y2:1, "
                f"stop:0 {c.accent_purple}, stop:0.5 #1A1030, "
                f"stop:1 {c.accent_blue}); "
                f"border: 1px solid {c.glass_border}; "
                f"border-radius: {tokens.radius.sm}px; }}"
            )
            outer.addWidget(tile, 0, Qt.AlignmentFlag.AlignTop)
        elif icon is not None:
            tint = icon_color or c.accent_blue
            tile = QLabel(row)
            tile.setObjectName("MediaWorkspaceTaskIcon")
            tile_side = 28
            glyph = 14
            tile.setFixedSize(tile_side, tile_side)
            tile.setAlignment(Qt.AlignmentFlag.AlignCenter)
            tile.setPixmap(
                self._theme.icons.icon(icon, tint, glyph)
                .pixmap(glyph, glyph)
            )
            tile.setStyleSheet(
                f"#MediaWorkspaceTaskIcon {{ "
                f"background: {c.surface_overlay}; "
                f"border: 1px solid {c.glass_border}; "
                f"border-radius: {tokens.radius.sm}px; }}"
            )
            outer.addWidget(tile, 0, Qt.AlignmentFlag.AlignTop)

        body = QVBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(s.xxs)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(s.sm)
        title_lbl = MetaLabel(
            self._theme, title, role="primary", style="body_small"
        )
        top.addWidget(title_lbl, 0)
        top.addStretch(1)
        if eta:
            eta_lbl = MetaLabel(
                self._theme, eta, role="muted", style="caption"
            )
            eta_lbl.setStyleSheet(f"color: {c.accent_cyan};")
            top.addWidget(eta_lbl, 0)
        pct_lbl = MetaLabel(
            self._theme,
            pct_text if pct_text is not None
            else f"{int(round(fraction * 100))}%",
            role="muted", style="caption",
        )
        top.addWidget(pct_lbl, 0)
        body.addLayout(top)

        sub_lbl = MetaLabel(self._theme, subtitle, role="muted", style="caption")
        body.addWidget(sub_lbl)

        progress = ProgressBar(self._theme, value=fraction, accent=accent)
        body.addWidget(progress)
        outer.addLayout(body, 1)
        # Expose the row's dynamic parts as attributes so the queue/task
        # observers can update REAL progress without any layout change.
        row._title_lbl = title_lbl
        row._sub_lbl = sub_lbl
        row._pct_lbl = pct_lbl
        row._progress = progress
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

        # Prompt input + Ask button: wired to the AIController (ai_core
        # pipeline) when one is available; reports honestly otherwise.
        self._ai_prompt = TextField(
            self._theme, placeholder="Ask the AI to edit\u2026"
        )
        self._ai_prompt.setObjectName("MediaWorkspaceAiPrompt")
        inner.addWidget(self._ai_prompt)
        ask = NeonButton(self._theme, "Ask AI", variant="primary", accent="purple")
        ask.setObjectName("MediaWorkspaceAiAsk")
        ask.clicked.connect(self._on_ai_ask)
        self._ai_prompt.return_pressed.connect(self._on_ai_ask)
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
        # Suggested-action -> real behavior. Phase actions run the backend
        # pipeline; AI-text actions go through the AIController; unmapped
        # actions report honestly on click.
        action_slots = {
            "Auto Edit": self.start_auto_edit,
            "Generate Highlights": lambda: self._run_ai_tool(
                "Generate Highlights", "highlight"),
            "Generate Captions": lambda: self._run_ai_tool(
                "Generate Captions", "subtitles"),
            "Clean Audio": lambda: self._run_ai_tool(
                "Clean Audio", "audio"),
            "Create Thumbnail": lambda: self._submit_ai(
                "generate_thumbnail", "Create a thumbnail brief for this video"),
        }
        pair_row = None
        for index, label in enumerate(action_labels):
            if index % 2 == 0:
                pair_row = QHBoxLayout()
                pair_row.setContentsMargins(0, 0, 0, 0)
                pair_row.setSpacing(tokens.spacing.xs)
                actions_grid.addLayout(pair_row)
            btn = NeonButton(self._theme, label, variant="ghost", accent="cyan")
            btn.setObjectName("MediaWorkspaceAiAction")
            slot = action_slots.get(label)
            if slot is not None:
                btn.clicked.connect(lambda _=False, s=slot: s())
            else:
                btn.clicked.connect(
                    lambda _=False, l=label: self._detail_status.set_text(
                        f"{l}: no backend capability yet"
                    )
                )
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
        # Tall enough for the toolbar + ruler + all 7 pro-NLE lanes (34px
        # each) without squeezing, like the reference timeline region.
        region.setMinimumHeight(360)
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

        # Track order preserves the frozen indices (0 = video, 1 = audio)
        # that the demo clips and tests rely on; the extra pro-NLE lanes
        # (Video Track 2 / Overlay / Text / Effects / Audio Track 2) are
        # appended after them (visual-only). Reference-style names so the
        # header chips read V1 / A1 / V2 / OV / A2 / A3 / A4 like the mock.
        self._timeline = Timeline(
            self._theme,
            duration=60.0,
            tracks=[
                "Video Track 1",
                "Music",
                "Video Track 2",
                "Overlay Track",
                "SFX",
                "Voice",
                "Subtitles",
            ],
        )
        # Clips 0-2 are the frozen demo clips (identical values); the rest
        # are appended decorative chips that dress the new lanes like the
        # reference gaming-montage timeline (visual-only, append-only).
        # Wire real thumbnail decoding for video clips in the timeline.
        self._timeline.set_thumbnail_fn(self._decode_timeline_thumbnail)
        self._timeline.set_clips(
            [
                {"track": 0, "start": 0.0, "length": 12.0, "label": "Intro"},
                {"track": 0, "start": 12.0, "length": 20.0, "label": "Gameplay"},
                {"track": 1, "start": 0.0, "length": 32.0, "label": "Music"},
                {"track": 2, "start": 4.0, "length": 10.0,
                 "label": "Valorant 2026-05-08.mp4", "kind": "video"},
                {"track": 2, "start": 18.0, "length": 8.0, "label": "Replay",
                 "kind": "video"},
                {"track": 3, "start": 2.0, "length": 9.0,
                 "label": "Facecam_01.mp4", "kind": "overlay"},
                {"track": 3, "start": 15.0, "length": 8.0,
                 "label": "Killfeed Overlay", "kind": "overlay"},
                {"track": 4, "start": 3.0, "length": 26.0, "label": "SFX",
                 "kind": "audio"},
                {"track": 5, "start": 6.0, "length": 24.0,
                 "label": "Voice Commentary.wav", "kind": "voice"},
                {"track": 6, "start": 1.0, "length": 4.0,
                 "label": "One enemy remaining.", "kind": "text"},
                {"track": 6, "start": 7.0, "length": 4.0,
                 "label": "Nice shot!", "kind": "text"},
                {"track": 6, "start": 13.0, "length": 4.0,
                 "label": "Spike planted.", "kind": "text"},
                {"track": 6, "start": 19.0, "length": 5.0,
                 "label": "This is my moment.", "kind": "text"},
                {"track": 6, "start": 26.0, "length": 4.0, "label": "Clutch!",
                 "kind": "text"},
                {"track": 6, "start": 32.0, "length": 4.0, "label": "GG WP!",
                 "kind": "text"},
            ]
        )
        inner.addWidget(self._timeline, 1)

        card.set_content(content)
        layout.addWidget(card, 1)
        return region

    # ------------------------------------------------------------------ #
    # Media import (file dialog + drag & drop; reuses VideoPicker filtering)
    # ------------------------------------------------------------------ #
    _VIDEO_SUFFIXES = (".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v")

    def _on_import_requested(self) -> None:
        """Open a native file dialog and add the chosen videos to the browser.

        Reuses the existing MediaBrowser API (set_items/select); when real
        media discovery is active the chosen paths are registered with the
        PreviewMediaSource path map so selection resolves to full paths.
        """
        from PySide6.QtWidgets import QFileDialog

        patterns = " ".join(f"*{s}" for s in self._VIDEO_SUFFIXES)
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Import Media", "", f"Video Files ({patterns});;All Files (*)"
        )
        if paths:
            self._add_media_paths(paths)

    def _add_media_paths(self, paths) -> None:
        """Append video paths to the browser (dedup; select the first new).

        Accepts str/Path items; non-video suffixes are filtered out with the
        same suffix vocabulary VideoPicker uses. Existing items are preserved.
        """
        from pathlib import Path as _P

        current = self._browser.items()
        added = []
        for raw in paths:
            p = _P(str(raw))
            if p.suffix.lower() not in self._VIDEO_SUFFIXES:
                continue
            name = p.name
            # Register the full path so selection can resolve it.
            if self._media_source is not None:
                self._media_source._paths[name] = p
            else:
                self._imported_paths[name] = p
            if name not in current and name not in added:
                added.append(name)
        if not added:
            return
        self._browser.set_items(current + added)
        # Select the first newly imported item (drives the backend when a
        # controller is present via the existing selection_changed wiring).
        self._browser.select(len(current))

    def dragEnterEvent(self, event) -> None:  # noqa: N802 (Qt override)
        """Accept drags carrying local video file URLs."""
        mime = event.mimeData()
        if mime.hasUrls() and any(
            url.isLocalFile()
            and url.toLocalFile().lower().endswith(self._VIDEO_SUFFIXES)
            for url in mime.urls()
        ):
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: N802 (Qt override)
        """Import dropped local video files via the shared add path."""
        paths = [
            url.toLocalFile()
            for url in event.mimeData().urls()
            if url.isLocalFile()
        ]
        if paths:
            self._add_media_paths(paths)
            event.acceptProposedAction()

    # ------------------------------------------------------------------ #
    # Thumbnail loading (lazy, one per tick; reuses PreviewMediaSource)
    # ------------------------------------------------------------------ #
    def _start_thumbnail_loading(self) -> None:
        """Queue browser rows for thumbnail decoding (one per idle tick).

        Each tick decodes AT MOST one first frame via the existing
        PreviewMediaSource (FFmpegService seam) and applies it as the row
        button's icon. Decoded thumbnails are cached by name; the timer stops
        when the queue drains. Skipped entirely without a real media source.
        """
        if self._media_source is None:
            return
        self._thumb_cache = {}
        self._thumb_queue = list(self._browser.items())
        if not self._thumb_queue:
            return
        self._thumb_timer = QTimer(self)
        self._thumb_timer.setInterval(150)
        self._thumb_timer.timeout.connect(self._load_next_thumbnail)
        self._thumb_timer.start()

    def _load_next_thumbnail(self) -> None:
        """Decode and apply one queued thumbnail; stop when the queue drains."""
        queue = getattr(self, "_thumb_queue", None)
        if not queue:
            timer = getattr(self, "_thumb_timer", None)
            if timer is not None:
                timer.stop()
            return
        name = queue.pop(0)
        if name in self._thumb_cache:
            return
        image = self._media_source.load_first_frame(name)
        if image is None:
            return
        from PySide6.QtGui import QIcon

        pixmap = QPixmap.fromImage(image).scaled(
            48, 27,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        icon = QIcon(pixmap)
        self._thumb_cache[name] = icon
        # Apply to the matching browser row's inner QPushButton.
        try:
            items = self._browser.items()
            index = items.index(name)
            button = self._browser._buttons[index]
            inner = getattr(button, "_button", None)
            if inner is not None:
                from PySide6.QtCore import QSize

                inner.setIcon(icon)
                inner.setIconSize(QSize(48, 27))
        except (ValueError, IndexError, AttributeError):
            pass

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

        Performance: decoded frames are cached per (path, frame-bucket) in a
        small bounded LRU so scrubbing back over recent positions redisplays
        instantly, and a repeat request for the bucket already on screen is
        a no-op (no redundant ffmpeg subprocess per timer tick).
        """
        if self._controller is None or self._media_path is None:
            return
        # Quantize to a display bucket (~10 buckets/second) for caching.
        bucket = (str(self._media_path), int(seconds * 10))
        if getattr(self, "_frame_on_screen", None) == bucket:
            return
        cache = getattr(self, "_frame_cache", None)
        if cache is None:
            from collections import OrderedDict

            cache = self._frame_cache = OrderedDict()
        cached = cache.get(bucket)
        if cached is not None:
            cache.move_to_end(bucket)
            self._frame_on_screen = bucket
            self._show_cached_pixmap(cached)
            return
        try:
            frame = self._controller.decode_frame(self._media_path, seconds)
        except Exception:
            return
        if frame is not None:
            self._frame_on_screen = bucket
            self.show_frame(frame)
            pixmap = self._preview_frame.pixmap()
            if pixmap is not None and not pixmap.isNull():
                cache[bucket] = pixmap
                cache.move_to_end(bucket)
                while len(cache) > 120:  # ~12s of scrub history
                    cache.popitem(last=False)

    def _show_cached_pixmap(self, pixmap) -> None:
        """Display an already-scaled cached pixmap in the frame sink."""
        self._preview_placeholder.setVisible(False)
        self._preview_play_tile.setVisible(False)
        self._preview_frame.setPixmap(pixmap)
        self._preview_frame.setVisible(True)

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
            # BGR888 avoids the per-frame numpy channel reversal (a full
            # 2.7MB copy at 720p) — Qt swizzles during the scale instead.
            # `buf` must outlive the QImage until scaled() deep-copies.
            buf = bgr.tobytes()
            image = QImage(buf, width, height, 3 * width,
                           QImage.Format.Format_BGR888)
        except Exception:
            return
        zoom_text = getattr(self, "_preview_zoom", "Fit")
        # Determine the target size for scaling.  Use the frame size
        # if it's been laid out, otherwise fall back to the stage size.
        target = self._preview_frame.size()
        if target.width() <= 100 or target.height() <= 100:
            stage = self._preview_frame.parentWidget()
            if stage is not None:
                target = stage.size()
        # Scaling mode: smooth for stills (seek/pause), fast during
        # playback — smooth scaling of HD frames on the GUI thread costs
        # more than a frame interval and drops the display rate.
        mode = (
            Qt.TransformationMode.FastTransformation
            if self._timeline.is_playing()
            else Qt.TransformationMode.SmoothTransformation
        )
        if zoom_text == "Fill" and target.width() > 0 and target.height() > 0:
            # Fill: scale to cover, then crop center (filmic look).
            sx = target.width() / max(1, width)
            sy = target.height() / max(1, height)
            s = max(sx, sy)
            sw = int(width * s)
            sh = int(height * s)
            image = image.scaled(sw, sh,
                                 Qt.AspectRatioMode.KeepAspectRatio,
                                 mode)
            # Center-crop to target
            cx = (sw - target.width()) // 2
            cy = (sh - target.height()) // 2
            image = image.copy(cx, cy, target.width(), target.height())
        elif zoom_text != "Fit" and zoom_text.endswith("%"):
            try:
                s = float(zoom_text.rstrip("%")) / 100.0
                image = image.scaled(
                    int(width * s), int(height * s),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    mode,
                )
            except ValueError:
                pass
        elif target.width() > 0 and target.height() > 0:
            image = image.scaled(
                target,
                Qt.AspectRatioMode.KeepAspectRatio,
                mode,
            )
        pixmap = QPixmap.fromImage(image)
        # Hide the empty-state chrome so the preview frame fills the stage.
        self._preview_placeholder.setVisible(False)
        self._preview_play_tile.setVisible(False)
        hint = self.findChild(QLabel, "MediaWorkspacePreviewHint")
        if hint is not None:
            hint.setVisible(False)
        safe = self.findChild(QFrame, "MediaWorkspacePreviewSafeArea")
        if safe is not None:
            safe.setVisible(False)
        # Force the QLabel to the stage size so scaling targets the full
        # viewport (prevents the label from shrinking to the pixmap size).
        stage = self._preview_frame.parentWidget()
        if stage is not None:
            self._preview_frame.resize(stage.size())
        self._preview_frame.setPixmap(pixmap)
        self._preview_frame.setVisible(True)

    def clear_frame(self) -> None:
        """Hide the frame sink and restore the empty-state placeholder."""
        self._preview_frame.clear()
        self._preview_frame.setVisible(False)
        hint = self.findChild(QLabel, "MediaWorkspacePreviewHint")
        if hint is not None:
            hint.setVisible(True)
        safe = self.findChild(QFrame, "MediaWorkspacePreviewSafeArea")
        if safe is not None:
            safe.setVisible(True)

    def _decode_timeline_thumbnail(self, source_path: str, seconds: float):
        """Decode a single frame for a timeline clip thumbnail (returns QImage)."""
        if self._controller is None:
            return None
        try:
            resolved = self._resolve_media_path(source_path)
            frame = self._controller.decode_frame(resolved, seconds)
            if frame is None:
                return None
            h, w = frame.shape[:2]
            rgb = frame[:, :, ::-1].copy()
            return QImage(rgb.tobytes(), w, h, 3 * w,
                          QImage.Format.Format_RGB888).copy()
        except Exception:
            return None

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

    def _invalidate_frame_cache(self) -> None:
        """Drop cached preview pixmaps AND timeline thumbnails."""
        cache = getattr(self, "_frame_cache", None)
        if cache is not None:
            cache.clear()
        self._frame_on_screen = None
        # Also clear timeline thumbnail cache so new media gets fresh thumbs.
        thumb_cache = getattr(self._timeline, "_thumb_cache", None)
        if thumb_cache is not None:
            thumb_cache.clear()

    def _reset_audio_for_new_media(self) -> None:
        """Stop audio and background decoder, invalidate caches for a new selection."""
        self._stop_decoder()
        if self._audio_player is not None:
            self._audio_player.stop()
        self._audio_loaded_for = None
        self._invalidate_frame_cache()

    def _resolve_media_path(self, item: str):
        """Resolve a browser display name to its full path when known.

        Names discovered by the PreviewMediaSource or added via import/drop
        map to their real filesystem paths; unknown names pass through
        unchanged (the original behavior, relied on by tests seeding paths
        directly).
        """
        if self._media_source is not None:
            resolved = self._media_source.path_for(item)
            if resolved is not None:
                return resolved
        resolved = self._imported_paths.get(item)
        return resolved if resolved is not None else item

    def _reflect_selected_video(self, item: str) -> None:
        """Drive ``select_video`` and reflect the controller's ProjectState.

        Integration-only helper (called when a WorkflowController is present).
        Reuses the controller's existing write (``select_video``) and read
        (``project_state``) surface; it invents no new backend API and mutates
        no frozen component. The authoritative ``ProjectState`` snapshot is
        then observed by :meth:`_reflect_preview`.
        """
        try:
            self._controller.select_video(self._resolve_media_path(item))
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
        # Real media duration -> the single playback clock (Timeline widget),
        # via the backend's existing metadata service. A fresh baseline
        # (single media-spanning clip) is written when there is no backend
        # timeline yet OR when the previous timeline was an auto-created,
        # never-edited baseline for a DIFFERENT media file (switching media
        # must not keep the old duration). A user-edited timeline is never
        # discarded.
        try:
            meta = self._controller.media_metadata(video_path)
            duration = float(getattr(meta, "duration", 0.0) or 0.0)
            existing = self._controller.timeline()
            baseline_for = getattr(self, "_baseline_media", None)
            replaceable = (
                existing is None
                or (
                    baseline_for is not None
                    and baseline_for != str(video_path)
                    and not getattr(self, "_timeline_user_edited", False)
                )
            )
            if duration > 0 and replaceable:
                self._timeline.set_duration(duration)
                # Replace demo clips with a single media-spanning clip.
                self._timeline.set_clips([
                    {
                        "track": 0,
                        "start": 0.0,
                        "length": duration,
                        "label": display,
                    }
                ])
                self._timeline.select_clip(-1)
                self._persist_timeline_to_backend(record_history=False)
                self._last_clips_snapshot = self._timeline.clips()
                self._baseline_media = str(video_path)
                self._timeline_user_edited = False
        except Exception:
            pass
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

    def _run_ai_tool(self, title: str, phase_id: str) -> None:
        """Run an AI tool card's backend phase with pipeline-owned gating.

        Availability is re-checked at click time via the controller's
        existing available_phases() (the registry/pipeline own ordering and
        dependencies — nothing is hardcoded here). A blocked or unknown
        phase, a busy controller, and UI-only mode are all reported in the
        Details status row instead of failing silently.
        """
        if self._controller is None:
            self._detail_status.set_text(f"{title}: no backend connected")
            return
        if self._controller.is_phase_running():
            self._detail_status.set_text(f"{title}: a phase is already running")
            return
        runnable = {
            getattr(p, "id", None) for p in self._controller.available_phases()
        }
        if phase_id not in runnable:
            self._detail_status.set_text(
                f"{title}: blocked — run its dependencies first"
            )
            return
        if self._controller.run_phase(phase_id):
            self._set_phase_status(f"Running: {phase_id}")
        else:
            self._detail_status.set_text(f"{title}: could not start")

    # ------------------------------------------------------------------ #
    # Auto Edit: sequence the existing pipeline (order owned by gui_core)
    # ------------------------------------------------------------------ #
    def start_auto_edit(self) -> bool:
        """Run the AI pipeline end to end using the existing gating pipeline.

        Reuses controller.available_phases() (pipeline/registry order) to pick
        the next runnable phase and controller.run_phase() to execute it. The
        sequence advances on each phase_completed by re-querying availability,
        so ordering/gating stays owned by gui_core.Pipeline. Returns whether a
        first phase was started.
        """
        if self._controller is None:
            return False
        self._auto_edit_active = True
        self._auto_edit_attempted = set()
        return self._run_next_auto_phase()

    def _run_next_auto_phase(self) -> bool:
        """Run the next not-yet-attempted runnable phase; stop when none left."""
        if self._controller is None or not self._auto_edit_active:
            return False
        for plugin in self._controller.available_phases():
            phase_id = getattr(plugin, "id", None)
            if phase_id is None or phase_id in self._auto_edit_attempted:
                continue
            self._auto_edit_attempted.add(phase_id)
            if self._controller.run_phase(phase_id):
                return True
        # Nothing new to run: the pipeline is complete for now.
        self._auto_edit_active = False
        return False

    def export(self) -> bool:
        """Render/export the current project via the existing 'render' phase.

        Reuses the frozen render pipeline (VideoEditor + FFmpegService) through
        WorkflowController.run_phase("render"); real FFmpeg rendering and its
        artifact/lifecycle events are produced by the existing backend. The
        render phase is gated by the pipeline (it requires the decision/edit
        plan artifact), so this returns False when render is not currently
        runnable, when there is no controller, or when a phase is already
        running. Progress/completion surface through the existing phase
        observers.
        """
        if self._controller is None:
            return False
        return self._controller.run_phase("render")

    def _set_phase_status(self, text: str) -> None:
        """Reflect phase run state into the existing Preview HUD status label.

        Pulses the badge with a brief opacity animation so status changes are
        visually noticed by the user.
        """
        badge = getattr(self, "_preview_status_badge", None)
        if badge is None:
            return
        badge.setText(text)
        # Pulse opacity: 1 → 0.5 → 1 for a subtle visual confirmation.
        from gui.widgets.animation import tween_value
        tween_value(
            0.5, 1.0, lambda v: badge.setStyleSheet(
                f"#MediaWorkspacePreviewStatusBadge {{ color: {self._theme.tokens.colors.text_secondary}; "
                f"background: {self._theme.tokens.colors.surface_overlay}; "
                f"border: 1px solid {self._theme.tokens.colors.glass_border}; "
                f"border-radius: {self._theme.tokens.radius.sm}px; "
                f"padding: {self._theme.tokens.spacing.xxs}px {self._theme.tokens.spacing.sm}px; "
                f"opacity: {v}; }}"
            ),
            duration_ms=300,
            easing=self._theme.easing("out_cubic"),
        )

    def _on_phase_started(self, phase_id: str) -> None:
        """Observer: a background phase run began."""
        self._set_phase_status(f"Running: {phase_id}")
        self._reflect_task_row(phase_id, running=True)
        if phase_id == "render":
            self._enqueue_render_job()

    def _reflect_task_row(
        self, phase_id: str, *, running: bool, success: bool = True
    ) -> None:
        """Reflect a phase run's real state into its Background Tasks row.

        Rows exist for analysis / subtitles / audio (the frozen UI rows);
        other phases update only the HUD badge. Progress is indeterminate
        for a running phase (the backend reports no fraction), so the row
        shows a running/'done' state honestly rather than a fabricated %.
        """
        row = getattr(self, "_bg_task_rows", {}).get(phase_id)
        if row is None:
            return
        if running:
            row._pct_lbl.set_text("Running…")
            row._progress.set_value(0.1)
        else:
            row._pct_lbl.set_text("Done" if success else "Failed")
            row._progress.set_value(1.0 if success else 0.0)
        # Live count of running background rows.
        counter = getattr(self, "_bg_tasks_count", None)
        if counter is not None:
            active = sum(
                1 for r in self._bg_task_rows.values()
                if r._pct_lbl.text() == "Running…"
            )
            counter.set_text(f"{active} Active" if active else "Idle")

    # ------------------------------------------------------------------ #
    # Render queue (real gui_core.RenderQueue model behind the frozen rows)
    # ------------------------------------------------------------------ #
    def _enqueue_render_job(self) -> None:
        """Track the running render phase as a RenderJob in a RenderQueue."""
        from gui_core import RenderJob, RenderQueue

        if not hasattr(self, "_render_queue"):
            self._render_queue = RenderQueue()
        stem = getattr(self._media_path, "stem", None) or "render"
        job_id = f"job_{len(self._render_queue.jobs) + 1}"
        job = RenderJob(id=job_id, source=stem).mark_running()
        self._render_queue = self._render_queue.enqueue(job)
        self._active_render_job = job_id
        # Real elapsed-time tracking: the backend PhaseRunner reports no
        # fractional progress, so the row shows REAL elapsed seconds (and an
        # elapsed-based estimate against media duration) instead of a fake
        # frozen percentage. Ticks once per second while running.
        import time as _time

        self._render_started_at = _time.monotonic()
        if not hasattr(self, "_render_tick_timer"):
            self._render_tick_timer = QTimer(self)
            self._render_tick_timer.setInterval(1000)
            self._render_tick_timer.timeout.connect(self._reflect_render_queue)
        self._render_tick_timer.start()
        self._reflect_render_queue()

    def _finish_render_job(self, success: bool, message: str = "") -> None:
        """Mark the active render job terminal and refresh the queue rows."""
        job_id = getattr(self, "_active_render_job", None)
        if job_id is None or not hasattr(self, "_render_queue"):
            return
        job = self._render_queue.job_by_id(job_id)
        if job is None:
            return
        job = job.mark_succeeded() if success else job.mark_failed(message)
        self._render_queue = self._render_queue.replace_job(job)
        self._active_render_job = None
        timer = getattr(self, "_render_tick_timer", None)
        if timer is not None:
            timer.stop()
        self._reflect_render_queue()

    def _reflect_render_queue(self) -> None:
        """Reflect the real RenderQueue model into the frozen queue rows."""
        queue = getattr(self, "_render_queue", None)
        if queue is None:
            return
        counter = getattr(self, "_render_queue_count", None)
        if counter is not None:
            pending = queue.pending_count()
            total = len(queue.jobs)
            counter.set_text(
                f"{pending} Active" if pending else f"{total} Done"
            )
        row = getattr(self, "_render_task_row", None)
        if row is not None and queue.jobs:
            latest = queue.jobs[-1]
            row._title_lbl.set_text(latest.source)
            status = latest.status
            if status == "running":
                import time as _time

                elapsed = _time.monotonic() - getattr(
                    self, "_render_started_at", _time.monotonic()
                )
                row._sub_lbl.set_text(
                    f"Render · running · {int(elapsed)}s elapsed"
                )
                row._pct_lbl.set_text(f"{int(elapsed)}s")
                # Honest progress estimate: renders typically take on the
                # order of the media duration; cap at 90% until completion
                # is confirmed (never claim done before it is).
                duration = max(1.0, self._timeline.duration())
                row._progress.set_value(min(0.9, elapsed / duration))
            elif status == "succeeded":
                row._sub_lbl.set_text("Render · complete")
                row._pct_lbl.set_text("Done")
                row._progress.set_value(1.0)
            else:
                row._sub_lbl.set_text(f"Render · {status}")
                row._pct_lbl.set_text(status.capitalize())
                row._progress.set_value(0.0)

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
        phase_id = getattr(result, "phase_id", "")
        self._reflect_task_row(phase_id, running=False, success=success)
        if phase_id == "render":
            self._finish_render_job(
                success, str(getattr(result, "message", ""))
            )
        if self._controller is None:
            return
        try:
            state = self._controller.project_state()
        except Exception:
            return
        self._detail_status.set_text(self._artifact_status(state))
        # Auto Edit: advance to the next runnable phase on success; stop on
        # failure. Availability is re-queried so order stays pipeline-owned.
        if self._auto_edit_active:
            if success:
                self._run_next_auto_phase()
            else:
                self._auto_edit_active = False

    def _on_phase_failed(self, message: str) -> None:
        """Observer: a phase run raised; reflect the failure."""
        self._set_phase_status("Failed")
        # A raised run never delivered a result; close out any open render
        # job and any running task rows honestly.
        self._finish_render_job(False, message)
        for phase_id, row in getattr(self, "_bg_task_rows", {}).items():
            if row._pct_lbl.text() == "Running…":
                self._reflect_task_row(phase_id, running=False, success=False)

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

    def _build_backend_timeline(self):
        """Map the Timeline widget's current model into a gui_core.Timeline.

        The Timeline widget exposes no persistent clip identifier: its clip is
        a plain dict (track/start/length/label) and the widget's own identity
        for a clip is its positional index (used by select/move/trim). The
        backend model requires unique clip ids, so ids are derived from that
        same index (``clip_<i>``) -- mirroring the widget's existing identity
        rather than inventing a separate id scheme.

        May raise ValueError from backend Timeline/Clip validation (e.g. an
        overlapping or out-of-bounds edit); callers handle that explicitly.
        """
        from gui_core import Timeline, Track
        from gui_core.timeline import Clip as BackendClip

        names = self._timeline.tracks()
        tracks = tuple(Track(index=i, name=name) for i, name in enumerate(names))
        backend = Timeline(duration=float(self._timeline.duration()), tracks=tracks)
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
        return backend

    def _persist_timeline_to_backend(self, record_history: bool = True) -> None:
        """Persist the Timeline widget's model into the backend Timeline.

        Maps the widget model to a validated gui_core.Timeline and calls
        controller.update_timeline (publishing TimelineChanged). No-op without
        a controller (history is still recorded so undo/redo works UI-only).

        Validation failures are NOT silently ignored: a backend ValueError
        (invalid edit) is surfaced in the Details status row so the user sees
        the edit did not persist. The Qt thread is never crashed, but the
        failure is reported rather than swallowed.
        """
        # History: push the pre-edit snapshot (captured after the previous
        # persist) so Ctrl+Z restores the state before this edit.
        if record_history:
            # Any user edit marks the timeline as owned by the user, so a
            # media switch will no longer replace it with a fresh baseline.
            self._timeline_user_edited = True
            previous = getattr(self, "_last_clips_snapshot", None)
            if previous is not None:
                if not hasattr(self, "_undo_stack"):
                    self._undo_stack, self._redo_stack = [], []
                self._undo_stack.append(previous)
                if len(self._undo_stack) > 100:
                    self._undo_stack.pop(0)
                self._redo_stack.clear()
        self._last_clips_snapshot = self._timeline.clips()
        if self._controller is None:
            return
        try:
            backend = self._build_backend_timeline()
        except ValueError as exc:
            # Invalid edit (e.g. overlap / out of bounds): surface it.
            self._detail_status.set_text(f"Timeline: invalid edit \u2014 {exc}")
            return
        self._controller.update_timeline(backend)
        # Successful persist: restore the artifact-derived status.
        try:
            self._detail_status.set_text(
                self._artifact_status(self._controller.project_state())
            )
        except Exception:
            pass

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
        """Mirror the timeline transport state onto the TransportBar."""
        self._transport.set_state(state)
        if state == "playing":
            self._start_decoder()
        elif state in ("paused", "stopped"):
            self._stop_decoder()

    def _start_decoder(self) -> None:
        """Start the persistent-pipe background decoder for smooth playback."""
        if self._decoder is not None:
            return
        if self._controller is None or self._media_path is None:
            return
        fps = self._media_fps()
        start = self._timeline.playhead()
        decoder = _FrameDecoder(
            self._controller, self._media_path,
            fps=fps, max_frames=8, start_at=start,
        )
        # Wire decoder error signal to show failures to user
        decoder.error.connect(self._on_decoder_error)
        decoder.start()
        self._decoder = decoder
        # Frame pacing: frame N of this stream corresponds to media time
        # start + N/fps. A frame is popped only once the playhead reaches
        # its timestamp, so display speed always matches the playhead
        # (including rate changes) regardless of decode speed.
        self._decoder_start = start
        self._decoder_frames_shown = 0
        self._decoder_fps = fps

    def _stop_decoder(self) -> None:
        """Stop the background decoder (idempotent)."""
        dec = self._decoder
        if dec is None:
            return
        self._decoder = None
        dec.stop_decoding()
        dec.quit()
        dec.wait(2000)

    def _on_decoder_error(self, message: str) -> None:
        """Handle decoder errors by stopping playback and showing error to user."""
        self._timeline.pause()
        self._stop_decoder()
        self._detail_status.set_text(f"Playback error: {message}")
        # Show error in preview status badge too
        badge = getattr(self, "_preview_status_badge", None)
        if badge is not None:
            badge.setText(f"Error: decode failed")

    def _pull_playback_frame(self, seconds: float):
        """Pull the next due frame from the decoder (paced to media time).

        Skips ahead (dropping late frames) when the playhead outran the
        stream, so audio/video never drift apart.
        """
        dec = self._decoder
        if dec is None:
            return None
        fps = getattr(self, "_decoder_fps", 30.0)
        start = getattr(self, "_decoder_start", 0.0)
        shown = getattr(self, "_decoder_frames_shown", 0)
        next_time = start + shown / fps
        if seconds + (0.5 / fps) < next_time:
            return None  # next frame not due yet
        frame = dec.pop()
        if frame is None:
            return None
        self._decoder_frames_shown = shown + 1
        # Catch-up: drop frames that are already older than the playhead.
        while start + self._decoder_frames_shown / fps < seconds - (1.0 / fps):
            skipped = dec.pop()
            if skipped is None:
                break
            frame = skipped
            self._decoder_frames_shown += 1
        return frame

    # ------------------------------------------------------------------ #
    # Preview playback wiring (transport seek / loop / step / speed / etc.)
    # ------------------------------------------------------------------ #
    def _on_transport_seek(self, fraction: float) -> None:
        """Drive the timeline playhead from the transport's seek scrubber.

        The timeline stays the single playback clock: its set_playhead emits
        playhead_changed which decodes+displays the frame and (via
        _on_playhead_changed -> transport.set_position) keeps the scrubber in
        sync without re-emitting seek_requested (no loop). A seek during
        playback re-anchors the streaming decoder at the new position.
        """
        duration = self._timeline.duration()
        target = max(0.0, min(1.0, fraction)) * duration
        if self._decoder is not None:
            self._decoder.seek(target)
            self._decoder_start = target
            self._decoder_frames_shown = 0
        self._timeline.set_playhead(target)

    def _on_playback_finished(self) -> None:
        """Loop playback when the loop toggle is active."""
        if getattr(self, "_loop_enabled", False):
            self._timeline.set_playhead(0.0)
            self._timeline.play()
            if self._audio_player is not None:
                self._audio_player.setPosition(0)
                self._audio_player.play()

    def _media_fps(self) -> float:
        """Return the selected media's fps via backend metadata (30.0 fallback).

        Cached per media path: metadata probing spawns an ffprobe subprocess,
        so it must never run per playhead tick.
        """
        cached = getattr(self, "_media_fps_cache", None)
        if cached is not None and cached[0] == self._media_path:
            return cached[1]
        fps = 30.0
        if self._controller is not None and self._media_path is not None:
            try:
                meta = self._controller.media_metadata(self._media_path)
                probed = float(getattr(meta, "fps", 0.0) or 0.0)
                if probed > 0:
                    fps = probed
            except Exception:
                pass
        self._media_fps_cache = (self._media_path, fps)
        return fps

    def _step_frames(self, frames: int) -> None:
        """Step the playhead by ``frames`` (negative steps backward)."""
        self._timeline.pause()
        step = frames / self._media_fps()
        self._timeline.set_playhead(self._timeline.playhead() + step)

    def _shuttle(self, seconds: float) -> None:
        """Jump the playhead by ``seconds`` (rewind/fast-forward)."""
        self._timeline.set_playhead(self._timeline.playhead() + seconds)

    def _wire_transport_buttons(self) -> None:
        """Connect the transport's frame-step / shuttle NeonButtons.

        The buttons already exist on the TransportBar (frozen object names);
        this only adds clicked connections. A missing button stays unwired.
        """
        from gui.widgets.neon_button import NeonButton as _NB

        for name, slot in (
            ("TransportPrevFrame", lambda: self._step_frames(-1)),
            ("TransportNextFrame", lambda: self._step_frames(1)),
            ("TransportRewind", lambda: self._shuttle(-5.0)),
            ("TransportFastForward", lambda: self._shuttle(5.0)),
            ("TransportFullscreen", self._on_toggle_fullscreen),
        ):
            btn = self._transport.findChild(_NB, name)
            if btn is not None:
                btn.clicked.connect(lambda _=False, s=slot: s())

    def _wire_viewer_toolbar(self) -> None:
        """Connect the viewer toolbar's zoom / screenshot / fullscreen controls."""
        self._loop_enabled = False
        self._decoder: Optional[_FrameDecoder] = None
        zoom = self.findChild(Dropdown, "MediaWorkspaceViewerZoom")
        if zoom is not None:
            zoom.changed.connect(self._on_viewer_zoom_changed)
        shot = self.findChild(NeonButton, "MediaWorkspaceViewerScreenshot")
        if shot is not None:
            shot.clicked.connect(self._on_screenshot)
        fs = self.findChild(NeonButton, "MediaWorkspaceViewerFullscreen")
        if fs is not None:
            fs.clicked.connect(self._on_toggle_fullscreen)
        # Playback speed: clicking the transport's existing rate chip cycles
        # through the preset rates. Loop: clicking the player toolbar's Loop
        # chip toggles looping. Both are existing labels; click handling is
        # added via event filters (wiring only, no widget change).
        self._rate_presets = (0.5, 1.0, 1.5, 2.0)
        self._rate_label = self._transport.findChild(QLabel, "TransportRate") \
            or getattr(self._transport, "_rate", None)
        if self._rate_label is not None:
            self._register_click(self._rate_label, self._cycle_playback_rate)
        self._loop_label = self.findChild(QWidget, "MediaWorkspacePlayerLoop")
        if self._loop_label is not None:
            self._register_click(self._loop_label, self._toggle_loop)

    def eventFilter(self, watched, event):  # noqa: N802 (Qt override)
        """Dispatch clicks on wired chip/glyph labels (wiring only).

        ``_click_actions`` maps a watched widget to a zero-arg callable;
        entries are registered by the wiring helpers (_wire_viewer_toolbar /
        _wire_timeline_tools / _wire_track_header_controls).
        """
        from PySide6.QtCore import QEvent

        if event.type() == QEvent.Type.MouseButtonRelease:
            action = getattr(self, "_click_actions", {}).get(watched)
            if action is not None:
                action()
                return True
        return super().eventFilter(watched, event)

    def _register_click(self, widget, action) -> None:
        """Register ``action`` to run when ``widget`` is clicked."""
        if not hasattr(self, "_click_actions"):
            self._click_actions = {}
        self._click_actions[widget] = action
        widget.installEventFilter(self)
        try:
            widget.setCursor(Qt.CursorShape.PointingHandCursor)
        except Exception:
            pass

    def _cycle_playback_rate(self) -> None:
        """Advance to the next playback-rate preset and apply it everywhere."""
        current = self._timeline.playback_rate()
        presets = self._rate_presets
        try:
            idx = min(
                range(len(presets)),
                key=lambda i: abs(presets[i] - current),
            )
            rate = presets[(idx + 1) % len(presets)]
        except ValueError:
            rate = 1.0
        self._timeline.set_playback_rate(rate)
        audio_rate_ok = True
        if self._audio_player is not None:
            try:
                self._audio_player.setPlaybackRate(rate)
            except Exception:
                audio_rate_ok = False
        # Warn user if audio rate sync failed
        if not audio_rate_ok and rate != 1.0:
            self._detail_status.set_text(
                f"Speed: {rate:g}x (audio at 1x — backend limitation)"
            )
        label = self._rate_label
        if label is not None:
            text = f"{rate:g}x"
            if hasattr(label, "set_text"):
                label.set_text(text)
            else:
                label.setText(text)

    def _toggle_loop(self) -> None:
        """Toggle loop mode; reflect the state on the existing Loop chip."""
        self._loop_enabled = not getattr(self, "_loop_enabled", False)
        label = self._loop_label
        if label is not None:
            c = self._theme.tokens.colors
            color = c.accent_cyan if self._loop_enabled else c.text_muted
            label.setStyleSheet(
                f"#MediaWorkspacePlayerLoop {{ color: {color}; "
                f"background: transparent; }}"
            )

    # ------------------------------------------------------------------ #
    # Timeline editing operations (Phase 3 wiring; widget API + persist)
    # ------------------------------------------------------------------ #
    def _selected_clip_index(self) -> int:
        """Return the timeline's selected clip index (-1 when none)."""
        return self._timeline.selected_index()

    def _clip_track_locked(self, index: int) -> bool:
        """Return whether the clip at ``index`` sits on a locked track."""
        if index < 0:
            return False
        clips = self._timeline.clips()
        if index >= len(clips):
            return False
        track = int(clips[index].get("track", 0))
        return getattr(self, "_track_locked", {}).get(track, False)

    def _split_selected_clip(self) -> None:
        """Split the selected clip at the playhead into two clips.

        Uses only the widget's public clips()/set_clips() API; both halves
        keep the source clip's track/label. A playhead outside the clip (or
        halves under the 1s minimum) is a no-op. Persists to the backend.
        """
        index = self._selected_clip_index()
        if index < 0 or self._clip_track_locked(index):
            return
        clips = self._timeline.clips()
        clip = clips[index]
        start = float(clip.get("start", 0.0))
        length = float(clip.get("length", 0.0))
        cut = self._timeline.playhead()
        if not (start + 1.0 <= cut <= start + length - 1.0):
            return
        left = dict(clip)
        left["length"] = cut - start
        right = dict(clip)
        right["start"] = cut
        right["length"] = start + length - cut
        clips[index] = left
        clips.insert(index + 1, right)
        self._timeline.set_clips(clips)
        self._timeline.select_clip(index)
        self._persist_timeline_to_backend()

    def _delete_selected_clip(self) -> None:
        """Remove the selected clip from the timeline; persist to backend."""
        index = self._selected_clip_index()
        if index < 0 or self._clip_track_locked(index):
            return
        clips = self._timeline.clips()
        del clips[index]
        self._timeline.set_clips(clips)
        self._persist_timeline_to_backend()

    def _duplicate_selected_clip(self) -> None:
        """Duplicate the selected clip right after itself (or at the first
        gap on its track that fits); persist to backend."""
        index = self._selected_clip_index()
        if index < 0 or self._clip_track_locked(index):
            return
        clips = self._timeline.clips()
        clip = dict(clips[index])
        length = float(clip.get("length", 0.0))
        track = int(clip.get("track", 0))
        # Place the copy at the end of the source clip; nudge forward past
        # any occupied span on the same track.
        candidate = float(clip.get("start", 0.0)) + length
        occupied = sorted(
            (float(c.get("start", 0.0)), float(c.get("start", 0.0)) + float(c.get("length", 0.0)))
            for c in clips if int(c.get("track", 0)) == track
        )
        for span_start, span_end in occupied:
            if candidate < span_end and candidate + length > span_start:
                candidate = span_end
        if candidate + length > self._timeline.duration():
            return  # no room on this track
        clip["start"] = candidate
        clips.insert(index + 1, clip)
        self._timeline.set_clips(clips)
        self._timeline.select_clip(index + 1)
        self._persist_timeline_to_backend()

    def _add_timeline_track(self) -> None:
        """Append a new track lane; persist to backend."""
        count = self._timeline.track_count()
        self._timeline.add_track(f"Track {count + 1}")
        self._persist_timeline_to_backend()

    def _add_marker_at_playhead(self) -> None:
        """Add a backend Marker at the playhead (backend marker API exists).

        The Timeline widget has no marker rendering; the marker lives in the
        authoritative backend Timeline (gui_core.Marker) and is reported in
        the Details status row. No-op without a controller.
        """
        if self._controller is None:
            return
        try:
            from gui_core.timeline import Marker

            backend = self._controller.timeline()
            if backend is None:
                backend = self._build_backend_timeline()
            marker_id = f"marker_{len(backend.markers) + 1}"
            backend = backend.add_marker(
                Marker(id=marker_id, time=min(self._timeline.playhead(), backend.duration))
            )
            self._controller.update_timeline(backend)
            self._detail_status.set_text(
                f"Marker added at {self._format_timecode(self._timeline.playhead())}"
            )
        except Exception as exc:
            self._detail_status.set_text(f"Marker: failed — {exc}")

    def _wire_timeline_tools(self) -> None:
        """Wire the timeline toolbar's existing glyph labels to real edits.

        The glyphs are frozen QLabels (#TimelineToolItem) identified by their
        tooltips; only click handling is added. Undo/Redo glyphs are wired by
        the project-system phase (history stack); unknown tooltips stay inert.
        """
        actions = {
            "Cut": self._split_selected_clip,
            "Split": self._split_selected_clip,
            "Razor": self._split_selected_clip,
            "Zoom In": self._timeline.zoom_in,
            "Zoom Out": self._timeline.zoom_out,
            "Fit": self._timeline.fit_to_contents,
            "Marker": self._add_marker_at_playhead,
            "Add Track": self._add_timeline_track,
            # "Remove Track" stays inert: the Timeline widget exposes no
            # track-removal API and inventing one is out of scope.
            "Undo": self._undo,
            "Redo": self._redo,
        }
        toolbar = getattr(self._timeline, "_toolbar", None)
        if toolbar is None:
            return
        for item in toolbar.findChildren(QLabel, "TimelineToolItem"):
            action = actions.get(item.toolTip())
            if action is not None:
                self._register_click(item, action)

    def _wire_track_header_controls(self) -> None:
        """Wire the track headers' existing Mute / Solo / Lock glyphs.

        Toggles view-state per track (locked tracks reject clip edits via the
        persist path; mute/solo drive the audio player's mute state for audio
        lanes). Uses only the frozen header labels; no layout change.
        """
        self._track_locked: dict = {}
        self._track_muted: dict = {}
        self._track_solo: dict = {}
        headers = getattr(self._timeline, "_header_widgets", [])
        for track_index, header in enumerate(headers):
            for obj_name, toggle in (
                ("TimelineTrackMute", self._toggle_track_mute),
                ("TimelineTrackSolo", self._toggle_track_solo),
                ("TimelineTrackLock", self._toggle_track_lock),
            ):
                glyph = header.findChild(QLabel, obj_name)
                if glyph is not None:
                    self._register_click(
                        glyph,
                        lambda t=track_index, g=glyph, f=toggle: f(t, g),
                    )

    def _paint_track_glyph(self, glyph: QLabel, active: bool) -> None:
        """Tint a track-header glyph to reflect its toggled state."""
        c = self._theme.tokens.colors
        color = c.accent_cyan if active else c.text_muted
        glyph.setStyleSheet(
            f"#{glyph.objectName()} {{ color: {color}; "
            f"background: transparent; }}"
        )

    def _toggle_track_mute(self, track: int, glyph: QLabel) -> None:
        """Toggle mute for ``track``; audio player follows for audio lanes."""
        self._track_muted[track] = not self._track_muted.get(track, False)
        self._paint_track_glyph(glyph, self._track_muted[track])
        self._apply_audio_mute_state()

    def _toggle_track_solo(self, track: int, glyph: QLabel) -> None:
        """Toggle solo for ``track``; audio player follows."""
        self._track_solo[track] = not self._track_solo.get(track, False)
        self._paint_track_glyph(glyph, self._track_solo[track])
        self._apply_audio_mute_state()

    def _toggle_track_lock(self, track: int, glyph: QLabel) -> None:
        """Toggle edit-lock for ``track``; locked tracks reject clip edits."""
        self._track_locked[track] = not self._track_locked.get(track, False)
        self._paint_track_glyph(glyph, self._track_locked[track])

    def _apply_audio_mute_state(self) -> None:
        """Mute the audio player when any soloed track excludes audio, or the
        audio track itself is muted. Track 1 ('Music') is the audio lane."""
        if self._audio_output is None:
            return
        audio_tracks = {
            i for i, name in enumerate(self._timeline.tracks())
            if "music" in name.lower() or "audio" in name.lower()
            or "voice" in name.lower() or "sfx" in name.lower()
        }
        solo_active = any(self._track_solo.values())
        if solo_active:
            muted = not any(
                self._track_solo.get(t, False) for t in audio_tracks
            )
        else:
            muted = any(
                self._track_muted.get(t, False) for t in audio_tracks
            )
        try:
            self._audio_output.setMuted(muted)
        except Exception:
            pass

    def _wire_edit_shortcuts(self) -> None:
        """Add standard editing shortcuts (additive; no menu/layout change).

        Delete removes the selected clip; Ctrl+D duplicates; S splits at the
        playhead; Ctrl+Z / Ctrl+Y drive the history stack; M adds a marker.
        """
        from PySide6.QtGui import QKeySequence, QShortcut

        for seq, slot in (
            ("Delete", self._delete_selected_clip),
            ("Ctrl+D", self._duplicate_selected_clip),
            ("S", self._split_selected_clip),
            ("M", self._add_marker_at_playhead),
            ("Ctrl+Z", self._undo),
            ("Ctrl+Y", self._redo),
            ("Ctrl+N", self.new_project),
            ("Ctrl+O", self.open_project),
            ("Ctrl+S", self.save_project),
            ("Ctrl+Shift+S", self.save_project_as),
            ("Ctrl+I", self._on_import_requested),
        ):
            QShortcut(QKeySequence(seq), self, activated=slot)

    # ------------------------------------------------------------------ #
    # Undo / Redo history (snapshots of the widget clip model)
    # ------------------------------------------------------------------ #
    # ------------------------------------------------------------------ #
    # Properties panel wiring (Phase 4: sliders/fields -> backend settings)
    # ------------------------------------------------------------------ #
    def _on_property_changed(self, key: str, value) -> None:
        """Write a clip/property value through the backend settings store.

        Property keys are scoped to the SELECTED timeline clip when one is
        selected (``clip.3.rotation``), falling back to the unscoped key
        (``clip.rotation``) with no selection — so per-clip values never
        overwrite each other. Writes go through the controller's existing
        ``set_setting`` (StateStore.update_setting -> SettingsChanged), which
        keeps them in ProjectState snapshots (undo/redo compatible via the
        project save files). Real-time visual feedback is applied to the
        selected clip widget for opacity.
        """
        selected = self._timeline.selected_index()
        if key.startswith("clip.") and selected >= 0:
            prop = key.split(".", 1)[1]
            key = f"clip.{selected}.{prop}"
            # Real-time feedback: opacity dims the actual clip widget.
            if prop == "opacity":
                self._apply_clip_opacity(selected, float(value))
        if self._controller is None:
            return
        try:
            self._controller.set_setting(key, value)
        except Exception:
            pass

    def _apply_clip_opacity(self, index: int, percent: float) -> None:
        """Dim the selected timeline clip widget to ``percent`` opacity."""
        widgets = getattr(self._timeline, "_clip_widgets", [])
        if not (0 <= index < len(widgets)) or widgets[index] is None:
            return
        from PySide6.QtWidgets import QGraphicsOpacityEffect

        frame = widgets[index]
        effect = frame.graphicsEffect()
        if not isinstance(effect, QGraphicsOpacityEffect):
            effect = QGraphicsOpacityEffect(frame)
            frame.setGraphicsEffect(effect)
        effect.setOpacity(max(0.1, min(1.0, percent / 100.0)))

    def _wire_transform_fields(self, accordion) -> None:
        """Wire the Transform accordion's axis TextFields to backend settings.

        Fields are discovered by their frozen object name in creation order:
        Position X/Y, Scale X/Y, then Anchor X/Y (the order add_axis_row was
        called). editing_finished commits the typed value.
        """
        fields = accordion.findChildren(
            TextField, "MediaWorkspaceStreamAxisField"
        )
        keys = (
            "clip.position_x", "clip.position_y",
            "clip.scale_x", "clip.scale_y",
            "clip.anchor_x", "clip.anchor_y",
        )
        for field, key in zip(fields, keys):
            field.editing_finished.connect(
                lambda f=field, k=key: self._commit_axis_field(f, k)
            )

    def _commit_axis_field(self, field, key: str) -> None:
        """Parse and commit an axis field's numeric value to the backend."""
        raw = field.text().strip().rstrip("%").rstrip("°")
        try:
            value = float(raw)
        except ValueError:
            return
        self._on_property_changed(key, value)

    # ------------------------------------------------------------------ #
    # Project system (save/load reuse Timeline.to_dict/from_dict + facade)
    # ------------------------------------------------------------------ #
    def _project_dir(self):
        """Return (and create) the projects directory under the output dir."""
        from pathlib import Path as _P

        try:
            from config import config as _cfg
            base = _P(_cfg.paths.output_dir)
        except Exception:
            base = _P.cwd() / "output"
        target = base / "projects"
        target.mkdir(parents=True, exist_ok=True)
        return target

    def _project_snapshot(self) -> dict:
        """Serialize the current project using existing model serializers.

        Timeline serialization is owned by gui_core (Timeline.to_dict);
        settings and the selected video come from the controller state. In
        UI-only mode the widget's own clip model is saved so save/open still
        round-trips.
        """
        data = {"version": 1}
        if self._controller is not None:
            state = self._controller.project_state()
            if state.video_path is not None:
                data["video_path"] = str(state.video_path)
            data["settings"] = dict(state.settings)
            timeline = state.timeline
            if timeline is None:
                timeline = self._build_backend_timeline()
            data["timeline"] = timeline.to_dict()
        else:
            data["timeline"] = self._build_backend_timeline().to_dict()
        return data

    def save_project(self, path=None) -> bool:
        """Save the project to ``path`` (or the current/derived path).

        Returns whether the save succeeded; the result is reported in the
        Details status row either way.
        """
        import json
        from pathlib import Path as _P

        if path is None:
            path = getattr(self, "_project_path", None)
        if path is None:
            stem = getattr(self._media_path, "stem", None) or "untitled"
            path = self._project_dir() / f"{stem}.ivproj.json"
        path = _P(path)
        try:
            path.write_text(
                json.dumps(self._project_snapshot(), indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            self._detail_status.set_text(f"Save failed — {exc}")
            return False
        self._project_path = path
        self._detail_status.set_text(f"Saved: {path.name}")
        self._remember_recent_project(path)
        return True

    def save_project_as(self) -> bool:
        """Save the project under a user-chosen filename."""
        from PySide6.QtWidgets import QFileDialog

        chosen, _ = QFileDialog.getSaveFileName(
            self, "Save Project As", str(self._project_dir()),
            "INFY Project (*.ivproj.json)",
        )
        if not chosen:
            return False
        return self.save_project(chosen)

    def open_project(self, path=None) -> bool:
        """Open a saved project; reflect it through the existing seams.

        The video is re-selected via controller.select_video (artifacts
        refresh), settings are re-applied via set_setting, and the timeline
        is restored via gui_core Timeline.from_dict + update_timeline (then
        reflected into the widget by the existing observer path).
        """
        import json
        from pathlib import Path as _P

        if path is None:
            from PySide6.QtWidgets import QFileDialog

            chosen, _ = QFileDialog.getOpenFileName(
                self, "Open Project", str(self._project_dir()),
                "INFY Project (*.ivproj.json)",
            )
            if not chosen:
                return False
            path = chosen
        path = _P(path)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            self._detail_status.set_text(f"Open failed — {exc}")
            return False
        from gui_core import Timeline as BackendTimeline

        try:
            timeline = (
                BackendTimeline.from_dict(data["timeline"])
                if data.get("timeline") else None
            )
        except Exception as exc:
            self._detail_status.set_text(f"Open failed — bad timeline: {exc}")
            return False
        if self._controller is not None:
            video = data.get("video_path")
            if video:
                try:
                    self._reflect_selected_video(video)
                except Exception:
                    pass
            for key, value in (data.get("settings") or {}).items():
                self._on_property_changed(key, value)
            if timeline is not None:
                self._controller.update_timeline(timeline)
                self._reflect_timeline()
        elif timeline is not None:
            # UI-only: reflect the saved timeline into the widget directly.
            self._timeline.set_duration(timeline.duration)
            needed = max((t.index for t in timeline.tracks), default=-1) + 1
            while self._timeline.track_count() < needed:
                self._timeline.add_track(
                    f"Track {self._timeline.track_count() + 1}"
                )
            self._timeline.set_clips(
                [
                    {
                        "track": c.track_index,
                        "start": c.start,
                        "length": c.length,
                        "label": c.label or (c.source or ""),
                    }
                    for c in timeline.clips
                ]
            )
        self._project_path = path
        self._last_clips_snapshot = self._timeline.clips()
        self._detail_status.set_text(f"Opened: {path.name}")
        self._remember_recent_project(path)
        return True

    def new_project(self) -> None:
        """Reset to a fresh project (autosaving the current one first)."""
        if getattr(self, "_project_path", None) is not None:
            self.save_project()
        self._project_path = None
        self._timeline.set_clips([])
        self._undo_stack, self._redo_stack = [], []
        self._last_clips_snapshot = []
        self._browser.select(-1)
        self._persist_timeline_to_backend(record_history=False)
        self._detail_status.set_text("New project")

    def _remember_recent_project(self, path) -> None:
        """Append ``path`` to the persisted recent-projects list (max 10)."""
        import json

        index = self._project_dir() / "recent.json"
        try:
            recents = json.loads(index.read_text(encoding="utf-8"))
        except Exception:
            recents = []
        entry = str(path)
        recents = [entry] + [r for r in recents if r != entry]
        try:
            index.write_text(
                json.dumps(recents[:10], indent=2), encoding="utf-8"
            )
        except Exception:
            pass

    def recent_projects(self) -> list:
        """Return the persisted recent-project paths (most recent first)."""
        import json

        index = self._project_dir() / "recent.json"
        try:
            return list(json.loads(index.read_text(encoding="utf-8")))
        except Exception:
            return []

    def _start_autosave(self) -> None:
        """Start the autosave timer (every 2 minutes; saves only once a
        project path exists so no unnamed file is fabricated)."""
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setInterval(120_000)
        self._autosave_timer.timeout.connect(self._autosave_tick)
        self._autosave_timer.start()

    def _autosave_tick(self) -> None:
        """Autosave into a sidecar recovery file next to the project."""
        import json

        path = getattr(self, "_project_path", None)
        target = (
            path.with_suffix(".autosave.json")
            if path is not None
            else self._project_dir() / "recovery.autosave.json"
        )
        try:
            target.write_text(
                json.dumps(self._project_snapshot(), indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    def recover_autosave(self) -> bool:
        """Open the most recent autosave/recovery file if one exists."""
        candidates = sorted(
            self._project_dir().glob("*.autosave.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not candidates:
            self._detail_status.set_text("No autosave found")
            return False
        return self.open_project(candidates[0])

    def _wire_sidebar_projects(self) -> None:
        """Wire the sidebar's New Project label and recent-project rows.

        "+ New Project" runs new_project(); a recent row whose name matches a
        saved project (by stem) opens it, otherwise the click reports that no
        saved file exists (the seed rows are decorative until real saves).
        """
        sidebar = getattr(self, "_sidebar", None)
        if sidebar is None:
            return
        new_lbl = sidebar.findChild(QLabel, "NavigationRecentNewProject")
        if new_lbl is not None:
            self._register_click(new_lbl, self.new_project)
        for row in sidebar.findChildren(QWidget, "NavigationRecentItem"):
            name_lbl = row.findChild(QLabel, "NavigationRecentName")
            if name_lbl is None:
                continue
            self._register_click(
                row,
                lambda n=name_lbl.text(): self._open_recent_by_name(n),
            )

    def _on_nav_changed(self, index: int) -> None:
        """Route every sidebar nav item to a real, existing surface.

        No new screens are fabricated: each item maps to the existing panel
        or region that already implements it, and items with no existing
        surface report that honestly in the Details status row instead of
        silently doing nothing.
        """
        # Hide the optional overlays first; the chosen item re-shows its own.
        self._browser.setVisible(False)
        self._ai_host.setVisible(False)
        self._inspector_host.setVisible(False)
        names = self._sidebar.items()
        name = names[index] if 0 <= index < len(names) else f"#{index}"
        if index == getattr(self, "_nav_media_index", 2):  # Media
            self._browser.setVisible(True)
            if self._browser.current_index() < 0 and self._browser.count() > 0:
                self._browser.select(0)
        elif name == "Projects":
            # Recent projects live in the sidebar itself; surface the count.
            count = len(self.recent_projects())
            self._detail_status.set_text(
                f"Projects: {count} recent (see sidebar)"
            )
        elif name == "Timeline":
            self._timeline.setFocus()
            self._detail_status.set_text("Timeline focused")
        elif name == "AI Studio":
            self._ai_host.setVisible(True)
        elif name == "Effects":
            self._detail_status.set_text(
                "Effects: toggles in the right panel (no render backend yet)"
            )
        elif name == "Export":
            started = self.export()
            self._detail_status.set_text(
                "Export: render phase started" if started
                else "Export: run the AI pipeline first (render is gated)"
            )
        elif name == "Audio":
            self._detail_status.set_text(
                "Audio: use Mute/Solo on timeline track headers"
            )
        elif name == "Captions":
            started = self.run_phase("subtitles")
            self._detail_status.set_text(
                "Captions: subtitle generation started" if started
                else "Captions: select a video first"
            )
        else:
            # Dashboard / Assets / Transitions / Templates / Settings:
            # no dedicated surface exists in this screen yet — say so.
            self._detail_status.set_text(f"{name}: coming soon")

    # ------------------------------------------------------------------ #
    # AI Assistant wiring (AIController -> ai_core pipeline)
    # ------------------------------------------------------------------ #
    def _ai_view_state(self) -> dict:
        """View-only context for the AI ContextEngine."""
        selected = self._timeline.selected_clip()
        return {
            "selected_clip": (
                str(selected.get("label", "")) if selected else ""
            ),
            "playhead_seconds": self._timeline.playhead(),
        }

    def _submit_ai(self, capability: str, prompt: str) -> None:
        """Submit an AI request through the AIController (async)."""
        if self._ai_controller is None:
            self._detail_status.set_text("AI: no AI controller (offline)")
            return
        if not self._ai_controller.submit(capability, prompt):
            self._detail_status.set_text("AI: busy — request in progress")

    def _on_play_tile_clicked(self) -> None:
        """Empty-state play button: select the first media and play.

        With no media selected, selects the browser's first item (which
        decodes and displays the first frame via the existing selection
        path), then starts playback. With media already selected it simply
        toggles play.
        """
        if self._media_path is None and self._browser.count() > 0:
            index = self._browser.current_index()
            self._browser.select(0 if index < 0 else index)
        if self._media_path is not None:
            self._timeline.play()
        else:
            self._detail_status.set_text(
                "No media: use Import (Ctrl+I) or drop a video file here"
            )

    def _on_ai_ask(self) -> None:
        """Run the AI prompt field's text through the chat pipeline."""
        prompt = self._ai_prompt.text().strip()
        if not prompt:
            self._detail_status.set_text("AI: type a prompt first")
            return
        self._submit_ai("chat", prompt)

    def _on_ai_request_started(self, capability: str) -> None:
        self._set_phase_status(f"AI: {capability}…")

    def _on_ai_request_completed(self, capability: str, result) -> None:
        self._set_phase_status("AI: done")
        # Surface a compact result summary in the Details status row.
        text = ""
        if isinstance(result, str):
            text = result[:160]
        elif hasattr(result, "titles"):
            text = "; ".join(result.titles[:3])
        elif hasattr(result, "prompt"):
            text = result.prompt[:160]
        elif hasattr(result, "segments"):
            text = f"{len(result.segments)} segment(s)"
        elif hasattr(result, "tags"):
            text = ", ".join(result.tags[:8])
        if text:
            self._detail_status.set_text(f"AI {capability}: {text}")

    def _on_ai_request_failed(self, capability: str, message: str) -> None:
        self._set_phase_status("AI: failed")
        self._detail_status.set_text(f"AI {capability} failed: {message[:120]}")

    def _open_recent_by_name(self, name: str) -> None:
        """Open the saved project whose filename matches ``name`` (slugged)."""
        from pathlib import Path as _P

        slug = name.lower().replace(" ", "_")
        for entry in self.recent_projects():
            stem = _P(entry).name.lower()
            if slug in stem or stem.startswith(slug):
                self.open_project(entry)
                return
        candidate = self._project_dir() / f"{slug}.ivproj.json"
        if candidate.exists():
            self.open_project(candidate)
        else:
            self._detail_status.set_text(f"No saved project for: {name}")

    def _undo(self) -> None:
        """Restore the previous clip model snapshot (and persist it)."""
        stack = getattr(self, "_undo_stack", None)
        if not stack:
            return
        self._redo_stack.append(self._timeline.clips())
        snapshot = stack.pop()
        self._restoring_history = True
        try:
            self._timeline.set_clips(snapshot)
        finally:
            self._restoring_history = False
        self._persist_timeline_to_backend(record_history=False)

    def _redo(self) -> None:
        """Re-apply an undone clip model snapshot (and persist it)."""
        stack = getattr(self, "_redo_stack", None)
        if not stack:
            return
        self._undo_stack.append(self._timeline.clips())
        snapshot = stack.pop()
        self._restoring_history = True
        try:
            self._timeline.set_clips(snapshot)
        finally:
            self._restoring_history = False
        self._persist_timeline_to_backend(record_history=False)

    def _on_viewer_zoom_changed(self, index: int) -> None:
        """Apply the zoom preset to the preview frame scaling and HUD badge.

        'Fit' rescales to the stage (the default show_frame behavior); a
        percentage renders the decoded frame at that scale. The current
        preset is stored and applied on the next decoded frame.
        """
        zoom = self.findChild(Dropdown, "MediaWorkspaceViewerZoom")
        text = zoom.current_text() if zoom is not None else "Fit"
        self._preview_zoom = text
        badge = self.findChild(QLabel, "MediaWorkspacePreviewZoomBadge")
        if badge is not None:
            badge.setText(text if text != "Fit" else "100%")
        # Zoom changes the rendered scale: drop the scaled-pixmap cache and
        # re-render the current frame at the new zoom.
        self._invalidate_frame_cache()
        self._decode_and_show(self._timeline.playhead())

    def _on_screenshot(self) -> None:
        """Save the currently displayed frame as a PNG in the output dir.

        Reuses the already-decoded preview pixmap; reports the saved path (or
        the failure) in the Details status row. No new backend API.
        """
        pixmap = self._preview_frame.pixmap()
        if pixmap is None or pixmap.isNull():
            self._detail_status.set_text("Screenshot: no frame to capture")
            return
        try:
            from datetime import datetime
            from pathlib import Path as _P

            try:
                from config import config as _cfg
                out_dir = _P(_cfg.paths.output_dir)
            except Exception:
                out_dir = _P.cwd() / "output"
            out_dir.mkdir(parents=True, exist_ok=True)
            stem = (
                getattr(self._media_path, "stem", None) or "frame"
            )
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            target = out_dir / f"{stem}_screenshot_{stamp}.png"
            if pixmap.save(str(target), "PNG"):
                self._detail_status.set_text(f"Screenshot: {target.name}")
            else:
                self._detail_status.set_text("Screenshot: save failed")
        except Exception as exc:
            self._detail_status.set_text(f"Screenshot: failed — {exc}")

    def _on_toggle_fullscreen(self) -> None:
        """Toggle the top-level window between fullscreen and normal."""
        window = self.window()
        if window is None:
            return
        if window.isFullScreen():
            window.showNormal()
        else:
            window.showFullScreen()

    def _format_timecode(self, seconds: float) -> str:
        """Render ``seconds`` as an HH:MM:SS:FF editorial timecode."""
        fps = self._media_fps()
        seconds = max(0.0, float(seconds))
        whole = int(seconds)
        frames = int(round((seconds - whole) * fps)) % max(1, int(round(fps)))
        hours, rem = divmod(whole, 3600)
        minutes, secs = divmod(rem, 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}:{frames:02d}"

    def _update_timecode_displays(self, seconds: float) -> None:
        """Reflect the playhead into the HUD and transport timecode labels."""
        code = self._format_timecode(seconds)
        hud = self.findChild(QLabel, "MediaWorkspacePreviewTimecode")
        if hud is not None:
            hud.setText(code)
        tc = self._transport.findChild(QLabel, "TransportTimecode") or getattr(
            self._transport, "_timecode", None
        )
        if tc is not None and hasattr(tc, "set_text"):
            tc.set_text(code)
        elif tc is not None and hasattr(tc, "setText"):
            tc.setText(code)

    def _on_playhead_changed(self, seconds: float) -> None:
        """Reflect the timeline playhead on the TransportBar's seek position.

        Normalizes the playhead time to the timeline duration; set_position
        clamps and does not re-emit seek_requested, so there is no loop.
        During playback, pulls from the background decoder queue (no UI
        blocking). During seeking, decodes on demand.
        """
        duration = self._timeline.duration()
        fraction = seconds / duration if duration > 0 else 0.0
        self._transport.set_position(fraction)
        self._update_timecode_displays(seconds)
        # During playback, prefer the paced background decoder stream.
        if self._decoder is not None:
            frame = self._pull_playback_frame(seconds)
            if frame is not None:
                self.show_frame(frame)
            # No frame due yet (or decoder warming up): keep the last frame
            # on screen — falling back to a blocking per-frame decode here
            # would stall the GUI thread and break audio sync.
            return
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
        # Ignored horizontal policy: the accordion fits the fixed right-panel
        # width instead of its grid's content minimums widening the scroll
        # content (same fix as the AI card grid).
        self.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(s.xxs)

        # Header row: the collapse toggle plus trailing decorative micro
        # icons like the reference accordions (wired to nothing).
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(s.xs)
        self._toggle = NeonButton(
            theme, f"{self._CHEVRON_EXPANDED}  {title}", variant="ghost", accent="cyan"
        )
        self._toggle.setObjectName("MediaWorkspaceStreamAccordionToggle")
        self._title = title
        self._toggle.clicked.connect(self._on_toggle)
        header_row.addWidget(self._toggle, 0)
        header_row.addStretch(1)
        icon_side = 12
        for icon_name in ("gauge", "split", "settings"):
            micro = QLabel(self)
            micro.setObjectName("MediaWorkspaceStreamAccordionIcon")
            micro.setFixedSize(icon_side + 8, icon_side + 8)
            micro.setAlignment(Qt.AlignmentFlag.AlignCenter)
            micro.setPixmap(
                theme.icons.icon(icon_name, c.text_muted, icon_side)
                .pixmap(icon_side, icon_side)
            )
            micro.setStyleSheet(
                "#MediaWorkspaceStreamAccordionIcon { "
                "background: transparent; }"
            )
            header_row.addWidget(micro, 0)
        column.addLayout(header_row)

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
            c = self._theme.tokens.colors
            link = NeonButton(
                self._theme, "", variant="ghost", accent="blue",
                icon_name="link-2", icon_color=c.accent_blue,
                corner_radius=8, pad_h=8, pad_v=8,
            )
            link.setObjectName("MediaWorkspaceStreamAxisLink")
            link.setToolTip("Link X / Y")
            link.setFixedSize(30, 30)
            link.setStyleSheet(
                f"#MediaWorkspaceStreamAxisLink {{ "
                f"background: rgba(168, 85, 247, 0.14); "
                f"border: 1px solid rgba(168, 85, 247, 0.45); "
                f"border-radius: 8px; padding: 0px; }} "
                f"#MediaWorkspaceStreamAxisLink:hover {{ "
                f"background: rgba(168, 85, 247, 0.26); "
                f"border: 1px solid {c.accent_blue}; }}"
            )
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
        self, label: str, control: QWidget, value: str,
        *, chip: Optional[str] = None, reset: bool = False,
    ) -> None:
        """Append a single-slider row into the shared grid.

        Columns: 0 = name (left), 1 = the stretching horizontal slider,
        2 = one standalone value field on the outer-right boundary. Shares
        the axis rows' column boundaries so the name and the trailing value
        align with the Transform rows above. ``chip`` (a color string) adds
        a small checkbox-style swatch before the name like the reference's
        Effects rows; ``reset`` appends a tiny undo icon after the value
        field. UI-only / decorative.
        """
        if chip:
            name_wrap = QWidget(self._content)
            wrap_row = QHBoxLayout(name_wrap)
            wrap_row.setContentsMargins(0, 0, 0, 0)
            wrap_row.setSpacing(self._theme.tokens.spacing.xs)
            swatch = QLabel("✓", name_wrap)
            swatch.setObjectName("MediaWorkspaceStreamEffectChip")
            side = 14
            swatch.setFixedSize(side, side)
            swatch.setAlignment(Qt.AlignmentFlag.AlignCenter)
            swatch.setStyleSheet(
                f"#MediaWorkspaceStreamEffectChip {{ "
                f"background: {chip}; "
                f"color: {self._theme.tokens.colors.text_on_accent}; "
                f"border-radius: 3px; font-size: 9px; }}"
            )
            wrap_row.addWidget(swatch, 0)
            wrap_row.addWidget(
                MetaLabel(self._theme, label, role="muted", style="body_small"),
                0,
            )
            name: QWidget = name_wrap
        else:
            name = MetaLabel(
                self._theme, label, role="muted", style="body_small"
            )
        self._grid.addWidget(
            name, self._grid_row, 0,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        )
        control.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        # Keep the slider usable even when a long sibling row label (e.g.
        # "AI Voice Enhance") widens the name column.
        control.setMinimumWidth(96)
        self._grid.addWidget(control, self._grid_row, 1)
        field = TextField(self._theme, text=value)
        field.setObjectName("MediaWorkspaceStreamNumericField")
        field.setFixedWidth(64)
        field.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        if reset:
            c = self._theme.tokens.colors
            value_wrap = QWidget(self._content)
            value_row = QHBoxLayout(value_wrap)
            value_row.setContentsMargins(0, 0, 0, 0)
            value_row.setSpacing(self._theme.tokens.spacing.xs)
            value_row.addWidget(field, 0)
            undo = QLabel(value_wrap)
            undo.setObjectName("MediaWorkspaceStreamRowReset")
            undo.setFixedSize(16, 16)
            undo.setAlignment(Qt.AlignmentFlag.AlignCenter)
            undo.setPixmap(
                self._theme.icons.icon("undo-2", c.text_muted, 12)
                .pixmap(12, 12)
            )
            undo.setToolTip("Reset")
            value_row.addWidget(undo, 0)
            trailing: QWidget = value_wrap
        else:
            trailing = field
        self._grid.addWidget(
            trailing, self._grid_row, 2,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        )
        self._grid_row += 1

    def _on_toggle(self) -> None:
        """Flip the local expanded state with a smooth height animation."""
        self._expanded = not self._expanded
        chevron = (
            self._CHEVRON_EXPANDED if self._expanded else self._CHEVRON_COLLAPSED
        )
        self._toggle.set_text(f"{chevron}  {self._title}")

        content = self._content
        if self._expanded:
            # Expand: show content, then animate height 0 → target.
            content.setVisible(True)
            target_h = content.sizeHint().height()
            target_h = max(target_h, 50)  # floor so short sections still animate
            content.setMaximumHeight(0)
            anim = QPropertyAnimation(content, b"maximumHeight", self)
            anim.setDuration(self._theme.duration("fast"))
            anim.setStartValue(0)
            anim.setEndValue(target_h)
            anim.setEasingCurve(self._theme.easing("out_cubic"))
            anim.finished.connect(lambda: content.setMaximumHeight(16777215))
            anim.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
            self._collapse_anim = anim
        else:
            # Collapse: animate height current → 0, then hide.
            current_h = content.height()
            content.setMaximumHeight(current_h)
            anim = QPropertyAnimation(content, b"maximumHeight", self)
            anim.setDuration(self._theme.duration("fast"))
            anim.setStartValue(current_h)
            anim.setEndValue(0)
            anim.setEasingCurve(self._theme.easing("in_cubic"))
            anim.finished.connect(lambda: content.setVisible(False))
            anim.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
            self._collapse_anim = anim


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
