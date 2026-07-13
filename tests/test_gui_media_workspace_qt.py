"""Offscreen Qt tests for the Phase 8H Milestone 2 media workspace screen.

Builds :func:`gui.screens.media_workspace_screen.build_media_workspace_screen`
headlessly and asserts its structure, object names, embedded widgets, and the
UI-only selection wiring (selecting a media item updates the preview subtitle
and the details panel). Additive and independent of existing tests. Skipped
when PySide6 is unavailable; runs under the ``offscreen`` Qt platform. No
backend and no :mod:`gui_core` involvement.
"""
from __future__ import annotations

import os

import pytest

pytest.importorskip("PySide6")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from gui.screens.media_workspace_screen import build_media_workspace_screen  # noqa: E402
from gui.theme.manager import ThemeManager  # noqa: E402
from gui.widgets import MediaBrowser, TransportBar  # noqa: E402
from gui.widgets.section_header import SectionHeader  # noqa: E402
from gui.widgets.timeline import Timeline  # noqa: E402


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


def _preview_header(screen):
    """Return the preview SectionHeader (the one titled 'Preview')."""
    for header in screen.findChildren(SectionHeader):
        if header.title() == "Preview":
            return header
    return None


def test_build_returns_widget(theme):
    screen = build_media_workspace_screen(theme)
    assert isinstance(screen, QWidget)
    assert screen.objectName() == "MediaWorkspaceScreen"


def test_regions_present(theme):
    screen = build_media_workspace_screen(theme)
    for name in (
        "MediaWorkspacePreview",
        "MediaWorkspacePreviewStage",
        "MediaWorkspaceDetails",
    ):
        assert _find(screen, name) is not None, f"missing region: {name}"


def test_embeds_media_browser_and_transport(theme):
    screen = build_media_workspace_screen(theme)
    assert screen.findChildren(MediaBrowser)
    assert screen.findChildren(TransportBar)


def test_browser_is_seeded(theme):
    screen = build_media_workspace_screen(theme)
    browser = screen.findChildren(MediaBrowser)[0]
    assert browser.count() >= 1
    assert browser.current_index() == -1  # nothing selected initially


def test_initial_preview_subtitle_is_empty_state(theme):
    screen = build_media_workspace_screen(theme)
    header = _preview_header(screen)
    assert header is not None
    assert header.subtitle() == "No clip selected"


def test_selection_updates_preview_subtitle(theme):
    screen = build_media_workspace_screen(theme)
    browser = screen.findChildren(MediaBrowser)[0]
    header = _preview_header(screen)
    browser.select(0)
    assert header.subtitle() == browser.current_item()


def test_selection_updates_details_panel(theme):
    screen = build_media_workspace_screen(theme)
    browser = screen.findChildren(MediaBrowser)[0]
    details = _find(screen, "MediaWorkspaceDetails")
    browser.select(0)
    item = browser.current_item()
    # The details panel should now mention the selected item's name somewhere.
    from gui.widgets.meta_label import MetaLabel

    texts = [m.text() for m in details.findChildren(MetaLabel)]
    assert any(item in t for t in texts), texts


def test_clearing_selection_resets_details(theme):
    screen = build_media_workspace_screen(theme)
    browser = screen.findChildren(MediaBrowser)[0]
    header = _preview_header(screen)
    browser.select(0)
    browser.select(-1)
    assert header.subtitle() == "No clip selected"


# ---------------------------------------------------------------------- #
# Timeline integration (Phase 8H, Milestone 3)
# ---------------------------------------------------------------------- #
def test_timeline_region_present(theme):
    screen = build_media_workspace_screen(theme)
    assert _find(screen, "MediaWorkspaceTimeline") is not None


def test_embeds_timeline(theme):
    screen = build_media_workspace_screen(theme)
    assert screen.findChildren(Timeline)
