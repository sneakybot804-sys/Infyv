"""Widget-specific token-value -> QSS builders (pure, no token imports).

This is the only place per-widget stylesheets are generated. To avoid
importing token modules (per the widget-layer architecture), each function
accepts a duck-typed colors object -- any object exposing the color attributes
used below, which is exactly what ``ThemeManager.tokens.colors`` provides --
plus explicit scalar values (radius, etc.) resolved by the caller. Functions
are pure: they create no widgets and have no side effects.
"""
from __future__ import annotations

from typing import Protocol


class ColorsLike(Protocol):
    """Structural type for the color tokens these builders read.

    Any object exposing these string attributes satisfies the protocol; in
    practice this is ``ThemeManager.tokens.colors``. Declaring it structurally
    avoids importing the concrete token module into the widget layer.
    """

    surface_elevated: str
    glass_fill: str
    glass_border: str
    border: str
    focus_ring: str
    accent_blue: str
    accent_cyan: str
    accent_purple: str
    accent_blue_glow: str
    accent_cyan_glow: str
    accent_purple_glow: str
    success: str
    warning: str
    error: str
    success_glow: str
    warning_glow: str
    error_glow: str


def surface_card_qss(
    colors: ColorsLike, *, radius: int, selector: str = "QFrame"
) -> str:
    """Return QSS for a plain elevated surface card.

    Args:
        colors: Duck-typed color tokens (``ThemeManager.tokens.colors``).
        radius: Corner radius in pixels (from a radius token).
        selector: The Qt selector the rules apply to (default ``QFrame``).
    """
    return f"""
{selector} {{
    background-color: {colors.surface_elevated};
    border: 1px solid {colors.border};
    border-radius: {radius}px;
}}
""".strip()


def glass_card_qss(
    colors: ColorsLike, *, radius: int, selector: str = "QFrame"
) -> str:
    """Return QSS for a translucent glass card (fill + light border)."""
    return f"""
{selector} {{
    background-color: {colors.glass_fill};
    border: 1px solid {colors.glass_border};
    border-radius: {radius}px;
}}
""".strip()


def focus_ring_qss(colors: ColorsLike, *, selector: str) -> str:
    """Return QSS adding a visible neon focus ring to ``selector``."""
    return f"""
{selector}:focus {{
    border: 1px solid {colors.focus_ring};
}}
""".strip()


def accent_color(colors: ColorsLike, role: str) -> str:
    """Return the accent color string for a named ``role``.

    Args:
        colors: Duck-typed color tokens.
        role: One of ``"blue"``, ``"cyan"``, ``"purple"``, ``"success"``,
            ``"warning"``, ``"error"``.

    Raises:
        KeyError: If ``role`` is not a known accent role.
    """
    mapping = {
        "blue": colors.accent_blue,
        "cyan": colors.accent_cyan,
        "purple": colors.accent_purple,
        "success": colors.success,
        "warning": colors.warning,
        "error": colors.error,
    }
    return mapping[role]


def accent_glow(colors: ColorsLike, role: str) -> str:
    """Return the glow color string for a named accent ``role``."""
    mapping = {
        "blue": colors.accent_blue_glow,
        "cyan": colors.accent_cyan_glow,
        "purple": colors.accent_purple_glow,
        "success": colors.success_glow,
        "warning": colors.warning_glow,
        "error": colors.error_glow,
    }
    return mapping[role]
