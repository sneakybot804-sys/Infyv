"""Qt-touching theme tests (offscreen; skipped when PySide6 is absent)."""
from __future__ import annotations

import os

import pytest

pytest.importorskip("PySide6", reason="PySide6 not installed; GUI tests skipped")

# Force the headless platform before any QApplication is created.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QColor, QPalette  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from gui.theme.colorutils import parse_color, to_qss  # noqa: E402
from gui.theme.icons import IconLoader  # noqa: E402
from gui.theme.manager import ThemeManager  # noqa: E402
from gui.theme.palette_builder import build_qpalette  # noqa: E402
from gui.theme.palettes import DARK_TOKENS  # noqa: E402
from gui.theme.qss import build_stylesheet  # noqa: E402


@pytest.fixture(scope="module")
def app() -> QApplication:
    instance = QApplication.instance() or QApplication([])
    return instance  # type: ignore[return-value]


def test_parse_hex_and_rgba() -> None:
    assert parse_color("#3b82f6") == QColor("#3b82f6")
    rgba = parse_color("rgba(34, 211, 238, 0.5)")
    assert (rgba.red(), rgba.green(), rgba.blue()) == (34, 211, 238)
    assert rgba.alpha() == 128


def test_parse_color_rejects_malformed() -> None:
    with pytest.raises(ValueError):
        parse_color("not-a-color")


def test_to_qss_validates() -> None:
    assert to_qss("#eef2ff") == "#eef2ff"
    with pytest.raises(ValueError):
        to_qss("blue")


def test_build_stylesheet_contains_token_colors() -> None:
    qss = build_stylesheet(DARK_TOKENS)
    assert isinstance(qss, str) and qss.strip()
    assert DARK_TOKENS.colors.background_base in qss
    assert DARK_TOKENS.colors.accent_cyan in qss


def test_build_qpalette_sets_core_roles(app: QApplication) -> None:
    palette = build_qpalette(DARK_TOKENS)
    window = palette.color(QPalette.ColorRole.Window)
    assert window == QColor(DARK_TOKENS.colors.background_base)
    highlight = palette.color(QPalette.ColorRole.Highlight)
    assert highlight == QColor(DARK_TOKENS.colors.accent_blue)


def test_icon_loader_loads_recolors_and_caches(app: QApplication) -> None:
    loader = IconLoader()
    pm1 = loader.pixmap("play", DARK_TOKENS.colors.accent_cyan, 24)
    assert not pm1.isNull()
    pm2 = loader.pixmap("play", DARK_TOKENS.colors.accent_cyan, 24)
    assert pm1 is pm2  # cached identity


def test_icon_loader_missing_icon_raises(app: QApplication) -> None:
    loader = IconLoader()
    with pytest.raises(FileNotFoundError):
        loader.pixmap("does_not_exist", DARK_TOKENS.colors.accent_blue, 16)


def test_theme_manager_dark_is_default_and_only() -> None:
    manager = ThemeManager()
    assert manager.available_themes() == ["dark"]
    assert manager.tokens is DARK_TOKENS


def test_theme_manager_light_raises_not_implemented() -> None:
    manager = ThemeManager()
    with pytest.raises(NotImplementedError):
        manager.set_theme("light")


def test_theme_manager_change_callback_fires() -> None:
    manager = ThemeManager()
    seen = []
    manager.on_theme_changed(lambda tokens: seen.append(tokens.name))
    manager.set_theme("dark")
    assert seen == ["dark"]


def test_theme_manager_apply_runs(app: QApplication) -> None:
    manager = ThemeManager()
    manager.apply(app)
    assert app.styleSheet().strip()
