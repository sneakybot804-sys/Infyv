"""NeonButton: a neon-accented action button (composes a QPushButton).

Composition over inheritance: the widget wraps an inner :class:`QPushButton`
so styling is fully controlled while native button behaviour (keyboard
activation, click) is preserved. All visual values come from the injected
:class:`ThemeManager`.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QVariantAnimation, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget

from gui.theme.manager import ThemeManager
from gui.widgets import styling
from gui.widgets.base import ThemedWidget

_VARIANTS = ("primary", "secondary", "ghost")


class NeonButton(ThemedWidget):
    """A themed action button with smooth hover/press animations.

    Args:
        theme: Injected theme manager.
        text: Button label.
        variant: ``primary`` / ``secondary`` / ``ghost``. Default ``primary``.
        accent: Accent role ``blue`` / ``cyan`` / ``purple``. Default ``cyan``.
        icon_name: Optional leading icon name (an SVG under gui/assets/icons).
        animated: When ``True`` (default), hover and press are animated via
            a QVariantAnimation color tween. No QGraphicsEffect is used —
            safe inside GlassCard's drop-shadow tree.
        parent: Optional Qt parent.

    Signals:
        clicked: Emitted when the button is activated (mouse or keyboard).
    """

    clicked = Signal()

    def __init__(
        self,
        theme: ThemeManager,
        text: str = "",
        *,
        variant: str = "primary",
        accent: str = "cyan",
        icon_name: Optional[str] = None,
        icon_color: Optional[str] = None,
        corner_radius: Optional[int] = None,
        pad_h: Optional[int] = None,
        pad_v: Optional[int] = None,
        animated: bool = True,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(theme, parent)
        if variant not in _VARIANTS:
            raise ValueError(f"Unknown variant: {variant!r}")
        self._variant = variant
        self._accent = accent
        self._icon_name = icon_name
        self._icon_color = icon_color
        self._corner_radius = corner_radius
        self._pad_h = pad_h
        self._pad_v = pad_v
        self._animated = animated
        self._loading = False
        self._text = text

        # Hover blend factor: 0.0 = resting, 1.0 = fully hovered.
        # Driven by a persistent QVariantAnimation so rapid enter/leave
        # interrupts cleanly. No QGraphicsEffect — safe inside GlassCard.
        self._hover_factor: float = 0.0
        self._hover_anim = QVariantAnimation(self)
        self._hover_anim.setStartValue(0.0)
        self._hover_anim.setEndValue(1.0)
        self._hover_anim.valueChanged.connect(self._on_hover_step)

        # Press blend: separate short animation for tactile feedback.
        self._press_factor: float = 0.0
        self._press_anim = QVariantAnimation(self)
        self._press_anim.valueChanged.connect(self._on_press_step)

        self._button = QPushButton(text, self)
        self._button.setObjectName("NeonButton")
        self._button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._button.clicked.connect(self.clicked.emit)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._button)

        self.setAccessibleName(text or "button")
        self.apply_theme()

    # ------------------------------------------------------------------ #
    # Hover / press animation (QVariantAnimation color tween; no effects)
    # ------------------------------------------------------------------ #
    def enterEvent(self, event) -> None:  # noqa: N802
        """Fade hover highlight in on mouse enter."""
        self._animate_hover(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        """Fade hover highlight out on mouse leave."""
        self._animate_hover(0.0)
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        """Briefly deepen the button on press for tactile feedback."""
        if event.button() == Qt.MouseButton.LeftButton and self._animated:
            self._press_anim.stop()
            self._press_anim.setDuration(self._theme.duration("fast") // 3)
            self._press_anim.setEasingCurve(self._theme.easing("in_cubic"))
            self._press_anim.setStartValue(float(self._press_factor))
            self._press_anim.setEndValue(1.0)
            self._press_anim.start()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        """Release the press deepening on mouse up."""
        if event.button() == Qt.MouseButton.LeftButton and self._animated:
            self._press_anim.stop()
            self._press_anim.setDuration(self._theme.duration("fast") // 2)
            self._press_anim.setEasingCurve(self._theme.easing("out_cubic"))
            self._press_anim.setStartValue(float(self._press_factor))
            self._press_anim.setEndValue(0.0)
            self._press_anim.start()
        super().mouseReleaseEvent(event)

    def _animate_hover(self, target: float) -> None:
        """Drive hover_factor toward ``target``, interrupting any in-flight run."""
        if not self._animated:
            self._hover_factor = target
            self._apply_hover_style()
            return
        self._hover_anim.stop()
        self._hover_anim.setDuration(self._theme.duration("fast"))
        easing = (
            self._theme.easing("out_cubic")
            if target > 0.5
            else self._theme.easing("in_cubic")
        )
        self._hover_anim.setEasingCurve(easing)
        self._hover_anim.setStartValue(float(self._hover_factor))
        self._hover_anim.setEndValue(float(target))
        self._hover_anim.start()

    def _on_hover_step(self, value: object) -> None:
        self._hover_factor = float(value)
        self._apply_hover_style()

    def _on_press_step(self, value: object) -> None:
        self._press_factor = float(value)
        self._apply_hover_style()

    def _apply_hover_style(self) -> None:
        """Blend the button background between resting and hovered states."""
        tokens = self.tokens
        c = tokens.colors
        radius = (
            self._corner_radius
            if self._corner_radius is not None
            else self.scaled(tokens.radius.md)
        )
        pad_v = (
            self._pad_v
            if self._pad_v is not None
            else self.scaled(tokens.spacing.sm)
        )
        pad_h = (
            self._pad_h
            if self._pad_h is not None
            else self.scaled(tokens.spacing.lg)
        )

        hf = max(0.0, min(1.0, self._hover_factor))
        pf = max(0.0, min(1.0, self._press_factor))

        # Press darkens further on top of hover.
        effective = max(hf, pf * 0.6)

        base_qss = styling.neon_button_qss(
            c,
            radius=radius,
            pad_v=pad_v,
            pad_h=pad_h,
            accent=self._accent,
            variant=self._variant,
            selector="#NeonButton",
        )

        if effective < 0.01:
            self._button.setStyleSheet(base_qss)
            return

        # Build a blended overlay tint on top of the base QSS. We derive the
        # hover overlay color from the accent — a semi-transparent tint whose
        # alpha scales with the blend factor. This avoids any QGraphicsEffect.
        accent_hex = styling.accent_color(c, self._accent).lstrip("#")
        try:
            ar = int(accent_hex[0:2], 16)
            ag = int(accent_hex[2:4], 16)
            ab = int(accent_hex[4:6], 16)
        except (ValueError, IndexError):
            ar, ag, ab = 168, 85, 247  # fallback purple

        overlay_alpha = int(effective * (40 + pf * 20))
        border_alpha = int(effective * 160)

        if self._variant == "ghost":
            bg = f"rgba({ar},{ag},{ab},{overlay_alpha})"
            border = f"rgba({ar},{ag},{ab},{border_alpha})"
            overlay = (
                f"#NeonButton {{ background: {bg}; "
                f"border: 1px solid {border}; "
                f"border-radius: {radius}px; "
                f"padding: {pad_v}px {pad_h}px; }}"
            )
        elif self._variant == "secondary":
            bg = f"rgba({ar},{ag},{ab},{overlay_alpha})"
            border = f"rgba({ar},{ag},{ab},{border_alpha})"
            overlay = (
                f"#NeonButton {{ background: {bg}; "
                f"border: 1px solid {border}; "
                f"border-radius: {radius}px; "
                f"padding: {pad_v}px {pad_h}px; }}"
            )
        else:  # primary — lighten the gradient
            light_alpha = int(effective * 30)
            overlay = (
                f"#NeonButton {{ "
                f"background: qlineargradient(x1:0,y1:0,x2:1,y2:1,"
                f"stop:0 rgba({ar},{ag},{ab},{180 + light_alpha}),"
                f"stop:1 rgba({ar},{ag},{ab},{200 + light_alpha})); "
                f"border: 1px solid rgba({ar},{ag},{ab},{200 + border_alpha // 2}); "
                f"border-radius: {radius}px; "
                f"padding: {pad_v}px {pad_h}px; }}"
            )

        self._button.setStyleSheet(overlay)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def set_text(self, text: str) -> None:
        """Set the button label."""
        self._text = text
        self._button.setText(text)
        self.setAccessibleName(text or "button")

    def text(self) -> str:
        """Return the button label."""
        return self._text

    def set_icon(self, name: Optional[str]) -> None:
        """Set (or clear with ``None``) the leading icon."""
        self._icon_name = name
        self.apply_theme()

    def set_variant(self, variant: str) -> None:
        """Set the visual variant (``primary``/``secondary``/``ghost``).

        No-op (no restyle) when the variant is unchanged.
        """
        if variant not in _VARIANTS:
            raise ValueError(f"Unknown variant: {variant!r}")
        if variant == self._variant:
            return
        self._variant = variant
        self.apply_theme()

    def set_accent(self, accent: str) -> None:
        """Set the accent role (``blue``/``cyan``/``purple``).

        No-op (no restyle) when the accent is unchanged.
        """
        if accent == self._accent:
            return
        self._accent = accent
        self.apply_theme()

    def set_loading(self, loading: bool) -> None:
        """Set a lightweight loading state (disables + marks busy)."""
        self._loading = loading
        self._button.setEnabled(not loading)
        self._button.setText("…" if loading else self._text)
        self.setAccessibleDescription("busy" if loading else "")

    @property
    def variant(self) -> str:
        """Return the current variant."""
        return self._variant

    @property
    def accent(self) -> str:
        """Return the current accent role."""
        return self._accent

    @property
    def loading(self) -> bool:
        """Return whether the button is in the loading state."""
        return self._loading

    # ------------------------------------------------------------------ #
    # Theming
    # ------------------------------------------------------------------ #
    def apply_theme(self) -> None:
        """Rebuild the button styling, icon and font from the theme."""
        tokens = self.tokens
        radius = (
            self._corner_radius
            if self._corner_radius is not None
            else self.scaled(tokens.radius.md)
        )
        self._button.setStyleSheet(
            styling.neon_button_qss(
                tokens.colors,
                radius=radius,
                pad_v=(
                    self._pad_v
                    if self._pad_v is not None
                    else self.scaled(tokens.spacing.sm)
                ),
                pad_h=(
                    self._pad_h
                    if self._pad_h is not None
                    else self.scaled(tokens.spacing.lg)
                ),
                accent=self._accent,
                variant=self._variant,
                selector="#NeonButton",
            )
        )
        self._button.setFont(self._theme.font("body"))
        if self._icon_name is not None:
            size = self.scaled(tokens.spacing.lg)
            color = self._icon_color or self._theme_accent_token()
            self._button.setIcon(self.icon(self._icon_name, color, size))

    def _theme_accent_token(self) -> str:
        """Return the accent color string for the current accent role."""
        return styling.accent_color(self.tokens.colors, self._accent)
