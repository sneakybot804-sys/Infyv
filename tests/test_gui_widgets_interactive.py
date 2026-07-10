"""Tests for Phase 8C-4 interactive widgets (offscreen; skip without Qt).

Architecture and behavior only -- no pixel or rendering assertions.
"""
from __future__ import annotations

import os

import pytest

pytest.importorskip("PySide6", reason="PySide6 not installed; GUI tests skipped")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from gui.theme.manager import ThemeManager  # noqa: E402
from gui.widgets import Checkbox, TextField, ToggleSwitch  # noqa: E402


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


# -------------------------------------------------------------- ToggleSwitch #
def test_toggle_construction_and_state(app: QApplication) -> None:
    t = ToggleSwitch(ThemeManager(), checked=True, accent="blue")
    assert t.is_checked() is True
    assert t.checked is True
    assert t.accent == "blue"


def test_toggle_set_checked_emits_once(app: QApplication) -> None:
    t = ToggleSwitch(ThemeManager())
    seen = []
    t.toggled.connect(seen.append)
    t.set_checked(True)
    assert t.is_checked() is True
    assert seen == [True]
    # No-op set must not re-emit.
    t.set_checked(True)
    assert seen == [True]


def test_toggle_invalid_accent_raises(app: QApplication) -> None:
    with pytest.raises(ValueError):
        ToggleSwitch(ThemeManager(), accent="green")
    t = ToggleSwitch(ThemeManager())
    with pytest.raises(ValueError):
        t.set_accent("green")


def test_toggle_accent_valid_setter(app: QApplication) -> None:
    t = ToggleSwitch(ThemeManager())
    for accent in ("blue", "cyan", "purple"):
        t.set_accent(accent)
        assert t.accent == accent


def test_toggle_accessible_name_auto_on_off(app: QApplication) -> None:
    t = ToggleSwitch(ThemeManager(), checked=False)
    assert t.accessibleName() == "Off"
    t.set_checked(True)
    assert t.accessibleName() == "On"


def test_toggle_explicit_accessible_name_takes_precedence(app: QApplication) -> None:
    t = ToggleSwitch(ThemeManager())
    t.setAccessibleName("Mute")
    assert t.accessibleName() == "Mute"
    t.set_checked(True)  # must not overwrite the explicit name
    assert t.accessibleName() == "Mute"


def test_toggle_reduce_motion_no_running_animation(app: QApplication) -> None:
    from PySide6.QtCore import QAbstractAnimation

    t = ToggleSwitch(ThemeManager(), animated=False)
    t.set_checked(True)
    assert t._knob_anim.state() != QAbstractAnimation.State.Running


def test_toggle_no_graphics_effect(app: QApplication) -> None:
    t = ToggleSwitch(ThemeManager())
    assert t.graphicsEffect() is None
    assert t._checkbox.graphicsEffect() is None
    assert t._track.graphicsEffect() is None
    assert t._knob.graphicsEffect() is None


def test_toggle_keyboard_space(app: QApplication) -> None:
    t = ToggleSwitch(ThemeManager())
    seen = []
    t.toggled.connect(seen.append)
    t.show()
    t._checkbox.setFocus()
    QTest.keyClick(t._checkbox, Qt.Key.Key_Space)
    t.hide()
    assert seen == [True]


# ------------------------------------------------------------------ Checkbox #
def test_checkbox_construction_and_text(app: QApplication) -> None:
    c = Checkbox(ThemeManager(), "Enable", checked=True, accent="purple")
    assert c.is_checked() is True
    assert c.text() == "Enable"
    assert c.accent == "purple"


def test_checkbox_set_checked_emits_once(app: QApplication) -> None:
    c = Checkbox(ThemeManager(), "x")
    seen = []
    c.toggled.connect(seen.append)
    c.set_checked(True)
    assert seen == [True]
    c.set_checked(True)  # no-op
    assert seen == [True]


def test_checkbox_invalid_accent_raises(app: QApplication) -> None:
    with pytest.raises(ValueError):
        Checkbox(ThemeManager(), "x", accent="green")
    c = Checkbox(ThemeManager(), "x")
    with pytest.raises(ValueError):
        c.set_accent("green")


def test_checkbox_accessible_name_policy(app: QApplication) -> None:
    c = Checkbox(ThemeManager(), "Loop")
    assert c.accessibleName() == "Loop"
    empty = Checkbox(ThemeManager(), "")
    assert empty.accessibleName() == "checkbox"
    c.setAccessibleName("Explicit")
    c.set_text("Changed")  # explicit name must win
    assert c.accessibleName() == "Explicit"


def test_checkbox_no_graphics_effect(app: QApplication) -> None:
    c = Checkbox(ThemeManager(), "x")
    assert c.graphicsEffect() is None
    assert c._checkbox.graphicsEffect() is None


def test_checkbox_keyboard_space(app: QApplication) -> None:
    c = Checkbox(ThemeManager(), "x")
    seen = []
    c.toggled.connect(seen.append)
    c.show()
    c._checkbox.setFocus()
    QTest.keyClick(c._checkbox, Qt.Key.Key_Space)
    c.hide()
    assert seen == [True]


# ----------------------------------------------------------------- TextField #
def test_text_field_text_roundtrip(app: QApplication) -> None:
    f = TextField(ThemeManager(), text="hello")
    assert f.text() == "hello"
    f.set_text("world")
    assert f.text() == "world"
    f.clear()
    assert f.text() == ""


def test_text_field_placeholder(app: QApplication) -> None:
    f = TextField(ThemeManager(), placeholder="name")
    assert f.placeholder() == "name"
    f.set_placeholder("email")
    assert f.placeholder() == "email"


def test_text_field_text_changed_signal(app: QApplication) -> None:
    f = TextField(ThemeManager())
    seen = []
    f.text_changed.connect(seen.append)
    f.set_text("a")
    assert seen == ["a"]


def test_text_field_set_text_noop_when_unchanged(app: QApplication) -> None:
    f = TextField(ThemeManager(), text="same")
    seen = []
    f.text_changed.connect(seen.append)
    f.set_text("same")  # unchanged -> no emit
    assert seen == []


def test_text_field_return_pressed_signal(app: QApplication) -> None:
    f = TextField(ThemeManager())
    seen = []
    f.return_pressed.connect(lambda: seen.append(True))
    f.show()
    f._edit.setFocus()
    QTest.keyClick(f._edit, Qt.Key.Key_Return)
    f.hide()
    assert seen == [True]


def test_text_field_accessible_name_policy(app: QApplication) -> None:
    f = TextField(ThemeManager(), placeholder="Search")
    assert f.accessibleName() == "Search"
    empty = TextField(ThemeManager())
    assert empty.accessibleName() == "text field"
    f.setAccessibleName("Explicit")
    f.set_placeholder("Other")  # explicit name must win
    assert f.accessibleName() == "Explicit"


def test_text_field_no_graphics_effect(app: QApplication) -> None:
    f = TextField(ThemeManager())
    assert f.graphicsEffect() is None
    assert f._edit.graphicsEffect() is None


# --------------------------------------------------------------- Re-theming #
def test_interactive_widgets_restyle_on_theme_change(app: QApplication) -> None:
    theme = ThemeManager()
    widgets = [
        ToggleSwitch(theme),
        Checkbox(theme, "x"),
        TextField(theme),
    ]
    theme.set_theme("dark")  # must invoke apply_theme on all without raising
    assert len(widgets) == 3
