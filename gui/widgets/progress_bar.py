"""ProgressBar: a determinate/indeterminate linear progress indicator.

Composition over inheritance: wraps an inner :class:`QProgressBar` so native
progress behaviour (including Qt's built-in indeterminate 'busy' animation) is
preserved while all visuals come from the injected :class:`ThemeManager`. It
is painted/styled entirely through QSS and installs **no**
:class:`QGraphicsEffect`, avoiding the nested-effect rendering hazard. Motion
is reduce-motion aware via the ``animated`` flag.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import QProgressBar, QVBoxLayout, QWidget

from gui.theme.manager import ThemeManager
from gui.widgets import styling
from gui.widgets.base import ThemedWidget

#: The frozen accent vocabulary (Phase 8C-3).
ACCENTS = ("blue", "cyan", "purple")

_RESOLUTION = 1000  # inner integer range for a 0..1 float value


class ProgressBar(ThemedWidget):
    """A themed linear progress bar.

    Args:
        theme: Injected theme manager (sole source of visual values).
        value: Initial progress in ``0.0..1.0`` (clamped). Default ``0.0``.
        indeterminate: Start in the indeterminate 'busy' state. Default False.
        accent: Accent role, one of :data:`ACCENTS`. Default ``cyan``.
        animated: When ``False``, the indeterminate busy animation is not run
            (reduce-motion path); determinate progress still updates.
        parent: Optional Qt parent.

    Raises:
        ValueError: If ``accent`` is not in :data:`ACCENTS`.
    """

    def __init__(
        self,
        theme: ThemeManager,
        *,
        value: float = 0.0,
        indeterminate: bool = False,
        accent: str = "cyan",
        animated: bool = True,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(theme, parent)
        self._accent = self._validate_accent(accent)
        self._animated = animated
        self._value = self._clamp(value)
        self._indeterminate = indeterminate

        self._bar = QProgressBar(self)
        self._bar.setObjectName("ProgressBar")
        self._bar.setTextVisible(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._bar)

        self._apply_mode()
        self.apply_theme()

    # ------------------------------------------------------------------ #
    # Validation / helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _validate_accent(accent: str) -> str:
        """Return ``accent`` if valid, else raise :class:`ValueError`."""
        if accent not in ACCENTS:
            raise ValueError(
                f"Unknown accent: {accent!r}. Valid accents: "
                f"{', '.join(ACCENTS)}."
            )
        return accent

    @staticmethod
    def _clamp(value: float) -> float:
        """Clamp ``value`` into the inclusive ``0.0..1.0`` range."""
        return max(0.0, min(1.0, float(value)))

    def _apply_mode(self) -> None:
        """Configure the inner bar for the current (in)determinate state.

        Indeterminate is expressed as a zero-length range (Qt's busy mode).
        When motion is disabled, the busy animation is suppressed by pinning a
        static full range so no sweeping occurs.
        """
        if self._indeterminate and self._animated:
            self._bar.setRange(0, 0)  # Qt busy/indeterminate animation
        elif self._indeterminate and not self._animated:
            # Reduce-motion: show a static (non-sweeping) filled track.
            self._bar.setRange(0, _RESOLUTION)
            self._bar.setValue(_RESOLUTION)
        else:
            self._bar.setRange(0, _RESOLUTION)
            self._bar.setValue(int(round(self._value * _RESOLUTION)))
        self._update_accessible_name()

    def _update_accessible_name(self) -> None:
        """Set an accessible name reflecting percent or the busy state."""
        if self._indeterminate:
            self.setAccessibleName("busy")
        else:
            self.setAccessibleName(f"{int(round(self._value * 100))}%")

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def set_value(self, value: float) -> None:
        """Set determinate progress in ``0.0..1.0`` (clamped).

        Has no visible effect while indeterminate, but the value is retained
        and applied when :meth:`set_indeterminate` turns the busy state off.
        """
        self._value = self._clamp(value)
        if not self._indeterminate:
            self._bar.setValue(int(round(self._value * _RESOLUTION)))
            self._update_accessible_name()

    def value(self) -> float:
        """Return the current determinate progress (``0.0..1.0``)."""
        return self._value

    def set_indeterminate(self, indeterminate: bool) -> None:
        """Toggle the indeterminate 'busy' state; no-op when unchanged."""
        if bool(indeterminate) == self._indeterminate:
            return
        self._indeterminate = bool(indeterminate)
        self._apply_mode()

    def is_indeterminate(self) -> bool:
        """Return whether the bar is in the indeterminate state."""
        return self._indeterminate

    def set_accent(self, accent: str) -> None:
        """Set the accent role; no-op (no restyle) when unchanged.

        Raises:
            ValueError: If ``accent`` is not in :data:`ACCENTS`.
        """
        accent = self._validate_accent(accent)
        if accent == self._accent:
            return
        self._accent = accent
        self.apply_theme()

    def accent(self) -> str:
        """Return the current accent role."""
        return self._accent

    # ------------------------------------------------------------------ #
    # Theming
    # ------------------------------------------------------------------ #
    def apply_theme(self) -> None:
        """Rebuild the track and chunk styling from the theme."""
        tokens = self.tokens
        radius = self.scaled(tokens.radius.sm)
        height = self.scaled(tokens.spacing.sm)
        track = styling.progress_track_qss(
            tokens.colors, radius=radius, height=height, selector="#ProgressBar"
        )
        chunk = styling.progress_chunk_qss(
            tokens.colors,
            accent=self._accent,
            radius=radius,
            selector="#ProgressBar::chunk",
        )
        self._bar.setStyleSheet(f"{track}\n{chunk}")
