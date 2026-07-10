"""Optional, reusable animation helpers (Qt-only, no token imports).

These helpers are generic and widget-agnostic. They must not import token
modules: callers (widgets, which hold the injected :class:`ThemeManager`)
resolve concrete timing/easing from the active tokens and pass them in. Every
helper accepts ``animated``; when ``False`` it applies the final state
instantly (no running animation), which is also the accessibility \"reduce
motion\" path.
"""
from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import (
    QAbstractAnimation,
    QEasingCurve,
    QPropertyAnimation,
    QVariantAnimation,
)
from PySide6.QtWidgets import QGraphicsOpacityEffect, QWidget


def fade_effect(
    effect: QGraphicsOpacityEffect,
    start: float,
    end: float,
    *,
    duration_ms: int,
    easing: QEasingCurve,
    animated: bool = True,
    owner: Optional[QWidget] = None,
) -> Optional[QPropertyAnimation]:
    """Animate an EXISTING opacity ``effect`` from ``start`` to ``end``.

    Unlike :func:`fade`, this reuses a persistent effect (no new effect is
    installed per call), giving smooth, non-abrupt transitions when a widget
    animates repeatedly (hover/press/leave).

    Args:
        effect: The already-installed opacity effect to animate.
        start: Starting opacity (0..1).
        end: Ending opacity (0..1).
        duration_ms: Duration in milliseconds (caller-resolved from a token).
        easing: Easing curve (caller-resolved from a token).
        animated: When ``False``, set ``end`` instantly and return ``None``.
        owner: Optional parent for the animation's lifetime management.

    Returns:
        The running :class:`QPropertyAnimation`, or ``None`` when not animated.
    """
    if not animated:
        effect.setOpacity(end)
        return None

    animation = QPropertyAnimation(effect, b"opacity", owner or effect)
    animation.setDuration(duration_ms)
    animation.setStartValue(start)
    animation.setEndValue(end)
    animation.setEasingCurve(easing)
    animation.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
    return animation


def fade(
    widget: QWidget,
    start: float,
    end: float,
    *,
    duration_ms: int,
    easing: QEasingCurve,
    animated: bool = True,
) -> Optional[QPropertyAnimation]:
    """Fade ``widget`` opacity from ``start`` to ``end``.

    Args:
        widget: The widget to fade (a QGraphicsOpacityEffect is installed).
        start: Starting opacity (0..1).
        end: Ending opacity (0..1).
        duration_ms: Animation duration in milliseconds (from a motion token,
            resolved by the caller).
        easing: The easing curve to use (resolved by the caller from a motion
            token via :mod:`gui.theme.motion`).
        animated: When ``False``, set the final opacity instantly and return
            ``None`` (reduce-motion path).

    Returns:
        The started :class:`QPropertyAnimation`, or ``None`` when not animated.
    """
    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)

    if not animated:
        effect.setOpacity(end)
        return None

    animation = QPropertyAnimation(effect, b"opacity", widget)
    animation.setDuration(duration_ms)
    animation.setStartValue(start)
    animation.setEndValue(end)
    animation.setEasingCurve(easing)
    animation.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
    return animation


def tween_value(
    start: float,
    end: float,
    on_value: Callable[[float], None],
    *,
    duration_ms: int,
    easing: QEasingCurve,
    animated: bool = True,
) -> Optional[QVariantAnimation]:
    """Tween a scalar from ``start`` to ``end``, calling ``on_value`` each step.

    Useful for custom-painted widgets (e.g. a progress ring sweeping to a new
    value). When ``animated`` is ``False``, ``on_value(end)`` is called once
    and ``None`` is returned.

    Args:
        start: Starting scalar value.
        end: Ending scalar value.
        on_value: Callback invoked with each intermediate value.
        duration_ms: Animation duration in milliseconds (caller-resolved).
        easing: The easing curve to use (caller-resolved).
        animated: When ``False``, call ``on_value(end)`` once and return None.
    """
    if not animated:
        on_value(end)
        return None

    animation = QVariantAnimation()
    animation.setStartValue(float(start))
    animation.setEndValue(float(end))
    animation.setDuration(duration_ms)
    animation.setEasingCurve(easing)
    animation.valueChanged.connect(lambda v: on_value(float(v)))
    animation.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
    return animation
