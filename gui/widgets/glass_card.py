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
from gui.widgets.base import ThemedWidget

# TEMPORARY debug instrumentation flag (Phase 8C-2 investigation). Remove once
# the widget-disappearance cause is confirmed.
_DEBUG = True
_CARD_SEQ = [0]


def _dbg(msg: str) -> None:
    """Temporary debug print (gated by _DEBUG)."""
    if _DEBUG:
        print(f"[GlassCard] {msg}")


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

        _CARD_SEQ[0] += 1
        self._dbg_id = _CARD_SEQ[0]
        self._dbg_paints = 0
        _dbg(f"construct #{self._dbg_id} glow={glow} elevation={elevation}")
        self.destroyed.connect(lambda: _dbg(f"destroyed #{self._dbg_id}"))

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
        """Set the glow accent role (or ``None``); no-op when unchanged."""
        if role == self._glow_role:
            return
        self._glow_role = role
        self.apply_theme()

    def set_elevation(self, level: str) -> None:
        """Set the elevation shadow level; no-op when unchanged."""
        if level == self._elevation_level:
            return
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
        """TEMPORARY: log show lifecycle (no behavior change)."""
        _dbg(
            f"showEvent #{self._dbg_id} visible={self.isVisible()} "
            f"frame_effect={self._frame.graphicsEffect() is not None} "
            f"self_effect={self.graphicsEffect() is not None} "
            f"children={len(self.findChildren(QWidget))}"
        )
        super().showEvent(event)

    def hideEvent(self, event) -> None:  # noqa: N802 (Qt override)
        """TEMPORARY: log hide lifecycle to catch unexpected hides."""
        _dbg(f"hideEvent #{self._dbg_id} (widget being hidden)")
        super().hideEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt override)
        """TEMPORARY: log the first few paints."""
        if self._dbg_paints < 3:
            self._dbg_paints += 1
            _dbg(
                f"paintEvent #{self._dbg_id} n={self._dbg_paints} "
                f"visible={self.isVisible()}"
            )
        super().paintEvent(event)

    # TEMPORARY (Phase 8C-2): the previous show-time fade-in installed a
    # QGraphicsOpacityEffect on the card starting at opacity 0.0. Because the
    # card is also an effect-bearing widget, that transient opacity effect
    # left the card in a transparent/stale state once the animation was torn
    # down, so content appeared briefly then vanished. The fade-in is removed
    # so the card renders at full opacity immediately and stays visible.
    #
    # A rendering-safe entrance animation (one that does not stack an opacity
    # effect on an effect-bearing card) will be revisited in Phase 8H
    # (Animation & Polish). The `animated` flag still governs the hover glow
    # transition, so the public API is unchanged.
