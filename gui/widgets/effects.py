"""Optional visual effects: thin wrappers over Qt graphics effects.

These functions only wrap Qt graphics effects; they make no styling or token
decisions and import no token modules. Callers (widgets holding the injected
:class:`ThemeManager`) resolve concrete values from the active tokens -- blur
radius/offset scalars and a :class:`QColor` -- and pass them in.

Note Qt allows a single graphics effect per widget, so glow and shadow are
mutually exclusive on the same widget (compose with a container if both are
needed).
"""
from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsBlurEffect, QGraphicsDropShadowEffect, QWidget


def apply_shadow(
    widget: QWidget,
    *,
    blur: float,
    x: float,
    y: float,
    color: QColor,
) -> QGraphicsDropShadowEffect:
    """Install a drop-shadow effect on ``widget`` from concrete values.

    Args:
        widget: Target widget.
        blur: Blur radius in pixels.
        x: Horizontal offset in pixels.
        y: Vertical offset in pixels.
        color: Shadow color (already resolved from a token by the caller).

    Returns:
        The created effect, so callers can tweak or remove it later.
    """
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(float(blur))
    effect.setOffset(float(x), float(y))
    effect.setColor(color)
    widget.setGraphicsEffect(effect)
    return effect


def apply_glow(
    widget: QWidget,
    *,
    blur: float,
    color: QColor,
) -> QGraphicsDropShadowEffect:
    """Install a neon glow (a zero-offset colored drop shadow) on ``widget``."""
    return apply_shadow(widget, blur=blur, x=0.0, y=0.0, color=color)


def apply_blur(widget: QWidget, radius: float) -> QGraphicsBlurEffect:
    """Install a blur effect on ``widget`` with the given ``radius`` (px)."""
    effect = QGraphicsBlurEffect(widget)
    effect.setBlurRadius(float(radius))
    widget.setGraphicsEffect(effect)
    return effect


def clear_effect(widget: QWidget) -> None:
    """Remove any graphics effect currently installed on ``widget``."""
    widget.setGraphicsEffect(None)
