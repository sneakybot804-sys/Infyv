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

from typing import Dict, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
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

    Raises:
        ValueError: If ``duration`` is not strictly positive.
    """

    playhead_changed = Signal(float)

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

        tokens = self.tokens
        self._column = QVBoxLayout(self)
        self._column.setContentsMargins(0, 0, 0, 0)
        self._column.setSpacing(tokens.spacing.xs)

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

        # Track lanes container.
        self._tracks_container = QWidget(self)
        self._tracks_container.setObjectName("TimelineTracks")
        self._tracks_layout = QVBoxLayout(self._tracks_container)
        self._tracks_layout.setContentsMargins(0, 0, 0, 0)
        self._tracks_layout.setSpacing(tokens.spacing.xs)
        self._column.addWidget(self._tracks_container, 1)

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

    def add_track(self, name: str) -> QWidget:
        """Append a track lane named ``name`` and return its widget."""
        lane = QFrame(self._tracks_container)
        lane.setObjectName("TimelineTrack")
        lane.setFrameShape(QFrame.Shape.StyledPanel)
        lane.setMinimumHeight(self.scaled(self.tokens.spacing.xxl))
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
        self._track_names.append(name)
        self._track_widgets.append(lane)
        self._tracks_layout.addWidget(lane)
        return lane

    def tracks(self) -> List[str]:
        """Return the current track names in order."""
        return list(self._track_names)

    def track_count(self) -> int:
        """Return the number of track lanes."""
        return len(self._track_names)

    def set_clips(self, clips: List[Clip]) -> None:
        """Replace all clip blocks.

        Each clip is a mapping with keys ``track`` (int index), ``start``
        (seconds), ``length`` (seconds) and optional ``label`` (str). Clips on
        unknown track indices are ignored. Static only: no DnD, no trimming.
        """
        self._clips = [dict(c) for c in clips]
        self._rebuild_clips()

    def clips(self) -> List[Clip]:
        """Return a copy of the current clip descriptors."""
        return [dict(c) for c in self._clips]

    def clip_count(self) -> int:
        """Return the number of rendered clip blocks."""
        return len(self._clips)

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
        # Five evenly spaced tick labels (0%..100% of duration).
        for i in range(5):
            seconds = self._duration * (i / 4.0)
            label = QLabel(f"{seconds:.0f}s", self._ruler)
            label.setObjectName("TimelineTick")
            label.setFont(self._theme.font("caption"))
            self._ruler_row.addWidget(label)
            if i < 4:
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

        for clip in self._clips:
            track_index = int(clip.get("track", 0))
            if not (0 <= track_index < len(self._track_widgets)):
                continue
            lane = self._track_widgets[track_index]
            row = lane.layout()
            block = QFrame(lane)
            block.setObjectName("TimelineClip")
            block.setFrameShape(QFrame.Shape.StyledPanel)
            label_text = str(clip.get("label", ""))
            block_layout = QHBoxLayout(block)
            block_layout.setContentsMargins(
                self.tokens.spacing.xs, 0, self.tokens.spacing.xs, 0
            )
            caption = QLabel(label_text, block)
            caption.setObjectName("TimelineClipLabel")
            caption.setFont(self._theme.font("caption"))
            block_layout.addWidget(caption)
            # Insert before the trailing stretch spacer.
            row.insertWidget(max(0, row.count() - 1), block)

        self.apply_theme()

    # ------------------------------------------------------------------ #
    # Theming
    # ------------------------------------------------------------------ #
    def apply_theme(self) -> None:
        """Apply themed backgrounds and borders to the timeline surfaces."""
        colors = self.tokens.colors
        radius = self.scaled(self.tokens.radius.sm)
        self._ruler.setStyleSheet(
            f"#TimelineRuler {{ background: {colors.surface_elevated}; "
            f"border-radius: {radius}px; }}"
        )
        self._tracks_container.setStyleSheet(
            f"#TimelineTracks {{ background: {colors.surface}; }}"
        )
        self._playhead_marker.setStyleSheet(
            f"#TimelinePlayhead {{ background: {colors.accent_cyan}; "
            f"border-radius: {radius}px; }}"
        )
        for lane in self._track_widgets:
            lane.setStyleSheet(
                f"#TimelineTrack {{ background: {colors.surface_overlay}; "
                f"border-radius: {radius}px; }}"
            )
        for block in self.findChildren(QFrame):
            if block.objectName() == "TimelineClip":
                block.setStyleSheet(
                    f"#TimelineClip {{ background: {colors.accent_purple}; "
                    f"border-radius: {radius}px; }}"
                )
