"""Offscreen Qt tests for the Phase 8D first application screen.

Builds the editor screen headlessly (no event loop) and asserts its structure.
Skipped entirely when PySide6 is unavailable, matching the Phase 8B/8C/8D
testing convention. Runs under the ``offscreen`` Qt platform.
"""
from __future__ import annotations

import os

import pytest

pytest.importorskip("PySide6")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from gui.screens import build_editor_screen  # noqa: E402
from gui.screens import editor_screen  # noqa: E402
from gui.theme.manager import ThemeManager  # noqa: E402
from gui.widgets import (  # noqa: E402
    FormField,
    FormSection,
    GlassCard,
    ProgressBar,
    SettingsGroup,
    StatusBadge,
)


@pytest.fixture(scope="module")
def app():
    """Provide a single QApplication for the module."""
    application = QApplication.instance() or QApplication([])
    yield application


@pytest.fixture
def theme(app):
    """Provide an applied ThemeManager (dark theme)."""
    manager = ThemeManager()
    manager.apply(app)
    return manager


def test_build_returns_widget(theme):
    screen = build_editor_screen(theme)
    assert isinstance(screen, QWidget)


def test_single_settings_group_with_four_sections(theme):
    screen = build_editor_screen(theme)
    groups = screen.findChildren(SettingsGroup)
    assert len(groups) == 1
    sections = groups[0].sections()
    assert [s.title() for s in sections] == [
        "Project Information",
        "AI Options",
        "Editing Style",
        "Intensity",
    ]


def test_section_field_counts(theme):
    screen = build_editor_screen(theme)
    group = screen.findChildren(SettingsGroup)[0]
    counts = [len(s.fields()) for s in group.sections()]
    assert counts == [3, 3, 1, 1]


def test_all_form_fields_have_non_empty_labels(theme):
    screen = build_editor_screen(theme)
    fields = screen.findChildren(FormField)
    assert fields
    assert all(f.label().strip() for f in fields)


def test_export_card_is_outside_settings_group(theme):
    screen = build_editor_screen(theme)
    group = screen.findChildren(SettingsGroup)[0]
    cards = screen.findChildren(GlassCard)
    assert cards, "expected an export GlassCard"
    # No export GlassCard is a descendant of the SettingsGroup.
    group_cards = group.findChildren(GlassCard)
    assert not group_cards


def test_export_card_contains_status_and_progress(theme):
    screen = build_editor_screen(theme)
    card = screen.findChildren(GlassCard)[0]
    assert card.findChildren(StatusBadge)
    assert card.findChildren(ProgressBar)


def test_status_and_progress_not_wrapped_in_form_field(theme):
    screen = build_editor_screen(theme)
    for field in screen.findChildren(FormField):
        assert not isinstance(field.control(), (StatusBadge, ProgressBar))


def test_only_public_builder_is_exposed():
    public = [n for n in vars(editor_screen) if not n.startswith("_")]
    # Only the builder plus imported symbols; assert no extra public helper
    # functions (helpers must be private).
    helpers = [
        n
        for n, v in vars(editor_screen).items()
        if callable(v) and not n.startswith("_") and n != "build_editor_screen"
    ]
    # Imported widget classes are callable; exclude them by module origin.
    local_helpers = [
        n
        for n in helpers
        if getattr(vars(editor_screen)[n], "__module__", "") == editor_screen.__name__
    ]
    assert local_helpers == ["build_editor_screen"]


def test_no_graphics_effect_on_form_composites(theme):
    screen = build_editor_screen(theme)
    for field in screen.findChildren(FormField):
        assert field.graphicsEffect() is None
    for section in screen.findChildren(FormSection):
        assert section.graphicsEffect() is None
    for group in screen.findChildren(SettingsGroup):
        assert group.graphicsEffect() is None
