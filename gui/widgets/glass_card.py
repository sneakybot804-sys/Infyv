"""GlassCard: a rounded, translucent container with optional glow/shadow.

A pure presentation container: it holds injected content and applies glass
styling plus an optional elevation shadow or neon glow, all resolved through
the injected :class:`ThemeManager`. It is not interactive and stores no
business state.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QPropertyAnimation, QVariantAnimation
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QFrame, QGraphicsDropShadowEffect, QVBoxLayout, QWidget

from gui.theme.manager import ThemeManager
from gui.widgets import styling
from gui.widgets.animation import fade
from gui.widgets.base import ThemedWidget

_SHADOW_BY_LEVEL = {
    "low": "low",
    "medium": "medium",
    "high": "high",
}


class GlassCard(ThemedWidget):
    """A translucent, rounded card container.

    Args:
        theme: The injected theme manager (sole source of visual values).
        radius: Radius token key (``sm``/``md``/``lg``/``xl``). Default ``lg``.
        glow: Accent role (``blue``/``cyan``/``purple``) for an outer glow, or
            ``None`` for a plain elevation shadow.
        elevation: Shadow token level (``low``/``medium``/``high``) used when
            ``glow`` is ``None``. Default ``medium``.
        animated: When ``True`` (default) the card fades in on first show.
        parent: Optional Qt parent.
    """

    def __init__(
        self,
        theme: ThemeManager,
        *,
        radius: str = "lg",
        glow: Optional[str] = None,
        elevation: str = "medium",
        animated: bool = True,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(theme, parent)
        self._radius_key = radius
        self._glow_role = glow
        self._elevation_level = elevation
        self._animated = animated
        self._content: Optional[QWidget] = None
        self._did_fade_in = False

        self._frame = QFrame(self)
        self._frame.setObjectName("GlassCard")
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(0, 0, 0, 0)
        self._outer.addWidget(self._frame)
        self._inner = QVBoxLayout(self._frame)

        # One persistent shadow/glow effect for the card's lifetime; its
        # intensity is animated between the resting shadow and the neon glow.
        self._effect = QGraphicsDropShadowEffect(self._frame)
        self._frame.setGraphicsEffect(self._effect)
        self._glow_active = False

        # Persistent, reused animations (created once; never recreated during
        # hover). Rapid state changes stop() and re-target these objects.
        self._blur_anim = QPropertyAnimation(self._effect, b"blurRadius", self)
        self._alpha_anim = QVariantAnimation(self)
        self._alpha_anim.valueChanged.connect(self._on_alpha_step)
        self._alpha_base_color = QColor(0, 0, 0, 0)

        self.setAccessibleName("card")
        self.apply_theme()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def set_content(self, widget: QWidget) -> None:
        """Replace the card's content with ``widget``."""
        if self._content is not None:
            self._inner.removeWidget(self._content)
            self._content.setParent(None)
        self._content = widget
        self._inner.addWidget(widget)

    def content(self) -> Optional[QWidget]:
        """Return the current content widget, or ``None``."""
        return self._content

    def set_glow(self, role: Optional[str]) -> None:
        """Set the glow accent role (or ``None`` for a plain shadow)."""
        self._glow_role = role
        self.apply_theme()

    def set_elevation(self, level: str) -> None:
        """Set the elevation shadow level (used when no glow is set)."""
        self._elevation_level = level
        self.apply_theme()

    @property
    def glow_role(self) -> Optional[str]:
        """Return the current glow accent role, or ``None``."""
        return self._glow_role

    @property
    def elevation_level(self) -> str:
        """Return the current elevation shadow level."""
        return self._elevation_level

    # ------------------------------------------------------------------ #
    # Theming
    # ------------------------------------------------------------------ #
    def apply_theme(self) -> None:
        """Rebuild the glass styling and set the effect to its current state.

        The single persistent shadow effect is set to either the resting
        elevation shadow or the neon glow depending on the current hover
        state, without animation (this is a restyle, not a transition).
        """
        tokens = self.tokens
        radius = self.scaled(getattr(tokens.radius, self._radius_key))
        self._frame.setStyleSheet(
            styling.glass_card_qss(
                tokens.colors, radius=radius, selector="#GlassCard"
            )
        )
        # Fixed offset from the resting shadow; glow uses zero offset but the
        # small elevation offset reads fine and avoids a second animation.
        shadow = self._resting_shadow()
        self._effect.setOffset(self.scaled(shadow.x), self.scaled(shadow.y))
        if self._glow_active and self._glow_role is not None:
            self._effect.setBlurRadius(self.scaled(self._glow_shadow().blur))
            self._effect.setColor(self._theme.color(f"{self._glow_role}_glow"))
        else:
            self._effect.setBlurRadius(self.scaled(shadow.blur))
            self._effect.setColor(self._theme.color(shadow.color))

    def glow_active(self) -> bool:
        """Return whether the hover/active glow is currently shown."""
        return self._glow_active

    def _resting_shadow(self):
        """Return the elevation shadow token for the current level."""
        return getattr(self.tokens.shadows, _SHADOW_BY_LEVEL[self._elevation_level])

    def _glow_shadow(self):
        """Return the glow shadow token for the current glow role."""
        return getattr(self.tokens.shadows, f"glow_{self._glow_role}")

    def _on_alpha_step(self, value: object) -> None:
        """Apply an animated alpha step to the persistent effect color."""
        c = QColor(self._alpha_base_color)
        c.setAlpha(int(round(float(value))))
        self._effect.setColor(c)

    def _transition_glow(self, to_glow: bool) -> None:
        """Smoothly fade the single effect between resting shadow and glow.

        Reuses the persistent blur and alpha animations: any in-flight run is
        stopped and the same objects are re-targeted, so rapid hover changes
        interrupt cleanly without allocating new effects or animations. When
        animations are disabled the end state is applied instantly.
        """
        self._glow_active = to_glow
        if self._glow_role is None:
            return

        resting = self._resting_shadow()
        glow = self._glow_shadow()
        start_blur = float(self._effect.blurRadius())
        end_blur = float(self.scaled(glow.blur if to_glow else resting.blur))

        base_color: QColor = (
            self._theme.color(f"{self._glow_role}_glow")
            if to_glow
            else self._theme.color(resting.color)
        )
        self._alpha_base_color = base_color
        target_alpha = base_color.alpha()
        start_alpha = self._effect.color().alpha()

        # Always stop in-flight runs first for clean interruption.
        self._blur_anim.stop()
        self._alpha_anim.stop()

        if not self._animated:
            self._effect.setBlurRadius(end_blur)
            self._effect.setColor(base_color)
            return

        duration = self._theme.duration("fast")
        easing = self._theme.easing()

        self._blur_anim.setDuration(duration)
        self._blur_anim.setStartValue(start_blur)
        self._blur_anim.setEndValue(end_blur)
        self._blur_anim.setEasingCurve(easing)
        self._blur_anim.start()

        self._alpha_anim.setDuration(duration)
        self._alpha_anim.setStartValue(float(start_alpha))
        self._alpha_anim.setEndValue(float(target_alpha))
        self._alpha_anim.setEasingCurve(easing)
        self._alpha_anim.start()

    def enterEvent(self, event) -> None:  # noqa: N802 (Qt override)
        """Fade the neon glow in while hovered/active."""
        self._transition_glow(True)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802 (Qt override)
        """Fade back to the resting elevation shadow when the hover ends."""
        self._transition_glow(False)
        super().leaveEvent(event)

    # ------------------------------------------------------------------ #
    # Behaviour
    # ------------------------------------------------------------------ #
    def showEvent(self, event) -> None:  # noqa: N802 (Qt override)
        """Fade the card in on first show when animations are enabled."""
        super().showEvent(event)
        if self._animated and not self._did_fade_in:
            self._did_fade_in = True
            fade(
                self,
                0.0,
                1.0,
                duration_ms=self._theme.duration("normal"),
                easing=self._theme.easing(),
                animated=self._animated,
            )
