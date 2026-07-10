"""Tests for Phase 8C-2 primitive widgets (offscreen; skip without Qt).

Architecture and behavior only -- no pixel or rendering assertions.
"""
from __future__ import annotations

import os

import pytest

pytest.importorskip("PySide6", reason="PySide6 not installed; GUI tests skipped")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, Qt  # noqa: E402
from PySide6.QtGui import QEnterEvent  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QLabel,
    QMenu,
    QVBoxLayout,
    QWidget,
)

from gui.theme.manager import ThemeManager  # noqa: E402
from gui.widgets import GlassCard, IconButton, NeonButton, SectionHeader  # noqa: E402


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


# ---------------------------------------------------------------- GlassCard #
def test_glass_card_content_swap(app: QApplication) -> None:
    theme = ThemeManager()
    card = GlassCard(theme, animated=False)
    assert card.content() is None
    first = QLabel("a")
    card.set_content(first)
    assert card.content() is first
    second = QLabel("b")
    card.set_content(second)
    assert card.content() is second


def test_glass_card_glow_and_elevation(app: QApplication) -> None:
    theme = ThemeManager()
    card = GlassCard(theme, animated=False)
    card.set_elevation("high")
    assert card.elevation_level == "high"
    card.set_glow("purple")
    assert card.glow_role == "purple"


def test_glass_card_hover_toggles_glow_state(app: QApplication) -> None:
    theme = ThemeManager()
    card = GlassCard(theme, glow="cyan", animated=False)
    assert card.glow_active() is False
    enter = QEnterEvent(card.rect().center(), card.rect().center(), card.rect().center())
    card.enterEvent(enter)
    assert card.glow_active() is True
    card.leaveEvent(QEvent(QEvent.Type.Leave))
    assert card.glow_active() is False


def test_neon_button_inner_has_no_graphics_effect(app: QApplication) -> None:
    # The inner button must carry no QGraphicsEffect, so it never nests inside
    # GlassCard's drop-shadow effect (which caused blank cards / QPainter
    # warnings). Hover/pressed feedback comes from QSS state rules instead.
    theme = ThemeManager()
    button = NeonButton(theme, "Go", animated=True)
    assert button._button.graphicsEffect() is None


# --------------------------------------------------------------- NeonButton #
def test_neon_button_clicked_emits(app: QApplication) -> None:
    theme = ThemeManager()
    button = NeonButton(theme, "Go")
    seen = []
    button.clicked.connect(lambda: seen.append(True))
    button._button.click()
    assert seen == [True]


def test_neon_button_variant_and_accent(app: QApplication) -> None:
    theme = ThemeManager()
    button = NeonButton(theme, "Go", variant="primary", accent="cyan")
    button.set_variant("ghost")
    assert button.variant == "ghost"
    button.set_accent("purple")
    assert button.accent == "purple"


def test_neon_button_invalid_variant_raises(app: QApplication) -> None:
    theme = ThemeManager()
    with pytest.raises(ValueError):
        NeonButton(theme, "Go", variant="nope")


def test_neon_button_loading_state(app: QApplication) -> None:
    theme = ThemeManager()
    button = NeonButton(theme, "Save")
    button.set_loading(True)
    assert button.loading is True
    assert button._button.isEnabled() is False
    button.set_loading(False)
    assert button.loading is False
    assert button._button.isEnabled() is True
    assert button.text() == "Save"


def test_neon_button_accessible_name(app: QApplication) -> None:
    theme = ThemeManager()
    button = NeonButton(theme, "Export")
    assert button.accessibleName() == "Export"


def test_neon_button_keyboard_activation(app: QApplication) -> None:
    theme = ThemeManager()
    button = NeonButton(theme, "Go")
    seen = []
    button.clicked.connect(lambda: seen.append(True))
    # The button must be shown and focused for a key-driven activation to fire.
    button.show()
    inner = button._button
    inner.setDefault(True)
    inner.setFocus()
    QTest.keyClick(inner, Qt.Key.Key_Return)
    button.hide()
    assert seen == [True]


# --------------------------------------------------------------- IconButton #
def test_icon_button_clicked_emits(app: QApplication) -> None:
    theme = ThemeManager()
    button = IconButton(theme, "play", tooltip="Play")
    seen = []
    button.clicked.connect(lambda: seen.append(True))
    button._button.click()
    assert seen == [True]


def test_icon_button_toggle(app: QApplication) -> None:
    theme = ThemeManager()
    button = IconButton(theme, "play", checkable=True, tooltip="Play")
    states = []
    button.toggled.connect(states.append)
    button.set_checked(True)
    assert button.is_checked() is True
    assert states == [True]


def test_icon_button_requires_accessible_name(app: QApplication) -> None:
    theme = ThemeManager()
    button = IconButton(theme, "play", tooltip="Play")
    assert button.accessibleName() == "Play"
    explicit = IconButton(theme, "spark", accessible_name="Sparkle")
    assert explicit.accessibleName() == "Sparkle"


def test_icon_button_set_icon(app: QApplication) -> None:
    theme = ThemeManager()
    button = IconButton(theme, "play", tooltip="Play")
    button.set_icon("spark")  # must not raise


def test_icon_button_context_menu_hook(app: QApplication) -> None:
    theme = ThemeManager()
    button = IconButton(theme, "play", tooltip="Play")
    assert button.has_context_menu() is False
    menu = QMenu()
    menu.addAction("Item")
    button.set_context_menu(menu)
    assert button.has_context_menu() is True
    button.set_context_menu(None)
    assert button.has_context_menu() is False


# ------------------------------------------------------------ SectionHeader #
def test_section_header_title_subtitle(app: QApplication) -> None:
    theme = ThemeManager()
    header = SectionHeader(theme, "Pipeline", subtitle="overview")
    assert header.title() == "Pipeline"
    assert header.subtitle() == "overview"
    header.set_title("Analysis")
    header.set_subtitle("")
    assert header.title() == "Analysis"
    assert header.subtitle() == ""


def test_section_header_action_slot(app: QApplication) -> None:
    theme = ThemeManager()
    header = SectionHeader(theme, "Title")
    action = NeonButton(theme, "Run")
    header.set_action(action)
    header.set_action(None)  # clearing must not raise


def test_section_header_badge_toggle(app: QApplication) -> None:
    theme = ThemeManager()
    # isVisible() reflects effective visibility, so host the header in a shown
    # top-level widget before asserting the badge's visibility.
    host = QWidget()
    layout = QVBoxLayout(host)
    header = SectionHeader(theme, "Title")
    layout.addWidget(header)
    host.show()
    try:
        assert header.badge_visible() is False
        header.set_badge("3", accent="purple")
        assert header.badge_visible() is True
        header.set_badge(None)
        assert header.badge_visible() is False
    finally:
        host.hide()


def test_section_header_divider_toggle(app: QApplication) -> None:
    theme = ThemeManager()
    host = QWidget()
    layout = QVBoxLayout(host)
    header = SectionHeader(theme, "Title")
    layout.addWidget(header)
    host.show()
    try:
        assert header.divider_visible() is False
        header.set_divider(True)
        assert header.divider_visible() is True
        header.set_divider(False)
        assert header.divider_visible() is False
    finally:
        host.hide()


# --------------------------------------------------------------- Re-theming #
def test_widgets_restyle_on_theme_change(app: QApplication) -> None:
    theme = ThemeManager()
    widgets = [
        GlassCard(theme, animated=False),
        NeonButton(theme, "Go"),
        IconButton(theme, "play", tooltip="Play"),
        SectionHeader(theme, "Title"),
    ]
    # Re-activating the theme must invoke apply_theme on all subscribers
    # without raising.
    theme.set_theme("dark")
    assert all(isinstance(w, QWidget) for w in widgets)
