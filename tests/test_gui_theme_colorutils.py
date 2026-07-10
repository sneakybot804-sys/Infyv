"""Focused tests for gui.theme.colorutils helpers (offscreen; skip w/o Qt)."""
from __future__ import annotations

import os

import pytest

pytest.importorskip("PySide6", reason="PySide6 not installed; GUI tests skipped")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QColor  # noqa: E402

from gui.theme.colorutils import parse_color, resolve_color  # noqa: E402
from gui.theme.palettes import DARK_TOKENS  # noqa: E402


def test_resolve_color_role_names() -> None:
    colors = DARK_TOKENS.colors
    assert resolve_color(colors, "cyan") == QColor(colors.accent_cyan)
    assert resolve_color(colors, "purple") == QColor(colors.accent_purple)
    assert resolve_color(colors, "error") == QColor(colors.error)


def test_resolve_color_glow_roles() -> None:
    colors = DARK_TOKENS.colors
    glow = resolve_color(colors, "blue_glow")
    assert 0 < glow.alpha() < 255


def test_resolve_color_raw_token_passthrough() -> None:
    colors = DARK_TOKENS.colors
    raw = colors.background_base
    assert resolve_color(colors, raw) == parse_color(raw)


def test_resolve_color_unknown_name_treated_as_raw_raises() -> None:
    colors = DARK_TOKENS.colors
    with pytest.raises(ValueError):
        resolve_color(colors, "not-a-color")
