"""Pure-data theme token tests (must import NO Qt)."""
from __future__ import annotations

import re
from pathlib import Path

from gui.theme.palettes import DARK_TOKENS
from gui.theme.tokens import ColorTokens, DesignTokens

_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
_RGBA_RE = re.compile(
    r"^rgba\(\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*(0|1|0?\.\d+)\s*\)$"
)


def _is_color(value: str) -> bool:
    return bool(_HEX_RE.match(value) or _RGBA_RE.match(value))


def test_dark_tokens_is_design_tokens() -> None:
    assert isinstance(DARK_TOKENS, DesignTokens)
    assert DARK_TOKENS.name == "dark"
    assert DARK_TOKENS.is_dark is True


def test_all_color_tokens_are_valid() -> None:
    colors = DARK_TOKENS.colors
    assert isinstance(colors, ColorTokens)
    for field_name, value in vars(colors).items():
        assert isinstance(value, str), field_name
        assert _is_color(value), f"{field_name}={value!r} is not a valid color"


def test_neon_accents_present() -> None:
    c = DARK_TOKENS.colors
    for token in (c.accent_blue, c.accent_cyan, c.accent_purple):
        assert _HEX_RE.match(token)
    for glow in (c.accent_blue_glow, c.accent_cyan_glow, c.accent_purple_glow):
        assert _RGBA_RE.match(glow)


def test_spacing_scale_positive_and_ascending() -> None:
    s = DARK_TOKENS.spacing
    values = [s.xxs, s.xs, s.sm, s.md, s.lg, s.xl, s.xxl]
    assert all(v > 0 for v in values)
    assert values == sorted(values)


def test_radius_and_motion_ranges() -> None:
    r = DARK_TOKENS.radius
    assert 0 < r.sm <= r.md <= r.lg <= r.xl
    assert r.pill >= r.xl
    m = DARK_TOKENS.motion
    assert 0 < m.duration_fast_ms < m.duration_normal_ms < m.duration_slow_ms


def test_family_stack_includes_fallbacks() -> None:
    stack = DARK_TOKENS.typography.family_stack()
    assert "Inter" in stack
    assert "sans-serif" in stack


def test_tokens_source_references_no_qt() -> None:
    # The pure-data token module must not reference PySide6/Qt in its source.
    source = Path(__file__).resolve().parent.parent / "gui" / "theme" / "tokens.py"
    text = source.read_text(encoding="utf-8")
    assert "PySide6" not in text
    assert "QColor" not in text
    assert "QFont" not in text
    assert "QPalette" not in text
    assert "QEasingCurve" not in text
