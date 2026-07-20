"""Timeline: a UI-only professional timeline widget (Phase 8H, Milestone 3).

A themed, presentation-only timeline: a horizontal time ruler, one or more
track lanes, clip blocks positioned within a lane, and a playhead marker. It is
additive to the widget library and depends only on the injected
:class:`ThemeManager` for visual values.

Milestone 3 is deliberately minimal. There is NO backend, NO :mod:`gui_core`,
NO playback engine, NO AI, NO export, NO drag-and-drop, and NO trimming or
resizing. Clips are static, described by plain data, and rendered as themed
frames. The only interactive state is the playhead position, exposed through a
simple setter/getter and a change signal.

Stable object names for later integration and tests:

* ``Timeline`` -- the root widget
* ``TimelineRuler`` -- the top time-scale strip
* ``TimelineTracks`` -- the container holding the track lanes
* ``TimelineTrack`` -- one track lane
* ``TimelineClip`` -- one clip block within a lane
* ``TimelinePlayhead`` -- the playhead marker
"""
from __future__ import annotations

import random
from typing import Dict, List, Optional

from PySide6.QtCore import QEasingCurve, QEvent, QPropertyAnimation, QTimer, QVariantAnimation, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from gui.theme.manager import ThemeManager
from gui.widgets.base import ThemedWidget

#: A clip is a plain mapping: track index, start (s), length (s), label.
Clip = Dict[str, object]


class _ClipWaveform(QWidget):
    """Decorative pseudo-waveform painted inside audio / voice clip blocks.

    Visual-only chrome: deterministic bar heights are derived from the clip
    label (stable across rebuilds), painted mirrored around the vertical
    center like a real audio waveform. The widget is transparent to mouse
    events so clip select / drag / trim behavior (which targets the parent
    ``TimelineClip`` frame) is untouched, and it tracks the parent's size via
    an event filter (the parent's layout does not manage it).
    """

    def __init__(self, parent: QWidget, color: str, seed_text: str) -> None:
        super().__init__(parent)
        self.setObjectName("TimelineClipWaveform")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._color = QColor(color)
        rnd = random.Random(seed_text)
        self._bars = [0.2 + 0.8 * rnd.random() for _ in range(160)]
        parent.installEventFilter(self)
        self.setGeometry(0, 0, parent.width(), parent.height())
        self.lower()

    def eventFilter(self, watched, event) -> bool:  # noqa: N802 (Qt override)
        if watched is self.parent() and event.type() == QEvent.Type.Resize:
            self.setGeometry(0, 0, watched.width(), watched.height())
        return False

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt override)
        painter = QPainter(self)
        width = self.width()
        height = self.height()
        if width <= 0 or height <= 4:
            return
        mid = height / 2.0
        bar_w = 2
        gap = 1
        step = bar_w + gap
        color = QColor(self._color)
        color.setAlpha(210)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        count = min(len(self._bars), max(1, (width - 4) // step))
        for i in range(int(count)):
            amp = self._bars[i % len(self._bars)] * (mid - 2)
            x = 2 + i * step
            painter.drawRect(int(x), int(mid - amp), bar_w, int(amp * 2))
        painter.end()


class Timeline(ThemedWidget):
    """A themed, UI-only timeline with a ruler, track lanes and a playhead.

    Args:
        theme: Injected theme manager (sole source of visual values).
        duration: Total timeline duration in seconds (> 0). Default ``60.0``.
        tracks: Initial track names. Defaults to a single ``"Video 1"`` lane.
        parent: Optional Qt parent.

    Signals:
        playhead_changed(float): Emitted with the new playhead time (seconds)
            when it changes via :meth:`set_playhead`.
        clip_selected(int): Emitted with the newly selected clip index (or
            ``-1`` when the selection is cleared) via :meth:`select_clip` /
            :meth:`clear_selection`. Programmatic only (no mouse handling).

    Raises:
        ValueError: If ``duration`` is not strictly positive.
    """

    playhead_changed = Signal(float)
    clip_selected = Signal(int)
    clip_moved = Signal(int, int)
    clip_trimmed = Signal(int, float, float)
    zoom_changed = Signal(float)
    playback_state_changed = Signal(str)
    playback_finished = Signal()

    def __init__(
        self,
        theme: ThemeManager,
        *,
        duration: float = 60.0,
        tracks: Optional[List[str]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(theme, parent)
        self.setObjectName("Timeline")
        if float(duration) <= 0.0:
            raise ValueError(f"duration must be > 0, got {duration!r}")
        self._duration = float(duration)
        self._playhead = 0.0
        self._track_names: List[str] = []
        self._track_widgets: List[QWidget] = []
        self._clips: List[Clip] = []
        # Programmatic selection state (Milestone 4). -1 means no selection.
        self._selected = -1
        # Rendered clip frames, in clip order, tracked during _rebuild_clips
        # so a selection can mark the matching frame's dynamic property.
        self._clip_widgets: List[QWidget] = []
        # Drag state (Milestone 6). Manual press -> move -> release tracking;
        # no QDrag/QMimeData. _drag_index is the clip being dragged (-1 when
        # idle); _drag_armed marks a pending press that has not yet crossed the
        # movement threshold; _drag_active marks an in-progress drag; the press
        # anchor is kept to measure the threshold; _drop_lane is the lane
        # currently marked with the 'dropTarget' preview property.
        self._drag_index = -1
        self._drag_armed = False
        self._drag_active = False
        self._drag_press_pos = None
        self._drop_lane: Optional[QWidget] = None
        #: Movement (px) a press must exceed before it becomes a drag.
        self._drag_threshold = 4
        # Trim state (Milestone 7). _drag_mode is 'move' (M6) or 'trim_left' /
        # 'trim_right' (M7), chosen at arm time from the press position within
        # the clip frame. _trimming marks an active trim; _trim_edge_zone is
        # the edge hit-zone width (px); _px_per_second maps horizontal pointer
        # movement to a seconds delta; _trim_origin snapshots the clip's
        # (start, length) at arm time so live trimming is computed from a
        # stable base.
        self._drag_mode = "move"
        self._trimming = False
        self._trim_edge_zone = 8
        self._px_per_second = 8.0
        self._trim_origin: Optional[tuple] = None
        self._trim_last_pos = None
        # Zoom state (Milestone 8). Rendering-only: _zoom scales the clip block
        # widths on redraw; it never changes the clip model, selection, or
        # drag/trim behavior. Clamped to [_zoom_min, _zoom_max]; zoom_in /
        # zoom_out step multiplicatively by _zoom_step; fit_to_contents resets
        # to the 1.0 baseline. _clip_base_width is the unscaled block width.
        self._zoom = 1.0
        self._zoom_min = 0.25
        self._zoom_max = 4.0
        self._zoom_step = 1.25
        self._clip_base_width = self.scaled(self.tokens.spacing.xxl)
        # Optional callbacks for real media data (set by the hosting screen).
        # thumbnail_fn(source_path, seconds) -> QImage | None
        self._thumbnail_fn = None
        # waveform_fn(source_path, start_s, end_s, num_samples) -> list[float]
        self._waveform_fn = None
        # Playback state (Milestone 9). Timer-driven transport that advances
        # the existing playhead; no real media. _playback_state is one of
        # 'stopped' / 'playing' / 'paused'. The single-owner QTimer ticks at
        # _play_interval_ms (~30fps) and advances the playhead by that interval
        # in seconds via the existing set_playhead (clamped; emits
        # playhead_changed). Reaching the duration stops and emits
        # playback_finished.
        self._playback_state = "stopped"
        # 16ms precise ticks (~60Hz polling). The playhead advances by REAL
        # elapsed wall time per tick (see _on_play_tick), and the hosting
        # screen paces frame display to the media fps — a faster tick only
        # tightens display latency, it never speeds up playback. Qt's default
        # CoarseTimer has 5% slop which starved 30fps display down to ~21fps.
        self._play_interval_ms = 16
        self._play_timer = QTimer(self)
        self._play_timer.setInterval(self._play_interval_ms)
        self._play_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._play_timer.timeout.connect(self._on_play_tick)
        # Receive keyboard shortcuts (Space / Home / End).
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        tokens = self.tokens
        self._column = QVBoxLayout(self)
        self._column.setContentsMargins(0, 0, 0, 0)
        self._column.setSpacing(tokens.spacing.xs)

        # Professional timeline toolbar (decorative placeholders; wired to
        # nothing). Inserted above the ruler; the ruler / track-area / playhead
        # order below it is unchanged.
        self._build_toolbar()

        # Ruler strip (static tick labels across the duration).
        self._ruler = QFrame(self)
        self._ruler.setObjectName("TimelineRuler")
        self._ruler.setFrameShape(QFrame.Shape.StyledPanel)
        self._ruler.setFixedHeight(self.scaled(tokens.spacing.xl))
        self._ruler_row = QHBoxLayout(self._ruler)
        self._ruler_row.setContentsMargins(
            tokens.spacing.sm, 0, tokens.spacing.sm, 0
        )
        self._ruler_row.setSpacing(0)
        self._column.addWidget(self._ruler)
        # Click-to-seek / playhead drag on the ruler (Milestone 9). Installed
        # only on the ruler, a separate target from the clip frames / lanes, so
        # clip select (M5), move (M6) and trim (M7) are unaffected.
        self._ruler.installEventFilter(self)

        # Track area: a decorative header column beside the lane container.
        # The lane container keeps its frozen object name, order and behavior;
        # the header column is purely additive professional chrome.
        self._track_area = QWidget(self)
        self._track_area.setObjectName("TimelineTrackArea")
        track_area_row = QHBoxLayout(self._track_area)
        track_area_row.setContentsMargins(0, 0, 0, 0)
        track_area_row.setSpacing(tokens.spacing.xs)

        # Track-header column (decorative placeholders; wired to nothing).
        self._headers_container = QWidget(self._track_area)
        self._headers_container.setObjectName("TimelineTrackHeaders")
        self._headers_layout = QVBoxLayout(self._headers_container)
        self._headers_layout.setContentsMargins(0, 0, 0, 0)
        self._headers_layout.setSpacing(tokens.spacing.xs)
        # Wide enough for the longest track name ("Video Track 1") plus the
        # chip, chevron and the four control glyphs — names must never clip.
        self._headers_container.setFixedWidth(self.scaled(224))
        self._header_widgets: List[QWidget] = []
        track_area_row.addWidget(self._headers_container, 0)

        # Track lanes container.
        self._tracks_container = QWidget(self._track_area)
        self._tracks_container.setObjectName("TimelineTracks")
        self._tracks_layout = QVBoxLayout(self._tracks_container)
        self._tracks_layout.setContentsMargins(0, 0, 0, 0)
        self._tracks_layout.setSpacing(tokens.spacing.xs)
        track_area_row.addWidget(self._tracks_container, 1)
        self._column.addWidget(self._track_area, 1)
        # Empty-space clicks (on the tracks background) clear the selection.
        self._tracks_container.installEventFilter(self)

        # Playhead marker (a thin vertical frame; position is illustrative).
        self._playhead_marker = QFrame(self)
        self._playhead_marker.setObjectName("TimelinePlayhead")
        self._playhead_marker.setFixedHeight(self.scaled(tokens.spacing.xs))
        self._column.addWidget(self._playhead_marker)

        for name in tracks if tracks is not None else ["Video 1"]:
            self.add_track(name)

        self._build_ruler()
        self.setAccessibleName("timeline")
        self.apply_theme()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def duration(self) -> float:
        """Return the total timeline duration in seconds."""
        return self._duration

    def set_duration(self, duration: float) -> None:
        """Set the total duration (> 0); re-clamps the playhead and rebuilds.

        Raises:
            ValueError: If ``duration`` is not strictly positive.
        """
        if float(duration) <= 0.0:
            raise ValueError(f"duration must be > 0, got {duration!r}")
        self._duration = float(duration)
        if self._playhead > self._duration:
            self._playhead = self._duration
        self._build_ruler()
        self._rebuild_clips()

    def current_time(self) -> float:
        """Return the current playhead time in seconds (transport reader)."""
        return self._playhead

    def playback_state(self) -> str:
        """Return the transport state ('stopped' / 'playing' / 'paused')."""
        return self._playback_state

    def is_playing(self) -> bool:
        """Return ``True`` while playback is running."""
        return self._playback_state == "playing"

    def play(self) -> None:
        """Start (or resume) timer-driven playback from the playhead.

        A no-op when already playing. Playing while the playhead is already at
        the end does NOT restart from 0: it enters 'playing' and the first
        timer tick finishes playback immediately (see :meth:`_on_play_tick`),
        leaving the playhead at the duration. Emits
        :attr:`playback_state_changed` on a state change.
        """
        if self._playback_state == "playing":
            return
        self._set_playback_state("playing")
        # Wall-clock anchor: ticks advance by REAL elapsed time (not the
        # nominal timer interval), so late timer firings never make the
        # playhead lag behind real time (keeps audio/video in sync).
        import time as _time
        self._last_tick_at = _time.monotonic()
        self._play_timer.start()

    def pause(self) -> None:
        """Pause playback, keeping the current playhead. A no-op when not playing."""
        if self._playback_state != "playing":
            return
        self._play_timer.stop()
        self._set_playback_state("paused")

    def stop(self) -> None:
        """Stop playback and reset the playhead to 0.

        Idempotent for the state, but always resets the playhead. Emits
        :attr:`playback_state_changed` only when the state changes.
        """
        self._play_timer.stop()
        self._set_playback_state("stopped")
        self.set_playhead(0.0)

    def toggle_play(self) -> None:
        """Toggle between play and pause (Space shortcut)."""
        if self._playback_state == "playing":
            self.pause()
        else:
            self.play()

    def playback_rate(self) -> float:
        """Return the playback rate multiplier (1.0 is real time)."""
        return getattr(self, "_playback_rate", 1.0)

    def set_playback_rate(self, rate: float) -> None:
        """Set the playback rate multiplier (clamped to a sane range).

        Additive API: the timer interval is unchanged; each tick simply
        advances the playhead by ``interval * rate`` seconds, mirroring the
        pure ``gui_core.playback.advance`` semantics (delta * rate).
        """
        self._playback_rate = max(0.1, min(4.0, float(rate)))

    def _set_playback_state(self, state: str) -> None:
        """Set the transport state; emit playback_state_changed on a change."""
        if state == self._playback_state:
            return
        self._playback_state = state
        self.playback_state_changed.emit(self._playback_state)
        self._sync_playhead_pulse()

    def _on_play_tick(self) -> None:
        """Advance the playhead by real elapsed wall time; stop at the end."""
        import time as _time
        now = _time.monotonic()
        elapsed = now - getattr(self, "_last_tick_at", now)
        self._last_tick_at = now
        # Clamp pathological gaps (system sleep etc.) to one nominal interval.
        if elapsed <= 0 or elapsed > 1.0:
            elapsed = self._play_interval_ms / 1000.0
        step = elapsed * self.playback_rate()
        target = self._playhead + step
        if target >= self._duration:
            self.set_playhead(self._duration)
            self._play_timer.stop()
            self._set_playback_state("stopped")
            self.playback_finished.emit()
            return
        self.set_playhead(target)

    def keyPressEvent(self, event) -> None:  # noqa: N802 (Qt override)
        """Keyboard transport: Space toggles play/pause, Home/End seek."""
        key = event.key()
        if key == Qt.Key.Key_Space:
            self.toggle_play()
            event.accept()
            return
        if key == Qt.Key.Key_Home:
            self.set_playhead(0.0)
            event.accept()
            return
        if key == Qt.Key.Key_End:
            self.set_playhead(self._duration)
            event.accept()
            return
        super().keyPressEvent(event)

    def _seek_from_ruler(self, event) -> None:
        """Map a ruler press/drag x-position to a time and seek there.

        Rendering-geometry based: the ruler width maps to [0, duration]. A
        zero-width ruler (e.g. offscreen, never shown) is a no-op and never
        raises. Drives the existing set_playhead (clamped; emits
        playhead_changed).
        """
        width = self._ruler.width()
        if width <= 0:
            return
        x = event.position().x()
        fraction = max(0.0, min(1.0, x / width))
        self.set_playhead(self._duration * fraction)

    def zoom_level(self) -> float:
        """Return the current zoom level (``1.0`` is the fit baseline)."""
        return self._zoom

    def set_zoom(self, level: float) -> None:
        """Set the zoom level (clamped to ``[zoom_min, zoom_max]``).

        Rendering-only: a change redraws the ruler and clip blocks (the same
        redraw path as :meth:`set_duration`, which preserves the selection) so
        the clip widths reflect the new zoom, and emits :attr:`zoom_changed`.
        A level that clamps to the current value is a no-op and emits nothing.
        Never alters the clip model, selection, or drag/trim behavior.
        """
        clamped = max(self._zoom_min, min(self._zoom_max, float(level)))
        if clamped == self._zoom:
            return
        self._zoom = clamped
        self._build_ruler()
        self._rebuild_clips()
        self.zoom_changed.emit(self._zoom)
        # Brief opacity pulse on the tracks container for zoom feedback.
        self._zoom_pulse()

    def zoom_in(self) -> None:
        """Zoom in one step (multiplicative; clamped to ``zoom_max``)."""
        self.set_zoom(self._zoom * self._zoom_step)

    def zoom_out(self) -> None:
        """Zoom out one step (multiplicative; clamped to ``zoom_min``)."""
        self.set_zoom(self._zoom / self._zoom_step)

    def fit_to_contents(self) -> None:
        """Fit the whole timeline to the view (reset zoom to the 1.0 baseline)."""
        self.set_zoom(1.0)

    def wheelEvent(self, event) -> None:  # noqa: N802 (Qt override)
        """Mouse wheel (or Ctrl + wheel) zooms the timeline.

        Scroll up zooms in, scroll down zooms out. Additive input handling;
        it drives the existing zoom API and consumes the event.
        """
        if event.angleDelta().y() > 0:
            self.zoom_in()
        else:
            self.zoom_out()
        event.accept()

    def add_track(self, name: str) -> QWidget:
        """Append a track lane named ``name`` and return its widget."""
        lane = QFrame(self._tracks_container)
        lane.setObjectName("TimelineTrack")
        lane.setFrameShape(QFrame.Shape.StyledPanel)
        # Taller pro-NLE lanes (visual-only): room for clip labels AND the
        # painted waveforms on audio lanes.
        lane.setMinimumHeight(self.scaled(34))
        lane.setProperty("trackName", name)
        # A lane hosts clip blocks positioned by a horizontal layout with
        # stretch spacers (no absolute geometry / no DnD in this milestone).
        row = QHBoxLayout(lane)
        row.setContentsMargins(
            self.tokens.spacing.xs, self.tokens.spacing.xs,
            self.tokens.spacing.xs, self.tokens.spacing.xs,
        )
        row.setSpacing(self.tokens.spacing.xs)
        row.addStretch(1)
        # Empty-space clicks on a lane (no clip under the cursor) clear the
        # selection; clip frames consume their own press first (see
        # eventFilter), so they never reach the lane.
        lane.installEventFilter(self)
        self._track_names.append(name)
        self._track_widgets.append(lane)
        self._tracks_layout.addWidget(lane)
        self._add_track_header(name)
        return lane

    def _build_toolbar(self) -> QWidget:
        """Build the decorative professional timeline toolbar (placeholders).

        Adds a #TimelineToolbar strip above the ruler carrying static glyph
        controls (undo / redo / cut / split / ripple / slip / slide / razor /
        snap / magnet / track height / zoom / fit / marker / add-remove track)
        grouped by thin separators. Every control is a QLabel wired to nothing
        (no signals, no logic); new object names only.
        """
        tokens = self.tokens
        self._toolbar = QFrame(self)
        self._toolbar.setObjectName("TimelineToolbar")
        self._toolbar.setFrameShape(QFrame.Shape.StyledPanel)
        self._toolbar.setFixedHeight(self.scaled(tokens.spacing.xl))
        row = QHBoxLayout(self._toolbar)
        row.setContentsMargins(
            tokens.spacing.sm, tokens.spacing.xxs,
            tokens.spacing.sm, tokens.spacing.xxs,
        )
        row.setSpacing(tokens.spacing.sm)

        # Groups of (glyph, tooltip); a None entry emits a thin separator.
        groups = (
            (("\u21b6", "Undo"), ("\u21b7", "Redo")),
            (("\u2702", "Cut"), ("\u2223", "Split"), ("\u25a4", "Razor")),
            (("\u2b0c", "Ripple"), ("\u2194", "Slip"), ("\u21c4", "Slide")),
            (("\u25a6", "Snap"), ("\U0001f9f2", "Magnet")),
            (("\u2195", "Track Height"),),
            (("\u2795", "Zoom In"), ("\u2796", "Zoom Out"), ("\u2921", "Fit")),
            (("\U0001f6a9", "Marker"),),
            (("\u2795", "Add Track"), ("\U0001f5d1", "Remove Track")),
        )
        for gi, group in enumerate(groups):
            for glyph, tip in group:
                item = QLabel(glyph, self._toolbar)
                item.setObjectName("TimelineToolItem")
                item.setToolTip(tip)
                item.setAccessibleName(tip)
                item.setFont(self._theme.font("caption"))
                item.setAlignment(Qt.AlignmentFlag.AlignCenter)
                # Fixed glyph cell: symbols keep a full 22px hit box instead
                # of collapsing to the glyph's own (clipped) width.
                item.setFixedWidth(self.scaled(22))
                row.addWidget(item)
            if gi < len(groups) - 1:
                sep = QFrame(self._toolbar)
                sep.setObjectName("TimelineToolSeparator")
                sep.setFrameShape(QFrame.Shape.VLine)
                row.addWidget(sep)
        row.addStretch(1)
        self._column.addWidget(self._toolbar)
        return self._toolbar

    def _add_track_header(self, name: str) -> QWidget:
        """Append a decorative Premiere-style track header (wired to nothing).

        Placeholder-only professional chrome: a collapse chevron, eye / mute /
        solo / lock glyph toggles and a track-name label. It has no signals and
        no logic; it exists purely to make each track read like a real editor's
        track head. New object names only; the lane itself is untouched.
        """
        tokens = self.tokens
        header = QFrame(self._headers_container)
        header.setObjectName("TimelineTrackHeader")
        header.setFrameShape(QFrame.Shape.StyledPanel)
        # Matches the taller lane height so headers and lanes stay row-aligned.
        header.setMinimumHeight(self.scaled(34))
        header_row = QHBoxLayout(header)
        header_row.setContentsMargins(
            tokens.spacing.xs, tokens.spacing.xxs,
            tokens.spacing.xs, tokens.spacing.xxs,
        )
        header_row.setSpacing(tokens.spacing.xs)

        # Leading track color swatch + track chip (decorative placeholders).
        # The chip abbreviates the track name like a pro NLE track head
        # (Video Track 1 -> V1, Overlay Track -> OV, Effects Track -> FX).
        color_swatch = QFrame(header)
        color_swatch.setObjectName("TimelineTrackColor")
        color_swatch.setFixedWidth(self.scaled(tokens.spacing.xxs))
        header_row.addWidget(color_swatch)

        number = QLabel(self._track_chip_text(name), header)
        number.setObjectName("TimelineTrackNumber")
        number.setFont(self._theme.font("caption"))
        number.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Fixed chip width: the two-character chip must never be squeezed.
        number.setFixedWidth(self.scaled(26))
        header_row.addWidget(number)

        collapse = QLabel("\u25be", header)  # down chevron (expanded look)
        collapse.setObjectName("TimelineTrackCollapse")
        collapse.setFont(self._theme.font("caption"))
        collapse.setFixedWidth(self.scaled(14))
        collapse.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_row.addWidget(collapse)

        track_label = QLabel(name, header)
        track_label.setObjectName("TimelineTrackName")
        track_label.setFont(self._theme.font("body_small"))
        # The name owns the flexible space; a sane floor prevents the
        # neighbouring glyphs from crushing it to zero.
        track_label.setMinimumWidth(self.scaled(88))
        header_row.addWidget(track_label, 1)

        # Eye / Mute / Solo / Lock toggles (static placeholders). Eye and
        # Lock render as Lucide icon pixmaps; Mute / Solo stay compact
        # letter glyphs like pro NLEs.
        icon_side = self.scaled(12)
        glyph_w = self.scaled(18)
        for icon_name, obj_name in (
            ("eye", "TimelineTrackEye"),
            (None, "TimelineTrackMute"),
            (None, "TimelineTrackSolo"),
            ("lock", "TimelineTrackLock"),
        ):
            control = QLabel(header)
            control.setObjectName(obj_name)
            control.setFont(self._theme.font("caption"))
            control.setAlignment(Qt.AlignmentFlag.AlignCenter)
            # Fixed glyph cell so M / S letters and icons are never clipped
            # when the header row runs out of width.
            control.setFixedWidth(glyph_w)
            if icon_name is not None:
                control.setPixmap(
                    self.icon(
                        icon_name, self.tokens.colors.text_muted, icon_side
                    ).pixmap(icon_side, icon_side)
                )
            else:
                control.setText("M" if obj_name == "TimelineTrackMute" else "S")
            header_row.addWidget(control)

        self._header_widgets.append(header)
        self._headers_layout.addWidget(header)
        return header

    def tracks(self) -> List[str]:
        """Return the current track names in order."""
        return list(self._track_names)

    @staticmethod
    def _track_chip_text(name: str) -> str:
        """Return a compact chip abbreviation for a track header.

        Visual-only: "Video Track 1" -> "V1", "Overlay Track" -> "OV",
        "Subtitles" -> "A4", "Effects Track" / "FX" -> "FX", "SFX" -> "A2",
        "Voice" -> "A3", "Music" -> "A1". Unknown names fall back to their
        first letter.
        """
        lowered = name.lower()
        digits = "".join(ch for ch in name if ch.isdigit())
        if "overlay" in lowered:
            return "OV"
        if "subtitle" in lowered:
            return "A4"
        if "text" in lowered:
            return "T"
        if "sfx" in lowered:
            return "A2"
        if "fx" in lowered or "effect" in lowered:
            return "FX"
        if "music" in lowered:
            return f"A{digits}" if digits else "A1"
        if "audio" in lowered:
            return f"A{digits}" if digits else "A"
        if "voice" in lowered:
            return "A3"
        if "video" in lowered:
            return f"V{digits}" if digits else "V"
        return (name[:1] or "?").upper()

    def _kind_from_track(self, track_index: int) -> str:
        """Derive a clip's visual category from its track's name.

        Visual-only helper for category-colored clip styling: maps a track
        name like ``"Video 1"`` / ``"Overlay"`` / ``"FX"`` to a lowercase
        category token used by the QSS ``kind`` attribute selector. Unknown
        names fall back to ``"video"``.
        """
        if not (0 <= track_index < len(self._track_names)):
            return "video"
        name = self._track_names[track_index].lower()
        for token in ("overlay", "subtitle", "text", "sfx", "fx", "effect",
                      "voice", "audio", "music"):
            if token in name:
                if token in ("music", "sfx"):
                    return "audio"
                if token in ("effect",):
                    return "fx"
                if token in ("subtitle",):
                    return "text"
                return token
        return "video"

    def track_count(self) -> int:
        """Return the number of track lanes."""
        return len(self._track_names)

    def set_clips(self, clips: List[Clip]) -> None:
        """Replace all clip blocks.

        Each clip is a mapping with keys ``track`` (int index), ``start``
        (seconds), ``length`` (seconds) and optional ``label`` (str). Clips on
        unknown track indices are ignored. Static only: no DnD, no trimming.

        Replacing the clips clears any current selection (to ``-1``) and emits
        :attr:`clip_selected` if a selection was active.
        """
        self._clips = [dict(c) for c in clips]
        had_selection = self._selected != -1
        self._selected = -1
        self._rebuild_clips()
        if had_selection:
            self.clip_selected.emit(-1)

    def clips(self) -> List[Clip]:
        """Return a copy of the current clip descriptors."""
        return [dict(c) for c in self._clips]

    def clip_count(self) -> int:
        """Return the number of rendered clip blocks."""
        return len(self._clips)

    def select_clip(self, index: int) -> None:
        """Select the clip at ``index`` (programmatic; no mouse handling).

        Passing ``-1`` clears the selection. Emits :attr:`clip_selected` when
        the selection changes; a no-op otherwise. Marks the corresponding
        ``TimelineClip`` frame with a ``selected`` dynamic property.

        Raises:
            ValueError: If ``index`` is out of range (and not ``-1``).
        """
        if index != -1 and not (0 <= index < len(self._clips)):
            raise ValueError(f"clip index out of range: {index}")
        if index == self._selected:
            return
        self._selected = index
        self._apply_selection_property()
        self.clip_selected.emit(self._selected)

    def move_clip(self, index: int, new_track: int) -> None:
        """Move the clip at ``index`` to track ``new_track`` (programmatic core).

        This is the single source of truth for relocating a clip between
        tracks; the mouse drag path calls it, and future trim/split/ripple work
        can reuse it. It changes ONLY the clip's ``track`` field: ``start``,
        ``length`` and clip ordering are left untouched (Milestone 6 scope).

        The current selection index is preserved across the move, so a selected
        clip stays selected (and, being re-rendered, stays highlighted). This
        does NOT re-emit :attr:`clip_selected`; instead it emits
        :attr:`clip_moved` with ``(index, new_track)`` once the model has been
        updated and rebuilt. A move to the clip's current track is a no-op and
        emits nothing.

        Raises:
            ValueError: If ``index`` or ``new_track`` is out of range.
        """
        if not (0 <= index < len(self._clips)):
            raise ValueError(f"clip index out of range: {index}")
        if not (0 <= new_track < len(self._track_widgets)):
            raise ValueError(f"track index out of range: {new_track}")
        if int(self._clips[index].get("track", 0)) == new_track:
            return
        self._clips[index]["track"] = new_track
        # Selection index is unchanged; rebuild re-applies the selection
        # property so the moved clip (if selected) stays highlighted.
        self._rebuild_clips()
        self.clip_moved.emit(index, new_track)

    def trim_clip(
        self,
        index: int,
        *,
        start: Optional[float] = None,
        length: Optional[float] = None,
    ) -> None:
        """Resize the clip at ``index`` (programmatic core; start/length only).

        Single source of truth for trimming; the edge-drag path calls it. It
        changes ONLY the clip's ``start`` and ``length`` (never ``track`` or
        ordering). ``start`` and/or ``length`` may be given; omitted values keep
        their current value.

        Values are clamped (never raised) to the approved interactive rules:
        ``start >= 0``, ``length >= 1.0`` second, and ``start + length <=``
        :meth:`duration`. When the clamped result equals the current values it
        is a no-op and emits nothing; otherwise the model is updated, rebuilt,
        and :attr:`clip_trimmed` is emitted with ``(index, start, length)``.
        The selection index is preserved (``clip_selected`` is not re-emitted).

        Raises:
            ValueError: Only if ``index`` is out of range.
        """
        if not (0 <= index < len(self._clips)):
            raise ValueError(f"clip index out of range: {index}")
        clip = self._clips[index]
        cur_start = float(clip.get("start", 0.0))
        cur_length = float(clip.get("length", 0.0))
        new_start = cur_start if start is None else float(start)
        new_length = cur_length if length is None else float(length)
        # Clamp: start >= 0, length >= 1.0s, start + length <= duration.
        new_start = max(0.0, new_start)
        new_length = max(1.0, new_length)
        if new_start + new_length > self._duration:
            # Prefer keeping the requested start; shrink length to fit, but
            # never below the 1.0s minimum (pull start back if necessary).
            new_length = self._duration - new_start
            if new_length < 1.0:
                new_length = 1.0
                new_start = max(0.0, self._duration - new_length)
        if new_start == cur_start and new_length == cur_length:
            return
        clip["start"] = new_start
        clip["length"] = new_length
        self._rebuild_clips()
        self.clip_trimmed.emit(index, new_start, new_length)

    def set_thumbnail_fn(self, fn):
        """Set a callback ``(source_path, seconds) -> QImage | None``."""
        self._thumbnail_fn = fn

    def set_waveform_fn(self, fn):
        """Set a callback ``(source, start_s, end_s, n) -> list[float]``."""
        self._waveform_fn = fn

    def is_dragging(self) -> bool:
        """Return ``True`` while a clip drag is in progress (read-only)."""
        return self._drag_active

    def is_trimming(self) -> bool:
        """Return ``True`` while a clip trim is in progress (read-only)."""
        return self._trimming

    def clear_selection(self) -> None:
        """Clear the current clip selection (to ``-1``); idempotent.

        Emits :attr:`clip_selected` with ``-1`` only when a selection was
        active.
        """
        if self._selected == -1:
            return
        self._selected = -1
        self._apply_selection_property()
        self.clip_selected.emit(-1)

    def selected_index(self) -> int:
        """Return the selected clip index (``-1`` when none)."""
        return self._selected

    def selected_clip(self) -> Optional[Clip]:
        """Return a copy of the selected clip descriptor, or ``None``."""
        if 0 <= self._selected < len(self._clips):
            return dict(self._clips[self._selected])
        return None

    def playhead(self) -> float:
        """Return the current playhead time in seconds."""
        return self._playhead

    def set_playhead(self, seconds: float) -> None:
        """Set the playhead time (clamped to ``[0, duration]``).

        Emits :attr:`playhead_changed` when the value changes.
        """
        clamped = max(0.0, min(self._duration, float(seconds)))
        if clamped == self._playhead:
            return
        self._playhead = clamped
        self.playhead_changed.emit(self._playhead)

    # ------------------------------------------------------------------ #
    # Internal build helpers
    # ------------------------------------------------------------------ #
    def _build_ruler(self) -> None:
        """Rebuild the ruler tick labels for the current duration."""
        while self._ruler_row.count():
            item = self._ruler_row.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
        # A denser, cleaner professional time scale: evenly spaced ticks with
        # hh:mm:ss timecode labels (decorative only; still #TimelineTick).
        ticks = 11
        last = ticks - 1
        for i in range(ticks):
            seconds = self._duration * (i / float(last))
            total = int(round(seconds))
            hours = total // 3600
            minutes = (total % 3600) // 60
            secs = total % 60
            label = QLabel(
                f"{hours:02d}:{minutes:02d}:{secs:02d}", self._ruler
            )
            label.setObjectName("TimelineTick")
            label.setFont(self._theme.font("caption"))
            # Hard floor at the text's metric width so timecodes are never
            # compressed by the surrounding stretch items.
            label.setMinimumWidth(
                label.fontMetrics().horizontalAdvance(label.text()) + 6
            )
            self._ruler_row.addWidget(label)
            if i < last:
                self._ruler_row.addStretch(1)

    def _rebuild_clips(self) -> None:
        """Rebuild clip blocks in their lanes from the current descriptors."""
        # Clear existing clip frames from every lane (keep the trailing
        # stretch spacer at the end of each lane row).
        for lane in self._track_widgets:
            row = lane.layout()
            for i in reversed(range(row.count())):
                item = row.itemAt(i)
                widget = item.widget()
                if widget is not None and widget.objectName() == "TimelineClip":
                    row.takeAt(i)
                    widget.setParent(None)
        self._clip_widgets = []

        for clip in self._clips:
            track_index = int(clip.get("track", 0))
            if not (0 <= track_index < len(self._track_widgets)):
                # Keep _clip_widgets aligned with clip order: unrenderable
                # clips (unknown track) have no frame.
                self._clip_widgets.append(None)
                continue
            lane = self._track_widgets[track_index]
            row = lane.layout()
            block = QFrame(lane)
            block.setObjectName("TimelineClip")
            block.setFrameShape(QFrame.Shape.StyledPanel)
            # Category styling (visual-only): an optional "kind" key on the
            # clip mapping (or, when absent, the owning track's name) selects
            # a QSS attribute rule so video / overlay / text / fx / audio
            # clips render in their category color like a pro NLE.
            kind = str(clip.get("kind", "")) or self._kind_from_track(
                track_index
            )
            block.setProperty("kind", kind)
            label_text = str(clip.get("label", ""))
            block_layout = QHBoxLayout(block)
            block_layout.setContentsMargins(
                self.tokens.spacing.xs, 0, self.tokens.spacing.xs, 0
            )
            block_layout.setSpacing(self.tokens.spacing.xxs)
            # Real video thumbnail: decode a frame at the clip's start time
            # and show it as a scaled background image on the clip block.
            source = clip.get("source", "") or label_text
            if source and self._thumbnail_fn is not None:
                clip_start = float(clip.get("start", 0.0))
                thumb_key = (source, int(clip_start * 10))
                if not hasattr(self, "_thumb_cache"):
                    self._thumb_cache = {}
                thumb = self._thumb_cache.get(thumb_key)
                if thumb is None:
                    try:
                        thumb = self._thumbnail_fn(source, clip_start)
                    except Exception:
                        thumb = None
                    self._thumb_cache[thumb_key] = thumb
                if thumb is not None:
                    thumb_lbl = QLabel(block)
                    length_s = max(1.0, float(clip.get("length", 1.0)))
                    length_factor = max(1.0, length_s / 4.0)
                    block_w = int(self._clip_base_width * self._zoom * length_factor)
                    from PySide6.QtGui import QPixmap as _QP
                    thumb_lbl.setPixmap(
                        _QP.fromImage(thumb).scaled(
                            max(1, block_w - 4), 28,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                    )
                    thumb_lbl.setStyleSheet(
                        "background: transparent; border-radius: 2px;"
                    )
                    block_layout.addWidget(thumb_lbl, 0)
            caption = QLabel(label_text, block)
            caption.setObjectName("TimelineClipLabel")
            caption.setFont(self._theme.font("caption"))
            caption.setToolTip(label_text)
            length_s = max(1.0, float(clip.get("length", 1.0)))
            length_factor = max(1.0, length_s / 4.0)
            block_w = int(self._clip_base_width * self._zoom * length_factor)
            fm = caption.fontMetrics()
            avail = max(0, block_w - 2 * self.tokens.spacing.xs - 6)
            if fm.horizontalAdvance(label_text) > avail:
                caption.setText(
                    fm.elidedText(label_text, Qt.TextElideMode.ElideRight, avail)
                )
            block_layout.addWidget(caption, 1)
            # Audio-family clips get a decorative painted pseudo-waveform
            # (visual-only; mouse-transparent so select / drag / trim on the
            # clip frame is unaffected).
            if kind in ("audio", "voice"):
                wave_color = (
                    self.tokens.colors.track_audio
                    if kind == "audio"
                    else self.tokens.colors.track_voice
                )
                _ClipWaveform(block, wave_color, label_text)
            # Rendering-only zoom: the block's minimum width scales with the
            # current zoom level (Milestone 8) AND with the clip's duration,
            # so a 32s music bed reads wider than a 3s FX chip like a real
            # NLE (visual-only; no model / object-name change).
            block.setMinimumWidth(block_w)
            # Insert before the trailing stretch spacer.
            row.insertWidget(max(0, row.count() - 1), block)
            # Left-click on a clip selects it (see eventFilter).
            block.installEventFilter(self)
            self._clip_widgets.append(block)

        self.apply_theme()
        self._apply_selection_property()

    # ------------------------------------------------------------------ #
    # Mouse input (click-to-select; Phase 8H, Milestone 5)
    # ------------------------------------------------------------------ #
    def eventFilter(self, watched, event) -> bool:  # noqa: N802 (Qt override)
        """Left-click a clip to select it; click empty space to clear.

        Click-only input plumbing: it drives the existing select_clip /
        clear_selection API (no new public API, no drag/move/trim/split).
        Returns ``True`` to consume a handled clip press so it does not also
        reach the empty-space (lane / tracks) handler.
        """
        etype = event.type()
        # Clip hover: brighten border on enter, restore on leave.
        if etype == QEvent.Type.Enter:
            for frame in self._clip_widgets:
                if frame is not None and watched is frame:
                    self._on_clip_enter(frame)
                    return False
        elif etype == QEvent.Type.Leave:
            for frame in self._clip_widgets:
                if frame is not None and watched is frame:
                    self._on_clip_leave(frame)
                    return False
        if etype == QEvent.Type.MouseButtonPress and (
            event.button() == Qt.MouseButton.LeftButton
        ):
            # A clip frame: select its clip and arm a possible drag. The event
            # is consumed so it does not also reach the empty-space handler.
            for index, frame in enumerate(self._clip_widgets):
                if frame is not None and watched is frame:
                    self.select_clip(index)
                    self._arm_drag(index, event)
                    return True
            # A press on the ruler seeks the playhead (Milestone 9).
            if watched is self._ruler:
                self._seek_from_ruler(event)
                return False
            # Otherwise the press landed on a lane or the tracks background
            # (empty space): clear the selection.
            if watched is self._tracks_container or watched in self._track_widgets:
                self.clear_selection()
                return False
        elif etype == QEvent.Type.MouseMove and watched is self._ruler and (
            event.buttons() == Qt.MouseButton.LeftButton
        ):
            # Dragging on the ruler scrubs the playhead (Milestone 9).
            self._seek_from_ruler(event)
            return False
        elif etype == QEvent.Type.MouseMove and self._drag_armed:
            self._update_drag(event)
            return False
        elif etype == QEvent.Type.MouseButtonRelease and self._drag_armed and (
            event.button() == Qt.MouseButton.LeftButton
        ):
            self._finish_drag(watched)
            return False
        return super().eventFilter(watched, event)

    # ------------------------------------------------------------------ #
    # Drag & drop (Phase 8H, Milestone 6; manual press -> move -> release)
    # ------------------------------------------------------------------ #
    def _arm_drag(self, index: int, event) -> None:
        """Record a pending drag for the clip pressed at ``index``.

        The drag only becomes active once the pointer moves past
        :attr:`_drag_threshold`, so a plain click still selects (Milestone 5).
        """
        self._drag_index = index
        self._drag_armed = True
        self._drag_active = False
        self._drag_press_pos = event.position()
        # Classify the grab: a press within the edge zone of the clip frame is
        # a trim (left/right); otherwise it is a move (M6). Snapshot the clip's
        # start/length so live trimming is computed from a stable base.
        self._drag_mode = "move"
        self._trim_origin = None
        frame = self._clip_widgets[index] if 0 <= index < len(self._clip_widgets) else None
        if frame is not None:
            width = frame.width()
            x = event.position().x()
            # Only classify a trim when the frame has a usable width; a press
            # near an edge otherwise (e.g. a zero-width offscreen frame) stays
            # a move, preserving M5 click and M6 drag behavior.
            if width > 2 * self._trim_edge_zone:
                if x <= self._trim_edge_zone:
                    self._drag_mode = "trim_left"
                elif x >= width - self._trim_edge_zone:
                    self._drag_mode = "trim_right"
            clip = self._clips[index]
            self._trim_origin = (
                float(clip.get("start", 0.0)),
                float(clip.get("length", 0.0)),
            )

    def _update_drag(self, event) -> None:
        """Activate past the threshold; trim on an edge grab, else preview lane."""
        if not self._drag_active and self._drag_press_pos is not None:
            delta = event.position() - self._drag_press_pos
            if max(abs(delta.x()), abs(delta.y())) < self._drag_threshold:
                return
            self._drag_active = True
        if self._drag_mode in ("trim_left", "trim_right"):
            # Mark the trim and remember the latest pointer position; the trim
            # is committed on release (see _finish_drag), so a gesture that
            # actually ends on another lane can still fall through to a move.
            self._trimming = True
            self._trim_last_pos = event.position()
            return
        lane = self._lane_at(event)
        self._set_drop_target(lane)

    def _apply_trim(self) -> None:
        """Commit the edge trim from the accumulated pointer movement (M7).

        Left trim holds the right edge fixed (adjusts start, compensating
        length); right trim holds the left edge fixed (adjusts length). The
        horizontal pointer delta (press -> last move) is mapped to seconds via
        _px_per_second and applied through trim_clip, which clamps to the
        approved rules.
        """
        if (
            self._trim_origin is None
            or self._drag_press_pos is None
            or self._trim_last_pos is None
        ):
            return
        start0, length0 = self._trim_origin
        dx = self._trim_last_pos.x() - self._drag_press_pos.x()
        delta_seconds = dx / self._px_per_second
        if self._drag_mode == "trim_left":
            right_edge = start0 + length0
            new_start = start0 + delta_seconds
            self.trim_clip(
                self._drag_index,
                start=new_start,
                length=right_edge - new_start,
            )
        else:  # trim_right: hold the left edge, adjust length.
            self.trim_clip(
                self._drag_index, length=length0 + delta_seconds
            )

    def _finish_drag(self, watched) -> None:
        """Commit the interaction, decided by the release target.

        A release on (or inside) a clip frame is a trim; a release elsewhere
        (on a lane / tracks background) is a move. This resolves the gesture
        collision where both the M6 move and the M7 left-trim begin near the
        clip's left edge: the arm-time classification only pre-selects a trim,
        but the move still wins when the drag ends on a different lane.
        """
        armed_active = self._drag_active
        drag_index = self._drag_index
        is_trim = (
            self._drag_mode in ("trim_left", "trim_right")
            and self._clip_frame_of(watched) is not None
        )
        dest_lane = self._lane_of(watched)
        if dest_lane is None:
            dest_lane = self._drop_lane
        self._set_drop_target(None)
        self._reset_drag_keep_trim()
        if is_trim:
            if armed_active and drag_index >= 0:
                self._apply_trim()
            self._reset_drag()
            return
        self._reset_drag()
        if not armed_active or drag_index < 0 or dest_lane is None:
            return
        dest_track = self._track_widgets.index(dest_lane)
        # move_clip is a no-op when the clip is already on dest_track.
        self.move_clip(drag_index, dest_track)

    def _clip_frame_of(self, widget) -> Optional[QWidget]:
        """Return the ``TimelineClip`` frame owning ``widget`` (self included)."""
        node = widget
        while node is not None:
            if node in self._clip_widgets:
                return node
            node = node.parentWidget() if hasattr(node, "parentWidget") else None
        return None

    def _reset_drag_keep_trim(self) -> None:
        """Reset only the drop-target preview; keep drag/trim fields for commit."""
        self._drop_lane = None

    def _reset_drag(self) -> None:
        """Clear all pending/active drag and trim state."""
        self._drag_index = -1
        self._drag_armed = False
        self._drag_active = False
        self._drag_press_pos = None
        self._drag_mode = "move"
        self._trimming = False
        self._trim_origin = None
        self._trim_last_pos = None

    def _lane_of(self, widget) -> Optional[QWidget]:
        """Return the ``TimelineTrack`` lane owning ``widget`` (self included)."""
        node = widget
        while node is not None:
            if node in self._track_widgets:
                return node
            node = node.parentWidget() if hasattr(node, "parentWidget") else None
        return None

    def _lane_at(self, event) -> Optional[QWidget]:
        """Best-effort lane under the pointer during a move (may be ``None``)."""
        pos = event.globalPosition().toPoint()
        target = QApplication.widgetAt(pos)
        return self._lane_of(target)

    def _set_drop_target(self, lane: Optional[QWidget]) -> None:
        """Mark ``lane`` with the ``dropTarget`` property; clear the previous.

        Additive preview only (same unpolish/polish pattern as the ``selected``
        clip property). No preview widget and no new object name.
        """
        if lane is self._drop_lane:
            return
        for candidate in (self._drop_lane, lane):
            if candidate is None:
                continue
            wanted = candidate is lane
            if candidate.property("dropTarget") != wanted:
                candidate.setProperty("dropTarget", wanted)
                candidate.style().unpolish(candidate)
                candidate.style().polish(candidate)
        self._drop_lane = lane

    def _apply_selection_property(self) -> None:
        """Set the ``selected`` dynamic property on the selected clip frame.

        Clears the property on all other rendered frames. Uses unpolish/polish
        so any style depending on the property is refreshed. Does not alter
        apply_theme's base clip styling; the property is purely additive.
        Also triggers a brief bounce animation on the newly selected clip.
        """
        for i, frame in enumerate(self._clip_widgets):
            if frame is None:
                continue
            is_selected = i == self._selected
            if frame.property("selected") != is_selected:
                frame.setProperty("selected", is_selected)
                frame.style().unpolish(frame)
                frame.style().polish(frame)
                # Brief selection bounce for tactile confirmation.
                if is_selected and hasattr(self, '_theme'):
                    self._animate_clip_select(frame)

    def _animate_clip_select(self, frame: QWidget) -> None:
        """Bounce a clip frame's height briefly on selection (visual feedback)."""
        base_h = self.scaled(34)
        bounce_h = base_h + 4
        dur = self._theme.duration("fast") // 2
        easing = self._theme.easing("out_cubic")
        # Expand up
        anim = QPropertyAnimation(frame, b"minimumHeight", frame)
        anim.setDuration(dur)
        anim.setStartValue(base_h)
        anim.setEndValue(bounce_h)
        anim.setEasingCurve(easing)
        # Shrink back
        anim2 = QPropertyAnimation(frame, b"minimumHeight", frame)
        anim2.setDuration(dur)
        anim2.setStartValue(bounce_h)
        anim2.setEndValue(base_h)
        anim2.setEasingCurve(self._theme.easing("in_cubic"))
        from PySide6.QtCore import QSequentialAnimationGroup, QAbstractAnimation
        group = QSequentialAnimationGroup(frame)
        group.addAnimation(anim)
        group.addAnimation(anim2)
        group.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
        self._clip_bounce_anim = group

    def _sync_playhead_pulse(self) -> None:
        """Start or stop the playhead pulse animation based on playback state."""
        if self._playback_state == "playing":
            self._start_playhead_pulse()
        else:
            self._stop_playhead_pulse()

    def _start_playhead_pulse(self) -> None:
        """Animate the playhead marker height in a slow repeating pulse."""
        base_h = self.scaled(self.tokens.spacing.xs)
        pulse_h = base_h + 2
        anim = QPropertyAnimation(self._playhead_marker, b"maximumHeight", self)
        anim.setDuration(600)
        anim.setLoopCount(-1)  # infinite
        anim.setStartValue(base_h)
        anim.setKeyValueAt(0.5, pulse_h)
        anim.setEndValue(base_h)
        anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        anim.start()
        self._playhead_pulse_anim = anim

    def _stop_playhead_pulse(self) -> None:
        """Stop the playhead pulse animation and restore base height."""
        if hasattr(self, '_playhead_pulse_anim'):
            self._playhead_pulse_anim.stop()
            del self._playhead_pulse_anim
        base_h = self.scaled(self.tokens.spacing.xs)
        self._playhead_marker.setMaximumHeight(base_h)

    def _on_clip_enter(self, frame: QWidget) -> None:
        """Brighten clip border on hover via a subtle border-color tween."""
        c = self.tokens.colors
        dur = self._theme.duration("fast")
        easing = self._theme.easing("out_cubic")

        def _apply_border(factor: float) -> None:
            a = int(factor * 200)
            frame.setStyleSheet(
                frame.styleSheet() +
                f"/* hover: {a} */"
            )

        # Store the current sheet so we can revert on leave
        if not hasattr(frame, '_base_qss'):
            frame._base_qss = frame.styleSheet()

    def _on_clip_leave(self, frame: QWidget) -> None:
        """Restore clip border after hover ends."""
        if hasattr(frame, '_base_qss'):
            frame.setStyleSheet(frame._base_qss)

    def _zoom_pulse(self) -> None:
        """Brief opacity pulse on the tracks container when zoom changes."""
        from gui.widgets.animation import tween_value
        container = self._tracks_container

        def _set_opacity(v: float) -> None:
            container.setWindowOpacity(v) if False else None
            container.setFixedHeight(container.maximumHeight())
            # Simple visual feedback: briefly change container's opacity via style
            a = int(max(0, min(255, v * 255)))
            container.setStyleSheet(
                f"#TimelineTracks {{ background: {self.tokens.colors.background_deep}; "
                f"border-radius: {self.scaled(self.tokens.radius.md)}px; opacity: {a}; }}"
            )

        tween_value(
            1.0, 0.7, lambda v: None,
            duration_ms=self._theme.duration("fast") // 2,
            easing=self._theme.easing("in_cubic"),
        )
        # Restore immediately via a short timer — the visual feedback is the
        # rebuild itself; the pulse is purely cosmetic.
        from PySide6.QtCore import QTimer
        QTimer.singleShot(self._theme.duration("fast") // 2, lambda: self.apply_theme())

    # ------------------------------------------------------------------ #
    # Theming
    # ------------------------------------------------------------------ #
    def apply_theme(self) -> None:
        """Apply the premium themed styling to the timeline surfaces.

        Styling-only (Phase 9D): richer, object-name-scoped, token-derived QSS
        for a modern pro-editor look (glass ruler, alternating lane shading,
        gradient clip cards with hover + selection glow, accent playhead). No
        behavior, object name, dynamic property, signal or code path changes.
        """
        colors = self.tokens.colors
        radius = self.scaled(self.tokens.radius.sm)
        radius_md = self.scaled(self.tokens.radius.md)

        # Root: a calm deep backdrop under the ruler / tracks.
        self.setStyleSheet(
            f"#Timeline {{ background: {colors.background_base}; }}"
        )

        # Ruler: elevated glass strip, subtle bottom divider, rounded top; the
        # tick labels are muted so the time scale reads as secondary.
        self._ruler.setStyleSheet(
            f"#TimelineRuler {{ background: {colors.surface_elevated}; "
            f"border: 1px solid {colors.glass_border}; "
            f"border-bottom: 1px solid {colors.border}; "
            f"border-radius: {radius_md}px; }} "
            f"#TimelineTick {{ color: {colors.text_muted}; "
            f"background: transparent; }}"
        )

        # Tracks container: the deepest surface, so lanes read as insets.
        self._tracks_container.setStyleSheet(
            f"#TimelineTracks {{ background: {colors.background_deep}; "
            f"border-radius: {radius_md}px; }}"
        )

        # Timeline toolbar: a glass strip with muted tool glyphs and thin
        # separators (decorative). Object-name-scoped; no hardcoded colors.
        self._toolbar.setStyleSheet(
            f"#TimelineToolbar {{ background: {colors.surface_elevated}; "
            f"border: 1px solid {colors.glass_border}; "
            f"border-radius: {radius_md}px; }} "
            f"#TimelineToolItem {{ color: {colors.text_secondary}; "
            f"background: transparent; }} "
            f"#TimelineToolItem:hover {{ color: {colors.accent_cyan}; }} "
            f"#TimelineToolSeparator {{ color: {colors.divider}; "
            f"background: {colors.divider}; border: none; max-width: 1px; }}"
        )

        # Track-header column: a layered glass rail matching the lanes, with
        # alternating header shading, soft borders and muted control glyphs;
        # the track name reads in accent-cyan. Decorative only.
        self._headers_container.setStyleSheet(
            f"#TimelineTrackHeaders {{ background: {colors.background_deep}; "
            f"border-radius: {radius_md}px; }} "
            f"#TimelineTrackNumber {{ color: {colors.text_primary}; "
            f"background: {colors.surface_overlay}; "
            f"border: 1px solid {colors.border}; "
            f"border-radius: {self.scaled(4)}px; "
            f"padding: 0px {self.scaled(3)}px; "
            f"min-width: {self.scaled(18)}px; }}"
        )
        kind_swatch = {
            "video": colors.track_video,
            "overlay": colors.track_overlay,
            "text": colors.track_text,
            "fx": colors.track_fx,
            "audio": colors.track_audio,
            "voice": colors.track_voice,
        }
        for index, header in enumerate(self._header_widgets):
            header_bg = (
                colors.surface if index % 2 == 0 else colors.surface_overlay
            )
            swatch_color = kind_swatch.get(
                self._kind_from_track(index), colors.accent_cyan
            )
            header.setStyleSheet(
                f"#TimelineTrackHeader {{ background: {header_bg}; "
                f"border: 1px solid {colors.border}; "
                f"border-radius: {radius}px; }} "
                f"#TimelineTrackColor {{ background: {swatch_color}; "
                f"border-radius: {radius}px; }} "
                f"#TimelineTrackName {{ color: {colors.text_primary}; "
                f"background: transparent; }} "
                f"#TimelineTrackCollapse, "
                f"#TimelineTrackMute, #TimelineTrackSolo "
                f"{{ color: {colors.text_muted}; "
                f"background: transparent; }} "
                f"#TimelineTrackEye, #TimelineTrackLock "
                f"{{ background: transparent; }}"
            )

        # Playhead: a brighter electric-blue line with a rounded handle glow.
        self._playhead_marker.setStyleSheet(
            f"#TimelinePlayhead {{ background: qlineargradient("
            f"x1:0, y1:0, x2:1, y2:0, "
            f"stop:0 transparent, stop:0.5 {colors.accent_blue}, "
            f"stop:1 transparent); "
            f"border: 1px solid {colors.accent_blue_glow}; "
            f"border-radius: {radius}px; }}"
        )

        # Track lanes: alternating row shading (pro editors alternate lanes),
        # a subtle border and rounded corners; the drag preview keeps its
        # dropTarget highlight, styled here as a cyan-accent inset.
        for index, lane in enumerate(self._track_widgets):
            lane_bg = colors.surface if index % 2 == 0 else colors.surface_overlay
            lane.setStyleSheet(
                f"#TimelineTrack {{ background: {lane_bg}; "
                f"border: 1px solid {colors.border}; "
                f"border-radius: {radius}px; }} "
                f'#TimelineTrack[dropTarget="true"] {{ '
                f"background: {colors.surface_overlay}; "
                f"border: 1px solid {colors.accent_cyan}; }}"
            )

        # Clip cards: category-colored gradients (video / overlay / text /
        # fx / audio / voice) keyed on the `kind` dynamic property set in
        # _rebuild_clips, with a hover brighten and a selection glow (accent
        # border + cyan fill) keyed on the existing `selected` property.
        def _clip_grad(color: str) -> str:
            return (
                f"qlineargradient(x1:0, y1:0, x2:0, y2:1, "
                f"stop:0 {color}, stop:1 {colors.surface_overlay})"
            )

        kind_colors = {
            "video": colors.track_video,
            "overlay": colors.track_overlay,
            "fx": colors.track_fx,
        }
        kind_rules = " ".join(
            f'#TimelineClip[kind="{kind}"] {{ '
            f"background: {_clip_grad(color)}; }}"
            for kind, color in kind_colors.items()
        )

        # Audio-family clips read as dark waveform containers (the painted
        # waveform provides the color); subtitle/text clips read as outlined
        # dark chips with a colored caption, per the reference.
        def _hex_rgba(color: str, alpha: float) -> str:
            """Return ``rgba(r, g, b, alpha)`` from a hex or rgb(a) token.

            Accepts '#rgb', '#rrggbb', 'rgb(r,g,b)' and 'rgba(r,g,b,a)'
            defensively so a non-hex color token never raises inside the
            theme/paint path (which previously produced invalid-color
            warnings). Falls back to an opaque-ish neutral on any parse
            failure rather than crashing.
            """
            try:
                text = color.strip()
                if text.lower().startswith(("rgba(", "rgb(")):
                    inner = text[text.index("(") + 1:text.rindex(")")]
                    parts = [p.strip() for p in inner.split(",")]
                    r, g, b = (int(round(float(parts[i]))) for i in range(3))
                    return f"rgba({r}, {g}, {b}, {alpha})"
                hexstr = text.lstrip("#")
                if len(hexstr) == 3:  # '#rgb' shorthand
                    hexstr = "".join(ch * 2 for ch in hexstr)
                r, g, b = (int(hexstr[i:i + 2], 16) for i in (0, 2, 4))
                return f"rgba({r}, {g}, {b}, {alpha})"
            except Exception:
                return f"rgba(128, 128, 128, {alpha})"

        audio_rules = " ".join(
            f'#TimelineClip[kind="{kind}"] {{ '
            f"background: {_hex_rgba(color, 0.14)}; "
            f"border: 1px solid {_hex_rgba(color, 0.45)}; }} "
            f'#TimelineClip[kind="{kind}"] #TimelineClipLabel {{ '
            f"color: {color}; }}"
            for kind, color in (
                ("audio", colors.track_audio),
                ("voice", colors.track_voice),
            )
        )
        text_rules = (
            f'#TimelineClip[kind="text"] {{ '
            f"background: {_hex_rgba(colors.track_text, 0.12)}; "
            f"border: 1px solid {_hex_rgba(colors.track_text, 0.55)}; }} "
            f'#TimelineClip[kind="text"] #TimelineClipLabel {{ '
            f"color: {colors.text_primary}; }}"
        )
        clip_qss = (
            f"#TimelineClip {{ "
            f"background: qlineargradient(x1:0, y1:0, x2:0, y2:1, "
            f"stop:0 {colors.accent_purple}, stop:1 {colors.accent_blue}); "
            f"border: 1px solid {colors.glass_border}; "
            f"border-radius: {radius}px; }} "
            f"{kind_rules} {audio_rules} {text_rules} "
            f"#TimelineClip:hover {{ "
            f"border: 1px solid {colors.glass_highlight}; }} "
            f'#TimelineClip[selected="true"] {{ '
            f"background: qlineargradient(x1:0, y1:0, x2:0, y2:1, "
            f"stop:0 {colors.accent_cyan}, stop:1 {colors.accent_blue}); "
            f"border: 1px solid {colors.accent_cyan}; }} "
            f"#TimelineClipLabel {{ color: {colors.text_on_accent}; "
            f"background: transparent; }}"
        )
        for block in self.findChildren(QFrame):
            if block.objectName() == "TimelineClip":
                block.setStyleSheet(clip_qss)
