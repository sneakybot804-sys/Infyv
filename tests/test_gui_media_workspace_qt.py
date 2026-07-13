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

from PySide6.QtCore import QEvent, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QMouseEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from gui.screens.media_workspace_screen import build_media_workspace_screen  # noqa: E402
from gui.theme.manager import ThemeManager  # noqa: E402
from gui.widgets import ClipInspector, MediaBrowser, TransportBar  # noqa: E402
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


# ---------------------------------------------------------------------- #
# Clip inspector integration (Phase 8H, Milestone 4)
# ---------------------------------------------------------------------- #
def test_inspector_region_present(theme):
    screen = build_media_workspace_screen(theme)
    assert _find(screen, "MediaWorkspaceInspector") is not None


def test_embeds_clip_inspector(theme):
    screen = build_media_workspace_screen(theme)
    assert screen.findChildren(ClipInspector)


def test_inspector_starts_empty(theme):
    screen = build_media_workspace_screen(theme)
    inspector = screen.findChildren(ClipInspector)[0]
    assert inspector.is_empty() is True


def test_selecting_timeline_clip_updates_inspector(theme):
    screen = build_media_workspace_screen(theme)
    timeline = screen.findChildren(Timeline)[0]
    inspector = screen.findChildren(ClipInspector)[0]
    # The screen seeds the timeline with clips; select the first one.
    timeline.select_clip(0)
    assert inspector.is_empty() is False
    assert inspector.current() == timeline.selected_clip()


def test_clearing_timeline_selection_empties_inspector(theme):
    screen = build_media_workspace_screen(theme)
    timeline = screen.findChildren(Timeline)[0]
    inspector = screen.findChildren(ClipInspector)[0]
    timeline.select_clip(0)
    timeline.clear_selection()
    assert inspector.is_empty() is True


# ---------------------------------------------------------------------- #
# Click-to-select end-to-end (Phase 8H, Milestone 5)
# ---------------------------------------------------------------------- #
def _left_click(widget):
    """Dispatch a synthetic left-button press to *widget*.

    Geometry-free and offscreen-safe (matches the timeline click tests): the
    QMouseEvent is delivered straight to the target with
    QApplication.sendEvent, so the embedded Timeline's installed event filter
    runs regardless of visibility or layout geometry (the screen is never
    shown). Selection triggers on MouseButtonPress.
    """
    event = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(1.0, 1.0),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.instance().sendEvent(widget, event)


def _first_clip_frame(timeline):
    """Return the first rendered TimelineClip frame in *timeline*, or None."""
    for frame in timeline.findChildren(QWidget):
        if frame.objectName() == "TimelineClip":
            return frame
    return None


def test_clicking_timeline_clip_updates_inspector(theme):
    screen = build_media_workspace_screen(theme)
    timeline = screen.findChildren(Timeline)[0]
    inspector = screen.findChildren(ClipInspector)[0]
    assert inspector.is_empty() is True

    received = []
    timeline.clip_selected.connect(received.append)

    frame = _first_clip_frame(timeline)
    assert frame is not None, "screen should seed the timeline with clips"
    _left_click(frame)

    # Full path: click -> selection -> clip_selected -> inspector update.
    assert timeline.selected_index() != -1
    assert len(received) == 1
    assert received[0] == timeline.selected_index()
    assert inspector.is_empty() is False
    assert inspector.current() == timeline.selected_clip()


def test_clicking_empty_timeline_space_empties_inspector(theme):
    screen = build_media_workspace_screen(theme)
    timeline = screen.findChildren(Timeline)[0]
    inspector = screen.findChildren(ClipInspector)[0]

    _left_click(_first_clip_frame(timeline))
    assert inspector.is_empty() is False

    tracks_bg = _find(timeline, "TimelineTracks")
    assert tracks_bg is not None
    _left_click(tracks_bg)

    assert timeline.selected_index() == -1
    assert inspector.is_empty() is True
