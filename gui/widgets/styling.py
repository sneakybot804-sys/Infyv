"""Widget-specific token->QSS builders.

This is the only place per-widget stylesheets are generated. Each function
takes the active :class:`~gui.theme.tokens.DesignTokens` (obtained by the
widget from its injected :class:`ThemeManager`) and returns a QSS string.
Colors come exclusively from tokens via :mod:`gui.theme.colorutils`; there are
no color literals here, and widgets never import token modules themselves.

Phase 8B's ``gui/theme`` package is frozen; these builders live on the widgets
side intentionally.
"""
from __future__ import annotations

from gui.theme.colorutils import to_qss
from gui.theme.tokens import DesignTokens


def surface_card_qss(tokens: DesignTokens, *, selector: str = "QFrame") -> str:
    """Return QSS for a plain elevated surface card.

    Args:
        tokens: Active design tokens.
        selector: The Qt selector the rules apply to (default ``QFrame``).
    """
    c = tokens.colors
    r = tokens.radius
    return f"""
{selector} {{
    background-color: {to_qss(c.surface_elevated)};
    border: 1px solid {to_qss(c.border)};
    border-radius: {r.lg}px;
}}
""".strip()


def glass_card_qss(tokens: DesignTokens, *, selector: str = "QFrame") -> str:
    """Return QSS for a translucent glass card (fill + light border)."""
    c = tokens.colors
    r = tokens.radius
    return f"""
{selector} {{
    background-color: {to_qss(c.glass_fill)};
    border: 1px solid {to_qss(c.glass_border)};
    border-radius: {r.lg}px;
}}
""".strip()


def focus_ring_qss(tokens: DesignTokens, *, selector: str) -> str:
    """Return QSS adding a visible neon focus ring to ``selector``."""
    c = tokens.colors
    return f"""
{selector}:focus {{
    border: 1px solid {to_qss(c.focus_ring)};
}}
""".strip()


def accent_color(tokens: DesignTokens, role: str) -> str:
    """Return the accent color token string for a named ``role``.

    Args:
        tokens: Active design tokens.
        role: One of ``"blue"``, ``"cyan"``, ``"purple"``, ``"success"``,
            ``"warning"``, ``"error"``.

    Raises:
        KeyError: If ``role`` is not a known accent role.
    """
    c = tokens.colors
    mapping = {
        "blue": c.accent_blue,
        "cyan": c.accent_cyan,
        "purple": c.accent_purple,
        "success": c.success,
        "warning": c.warning,
        "error": c.error,
    }
    return mapping[role]


def accent_glow(tokens: DesignTokens, role: str) -> str:
    """Return the glow color token string for a named accent ``role``."""
    c = tokens.colors
    mapping = {
        "blue": c.accent_blue_glow,
        "cyan": c.accent_cyan_glow,
        "purple": c.accent_purple_glow,
        "success": c.success_glow,
        "warning": c.warning_glow,
        "error": c.error_glow,
    }
    return mapping[role]
