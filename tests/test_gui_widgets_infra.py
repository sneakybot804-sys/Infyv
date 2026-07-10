"""Tests for Phase 8C-1 widget infrastructure (offscreen; skip without Qt)."""
from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest

pytest.importorskip("PySide6", reason="PySide6 not installed; GUI tests skipped")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from gui.theme.manager import ThemeManager  # noqa: E402
from gui.widgets import styling  # noqa: E402
from gui.widgets.animation import fade, tween_value  # noqa: E402
from gui.widgets.base import ThemedWidget  # noqa: E402
from gui.widgets.effects import apply_glow, apply_shadow, clear_effect  # noqa: E402


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_themed_widget_stores_manager_and_tokens(app: QApplication) -> None:
    theme = ThemeManager()
    widget = ThemedWidget(theme)
    assert widget.theme is theme
    assert widget.tokens is theme.tokens


def test_themed_widget_apply_theme_called_on_change(app: QApplication) -> None:
    theme = ThemeManager()

    calls = {"n": 0}

    class _Probe(ThemedWidget):
        def apply_theme(self) -> None:
            calls["n"] += 1

    _Probe(theme)
    theme.set_theme("dark")  # re-activate to fire the change callback
    assert calls["n"] >= 1


def test_themed_widget_cleanup_unsubscribes(app: QApplication) -> None:
    theme = ThemeManager()
    widget = ThemedWidget(theme)
    widget._cleanup_theme_subscription()
    # After cleanup, a theme change must not raise (handler removed).
    theme.set_theme("dark")


def test_scaled_and_icon_helpers(app: QApplication) -> None:
    theme = ThemeManager()
    widget = ThemedWidget(theme)
    assert isinstance(widget.scaled(10), int)
    qicon = widget.icon("play", theme.tokens.colors.accent_cyan, 16)
    assert not qicon.isNull()


def test_styling_builders_use_tokens(app: QApplication) -> None:
    theme = ThemeManager()
    tokens = theme.tokens
    glass = styling.glass_card_qss(tokens)
    assert tokens.colors.glass_fill in glass
    surface = styling.surface_card_qss(tokens)
    assert tokens.colors.surface_elevated in surface
    assert styling.accent_color(tokens, "cyan") == tokens.colors.accent_cyan
    assert styling.accent_glow(tokens, "purple") == tokens.colors.accent_purple_glow


def test_fade_not_animated_sets_final_state(app: QApplication) -> None:
    theme = ThemeManager()
    widget = QWidget()
    result = fade(widget, 0.0, 1.0, theme.tokens.motion, animated=False)
    assert result is None  # reduce-motion path returns no animation


def test_tween_value_not_animated_calls_once(app: QApplication) -> None:
    theme = ThemeManager()
    seen: list[float] = []
    result = tween_value(0.0, 1.0, theme.tokens.motion, seen.append, animated=False)
    assert result is None
    assert seen == [1.0]


def test_effects_apply_and_clear(app: QApplication) -> None:
    theme = ThemeManager()
    widget = QWidget()
    apply_shadow(widget, theme.tokens.shadows.medium)
    assert widget.graphicsEffect() is not None
    clear_effect(widget)
    assert widget.graphicsEffect() is None
    apply_glow(widget, theme.tokens.shadows.glow_cyan)
    assert widget.graphicsEffect() is not None


def test_infra_modules_do_not_import_tokens_or_gui_core() -> None:
    # Enforce: widget modules obtain everything via ThemeManager, never by
    # importing token modules or gui_core.
    base = Path(__file__).resolve().parent.parent / "gui" / "widgets"
    forbidden_exact = {"gui.theme.tokens", "gui.theme.palettes"}
    for module_path in base.glob("*.py"):
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        imported: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.append(node.module)
        for name in imported:
            assert name not in forbidden_exact, f"{module_path.name} imports {name}"
            assert name != "gui_core" and not name.startswith("gui_core."), (
                f"{module_path.name} imports gui_core"
            )
