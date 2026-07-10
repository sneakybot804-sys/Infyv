"""Tests for Phase 8C-3 information/progress widgets (offscreen; skip w/o Qt).

Architecture and behavior only -- no pixel or rendering assertions.
"""
from __future__ import annotations

import os

import pytest

pytest.importorskip("PySide6", reason="PySide6 not installed; GUI tests skipped")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from gui.theme.manager import ThemeManager  # noqa: E402
from gui.widgets import (  # noqa: E402
    MetaLabel,
    ProgressBar,
    StatBlock,
    StatusBadge,
)


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


# --------------------------------------------------------------- StatusBadge #
def test_status_badge_construction_and_text(app: QApplication) -> None:
    badge = StatusBadge(ThemeManager(), "Ready", status="success")
    assert badge.text() == "Ready"
    assert badge.status() == "success"
    badge.set_text("Done")
    assert badge.text() == "Done"


def test_status_badge_set_status_valid(app: QApplication) -> None:
    badge = StatusBadge(ThemeManager())
    for status in ("neutral", "info", "success", "warning", "error"):
        badge.set_status(status)
        assert badge.status() == status


def test_status_badge_invalid_status_raises(app: QApplication) -> None:
    with pytest.raises(ValueError):
        StatusBadge(ThemeManager(), "x", status="nope")
    badge = StatusBadge(ThemeManager())
    with pytest.raises(ValueError):
        badge.set_status("critical")


def test_status_badge_no_graphics_effect(app: QApplication) -> None:
    badge = StatusBadge(ThemeManager(), "x", status="info")
    assert badge.graphicsEffect() is None


def test_status_badge_accessible_name(app: QApplication) -> None:
    badge = StatusBadge(ThemeManager(), "Live")
    assert badge.accessibleName() == "Live"


# ----------------------------------------------------------------- MetaLabel #
def test_meta_label_construction_and_text(app: QApplication) -> None:
    label = MetaLabel(ThemeManager(), "Hello", role="primary", style="h1")
    assert label.text() == "Hello"
    assert label.role() == "primary"
    assert label.style() == "h1"
    label.set_text("World")
    assert label.text() == "World"


def test_meta_label_set_role_and_style_valid(app: QApplication) -> None:
    label = MetaLabel(ThemeManager())
    for role in ("primary", "secondary", "muted", "disabled"):
        label.set_role(role)
        assert label.role() == role
    for style in (
        "display",
        "h1",
        "h2",
        "h3",
        "body",
        "body_small",
        "caption",
        "mono",
    ):
        label.set_style(style)
        assert label.style() == style


def test_meta_label_invalid_role_raises(app: QApplication) -> None:
    with pytest.raises(ValueError):
        MetaLabel(ThemeManager(), role="loud")
    label = MetaLabel(ThemeManager())
    with pytest.raises(ValueError):
        label.set_role("loud")


def test_meta_label_invalid_style_raises(app: QApplication) -> None:
    with pytest.raises(ValueError):
        MetaLabel(ThemeManager(), style="title")
    label = MetaLabel(ThemeManager())
    with pytest.raises(ValueError):
        label.set_style("title")


def test_meta_label_no_graphics_effect(app: QApplication) -> None:
    assert MetaLabel(ThemeManager(), "x").graphicsEffect() is None


# ---------------------------------------------------------------- ProgressBar #
def test_progress_bar_value_clamped(app: QApplication) -> None:
    bar = ProgressBar(ThemeManager())
    bar.set_value(0.5)
    assert bar.value() == 0.5
    bar.set_value(2.0)
    assert bar.value() == 1.0
    bar.set_value(-1.0)
    assert bar.value() == 0.0


def test_progress_bar_initial_value_clamped(app: QApplication) -> None:
    assert ProgressBar(ThemeManager(), value=5.0).value() == 1.0


def test_progress_bar_indeterminate_toggle(app: QApplication) -> None:
    bar = ProgressBar(ThemeManager())
    assert bar.is_indeterminate() is False
    bar.set_indeterminate(True)
    assert bar.is_indeterminate() is True
    bar.set_indeterminate(False)
    assert bar.is_indeterminate() is False


def test_progress_bar_accent_valid_and_invalid(app: QApplication) -> None:
    bar = ProgressBar(ThemeManager(), accent="blue")
    assert bar.accent() == "blue"
    bar.set_accent("purple")
    assert bar.accent() == "purple"
    with pytest.raises(ValueError):
        ProgressBar(ThemeManager(), accent="green")
    with pytest.raises(ValueError):
        bar.set_accent("green")


def test_progress_bar_reduce_motion_indeterminate(app: QApplication) -> None:
    # With animation disabled, an indeterminate bar must not use Qt's busy
    # (zero-length) range that drives the sweep animation.
    bar = ProgressBar(ThemeManager(), indeterminate=True, animated=False)
    assert bar._bar.minimum() != bar._bar.maximum()


def test_progress_bar_no_graphics_effect(app: QApplication) -> None:
    bar = ProgressBar(ThemeManager())
    assert bar.graphicsEffect() is None
    assert bar._bar.graphicsEffect() is None


# ------------------------------------------------------------------ StatBlock #
def test_stat_block_construction(app: QApplication) -> None:
    block = StatBlock(ThemeManager(), "Scenes", "42")
    assert block.label() == "Scenes"
    assert block.value() == "42"
    assert block.subtitle() == ""


def test_stat_block_setters(app: QApplication) -> None:
    block = StatBlock(ThemeManager(), "a", "1")
    block.set_label("Frames")
    block.set_value("1000")
    block.set_subtitle("per second")
    assert block.label() == "Frames"
    assert block.value() == "1000"
    assert block.subtitle() == "per second"


def test_stat_block_subtitle_collapses_spacing(app: QApplication) -> None:
    # Empty subtitle: row hidden and column spacing collapsed to zero.
    block = StatBlock(ThemeManager(), "a", "1")
    assert block._subtitle.isVisibleTo(block) is False
    assert block._column.spacing() == 0
    # Non-empty subtitle: row shown and spacing restored (> 0).
    block.set_subtitle("note")
    assert block._subtitle.isVisibleTo(block) is True
    assert block._column.spacing() > 0
    # Clearing again collapses spacing back to zero.
    block.set_subtitle("")
    assert block._subtitle.isVisibleTo(block) is False
    assert block._column.spacing() == 0


def test_stat_block_no_graphics_effect(app: QApplication) -> None:
    assert StatBlock(ThemeManager(), "a", "1").graphicsEffect() is None


# --------------------------------------------------------------- Re-theming #
def test_information_widgets_restyle_on_theme_change(app: QApplication) -> None:
    theme = ThemeManager()
    widgets = [
        StatusBadge(theme, "x"),
        MetaLabel(theme, "y"),
        ProgressBar(theme),
        StatBlock(theme, "a", "1"),
    ]
    theme.set_theme("dark")  # must invoke apply_theme on all without raising
    assert len(widgets) == 4
