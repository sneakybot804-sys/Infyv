"""ToggleSwitch: a generic on/off switch (composes an inner QCheckBox).

Composition over inheritance: an inner :class:`QCheckBox` provides native
keyboard toggling (Space) and checked-state semantics, while the visible track
and knob are drawn as plain child :class:`QFrame` widgets styled through QSS.
The knob position is animated with a :class:`QVariantAnimation` driving a plain
float (no graphics effect), honoring the frozen no-``QGraphicsEffect`` policy
so the widget is safe inside an effect-bearing container such as ``GlassCard``.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QRect, Qt, QVariantAnimation, Signal
from PySide6.QtWidgets import QCheckBox, QFrame, QVBoxLayout, QWidget

from gui.theme.manager import ThemeManager
from gui.widgets import styling
from gui.widgets.base import ThemedWidget

#: The frozen accent vocabulary (Phase 8C-4).
ACCENTS = ("blue", "cyan", "purple")


class ToggleSwitch(ThemedWidget):
    """A themed on/off toggle switch.

    Args:
        theme: Injected theme manager (sole source of visual values).
        checked: Initial state. Default ``False``.
        accent: Accent role, one of :data:`ACCENTS`. Default ``cyan``.
        animated: When ``False``, the knob jumps to its end position with no
            running animation (reduce-motion path). Default ``True``.
        parent: Optional Qt parent.

    Signals:
        toggled(bool): Emitted when the checked state changes.

    Raises:
        ValueError: If ``accent`` is not in :data:`ACCENTS`.
    """

    toggled = Signal(bool)

    def __init__(
        self,
        theme: ThemeManager,
        *,
        checked: bool = False,
        accent: str = "cyan",
        animated: bool = True,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(theme, parent)
        self._accent = self._validate_accent(accent)
        self._animated = animated
        self._explicit_name = ""
        self._knob_pos = 0.0  # 0.0 (off) .. 1.0 (on)

        # Inner native checkbox: hidden visuals, native keyboard/state.
        self._checkbox = QCheckBox(self)
        self._checkbox.setObjectName("ToggleSwitchInput")
        self._checkbox.setChecked(checked)
        self._checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        self._checkbox.setText("")
        self._checkbox.toggled.connect(self._on_toggled)

        # Track + knob frames, drawn via QSS (no graphics effect).
        self._track = QFrame(self._checkbox)
        self._track.setObjectName("ToggleTrack")
        self._track.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._knob = QFrame(self._track)
        self._knob.setObjectName("ToggleKnob")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._checkbox)

        # Reused position animation (created once; re-targeted on change).
        self._knob_anim = QVariantAnimation(self)
        self._knob_anim.valueChanged.connect(self._on_knob_step)

        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self._knob_pos = 1.0 if checked else 0.0
        self._sync_accessible_name()
        self.apply_theme()

    # ------------------------------------------------------------------ #
    # Validation
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

    # ------------------------------------------------------------------ #
    # Accessibility
    # ------------------------------------------------------------------ #
    def setAccessibleName(self, name: str) -> None:  # noqa: N802 (Qt override)
        """Record an explicit accessible name; it takes precedence over On/Off."""
        self._explicit_name = name or ""
        super().setAccessibleName(name)

    def _sync_accessible_name(self) -> None:
        """Apply the automatic 'On'/'Off' name when none was set explicitly."""
        if self._explicit_name:
            return
        super().setAccessibleName("On" if self._checkbox.isChecked() else "Off")

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def set_checked(self, checked: bool) -> None:
        """Set the checked state; no-op when unchanged."""
        if bool(checked) == self._checkbox.isChecked():
            return
        self._checkbox.setChecked(bool(checked))  # emits _on_toggled

    def is_checked(self) -> bool:
        """Return whether the switch is on."""
        return self._checkbox.isChecked()

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

    @property
    def checked(self) -> bool:
        """Return the current checked state."""
        return self._checkbox.isChecked()

    # ------------------------------------------------------------------ #
    # Internal behaviour
    # ------------------------------------------------------------------ #
    def _on_toggled(self, checked: bool) -> None:
        """Handle the inner checkbox toggling: animate, restyle, notify."""
        self._sync_accessible_name()
        self._animate_knob(1.0 if checked else 0.0)
        self.apply_theme()
        self.toggled.emit(checked)

    def _animate_knob(self, target: float) -> None:
        """Move the knob to ``target`` (0..1) via the reused animation."""
        self._knob_anim.stop()
        if not self._animated:
            self._knob_pos = target
            self._layout_knob()
            return
        self._knob_anim.setDuration(self._theme.duration("fast"))
        self._knob_anim.setStartValue(float(self._knob_pos))
        self._knob_anim.setEndValue(float(target))
        self._knob_anim.setEasingCurve(self._theme.easing())
        self._knob_anim.start()

    def _on_knob_step(self, value: object) -> None:
        """Apply an animated knob position step."""
        self._knob_pos = float(value)
        self._layout_knob()

    def _track_metrics(self) -> tuple[int, int, int]:
        """Return (track_width, track_height, knob_size) in device pixels."""
        height = self.scaled(self.tokens.spacing.lg)
        width = self.scaled(self.tokens.spacing.xl + self.tokens.spacing.md)
        knob = max(1, height - self.scaled(self.tokens.spacing.xxs) * 2)
        return width, height, knob

    def _layout_knob(self) -> None:
        """Position the track (centered) and the knob (by knob position)."""
        width, height, knob = self._track_metrics()
        self._checkbox.setFixedSize(width, height)
        self._track.setGeometry(0, 0, width, height)
        margin = self.scaled(self.tokens.spacing.xxs)
        travel = width - knob - margin * 2
        x = int(round(margin + travel * self._knob_pos))
        self._knob.setGeometry(QRect(x, margin, knob, knob))

    # ------------------------------------------------------------------ #
    # Theming
    # ------------------------------------------------------------------ #
    def apply_theme(self) -> None:
        """Rebuild the track/knob styling and re-layout from the theme."""
        _, height, knob = self._track_metrics()
        qss = styling.toggle_switch_qss(
            self.tokens.colors,
            accent=self._accent,
            checked=self._checkbox.isChecked(),
            track_radius=height // 2,
            knob_radius=knob // 2,
            selector="#ToggleTrack",
            knob_selector="#ToggleKnob",
        )
        focus = styling.toggle_focus_qss(self.tokens.colors, selector="#ToggleTrack")
        self._track.setStyleSheet(f"{qss}\n{focus}")
        self._layout_knob()
