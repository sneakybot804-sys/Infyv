"""Optional, token-driven animation helpers.

All helpers are opt-in and seeded from the active theme's motion tokens
(durations and easing). Every helper accepts ``animated``; when ``False`` it
applies the final state instantly (no running animation), which is also the
accessibility \"reduce motion\" path. Widgets should route timings/easing only
through these helpers so no widget hardcodes animation values.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import (
    QAbstractAnimation,
    QEasingCurve,
    QPropertyAnimation,
    QVariantAnimation,
)
from PySide6.QtWidgets import QGraphicsOpacityEffect, QWidget

from gui.theme.motion import easing_curve
from gui.theme.tokens import MotionTokens


def fade(
    widget: QWidget,
    start: float,
    end: float,
    motion: MotionTokens,
    *,
    duration_ms: Optional[int] = None,
    easing_name: Optional[str] = None,
    animated: bool = True,
) -> Optional[QPropertyAnimation]:
    """Fade ``widget`` opacity from ``start`` to ``end``.

    Args:
        widget: The widget to fade (a QGraphicsOpacityEffect is installed).
        start: Starting opacity (0..1).
        end: Ending opacity (0..1).
        motion: Motion tokens supplying default duration/easing.
        duration_ms: Optional explicit duration override.
        easing_name: Optional explicit easing token name override.
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
    animation.setDuration(duration_ms if duration_ms is not None else motion.duration_normal_ms)
    animation.setStartValue(start)
    animation.setEndValue(end)
    animation.setEasingCurve(
        easing_curve(easing_name) if easing_name else easing_curve(motion.easing_standard)
    )
    animation.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
    return animation


def tween_value(
    start: float,
    end: float,
    motion: MotionTokens,
    on_value,
    *,
    duration_ms: Optional[int] = None,
    easing_name: Optional[str] = None,
    animated: bool = True,
) -> Optional[QVariantAnimation]:
    """Tween a scalar from ``start`` to ``end``, calling ``on_value`` each step.

    Useful for custom-painted widgets (e.g. a progress ring sweeping to a new
    value). When ``animated`` is ``False``, ``on_value(end)`` is called once
    and ``None`` is returned.
    """
    if not animated:
        on_value(end)
        return None

    animation = QVariantAnimation()
    animation.setStartValue(float(start))
    animation.setEndValue(float(end))
    animation.setDuration(duration_ms if duration_ms is not None else motion.duration_normal_ms)
    animation.setEasingCurve(
        easing_curve(easing_name) if easing_name else easing_curve(motion.easing_standard)
    )
    animation.valueChanged.connect(lambda v: on_value(float(v)))
    animation.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
    return animation


def resolve_easing(motion: MotionTokens, name: Optional[str] = None) -> QEasingCurve:
    """Return a :class:`QEasingCurve` for ``name`` or the standard easing."""
    return easing_curve(name) if name else easing_curve(motion.easing_standard)
