"""Map Qt-free motion tokens to Qt animation primitives.

:mod:`gui.theme.tokens` stores easing curves as plain names so it imports no
Qt symbol. This module resolves those names to :class:`QEasingCurve.Type` and
exposes duration lookups, so animation code in later phases stays fully
token-driven with no magic numbers.
"""
from __future__ import annotations

from PySide6.QtCore import QEasingCurve

from gui.theme.tokens import MotionTokens

#: Mapping from token easing names to Qt easing curve types.
_EASING_BY_NAME = {
    "in_cubic": QEasingCurve.Type.InCubic,
    "out_cubic": QEasingCurve.Type.OutCubic,
    "in_out_cubic": QEasingCurve.Type.InOutCubic,
    "in_out_quart": QEasingCurve.Type.InOutQuart,
}


def easing_curve(name: str) -> QEasingCurve:
    """Return a :class:`QEasingCurve` for a token easing ``name``.

    Raises:
        KeyError: If the easing name is not recognized.
    """
    return QEasingCurve(_EASING_BY_NAME[name])


def standard_easing(motion: MotionTokens) -> QEasingCurve:
    """Return the theme's standard easing curve."""
    return easing_curve(motion.easing_standard)
