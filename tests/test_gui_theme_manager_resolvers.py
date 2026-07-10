"""Tests for the additive ThemeManager resolved-value accessors (offscreen)."""
from __future__ import annotations

import os

import pytest

pytest.importorskip("PySide6", reason="PySide6 not installed; GUI tests skipped")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QColor, QFont  # noqa: E402
from PySide6.QtCore import QEasingCurve  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from gui.theme.manager import ThemeManager  # noqa: E402


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_color_resolves_role_names(app: QApplication) -> None:
    theme = ThemeManager()
    colors = theme.tokens.colors
    assert theme.color("cyan") == QColor(colors.accent_cyan)
    assert theme.color("purple") == QColor(colors.accent_purple)
    assert theme.color("success") == QColor(colors.success)


def test_color_resolves_glow_roles_with_alpha(app: QApplication) -> None:
    theme = ThemeManager()
    glow = theme.color("cyan_glow")
    # rgba token -> alpha < 255
    assert 0 < glow.alpha() < 255


def test_color_accepts_raw_token_string(app: QApplication) -> None:
    theme = ThemeManager()
    raw = theme.tokens.colors.background_base
    assert theme.color(raw) == QColor(raw)


def test_font_builds_for_styles(app: QApplication) -> None:
    theme = ThemeManager()
    body = theme.font("body")
    assert isinstance(body, QFont)
    h1 = theme.font("h1")
    assert h1.pixelSize() == theme.tokens.typography.h1.size_px


def test_font_default_is_body(app: QApplication) -> None:
    theme = ThemeManager()
    assert theme.font().pixelSize() == theme.tokens.typography.body.size_px


def test_easing_default_and_named(app: QApplication) -> None:
    theme = ThemeManager()
    assert isinstance(theme.easing(), QEasingCurve)
    assert isinstance(theme.easing("in_out_cubic"), QEasingCurve)


def test_duration_lookup(app: QApplication) -> None:
    theme = ThemeManager()
    motion = theme.tokens.motion
    assert theme.duration("fast") == motion.duration_fast_ms
    assert theme.duration("normal") == motion.duration_normal_ms
    assert theme.duration("slow") == motion.duration_slow_ms
    assert theme.duration() == motion.duration_normal_ms


def test_existing_api_unchanged(app: QApplication) -> None:
    # Backward-compatibility guard: the pre-existing surface still works.
    theme = ThemeManager()
    assert theme.available_themes() == ["dark"]
    assert theme.tokens is theme.tokens
    assert theme.icons is theme.icons
    with pytest.raises(NotImplementedError):
        theme.set_theme("light")
