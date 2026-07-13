"""Offscreen Qt tests for the Phase 8H Milestone 4 ClipInspector widget.

Covers object names, the empty state, show_clip / clear / current, and the
per-field text updates. Additive and independent of existing tests. Skipped
when PySide6 is unavailable; runs under the ``offscreen`` Qt platform. No
backend and no :mod:`gui_core` involvement.
"""
from __future__ import annotations

import os

import pytest

pytest.importorskip("PySide6")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from gui.theme.manager import ThemeManager  # noqa: E402
from gui.widgets import ClipInspector  # noqa: E402


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance() or QApplication([])
    yield application


@pytest.fixture
def theme(app):
    manager = ThemeManager()
    manager.apply(app)
    return manager


def _find(root, object_name):
    for child in root.findChildren(QWidget):
        if child.objectName() == object_name:
            return child
    return None


def _fields(inspector):
    return [
        w for w in inspector.findChildren(QWidget)
        if w.objectName() == "ClipInspectorField"
    ]


def _demo_clip():
    return {"track": 0, "start": 12.0, "length": 20.0, "label": "Gameplay"}


# ---------------------------------------------------------------------- #
# Structure / object names
# ---------------------------------------------------------------------- #
def test_object_names(theme):
    inspector = ClipInspector(theme)
    assert inspector.objectName() == "ClipInspector"
    assert _find(inspector, "ClipInspectorHeader") is not None
    assert _find(inspector, "ClipInspectorEmpty") is not None
    # Four field rows exist (label/track/start/length).
    assert len(_fields(inspector)) == 4


# ---------------------------------------------------------------------- #
# Empty state
# ---------------------------------------------------------------------- #
def test_starts_empty(theme):
    inspector = ClipInspector(theme)
    assert inspector.is_empty() is True
    assert inspector.current() is None


def test_empty_label_visible_fields_hidden_initially(theme):
    inspector = ClipInspector(theme)
    empty = _find(inspector, "ClipInspectorEmpty")
    # Requested-state checks (isVisible() would be False on an unshown tree),
    # so compare against the widget's own hidden flag.
    assert not empty.isHidden()
    for field in _fields(inspector):
        assert field.isHidden()


# ---------------------------------------------------------------------- #
# show_clip / current
# ---------------------------------------------------------------------- #
def test_show_clip_populates(theme):
    inspector = ClipInspector(theme)
    inspector.show_clip(_demo_clip())
    assert inspector.is_empty() is False
    current = inspector.current()
    assert current is not None
    assert current["label"] == "Gameplay"
    assert current["track"] == 0


def test_show_clip_reveals_fields_hides_empty(theme):
    inspector = ClipInspector(theme)
    inspector.show_clip(_demo_clip())
    empty = _find(inspector, "ClipInspectorEmpty")
    assert empty.isHidden()
    for field in _fields(inspector):
        assert not field.isHidden()


def test_show_clip_field_texts(theme):
    inspector = ClipInspector(theme)
    inspector.show_clip(_demo_clip())
    texts = "\n".join(f.text() for f in _fields(inspector))
    assert "Gameplay" in texts
    assert "Track: 0" in texts
    assert "Start: 12.0" in texts
    assert "Length: 20.0" in texts


def test_current_returns_copy(theme):
    inspector = ClipInspector(theme)
    clip = _demo_clip()
    inspector.show_clip(clip)
    got = inspector.current()
    got["label"] = "mutated"
    # Mutating the returned copy must not affect the stored clip.
    assert inspector.current()["label"] == "Gameplay"


# ---------------------------------------------------------------------- #
# clear / empty inputs
# ---------------------------------------------------------------------- #
def test_clear_returns_to_empty(theme):
    inspector = ClipInspector(theme)
    inspector.show_clip(_demo_clip())
    inspector.clear()
    assert inspector.is_empty() is True
    assert inspector.current() is None
    empty = _find(inspector, "ClipInspectorEmpty")
    assert not empty.isHidden()
    for field in _fields(inspector):
        assert field.isHidden()


def test_show_clip_none_is_empty_state(theme):
    inspector = ClipInspector(theme)
    inspector.show_clip(_demo_clip())
    inspector.show_clip(None)
    assert inspector.is_empty() is True


def test_show_clip_empty_mapping_is_empty_state(theme):
    inspector = ClipInspector(theme)
    inspector.show_clip(_demo_clip())
    inspector.show_clip({})
    assert inspector.is_empty() is True


def test_clear_is_idempotent(theme):
    inspector = ClipInspector(theme)
    inspector.clear()
    inspector.clear()
    assert inspector.is_empty() is True
