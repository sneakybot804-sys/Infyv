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

    surface: str
    surface_elevated: str
    surface_overlay: str
    glass_fill: str
    glass_border: str
    border: str
    divider: str
    focus_ring: str
    text_primary: str
    text_on_accent: str
    text_disabled: str
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


def label_color_qss(color: str, *, selector: str = "QLabel") -> str:
    """Return QSS setting a label's text color."""
    return f"{selector} {{ color: {color}; background: transparent; }}"


def badge_qss(
    colors: ColorsLike, *, radius: int, pad_v: int, pad_h: int, accent: str, selector: str
) -> str:
    """Return QSS for a small pill badge (accent fill, on-accent text)."""
    accent_c = accent_color(colors, accent)
    return f"""
{selector} {{
    background-color: {accent_c};
    color: {colors.text_on_accent};
    border-radius: {radius}px;
    padding: {pad_v}px {pad_h}px;
}}
""".strip()


def divider_qss(colors: ColorsLike, *, selector: str) -> str:
    """Return QSS for a 1px horizontal divider line."""
    return f"""
{selector} {{
    background-color: {colors.divider};
    border: none;
    max-height: 1px;
    min-height: 1px;
}}
""".strip()


def neon_button_qss(
    colors: ColorsLike,
    *,
    radius: int,
    pad_v: int,
    pad_h: int,
    accent: str,
    variant: str,
    selector: str,
) -> str:
    """Return QSS for a NeonButton's inner QPushButton.

    Args:
        colors: Duck-typed color tokens.
        radius: Corner radius in pixels.
        pad_v: Vertical padding in pixels.
        pad_h: Horizontal padding in pixels.
        accent: Accent role name (``blue``/``cyan``/``purple``).
        variant: One of ``primary``, ``secondary``, ``ghost``.
        selector: The Qt selector to scope the rules to.

    Raises:
        KeyError: If ``accent`` is not a known accent role.
        ValueError: If ``variant`` is not recognized.
    """
    accent_c = accent_color(colors, accent)
    if variant == "primary":
        base_bg, base_fg, base_border = accent_c, colors.text_on_accent, accent_c
        hover_bg = accent_c
    elif variant == "secondary":
        base_bg, base_fg, base_border = colors.surface_elevated, colors.text_primary, colors.border
        hover_bg = colors.surface_overlay
    elif variant == "ghost":
        base_bg, base_fg, base_border = "transparent", colors.text_primary, "transparent"
        hover_bg = colors.surface_elevated
    else:  # pragma: no cover - guarded by the widget API
        raise ValueError(f"Unknown NeonButton variant: {variant!r}")

    return f"""
{selector} {{
    background-color: {base_bg};
    color: {base_fg};
    border: 1px solid {base_border};
    border-radius: {radius}px;
    padding: {pad_v}px {pad_h}px;
}}
{selector}:hover {{
    background-color: {hover_bg};
    border: 1px solid {accent_c};
}}
{selector}:pressed {{
    background-color: {colors.surface_overlay};
}}
{selector}:focus {{
    border: 1px solid {colors.focus_ring};
}}
{selector}:disabled {{
    color: {colors.text_disabled};
    border: 1px solid {colors.divider};
    background-color: {colors.surface};
}}
""".strip()


def icon_button_qss(
    colors: ColorsLike,
    *,
    radius: int,
    accent: str,
    selector: str,
) -> str:
    """Return QSS for an IconButton's inner QToolButton.

    Checked state uses the accent fill; hover raises the surface. The neon
    focus ring is always applied for keyboard visibility.
    """
    accent_c = accent_color(colors, accent)
    return f"""
{selector} {{
    background-color: {colors.surface_elevated};
    border: 1px solid {colors.border};
    border-radius: {radius}px;
}}
{selector}:hover {{
    border: 1px solid {accent_c};
    background-color: {colors.surface_overlay};
}}
{selector}:pressed {{
    background-color: {colors.surface_overlay};
}}
{selector}:checked {{
    background-color: {accent_c};
    border: 1px solid {accent_c};
}}
{selector}:focus {{
    border: 1px solid {colors.focus_ring};
}}
{selector}:disabled {{
    border: 1px solid {colors.divider};
    background-color: {colors.surface};
}}
""".strip()
