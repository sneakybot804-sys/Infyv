"""GlassCard: a rounded, translucent container with optional glow/shadow.

A pure presentation container: it holds injected content and applies glass
styling plus an optional elevation shadow or neon glow, all resolved through
the injected :class:`ThemeManager`. It is not interactive and stores no
business state.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import QFrame, QVBoxLayout, QWidget

from gui.theme.manager import ThemeManager
from gui.widgets import effects, styling
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
        """Rebuild the glass styling and the resting elevation shadow.

        The neon glow is applied only on hover/active (see the enter/leave
        events); at rest the card shows its elevation shadow.
        """
        tokens = self.tokens
        radius = self.scaled(getattr(tokens.radius, self._radius_key))
        self._frame.setStyleSheet(
            styling.glass_card_qss(
                tokens.colors, radius=radius, selector="#GlassCard"
            )
        )
        self._apply_resting_shadow()

    def _apply_resting_shadow(self) -> None:
        """Install the elevation drop shadow (the at-rest state)."""
        shadow = getattr(self.tokens.shadows, _SHADOW_BY_LEVEL[self._elevation_level])
        effects.apply_shadow(
            self._frame,
            blur=self.scaled(shadow.blur),
            x=self.scaled(shadow.x),
            y=self.scaled(shadow.y),
            color=self._theme.color(shadow.color),
        )

    def _apply_hover_glow(self) -> None:
        """Install the neon glow (the hover/active state).

        Falls back to the resting shadow when no glow role is configured.
        """
        if self._glow_role is None:
            self._apply_resting_shadow()
            return
        glow = getattr(self.tokens.shadows, f"glow_{self._glow_role}")
        effects.apply_glow(
            self._frame,
            blur=self.scaled(glow.blur),
            color=self._theme.color(f"{self._glow_role}_glow"),
        )

    def enterEvent(self, event) -> None:  # noqa: N802 (Qt override)
        """Show the neon glow while hovered/active."""
        self._apply_hover_glow()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802 (Qt override)
        """Return to the resting elevation shadow when the hover ends."""
        self._apply_resting_shadow()
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
