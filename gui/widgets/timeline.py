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

from PySide6.QtCore import QEvent, Qt, Signal
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
        # Empty-space clicks on a lane (no clip under the cursor) clear the
        # selection; clip frames consume their own press first (see
        # eventFilter), so they never reach the lane.
        lane.installEventFilter(self)
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

    def is_dragging(self) -> bool:
        """Return ``True`` while a clip drag is in progress (read-only)."""
        return self._drag_active

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
            # Otherwise the press landed on a lane or the tracks background
            # (empty space): clear the selection.
            if watched is self._tracks_container or watched in self._track_widgets:
                self.clear_selection()
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

    def _update_drag(self, event) -> None:
        """Activate the drag past the threshold and preview the hovered lane."""
        if not self._drag_active and self._drag_press_pos is not None:
            delta = event.position() - self._drag_press_pos
            if max(abs(delta.x()), abs(delta.y())) < self._drag_threshold:
                return
            self._drag_active = True
        lane = self._lane_at(event)
        self._set_drop_target(lane)

    def _finish_drag(self, watched) -> None:
        """Resolve the destination lane and commit the move if it changed."""
        armed_active = self._drag_active
        drag_index = self._drag_index
        dest_lane = self._lane_of(watched)
        if dest_lane is None:
            dest_lane = self._drop_lane
        self._set_drop_target(None)
        self._reset_drag()
        if not armed_active or drag_index < 0 or dest_lane is None:
            return
        dest_track = self._track_widgets.index(dest_lane)
        # move_clip is a no-op when the clip is already on dest_track.
        self.move_clip(drag_index, dest_track)

    def _reset_drag(self) -> None:
        """Clear all pending/active drag state."""
        self._drag_index = -1
        self._drag_armed = False
        self._drag_active = False
        self._drag_press_pos = None

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
        """
        for i, frame in enumerate(self._clip_widgets):
            if frame is None:
                continue
            is_selected = i == self._selected
            if frame.property("selected") != is_selected:
                frame.setProperty("selected", is_selected)
                frame.style().unpolish(frame)
                frame.style().polish(frame)

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
