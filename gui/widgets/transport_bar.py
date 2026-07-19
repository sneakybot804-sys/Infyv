"""TransportBar: UI-only playback transport controls (Phase 8H, Milestone 2).

A themed transport row composed from the frozen widget library: Play / Pause /
Stop as icon :class:`NeonButton`s and a seek placeholder built on the library
:class:`Slider`.

This is a pure UI state machine. It tracks a transport ``state`` -- one of
``"stopped"`` / ``"playing"`` / ``"paused"`` -- and a normalized ``position``
in ``[0.0, 1.0]``. It performs no real playback, opens no media, and never
touches :mod:`gui_core`. All behaviour is signals + internal state so a future
milestone can bind it to an actual player.

NEXUS visual pass (UI-only, layout rebuild of the decorative chrome): the row
mirrors the reference transport -- a left monospace timecode dropdown pill and
edit-tool icon cluster, a centered playback control group (frame-step /
rewind / play / pause / stop / fast-forward), and a right indicator cluster
(playback rate, Safe Area, aspect / resolution / FPS chips, fullscreen). The
extra chrome is composed from the existing widget library and is decorative /
wired to nothing; the frozen controls, public API, signals and state machine
are unchanged.

Stable object names for later integration and tests:

* ``TransportBar`` -- the root widget
* ``TransportPlay`` / ``TransportPause`` / ``TransportStop`` -- the buttons
* ``TransportSeek`` -- the seek slider

Additive decorative object names (wired to nothing):

* ``TransportTimecode`` -- the monospace timecode readout (left pill).
* ``TransportTools`` -- the left edit-tool icon cluster.
* ``TransportControls`` -- the centered playback control group.
* ``TransportIndicators`` / ``TransportRate`` -- the right indicator cluster.
* ``TransportSeekRow`` -- the full-width seek scrubber row.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QAbstractAnimation, QPropertyAnimation, QVariantAnimation, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from gui.theme.manager import ThemeManager
from gui.widgets.base import ThemedWidget
from gui.widgets.meta_label import MetaLabel
from gui.widgets.neon_button import NeonButton
from gui.widgets.slider import Slider

#: The frozen transport-state vocabulary for this milestone.
STATES = ("stopped", "playing", "paused")


class TransportBar(ThemedWidget):
    """A themed, UI-only playback transport control row.

    Args:
        theme: Injected theme manager (sole source of visual values).
        parent: Optional Qt parent.

    Signals:
        play_requested(): Emitted when Play is activated.
        pause_requested(): Emitted when Pause is activated.
        stop_requested(): Emitted when Stop is activated.
        seek_requested(float): Emitted with the new normalized position when
            the seek slider changes (continuous; from Slider.value_changed).
        state_changed(str): Emitted with the new state on a transition.

    Raises:
        ValueError: If an invalid state is passed to :meth:`set_state`.
    """

    play_requested = Signal()
    pause_requested = Signal()
    stop_requested = Signal()
    seek_requested = Signal(float)
    state_changed = Signal(str)

    def __init__(
        self,
        theme: ThemeManager,
        *,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(theme, parent)
        self.setObjectName("TransportBar")

        self._state = "stopped"
        self._position = 0.0

        tokens = self.tokens
        c = tokens.colors

        # Root: a control zone stacked over a full-width seek scrubber.
        outer = QVBoxLayout(self)
        outer.setContentsMargins(
            tokens.spacing.md, tokens.spacing.sm, tokens.spacing.md, tokens.spacing.sm
        )
        outer.setSpacing(tokens.spacing.sm)

        # --- Control zone: timecode + tools | centered controls | chips --- #
        control_zone = QHBoxLayout()
        control_zone.setContentsMargins(0, 0, 0, 0)
        control_zone.setSpacing(tokens.spacing.md)

        # Left: monospace timecode dropdown pill, per the reference.
        timecode_wrap = QWidget(self)
        timecode_wrap.setObjectName("TransportTimecodePill")
        tc_row = QHBoxLayout(timecode_wrap)
        tc_row.setContentsMargins(
            tokens.spacing.sm, tokens.spacing.xxs,
            tokens.spacing.sm, tokens.spacing.xxs,
        )
        tc_row.setSpacing(tokens.spacing.xs)
        self._timecode = MetaLabel(
            self._theme, "00:00:47:15", role="secondary", style="mono"
        )
        self._timecode.setObjectName("TransportTimecode")
        tc_row.addWidget(self._timecode, 0, Qt.AlignmentFlag.AlignVCenter)
        tc_chevron = QLabel(timecode_wrap)
        tc_chevron.setObjectName("TransportTimecodeChevron")
        chev = 12
        try:
            tc_chevron.setPixmap(
                self._theme.icons.icon("chevron-down", c.text_muted, chev)
                .pixmap(chev, chev)
            )
        except Exception:  # pragma: no cover - icon optional
            tc_chevron.setText("⌄")
        tc_chevron.setStyleSheet(
            "#TransportTimecodeChevron { background: transparent; }"
        )
        tc_row.addWidget(tc_chevron, 0, Qt.AlignmentFlag.AlignVCenter)
        self._timecode_pill = timecode_wrap
        control_zone.addWidget(timecode_wrap, 0)

        # Left: decorative edit-tool icon cluster (cut / split / undo / redo).
        self._tools = QWidget(self)
        self._tools.setObjectName("TransportTools")
        tools_row = QHBoxLayout(self._tools)
        tools_row.setContentsMargins(0, 0, 0, 0)
        tools_row.setSpacing(tokens.spacing.xxs)
        tool_side = 30
        for icon_name, obj in (
            ("scissors", "TransportToolCut"),
            ("split", "TransportToolSplit"),
            ("undo-2", "TransportToolUndo"),
            ("redo-2", "TransportToolRedo"),
        ):
            tool = NeonButton(
                self._theme, "", variant="ghost", accent="cyan",
                icon_name=icon_name, icon_color=c.text_secondary,
                corner_radius=tokens.radius.sm, pad_h=0, pad_v=0,
            )
            tool.setObjectName(obj)
            tool.setFixedSize(tool_side, tool_side)
            tools_row.addWidget(tool)
        control_zone.addWidget(self._tools, 0)

        control_zone.addStretch(1)

        # Center: the playback control group. The frozen Play / Pause / Stop
        # buttons are added here exactly as before (same handlers/signals),
        # flanked by frame-step and rewind / fast-forward placeholders.
        self._controls = QWidget(self)
        self._controls.setObjectName("TransportControls")
        controls_row = QHBoxLayout(self._controls)
        controls_row.setContentsMargins(0, 0, 0, 0)
        controls_row.setSpacing(tokens.spacing.sm)

        side = 34
        self._prev_frame = NeonButton(
            self._theme, "", variant="ghost", accent="cyan",
            icon_name="skip-back", icon_color=c.text_secondary,
            corner_radius=side // 2, pad_h=0, pad_v=0,
        )
        self._prev_frame.setObjectName("TransportPrevFrame")
        self._prev_frame.setFixedSize(side, side)
        controls_row.addWidget(self._prev_frame)

        self._rewind = NeonButton(
            self._theme, "", variant="ghost", accent="cyan",
            icon_name="rewind", icon_color=c.text_secondary,
            corner_radius=side // 2, pad_h=0, pad_v=0,
        )
        self._rewind.setObjectName("TransportRewind")
        self._rewind.setFixedSize(side, side)
        controls_row.addWidget(self._rewind)

        play_side = 44
        self._play = NeonButton(
            self._theme, "", variant="primary", accent="blue",
            icon_name="play", icon_color=c.text_primary,
            corner_radius=play_side // 2, pad_h=0, pad_v=0,
        )
        self._play.setObjectName("TransportPlay")
        self._play.setFixedSize(play_side, play_side)
        self._play.clicked.connect(self._on_play)
        controls_row.addWidget(self._play)

        self._pause = NeonButton(
            self._theme, "", variant="secondary", accent="cyan",
            icon_name="pause", icon_color=c.text_primary,
            corner_radius=side // 2, pad_h=0, pad_v=0,
        )
        self._pause.setObjectName("TransportPause")
        self._pause.setFixedSize(side, side)
        self._pause.clicked.connect(self._on_pause)
        controls_row.addWidget(self._pause)

        self._stop = NeonButton(
            self._theme, "", variant="ghost", accent="cyan",
            icon_name="stop", icon_color=c.text_secondary,
            corner_radius=side // 2, pad_h=0, pad_v=0,
        )
        self._stop.setObjectName("TransportStop")
        self._stop.setFixedSize(side, side)
        self._stop.clicked.connect(self._on_stop)
        controls_row.addWidget(self._stop)

        self._fast_forward = NeonButton(
            self._theme, "", variant="ghost", accent="cyan",
            icon_name="fast-forward", icon_color=c.text_secondary,
            corner_radius=side // 2, pad_h=0, pad_v=0,
        )
        self._fast_forward.setObjectName("TransportFastForward")
        self._fast_forward.setFixedSize(side, side)
        controls_row.addWidget(self._fast_forward)

        self._next_frame = NeonButton(
            self._theme, "", variant="ghost", accent="cyan",
            icon_name="skip-forward", icon_color=c.text_secondary,
            corner_radius=side // 2, pad_h=0, pad_v=0,
        )
        self._next_frame.setObjectName("TransportNextFrame")
        self._next_frame.setFixedSize(side, side)
        controls_row.addWidget(self._next_frame)

        control_zone.addWidget(self._controls, 0)

        control_zone.addStretch(1)

        # Right: playback rate + Safe Area + format chips + fullscreen, per
        # the reference (decorative, wired to nothing).
        self._indicators = QWidget(self)
        self._indicators.setObjectName("TransportIndicators")
        indicators_row = QHBoxLayout(self._indicators)
        indicators_row.setContentsMargins(0, 0, 0, 0)
        indicators_row.setSpacing(tokens.spacing.xs)
        self._rate = MetaLabel(self._theme, "1.0x", role="muted", style="mono")
        self._rate.setObjectName("TransportRate")
        indicators_row.addWidget(self._rate, 0, Qt.AlignmentFlag.AlignVCenter)
        self._chips: list[QLabel] = []
        for chip_text, obj, active in (
            ("Safe Area", "TransportSafeArea", False),
            ("16:9", "TransportAspectChip", False),
            ("4K", "TransportResChip", True),
            ("60 FPS", "TransportFpsChip", False),
        ):
            chip = QLabel(chip_text, self._indicators)
            chip.setObjectName(obj)
            chip.setProperty("chipActive", active)
            chip.setFont(self._theme.font("caption"))
            chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._chips.append(chip)
            indicators_row.addWidget(chip, 0, Qt.AlignmentFlag.AlignVCenter)
        self._fullscreen = NeonButton(
            self._theme, "", variant="ghost", accent="cyan",
            icon_name="monitor", icon_color=c.text_secondary,
            corner_radius=tokens.radius.sm, pad_h=0, pad_v=0,
        )
        self._fullscreen.setObjectName("TransportFullscreen")
        self._fullscreen.setFixedSize(30, 30)
        indicators_row.addWidget(self._fullscreen)
        control_zone.addWidget(self._indicators, 0)

        outer.addLayout(control_zone)

        # --- Seek scrubber row: full-width normalized [0, 1] seek slider. --- #
        self._seek_row = QWidget(self)
        self._seek_row.setObjectName("TransportSeekRow")
        seek_layout = QHBoxLayout(self._seek_row)
        seek_layout.setContentsMargins(0, 0, 0, 0)
        seek_layout.setSpacing(0)
        # Seek placeholder: normalized [0, 1]; emits seek_requested on change.
        self._seek = Slider(
            self._theme, minimum=0.0, maximum=1.0, value=0.0, accent="cyan"
        )
        self._seek.setObjectName("TransportSeek")
        self._seek.value_changed.connect(self._on_seek)
        seek_layout.addWidget(self._seek, 1)
        outer.addWidget(self._seek_row)

        self.setAccessibleName("transport controls")
        self.apply_theme()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def state(self) -> str:
        """Return the current transport state (one of :data:`STATES`)."""
        return self._state

    def set_state(self, state: str) -> None:
        """Set the transport state; no-op when unchanged.

        Emits :attr:`state_changed` when the state actually changes.

        Raises:
            ValueError: If ``state`` is not in :data:`STATES`.
        """
        if state not in STATES:
            raise ValueError(
                f"Unknown transport state: {state!r}. Valid states: "
                f"{', '.join(STATES)}."
            )
        if state == self._state:
            return
        self._state = state
        self.state_changed.emit(self._state)

    def position(self) -> float:
        """Return the current normalized seek position in ``[0.0, 1.0]``."""
        return self._position

    def set_position(self, value: float) -> None:
        """Set the normalized seek position (clamped) without emitting a seek.

        Updates the slider to reflect an externally-driven position. Does not
        re-emit :attr:`seek_requested` (that is reserved for user-driven
        changes). Also triggers a subtle opacity pulse on the timecode label
        so the update is visually noticeable.
        """
        clamped = max(0.0, min(1.0, float(value)))
        self._position = clamped
        self._seek.blockSignals(True)
        self._seek.set_value(clamped)
        self._seek.blockSignals(False)
        # Micro-fade the timecode label on position change.
        self._pulse_timecode()

    # ------------------------------------------------------------------ #
    # Internal handlers (UI-only state machine)
    # ------------------------------------------------------------------ #
    def _on_play(self) -> None:
        """Handle Play: move to 'playing' and emit play_requested."""
        self.set_state("playing")
        self.play_requested.emit()

    def _on_pause(self) -> None:
        """Handle Pause: move to 'paused' and emit pause_requested."""
        self.set_state("paused")
        self.pause_requested.emit()

    def _on_stop(self) -> None:
        """Handle Stop: move to 'stopped', reset position, emit stop_requested."""
        self.set_state("stopped")
        self.set_position(0.0)
        self.stop_requested.emit()

    def _on_seek(self, value: float) -> None:
        """Handle a user seek: record the position and emit seek_requested."""
        self._position = max(0.0, min(1.0, float(value)))
        self.seek_requested.emit(self._position)

    def _pulse_timecode(self) -> None:
        """Briefly flash the timecode label for visual feedback."""
        from PySide6.QtCore import QTimer
        label = self._timecode._label if hasattr(self._timecode, '_label') else self._timecode
        c = self.tokens.colors
        label.setStyleSheet(
            f"#TransportTimecode {{ color: {c.text_primary}; "
            f"background: transparent; }}"
        )
        QTimer.singleShot(
            self._theme.duration("fast"),
            lambda: label.setStyleSheet(
                f"#TransportTimecode {{ color: {c.accent_cyan}; "
                f"background: transparent; }}"
            ),
        )

    # ------------------------------------------------------------------ #
    # Theming
    # ------------------------------------------------------------------ #
    def apply_theme(self) -> None:
        """Apply the premium transport-bar chrome to the row surface.

        Styling-only: object-name-scoped, token-derived QSS that makes the
        transport read as a docked, glassy control strip. The composed child
        widgets (the Play / Pause / Stop NeonButtons and the seek Slider)
        keep their own self-theming; no logic, signal, object name or API
        changes.
        """
        colors = self.tokens.colors
        r = self.tokens.radius
        s = self.tokens.spacing

        # Transport root + timecode pill + format chips.
        self.setStyleSheet(
            f"#TransportBar {{ background: qlineargradient("
            f"x1: 0, y1: 0, x2: 0, y2: 1, "
            f"stop: 0 {colors.surface_elevated}, "
            f"stop: 1 {colors.surface}); "
            f"border: 1px solid {colors.border}; "
            f"border-radius: {r.lg}px; }} "
            f"#TransportTools, #TransportControls, #TransportIndicators, "
            f"#TransportSeekRow {{ background: transparent; }} "
            f"#TransportTimecodePill {{ "
            f"background: {colors.surface}; "
            f"border: 1px solid {colors.border}; "
            f"border-radius: {r.sm}px; }} "
            # Format chips: quiet bordered pills; the active one (4K) is a
            # purple-tinted pill like the reference.
            f"#TransportSafeArea, #TransportAspectChip, #TransportFpsChip {{ "
            f"color: {colors.text_muted}; background: {colors.surface}; "
            f"border: 1px solid {colors.border}; "
            f"border-radius: {r.sm}px; "
            f"padding: {s.xxs}px {s.xs + 2}px; }} "
            f"#TransportResChip {{ "
            f"color: {colors.text_primary}; "
            f"background: rgba(168, 85, 247, 0.22); "
            f"border: 1px solid rgba(168, 85, 247, 0.55); "
            f"border-radius: {r.sm}px; "
            f"padding: {s.xxs}px {s.xs + 2}px; }}"
        )

        # Monospace timecode readout: accent-tinted mono chrome value.
        self._timecode.setStyleSheet(
            f"#TransportTimecode {{ color: {colors.accent_cyan}; "
            f"background: transparent; }}"
        )
