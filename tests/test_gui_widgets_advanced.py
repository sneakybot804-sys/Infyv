"""Tests for Phase 8C-5 advanced interactive widgets (offscreen; skip w/o Qt).

Architecture and behavior only -- no pixel or rendering assertions.
"""
from __future__ import annotations

import os

import pytest

pytest.importorskip("PySide6", reason="PySide6 not installed; GUI tests skipped")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from gui.theme.manager import ThemeManager  # noqa: E402
from gui.widgets import Dropdown, SegmentedControl, Slider  # noqa: E402


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


# ------------------------------------------------------------------ Dropdown #
def test_dropdown_construction_and_items(app: QApplication) -> None:
    d = Dropdown(ThemeManager(), items=["a", "b", "c"], current=1)
    assert d.items() == ["a", "b", "c"]
    assert d.current_index() == 1
    assert d.current_text() == "b"


def test_dropdown_empty_items(app: QApplication) -> None:
    d = Dropdown(ThemeManager())
    assert d.items() == []
    assert d.current_index() == -1
    assert d.current_text() == ""


def test_dropdown_changed_emits(app: QApplication) -> None:
    d = Dropdown(ThemeManager(), items=["a", "b"])
    seen = []
    d.changed.connect(seen.append)
    d.set_current_index(1)
    assert d.current_index() == 1
    assert seen == [1]
    d.set_current_index(1)  # no-op
    assert seen == [1]


def test_dropdown_invalid_index_raises(app: QApplication) -> None:
    with pytest.raises(ValueError):
        Dropdown(ThemeManager(), items=["a"], current=5)
    d = Dropdown(ThemeManager(), items=["a", "b"])
    with pytest.raises(ValueError):
        d.set_current_index(9)


def test_dropdown_invalid_accent_raises(app: QApplication) -> None:
    with pytest.raises(ValueError):
        Dropdown(ThemeManager(), accent="green")
    d = Dropdown(ThemeManager())
    with pytest.raises(ValueError):
        d.set_accent("green")


def test_dropdown_accessible_name_policy(app: QApplication) -> None:
    d = Dropdown(ThemeManager(), items=["Alpha", "Beta"], current=0)
    assert d.accessibleName() == "Alpha"
    d.setAccessibleName("Explicit")
    d.set_current_index(1)  # explicit name must win
    assert d.accessibleName() == "Explicit"


def test_dropdown_no_graphics_effect(app: QApplication) -> None:
    d = Dropdown(ThemeManager(), items=["a"])
    assert d.graphicsEffect() is None
    assert d._combo.graphicsEffect() is None


# -------------------------------------------------------------------- Slider #
def test_slider_construction_and_value(app: QApplication) -> None:
    s = Slider(ThemeManager(), minimum=0.0, maximum=10.0, value=5.0)
    assert s.minimum() == 0.0
    assert s.maximum() == 10.0
    assert s.value() == 5.0


def test_slider_value_clamped(app: QApplication) -> None:
    s = Slider(ThemeManager(), minimum=0.0, maximum=1.0, value=0.0)
    s.set_value(2.0)
    assert s.value() == 1.0
    s.set_value(-1.0)
    assert s.value() == 0.0


def test_slider_value_changed_emits(app: QApplication) -> None:
    s = Slider(ThemeManager(), minimum=0.0, maximum=1.0, value=0.0)
    seen = []
    s.value_changed.connect(seen.append)
    s.set_value(0.5)
    assert seen == [0.5]
    s.set_value(0.5)  # no-op
    assert seen == [0.5]


def test_slider_invalid_range_raises(app: QApplication) -> None:
    with pytest.raises(ValueError):
        Slider(ThemeManager(), minimum=1.0, maximum=1.0)
    with pytest.raises(ValueError):
        Slider(ThemeManager(), minimum=2.0, maximum=1.0)
    s = Slider(ThemeManager())
    with pytest.raises(ValueError):
        s.set_range(5.0, 5.0)


def test_slider_invalid_accent_raises(app: QApplication) -> None:
    with pytest.raises(ValueError):
        Slider(ThemeManager(), accent="green")
    s = Slider(ThemeManager())
    with pytest.raises(ValueError):
        s.set_accent("green")


def test_slider_accessible_name_policy(app: QApplication) -> None:
    s = Slider(ThemeManager(), minimum=0.0, maximum=1.0, value=0.5)
    assert s.accessibleName() == "Slider 0.5"
    whole = Slider(ThemeManager(), minimum=0.0, maximum=100.0, value=75.0)
    assert whole.accessibleName() == "Slider 75"
    s.setAccessibleName("Volume")
    s.set_value(0.2)  # explicit name must win
    assert s.accessibleName() == "Volume"


def test_slider_no_graphics_effect(app: QApplication) -> None:
    s = Slider(ThemeManager())
    assert s.graphicsEffect() is None
    assert s._slider.graphicsEffect() is None


# ------------------------------------------------------------ SegmentedControl #
def test_segmented_construction(app: QApplication) -> None:
    sc = SegmentedControl(ThemeManager(), ["Day", "Week", "Month"], current=1)
    assert sc.options() == ["Day", "Week", "Month"]
    assert sc.current_index() == 1
    assert sc.current_text() == "Week"


def test_segmented_requires_two_options(app: QApplication) -> None:
    with pytest.raises(ValueError):
        SegmentedControl(ThemeManager(), ["only"])
    sc = SegmentedControl(ThemeManager(), ["a", "b"])
    with pytest.raises(ValueError):
        sc.set_options(["x"])


def test_segmented_changed_emits(app: QApplication) -> None:
    sc = SegmentedControl(ThemeManager(), ["a", "b", "c"])
    seen = []
    sc.changed.connect(seen.append)
    sc.set_current_index(2)
    assert sc.current_index() == 2
    assert seen == [2]
    sc.set_current_index(2)  # no-op
    assert seen == [2]


def test_segmented_invalid_index_raises(app: QApplication) -> None:
    with pytest.raises(ValueError):
        SegmentedControl(ThemeManager(), ["a", "b"], current=5)
    sc = SegmentedControl(ThemeManager(), ["a", "b"])
    with pytest.raises(ValueError):
        sc.set_current_index(9)


def test_segmented_invalid_accent_raises(app: QApplication) -> None:
    with pytest.raises(ValueError):
        SegmentedControl(ThemeManager(), ["a", "b"], accent="green")
    sc = SegmentedControl(ThemeManager(), ["a", "b"])
    with pytest.raises(ValueError):
        sc.set_accent("green")


def test_segmented_accessible_name_policy(app: QApplication) -> None:
    sc = SegmentedControl(ThemeManager(), ["One", "Two"], current=0)
    assert sc.accessibleName() == "One"
    sc.setAccessibleName("Mode")
    sc.set_current_index(1)  # explicit name must win
    assert sc.accessibleName() == "Mode"


def test_segmented_no_graphics_effect(app: QApplication) -> None:
    sc = SegmentedControl(ThemeManager(), ["a", "b"])
    assert sc.graphicsEffect() is None


# --------------------------------------------------------------- Re-theming #
def test_advanced_widgets_restyle_on_theme_change(app: QApplication) -> None:
    theme = ThemeManager()
    widgets = [
        Dropdown(theme, items=["a", "b"]),
        Slider(theme),
        SegmentedControl(theme, ["a", "b"]),
    ]
    theme.set_theme("dark")  # must invoke apply_theme on all without raising
    assert len(widgets) == 3
