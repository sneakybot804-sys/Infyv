"""Verify the component gallery actually contains the primitive widgets.

Offscreen; skipped without PySide6. This guards two regressions: the gallery
rendering empty, and a NeonButton carrying a nested graphics effect (which
caused the QPainter warnings / blank cards).
"""
from __future__ import annotations

import os

import pytest

pytest.importorskip("PySide6", reason="PySide6 not installed; GUI tests skipped")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from gui.app_theme_preview import build_gallery  # noqa: E402
from gui.theme.manager import ThemeManager  # noqa: E402
from gui.widgets import GlassCard, IconButton, NeonButton, SectionHeader  # noqa: E402


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_gallery_contains_all_primitive_widgets(app: QApplication) -> None:
    theme = ThemeManager()
    window = build_gallery(theme)

    for widget_type in (GlassCard, NeonButton, IconButton, SectionHeader):
        found = window.findChildren(widget_type)
        assert found, f"gallery is missing any {widget_type.__name__}"


def test_gallery_neon_buttons_have_no_nested_effect(app: QApplication) -> None:
    theme = ThemeManager()
    window = build_gallery(theme)
    for button in window.findChildren(NeonButton):
        # The composed inner QPushButton must not carry a graphics effect,
        # so it never nests inside a GlassCard's drop-shadow effect.
        inner = button.findChild(type(button._button))
        assert inner is not None
        assert inner.graphicsEffect() is None


def test_gallery_widgets_are_shown(app: QApplication) -> None:
    theme = ThemeManager()
    window = build_gallery(theme)
    window.show()
    # After show(), the cards and their contents should not be explicitly
    # hidden (visibility of children follows the shown parent).
    cards = window.findChildren(GlassCard)
    assert cards
    for card in cards:
        assert not card.isHidden()
    window.hide()
