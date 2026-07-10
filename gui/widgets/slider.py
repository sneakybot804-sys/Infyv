"""Slider: a themed continuous numeric range control (composes a QSlider).

Composition over inheritance: an inner horizontal :class:`QSlider` provides
native dragging and keyboard stepping. The public API is float-based; the
inner integer slider uses a fixed resolution to map a ``[minimum, maximum]``
float range. All visuals come from the injected :class:`ThemeManager` via QSS.
No animation and no :class:`QGraphicsEffect` are used (frozen policy).
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QSlider, QVBoxLayout, QWidget

from gui.theme.manager import ThemeManager
from gui.widgets import styling
from gui.widgets.base import ThemedWidget

#: The frozen accent vocabulary (Phase 8C-5).
ACCENTS = ("blue", "cyan", "purple")

_RESOLUTION = 1000  # inner integer ticks spanning [minimum, maximum]


class Slider(ThemedWidget):
    """A themed continuous slider over a float range.

    Args:
        theme: Injected theme manager (sole source of visual values).
        minimum: Range lower bound. Must be strictly less than ``maximum``.
        maximum: Range upper bound.
        value: Initial value (clamped into the range). Default ``0.0``.
        accent: Accent role, one of :data:`ACCENTS`. Default ``cyan``.
        parent: Optional Qt parent.

    Signals:
        value_changed(float): Emitted with the new value when it changes.

    Raises:
        ValueError: If ``accent`` is invalid or ``minimum >= maximum``.
    """

    value_changed = Signal(float)

    def __init__(
        self,
        theme: ThemeManager,
        *,
        minimum: float = 0.0,
        maximum: float = 1.0,
        value: float = 0.0,
        accent: str = "cyan",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(theme, parent)
        self._accent = self._validate_accent(accent)
        self._min, self._max = self._validate_range(minimum, maximum)
        self._explicit_name = ""
        self._value = self._clamp(value)

        self._slider = QSlider(Qt.Orientation.Horizontal, self)
        self._slider.setObjectName("Slider")
        self._slider.setRange(0, _RESOLUTION)
        self._slider.setValue(self._to_ticks(self._value))
        self._slider.valueChanged.connect(self._on_ticks_changed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._slider)

        self._sync_accessible_name()
        self.apply_theme()

    # ------------------------------------------------------------------ #
    # Validation / mapping helpers
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
    def _validate_range(minimum: float, maximum: float) -> tuple[float, float]:
        """Return the validated range, else raise :class:`ValueError`."""
        if not float(minimum) < float(maximum):
            raise ValueError(
                f"minimum ({minimum}) must be strictly less than maximum "
                f"({maximum})."
            )
        return float(minimum), float(maximum)

    def _clamp(self, value: float) -> float:
        """Clamp ``value`` into ``[minimum, maximum]``."""
        return max(self._min, min(self._max, float(value)))

    def _to_ticks(self, value: float) -> int:
        """Map a float value to an inner integer tick."""
        frac = (value - self._min) / (self._max - self._min)
        return int(round(frac * _RESOLUTION))

    def _from_ticks(self, ticks: int) -> float:
        """Map an inner integer tick back to a float value."""
        frac = ticks / _RESOLUTION
        return self._min + frac * (self._max - self._min)

    # ------------------------------------------------------------------ #
    # Accessibility
    # ------------------------------------------------------------------ #
    def setAccessibleName(self, name: str) -> None:  # noqa: N802 (Qt override)
        """Record an explicit accessible name; it takes precedence."""
        self._explicit_name = name or ""
        super().setAccessibleName(name)

    def _sync_accessible_name(self) -> None:
        """Apply 'Slider <value>' when no explicit name is set."""
        if self._explicit_name:
            return
        super().setAccessibleName(f"Slider {self._value_label()}")

    def _value_label(self) -> str:
        """Return a compact string for the current value (int when whole)."""
        v = self._value
        return str(int(v)) if float(v).is_integer() else str(v)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def set_value(self, value: float) -> None:
        """Set the value (clamped to the range); no-op when unchanged."""
        clamped = self._clamp(value)
        if clamped == self._value:
            return
        self._value = clamped
        self._slider.blockSignals(True)
        self._slider.setValue(self._to_ticks(clamped))
        self._slider.blockSignals(False)
        self._sync_accessible_name()
        self.value_changed.emit(self._value)

    def value(self) -> float:
        """Return the current value."""
        return self._value

    def set_range(self, minimum: float, maximum: float) -> None:
        """Set the value range; re-clamps the current value.

        Raises:
            ValueError: If ``minimum >= maximum``.
        """
        self._min, self._max = self._validate_range(minimum, maximum)
        self._value = self._clamp(self._value)
        self._slider.blockSignals(True)
        self._slider.setValue(self._to_ticks(self._value))
        self._slider.blockSignals(False)
        self._sync_accessible_name()

    def minimum(self) -> float:
        """Return the range lower bound."""
        return self._min

    def maximum(self) -> float:
        """Return the range upper bound."""
        return self._max

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

    @property
    def accent(self) -> str:
        """Return the current accent role."""
        return self._accent

    # ------------------------------------------------------------------ #
    # Internal behaviour
    # ------------------------------------------------------------------ #
    def _on_ticks_changed(self, ticks: int) -> None:
        """Handle native slider movement: map to float, notify."""
        self._value = self._clamp(self._from_ticks(ticks))
        self._sync_accessible_name()
        self.value_changed.emit(self._value)

    # ------------------------------------------------------------------ #
    # Theming
    # ------------------------------------------------------------------ #
    def apply_theme(self) -> None:
        """Rebuild the slider styling from the theme."""
        tokens = self.tokens
        self._slider.setStyleSheet(
            styling.slider_qss(
                tokens.colors,
                accent=self._accent,
                groove=self.scaled(tokens.spacing.xs),
                handle=self.scaled(tokens.spacing.md),
                radius=self.scaled(tokens.radius.sm),
                selector="#Slider",
            )
        )
