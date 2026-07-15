"""TransportBar: UI-only playback transport controls (Phase 8H, Milestone 2).

A themed transport row composed from the frozen widget library: Play / Pause /
Stop as text :class:`NeonButton`s (no new icon assets in this milestone) and a
seek placeholder built on the library :class:`Slider`.

This is a pure UI state machine. It tracks a transport ``state`` -- one of
``"stopped"`` / ``"playing"`` / ``"paused"`` -- and a normalized ``position``
in ``[0.0, 1.0]``. It performs no real playback, opens no media, and never
touches :mod:`gui_core`. All behaviour is signals + internal state so a future
milestone can bind it to an actual player.

Stable object names for later integration and tests:

* ``TransportBar`` -- the root widget
* ``TransportPlay`` / ``TransportPause`` / ``TransportStop`` -- the buttons
* ``TransportSeek`` -- the seek slider
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QWidget

from gui.theme.manager import ThemeManager
from gui.widgets.base import ThemedWidget
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

        row = QHBoxLayout(self)
        # Inset padding so the controls sit inside a padded transport bar
        # rather than flush against the edges (layout values only).
        row.setContentsMargins(
            tokens.spacing.md, tokens.spacing.sm, tokens.spacing.md, tokens.spacing.sm
        )
        row.setSpacing(tokens.spacing.sm)

        self._play = NeonButton(self._theme, "Play", variant="primary", accent="cyan")
        self._play.setObjectName("TransportPlay")
        self._play.clicked.connect(self._on_play)
        row.addWidget(self._play)

        self._pause = NeonButton(self._theme, "Pause", variant="secondary", accent="cyan")
        self._pause.setObjectName("TransportPause")
        self._pause.clicked.connect(self._on_pause)
        row.addWidget(self._pause)

        self._stop = NeonButton(self._theme, "Stop", variant="ghost", accent="cyan")
        self._stop.setObjectName("TransportStop")
        self._stop.clicked.connect(self._on_stop)
        row.addWidget(self._stop)

        # Seek placeholder: normalized [0, 1]; emits seek_requested on change.
        self._seek = Slider(
            self._theme, minimum=0.0, maximum=1.0, value=0.0, accent="cyan"
        )
        self._seek.setObjectName("TransportSeek")
        self._seek.value_changed.connect(self._on_seek)
        row.addWidget(self._seek, 1)

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
        changes).
        """
        clamped = max(0.0, min(1.0, float(value)))
        self._position = clamped
        self._seek.blockSignals(True)
        self._seek.set_value(clamped)
        self._seek.blockSignals(False)

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

    # ------------------------------------------------------------------ #
    # Theming
    # ------------------------------------------------------------------ #
    def apply_theme(self) -> None:
        """Apply the premium transport-bar chrome to the row surface.

        Styling-only (Phase 10B): object-name-scoped, token-derived QSS that
        makes the transport read as a docked, glassy control strip (an
        elevated surface with a subtle vertical gradient, a soft glass border
        and rounded corners). The composed child widgets (the Play / Pause /
        Stop NeonButtons and the seek Slider) keep their own self-theming; no
        logic, signal, object name or API changes.
        """
        colors = self.tokens.colors
        radius_lg = self.tokens.radius.lg

        # Transport root: a layered elevated surface with a subtle vertical
        # gradient, a soft glass border and rounded corners, so the transport
        # reads as a first-class docked control strip.
        self.setStyleSheet(
            f"#TransportBar {{ background: qlineargradient("
            f"x1: 0, y1: 0, x2: 0, y2: 1, "
            f"stop: 0 {colors.surface_elevated}, "
            f"stop: 1 {colors.surface}); "
            f"border: 1px solid {colors.border}; "
            f"border-radius: {radius_lg}px; }}"
        )
