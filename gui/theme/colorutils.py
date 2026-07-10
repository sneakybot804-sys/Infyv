"""Conversion helpers between color token strings and Qt colors.

Color tokens are stored as ``#RRGGBB`` or ``rgba(r, g, b, a)`` strings (see
:mod:`gui.theme.tokens`). This module is the single place those strings are
parsed into :class:`QColor` or normalized for use in a Qt stylesheet. Keeping
conversion centralized means no other module needs to know the token string
format, and there are still no hardcoded colors outside the token definitions.
"""
from __future__ import annotations

from PySide6.QtGui import QColor


def parse_color(token: str) -> QColor:
    """Parse a color token string into a :class:`QColor`.

    Args:
        token: A ``#RRGGBB`` hex string or an ``rgba(r, g, b, a)`` string with
            ``a`` in the 0..1 range.

    Returns:
        The corresponding :class:`QColor` (including alpha for rgba tokens).

    Raises:
        ValueError: If the token is not a recognized color format.
    """
    text = token.strip()
    if text.startswith("#"):
        color = QColor(text)
        if not color.isValid():
            raise ValueError(f"Invalid hex color token: {token!r}")
        return color
    if text.startswith("rgba(") and text.endswith(")"):
        inner = text[len("rgba(") : -1]
        parts = [p.strip() for p in inner.split(",")]
        if len(parts) != 4:
            raise ValueError(f"Invalid rgba color token: {token!r}")
        r, g, b = (int(round(float(parts[i]))) for i in range(3))
        alpha = int(round(float(parts[3]) * 255))
        return QColor(r, g, b, alpha)
    raise ValueError(f"Unrecognized color token format: {token!r}")


def to_qss(token: str) -> str:
    """Return a color token normalized for embedding in a Qt style sheet.

    Qt Style Sheets accept both ``#RRGGBB`` and ``rgba(...)`` directly, so the
    token is returned trimmed. Validation is performed so malformed tokens are
    caught early rather than silently ignored by the stylesheet parser.
    """
    parse_color(token)  # validate; raises on malformed input
    return token.strip()
