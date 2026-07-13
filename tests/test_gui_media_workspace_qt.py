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


# ---------------------------------------------------------------------- #
# Trim end-to-end (Phase 8H, Milestone 7; inspector stays in sync)
# ---------------------------------------------------------------------- #
def test_programmatic_trim_updates_inspector(theme):
    screen = build_media_workspace_screen(theme)
    timeline = screen.findChildren(Timeline)[0]
    inspector = screen.findChildren(ClipInspector)[0]
    # Select "Intro" (index 0, track 0, start 0.0, length 12.0).
    timeline.select_clip(0)
    assert inspector.current()["start"] == pytest.approx(0.0)

    # Count emissions from the trim only (connect after the initial select).
    selected = []
    trimmed = []
    timeline.clip_selected.connect(selected.append)
    timeline.clip_trimmed.connect(lambda i, s, ln: trimmed.append((i, s, ln)))

    timeline.trim_clip(0, start=2.0, length=8.0)

    # Full path: trim_clip -> clip_trimmed -> _on_clip_trimmed -> show_clip.
    assert inspector.is_empty() is False
    assert inspector.current() == timeline.selected_clip()
    assert inspector.current()["start"] == pytest.approx(2.0)
    assert inspector.current()["length"] == pytest.approx(8.0)
    assert inspector.current()["track"] == 0
    assert len(trimmed) == 1
    assert trimmed[0][0] == 0
    # The trim keeps the same selection, so clip_selected is not re-emitted.
    assert selected == []
    assert timeline.selected_index() == 0


def test_noop_trim_leaves_inspector_unchanged(theme):
    screen = build_media_workspace_screen(theme)
    timeline = screen.findChildren(Timeline)[0]
    inspector = screen.findChildren(ClipInspector)[0]
    timeline.select_clip(0)
    before = inspector.current()

    trimmed = []
    timeline.clip_trimmed.connect(lambda i, s, ln: trimmed.append((i, s, ln)))
    # No arguments -> values unchanged -> no-op.
    timeline.trim_clip(0)

    assert trimmed == []
    assert inspector.current() == before


def test_mouse_edge_trim_updates_inspector(theme):
    screen = build_media_workspace_screen(theme)
    timeline = screen.findChildren(Timeline)[0]
    inspector = screen.findChildren(ClipInspector)[0]
    # Select "Intro" (index 0, start 0.0, length 12.0 -> right edge 12.0).
    timeline.select_clip(0)
    frame = _clip_frame_by_label(timeline, "Intro")
    assert frame is not None
    # Give the frame a real width so the width-guarded classification treats a
    # near-left-edge press as a trim (does not depend on offscreen layout).
    frame.resize(200, 40)

    selected = []
    trimmed = []
    timeline.clip_selected.connect(selected.append)
    timeline.clip_trimmed.connect(lambda i, s, ln: trimmed.append((i, s, ln)))

    # Left-edge press, drag right past the threshold (dx = 40px -> +5.0s at
    # 8 px/s). Left trim holds the right edge (12.0) fixed.
    _press(frame, QPointF(2.0, 5.0))
    _move(frame, QPointF(42.0, 5.0))
    _release(frame, QPointF(42.0, 5.0))

    assert inspector.is_empty() is False
    assert inspector.current() == timeline.selected_clip()
    assert inspector.current()["start"] == pytest.approx(5.0)
    assert inspector.current()["length"] == pytest.approx(7.0)
    assert inspector.current()["track"] == 0
    assert len(trimmed) >= 1
    # Pressing the already-selected clip re-selects it (no-op), so the trim
    # does not re-emit clip_selected.
    assert selected == []
    assert timeline.selected_index() == 0


# ---------------------------------------------------------------------- #
# Drag-move end-to-end (Phase 8H, Milestone 6; inspector stays in sync)
# ---------------------------------------------------------------------- #
def _mouse_event(kind, local, button, buttons):
    """Build a QMouseEvent of *kind* at *local* (local == global position).

    The deprecated 5-argument constructor is used deliberately; the resulting
    DeprecationWarnings are tracked as tech debt and are not addressed in
    Milestone 6. The offscreen tests never rely on the global coordinate (the
    production _finish_drag resolves the drop destination from the release
    event's target lane).
    """
    return QMouseEvent(
        kind,
        QPointF(local),
        QPointF(local),
        button,
        buttons,
        Qt.KeyboardModifier.NoModifier,
    )


def _press(widget, local):
    QApplication.instance().sendEvent(
        widget,
        _mouse_event(
            QEvent.Type.MouseButtonPress,
            local,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
        ),
    )


def _move(widget, local):
    QApplication.instance().sendEvent(
        widget,
        _mouse_event(
            QEvent.Type.MouseMove,
            local,
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
        ),
    )


def _release(widget, local):
    QApplication.instance().sendEvent(
        widget,
        _mouse_event(
            QEvent.Type.MouseButtonRelease,
            local,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
        ),
    )


def _clip_frame_by_label(timeline, label):
    """Return the TimelineClip frame whose caption text matches *label*."""
    for frame in timeline.findChildren(QWidget):
        if frame.objectName() != "TimelineClip":
            continue
        for child in frame.findChildren(QWidget):
            if child.objectName() == "TimelineClipLabel" and child.text() == label:
                return frame
    return None


def _lane(timeline, index):
    """Return the TimelineTrack lane widget at *index* (by creation order)."""
    lanes = [
        w for w in timeline.findChildren(QWidget)
        if w.objectName() == "TimelineTrack"
    ]
    return lanes[index]


def _drag_clip_to_lane(clip_frame, dest_lane):
    """Press the clip, move past the threshold, release over *dest_lane*."""
    _press(clip_frame, QPointF(1.0, 1.0))
    _move(clip_frame, QPointF(40.0, 40.0))
    _release(dest_lane, QPointF(2.0, 2.0))


def test_dragging_clip_updates_inspector_track(theme):
    screen = build_media_workspace_screen(theme)
    timeline = screen.findChildren(Timeline)[0]
    inspector = screen.findChildren(ClipInspector)[0]
    # "Intro" is index 0 on track 0; select it so the inspector shows it.
    timeline.select_clip(0)
    assert inspector.current()["track"] == 0

    received = []
    timeline.clip_moved.connect(lambda i, t: received.append((i, t)))
    _drag_clip_to_lane(_clip_frame_by_label(timeline, "Intro"), _lane(timeline, 1))

    # Full path: drag -> move_clip -> clip_moved -> _on_clip_moved -> show_clip.
    assert received == [(0, 1)]
    assert inspector.is_empty() is False
    assert inspector.current()["label"] == "Intro"
    assert inspector.current()["track"] == 1
    assert inspector.current() == timeline.selected_clip()


def test_drag_onto_origin_track_is_noop_for_inspector(theme):
    screen = build_media_workspace_screen(theme)
    timeline = screen.findChildren(Timeline)[0]
    inspector = screen.findChildren(ClipInspector)[0]
    timeline.select_clip(0)  # "Intro" on track 0
    before = inspector.current()

    received = []
    timeline.clip_moved.connect(lambda i, t: received.append((i, t)))
    # Drop "Intro" back onto track 0.
    _drag_clip_to_lane(_clip_frame_by_label(timeline, "Intro"), _lane(timeline, 0))

    assert received == []
    assert inspector.current() == before
    assert inspector.current()["track"] == 0


def test_selection_preserved_after_drag_move(theme):
    screen = build_media_workspace_screen(theme)
    timeline = screen.findChildren(Timeline)[0]
    timeline.select_clip(0)  # "Intro"
    assert timeline.selected_index() == 0
    _drag_clip_to_lane(_clip_frame_by_label(timeline, "Intro"), _lane(timeline, 1))
    assert timeline.selected_index() == 0
    assert timeline.selected_clip()["label"] == "Intro"
    assert timeline.selected_clip()["track"] == 1


def test_drag_move_emits_no_clip_selected(theme):
    screen = build_media_workspace_screen(theme)
    timeline = screen.findChildren(Timeline)[0]
    timeline.select_clip(0)  # pre-select "Intro" (emits clip_selected once)
    # Count emissions from the drag-move only.
    selected = []
    moved = []
    timeline.clip_selected.connect(selected.append)
    timeline.clip_moved.connect(lambda i, t: moved.append((i, t)))
    _drag_clip_to_lane(_clip_frame_by_label(timeline, "Intro"), _lane(timeline, 1))
    # The moved clip stays selected, so no clip_selected is re-emitted; the
    # inspector is kept in sync solely via clip_moved.
    assert selected == []
    assert moved == [(0, 1)]
