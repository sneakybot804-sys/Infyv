"""Optional visual effects (shadow, glow, blur) built from tokens.

Effects are configurable and removable. Colors and radii come only from the
active theme's shadow/blur tokens. These wrap Qt graphics effects; a widget
can install or clear them at will. Note Qt allows a single graphics effect per
widget, so glow and shadow are mutually exclusive on the same widget (compose
with a container if both are needed).
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import QGraphicsBlurEffect, QGraphicsDropShadowEffect, QWidget

from gui.theme.colorutils import parse_color
from gui.theme.tokens import BlurTokens, ShadowToken


def apply_shadow(widget: QWidget, shadow: ShadowToken) -> QGraphicsDropShadowEffect:
    """Install a drop-shadow effect on ``widget`` from a shadow token.

    Returns the created effect so callers can tweak or remove it later.
    """
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(float(shadow.blur))
    effect.setOffset(float(shadow.x), float(shadow.y))
    effect.setColor(parse_color(shadow.color))
    widget.setGraphicsEffect(effect)
    return effect


def apply_glow(widget: QWidget, glow: ShadowToken) -> QGraphicsDropShadowEffect:
    """Install a neon glow (a zero-offset colored drop shadow) on ``widget``.

    A glow token is a :class:`ShadowToken` with zero offset and an accent
    color; this is a thin, intention-revealing wrapper over ``apply_shadow``.
    """
    return apply_shadow(widget, glow)


def apply_blur(widget: QWidget, blur: BlurTokens, *, radius: Optional[int] = None) -> QGraphicsBlurEffect:
    """Install a blur effect on ``widget`` using a blur token radius.

    Args:
        widget: Target widget.
        blur: Blur tokens supplying the default panel radius.
        radius: Optional explicit blur radius override (pixels).
    """
    effect = QGraphicsBlurEffect(widget)
    effect.setBlurRadius(float(radius if radius is not None else blur.panel))
    widget.setGraphicsEffect(effect)
    return effect


def clear_effect(widget: QWidget) -> None:
    """Remove any graphics effect currently installed on ``widget``."""
    widget.setGraphicsEffect(None)
