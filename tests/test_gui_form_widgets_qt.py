"""Offscreen Qt tests for the Phase 8C-6 composite form widgets.

Covers FormField, FormSection and SettingsGroup. Skipped entirely when PySide6
is unavailable, matching the Phase 8B/8C testing convention. Runs under the
``offscreen`` Qt platform.
"""
from __future__ import annotations

import os

import pytest

pytest.importorskip("PySide6")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel, QWidget  # noqa: E402

from gui.theme.manager import ThemeManager  # noqa: E402
from gui.widgets.form_field import FormField  # noqa: E402
from gui.widgets.form_section import FormSection  # noqa: E402
from gui.widgets.settings_group import SettingsGroup  # noqa: E402
from gui.widgets.text_field import TextField  # noqa: E402


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


# ---------------------------------------------------------------------- #
# FormField
# ---------------------------------------------------------------------- #
def test_form_field_wraps_injected_control(theme):
    control = TextField(theme)
    field = FormField(theme, "Name", control)
    assert field.control() is control
    assert field.label() == "Name"


def test_form_field_rejects_non_widget_control(theme):
    with pytest.raises(TypeError):
        FormField(theme, "Bad", object())  # type: ignore[arg-type]


def test_form_field_rejects_non_str_label(theme):
    with pytest.raises(TypeError):
        FormField(theme, 123, TextField(theme))  # type: ignore[arg-type]


def test_form_field_has_no_set_control(theme):
    field = FormField(theme, "Name", TextField(theme))
    assert not hasattr(field, "set_control")


def test_form_field_label_setter(theme):
    field = FormField(theme, "Name", TextField(theme))
    field.set_label("Full name")
    assert field.label() == "Full name"


def test_form_field_helper_toggle(theme):
    field = FormField(theme, "Name", TextField(theme), helper="Enter a name")
    assert field.helper() == "Enter a name"
    field.set_helper("")
    assert field.helper() == ""


def test_form_field_required_flag(theme):
    field = FormField(theme, "Name", TextField(theme), required=True)
    assert field.is_required() is True
    assert "(required)" in field.accessibleName()
    field.set_required(False)
    assert field.is_required() is False
    assert "(required)" not in field.accessibleName()


def test_form_field_error_set_and_clear(theme):
    field = FormField(theme, "Name", TextField(theme))
    assert field.error() is None
    field.set_error("Required")
    assert field.error() == "Required"
    assert field.accessibleDescription() == "Required"
    field.set_error(None)
    assert field.error() is None
    assert field.accessibleDescription() == ""


def test_form_field_accessible_name_defaults_to_label(theme):
    field = FormField(theme, "Email", TextField(theme))
    assert field.accessibleName() == "Email"


# ---------------------------------------------------------------------- #
# FormSection
# ---------------------------------------------------------------------- #
def test_form_section_add_and_list_fields(theme):
    section = FormSection(theme, "Account")
    f1 = FormField(theme, "Name", TextField(theme))
    f2 = FormField(theme, "Email", TextField(theme))
    section.add_field(f1)
    section.add_field(f2)
    assert section.fields() == [f1, f2]


def test_form_section_rejects_non_form_field(theme):
    section = FormSection(theme, "Account")
    with pytest.raises(TypeError):
        section.add_field(QLabel("nope"))  # type: ignore[arg-type]


def test_form_section_clear(theme):
    section = FormSection(theme, "Account")
    section.add_field(FormField(theme, "Name", TextField(theme)))
    section.add_field(FormField(theme, "Email", TextField(theme)))
    section.clear()
    assert section.fields() == []


def test_form_section_title_and_subtitle(theme):
    section = FormSection(theme, "Account", subtitle="Basic info")
    assert section.title() == "Account"
    assert section.subtitle() == "Basic info"
    section.set_title("Profile")
    section.set_subtitle("Details")
    assert section.title() == "Profile"
    assert section.subtitle() == "Details"


def test_form_section_set_divider_does_not_raise(theme):
    section = FormSection(theme, "Account")
    section.set_divider(True)
    section.set_divider(False)


# ---------------------------------------------------------------------- #
# SettingsGroup
# ---------------------------------------------------------------------- #
def test_settings_group_add_and_list_sections(theme):
    group = SettingsGroup(theme)
    s1 = FormSection(theme, "Account")
    s2 = FormSection(theme, "Privacy")
    group.add_section(s1)
    group.add_section(s2)
    assert group.sections() == [s1, s2]


def test_settings_group_rejects_non_form_section(theme):
    group = SettingsGroup(theme)
    with pytest.raises(TypeError):
        group.add_section(FormField(theme, "Name", TextField(theme)))  # type: ignore[arg-type]


def test_settings_group_clear(theme):
    group = SettingsGroup(theme)
    group.add_section(FormSection(theme, "Account"))
    group.add_section(FormSection(theme, "Privacy"))
    group.clear()
    assert group.sections() == []


def test_settings_group_has_no_add_field(theme):
    group = SettingsGroup(theme)
    assert not hasattr(group, "add_field")


# ---------------------------------------------------------------------- #
# No-QGraphicsEffect policy (GlassCard safety)
# ---------------------------------------------------------------------- #
def test_composites_install_no_graphics_effect(theme):
    field = FormField(theme, "Name", TextField(theme))
    section = FormSection(theme, "Account")
    section.add_field(field)
    group = SettingsGroup(theme)
    group.add_section(section)
    assert field.graphicsEffect() is None
    assert section.graphicsEffect() is None
    assert group.graphicsEffect() is None


def test_composites_restyle_on_apply_theme(theme):
    field = FormField(theme, "Name", TextField(theme))
    section = FormSection(theme, "Account")
    section.add_field(field)
    group = SettingsGroup(theme)
    group.add_section(section)
    # Should not raise.
    field.apply_theme()
    section.apply_theme()
    group.apply_theme()
