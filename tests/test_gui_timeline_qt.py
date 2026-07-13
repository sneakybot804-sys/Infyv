"""Offscreen Qt tests for the Phase 8H Milestone 3 Timeline widget.

Covers object names, the duration/tracks/clips public API, the playhead API and
its ``playhead_changed`` signal, clamping, and invalid-duration handling.
Additive and independent of existing tests. Skipped when PySide6 is
unavailable; runs under the ``offscreen`` Qt platform. No backend and no
:mod:`gui_core` involvement.
"""
from __future__ import annotations

import os

import pytest

pytest.importorskip("PySide6")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QMouseEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from gui.theme.manager import ThemeManager  # noqa: E402
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


def _demo_clips():
    return [
        {"track": 0, "start": 0.0, "length": 12.0, "label": "Intro"},
        {"track": 0, "start": 12.0, "length": 20.0, "label": "Gameplay"},
        {"track": 1, "start": 0.0, "length": 32.0, "label": "Music"},
    ]


# ---------------------------------------------------------------------- #
# Structure / object names
# ---------------------------------------------------------------------- #
def test_object_names(theme):
    timeline = Timeline(theme)
    assert timeline.objectName() == "Timeline"
    assert _find(timeline, "TimelineRuler") is not None
    assert _find(timeline, "TimelineTracks") is not None
    assert _find(timeline, "TimelinePlayhead") is not None
    # A default track lane exists.
    assert _find(timeline, "TimelineTrack") is not None


def test_clip_object_name_after_set_clips(theme):
    timeline = Timeline(theme, tracks=["Video 1", "Audio 1"])
    timeline.set_clips(_demo_clips())
    assert _find(timeline, "TimelineClip") is not None


# ---------------------------------------------------------------------- #
# Duration API
# ---------------------------------------------------------------------- #
def test_default_duration(theme):
    timeline = Timeline(theme)
    assert timeline.duration() == pytest.approx(60.0)


def test_set_duration(theme):
    timeline = Timeline(theme)
    timeline.set_duration(120.0)
    assert timeline.duration() == pytest.approx(120.0)


def test_invalid_duration_in_ctor_raises(theme):
    with pytest.raises(ValueError):
        Timeline(theme, duration=0.0)
    with pytest.raises(ValueError):
        Timeline(theme, duration=-5.0)


def test_invalid_set_duration_raises(theme):
    timeline = Timeline(theme)
    with pytest.raises(ValueError):
        timeline.set_duration(0.0)
    with pytest.raises(ValueError):
        timeline.set_duration(-1.0)


def test_set_duration_reclamps_playhead(theme):
    timeline = Timeline(theme, duration=100.0)
    timeline.set_playhead(90.0)
    timeline.set_duration(50.0)
    assert timeline.playhead() == pytest.approx(50.0)


# ---------------------------------------------------------------------- #
# Tracks API
# ---------------------------------------------------------------------- #
def test_default_single_track(theme):
    timeline = Timeline(theme)
    assert timeline.tracks() == ["Video 1"]
    assert timeline.track_count() == 1


def test_custom_tracks(theme):
    timeline = Timeline(theme, tracks=["Video 1", "Audio 1"])
    assert timeline.tracks() == ["Video 1", "Audio 1"]
    assert timeline.track_count() == 2


def test_add_track(theme):
    timeline = Timeline(theme)
    timeline.add_track("Overlay")
    assert "Overlay" in timeline.tracks()
    assert timeline.track_count() == 2


# ---------------------------------------------------------------------- #
# Clips API
# ---------------------------------------------------------------------- #
def test_set_and_get_clips(theme):
    timeline = Timeline(theme, tracks=["Video 1", "Audio 1"])
    timeline.set_clips(_demo_clips())
    assert timeline.clip_count() == 3
    labels = [c.get("label") for c in timeline.clips()]
    assert labels == ["Intro", "Gameplay", "Music"]


def test_clips_on_unknown_track_ignored(theme):
    timeline = Timeline(theme, tracks=["Video 1"])  # only track 0 exists
    timeline.set_clips(
        [
            {"track": 0, "start": 0.0, "length": 5.0, "label": "ok"},
            {"track": 9, "start": 0.0, "length": 5.0, "label": "ignored"},
        ]
    )
    # clips() returns the stored descriptors; the rendered blocks skip unknown
    # tracks, so only one TimelineClip frame should exist.
    rendered = [
        w for w in timeline.findChildren(QWidget)
        if w.objectName() == "TimelineClip"
    ]
    assert len(rendered) == 1


def test_set_clips_replaces_previous(theme):
    timeline = Timeline(theme, tracks=["Video 1"])
    timeline.set_clips([{"track": 0, "start": 0.0, "length": 5.0, "label": "a"}])
    timeline.set_clips([{"track": 0, "start": 0.0, "length": 5.0, "label": "b"}])
    labels = [c.get("label") for c in timeline.clips()]
    assert labels == ["b"]


# ---------------------------------------------------------------------- #
# Playhead API + signal + clamping
# ---------------------------------------------------------------------- #
def test_playhead_default_zero(theme):
    timeline = Timeline(theme)
    assert timeline.playhead() == pytest.approx(0.0)


def test_set_playhead_emits_signal(theme):
    timeline = Timeline(theme, duration=60.0)
    received = []
    timeline.playhead_changed.connect(received.append)
    timeline.set_playhead(30.0)
    assert received == [pytest.approx(30.0)]
    assert timeline.playhead() == pytest.approx(30.0)


def test_set_playhead_noop_when_unchanged(theme):
    timeline = Timeline(theme)
    timeline.set_playhead(10.0)
    received = []
    timeline.playhead_changed.connect(received.append)
    timeline.set_playhead(10.0)
    assert received == []


def test_set_playhead_clamps_high(theme):
    timeline = Timeline(theme, duration=60.0)
    timeline.set_playhead(999.0)
    assert timeline.playhead() == pytest.approx(60.0)


def test_set_playhead_clamps_low(theme):
    timeline = Timeline(theme, duration=60.0)
    timeline.set_playhead(30.0)
    timeline.set_playhead(-5.0)
    assert timeline.playhead() == pytest.approx(0.0)


# ---------------------------------------------------------------------- #
# Clip selection (Phase 8H, Milestone 4; programmatic only)
# ---------------------------------------------------------------------- #
def _selectable_timeline(theme):
    timeline = Timeline(theme, tracks=["Video 1", "Audio 1"])
    timeline.set_clips(_demo_clips())
    return timeline


def test_default_no_selection(theme):
    timeline = _selectable_timeline(theme)
    assert timeline.selected_index() == -1
    assert timeline.selected_clip() is None


def test_select_clip_sets_state(theme):
    timeline = _selectable_timeline(theme)
    timeline.select_clip(1)
    assert timeline.selected_index() == 1
    clip = timeline.selected_clip()
    assert clip is not None
    assert clip["label"] == "Gameplay"


def test_select_clip_emits_signal(theme):
    timeline = _selectable_timeline(theme)
    received = []
    timeline.clip_selected.connect(received.append)
    timeline.select_clip(2)
    assert received == [2]


def test_select_clip_noop_when_unchanged(theme):
    timeline = _selectable_timeline(theme)
    timeline.select_clip(0)
    received = []
    timeline.clip_selected.connect(received.append)
    timeline.select_clip(0)
    assert received == []


def test_clear_selection_resets_and_emits(theme):
    timeline = _selectable_timeline(theme)
    timeline.select_clip(1)
    received = []
    timeline.clip_selected.connect(received.append)
    timeline.clear_selection()
    assert timeline.selected_index() == -1
    assert timeline.selected_clip() is None
    assert received == [-1]


def test_clear_selection_noop_when_empty(theme):
    timeline = _selectable_timeline(theme)
    received = []
    timeline.clip_selected.connect(received.append)
    timeline.clear_selection()
    assert received == []


def test_select_clip_minus_one_clears(theme):
    timeline = _selectable_timeline(theme)
    timeline.select_clip(0)
    timeline.select_clip(-1)
    assert timeline.selected_index() == -1
    assert timeline.selected_clip() is None


def test_select_clip_out_of_range_raises(theme):
    timeline = _selectable_timeline(theme)
    with pytest.raises(ValueError):
        timeline.select_clip(99)


def test_set_clips_clears_selection_and_emits(theme):
    timeline = _selectable_timeline(theme)
    timeline.select_clip(1)
    received = []
    timeline.clip_selected.connect(received.append)
    timeline.set_clips(_demo_clips())
    assert timeline.selected_index() == -1
    assert received == [-1]


def test_set_clips_no_emit_when_no_prior_selection(theme):
    timeline = _selectable_timeline(theme)
    received = []
    timeline.clip_selected.connect(received.append)
    timeline.set_clips(_demo_clips())
    assert received == []


# ---------------------------------------------------------------------- #
# Click-to-select (Phase 8H, Milestone 5; mouse interaction)
# ---------------------------------------------------------------------- #
def _left_click(widget):
    """Dispatch a synthetic left-button press to *widget*.

    Geometry-free and offscreen-safe: the QMouseEvent is delivered straight to
    the target with QApplication.sendEvent, so Timeline's installed event
    filter runs regardless of widget visibility or layout geometry (the widgets
    are never shown in these tests). Selection triggers on MouseButtonPress.
    """
    event = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(1.0, 1.0),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.instance().sendEvent(widget, event)


def _clip_frame(timeline, label):
    """Return the TimelineClip frame whose label caption matches *label*.

    Located by caption text rather than child-traversal order so the tests do
    not depend on findChildren ordering.
    """
    for frame in timeline.findChildren(QWidget):
        if frame.objectName() != "TimelineClip":
            continue
        for child in frame.findChildren(QWidget):
            if (
                child.objectName() == "TimelineClipLabel"
                and child.text() == label
            ):
                return frame
    return None


def test_click_clip_selects_it(theme):
    timeline = _selectable_timeline(theme)
    received = []
    timeline.clip_selected.connect(received.append)
    frame = _clip_frame(timeline, "Gameplay")
    assert frame is not None
    _left_click(frame)
    assert timeline.selected_index() == 1
    assert timeline.selected_clip()["label"] == "Gameplay"
    assert received == [1]


def test_click_another_clip_moves_selection(theme):
    timeline = _selectable_timeline(theme)
    _left_click(_clip_frame(timeline, "Intro"))
    assert timeline.selected_index() == 0
    received = []
    timeline.clip_selected.connect(received.append)
    _left_click(_clip_frame(timeline, "Music"))
    assert timeline.selected_index() == 2
    assert timeline.selected_clip()["label"] == "Music"
    assert received == [2]


def test_click_empty_space_clears_selection(theme):
    timeline = _selectable_timeline(theme)
    _left_click(_clip_frame(timeline, "Intro"))
    assert timeline.selected_index() == 0
    received = []
    timeline.clip_selected.connect(received.append)
    tracks_bg = _find(timeline, "TimelineTracks")
    assert tracks_bg is not None
    _left_click(tracks_bg)
    assert timeline.selected_index() == -1
    assert timeline.selected_clip() is None
    assert received == [-1]


def test_click_empty_lane_clears_selection(theme):
    timeline = _selectable_timeline(theme)
    _left_click(_clip_frame(timeline, "Intro"))
    assert timeline.selected_index() == 0
    received = []
    timeline.clip_selected.connect(received.append)
    lane = _find(timeline, "TimelineTrack")
    assert lane is not None
    _left_click(lane)
    assert timeline.selected_index() == -1
    assert received == [-1]


def test_click_selected_clip_is_noop(theme):
    timeline = _selectable_timeline(theme)
    _left_click(_clip_frame(timeline, "Gameplay"))
    assert timeline.selected_index() == 1
    received = []
    timeline.clip_selected.connect(received.append)
    _left_click(_clip_frame(timeline, "Gameplay"))
    assert timeline.selected_index() == 1
    assert received == []


# ---------------------------------------------------------------------- #
# Drag & drop foundation (Phase 8H, Milestone 6; track-only move)
# ---------------------------------------------------------------------- #
def _mouse_event(kind, widget, local, button, buttons):
    """Build a QMouseEvent of *kind* at *local* on *widget*.

    The deprecated 5-argument constructor is used deliberately; the resulting
    DeprecationWarnings are tracked as tech debt and are not addressed in
    Milestone 6.
    """
    # Local and global positions are both QPointF(local): the offscreen tests
    # never rely on the global coordinate (the production _finish_drag resolves
    # the drop destination from the release event's target lane).
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
            widget,
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
            widget,
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
            widget,
            local,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
        ),
    )


def _drag_clip_to_lane(timeline, clip_frame, dest_lane):
    """Press the clip, move past the threshold, release over *dest_lane*.

    The release is delivered to the destination lane so the production
    _finish_drag resolves the destination from the event target's lane
    ancestry (geometry-free / offscreen-safe).
    """
    _press(clip_frame, QPointF(1.0, 1.0))
    # A far move crosses the widget's movement threshold and activates drag.
    _move(clip_frame, QPointF(40.0, 40.0))
    _release(dest_lane, QPointF(2.0, 2.0))


def _lane(timeline, index):
    """Return the TimelineTrack lane widget at *index* (by creation order)."""
    lanes = [
        w for w in timeline.findChildren(QWidget)
        if w.objectName() == "TimelineTrack"
    ]
    return lanes[index]


def test_drag_across_tracks_updates_model(theme):
    timeline = _selectable_timeline(theme)
    # "Intro" is index 0 on track 0; drag it to track 1.
    received = []
    timeline.clip_moved.connect(lambda i, t: received.append((i, t)))
    _drag_clip_to_lane(timeline, _clip_frame(timeline, "Intro"), _lane(timeline, 1))
    moved = timeline.clips()[0]
    assert moved["label"] == "Intro"
    assert moved["track"] == 1
    # Only the track changed; start/length are untouched.
    assert moved["start"] == pytest.approx(0.0)
    assert moved["length"] == pytest.approx(12.0)
    assert received == [(0, 1)]


def test_drag_emits_clip_moved_once(theme):
    timeline = _selectable_timeline(theme)
    received = []
    timeline.clip_moved.connect(lambda i, t: received.append((i, t)))
    _drag_clip_to_lane(timeline, _clip_frame(timeline, "Intro"), _lane(timeline, 1))
    assert len(received) == 1


def test_drop_on_origin_track_is_noop(theme):
    timeline = _selectable_timeline(theme)
    before = timeline.clips()
    received = []
    timeline.clip_moved.connect(lambda i, t: received.append((i, t)))
    # "Intro" is on track 0; drop it back on track 0.
    _drag_clip_to_lane(timeline, _clip_frame(timeline, "Intro"), _lane(timeline, 0))
    assert timeline.clips() == before
    assert received == []


def test_selection_preserved_after_move(theme):
    timeline = _selectable_timeline(theme)
    timeline.select_clip(0)  # select "Intro"
    assert timeline.selected_index() == 0
    _drag_clip_to_lane(timeline, _clip_frame(timeline, "Intro"), _lane(timeline, 1))
    assert timeline.selected_index() == 0
    assert timeline.selected_clip()["label"] == "Intro"
    assert timeline.selected_clip()["track"] == 1


def test_is_dragging_false_before_and_after(theme):
    timeline = _selectable_timeline(theme)
    assert timeline.is_dragging() is False
    _drag_clip_to_lane(timeline, _clip_frame(timeline, "Intro"), _lane(timeline, 1))
    assert timeline.is_dragging() is False


def test_drop_target_property_set_and_cleared(theme):
    timeline = _selectable_timeline(theme)
    lane = _lane(timeline, 1)
    # Exercise the production preview mechanism directly (geometry-free).
    timeline._set_drop_target(lane)
    assert lane.property("dropTarget") is True
    timeline._set_drop_target(None)
    assert lane.property("dropTarget") is False


def test_subthreshold_drag_behaves_as_click(theme):
    timeline = _selectable_timeline(theme)
    received = []
    timeline.clip_moved.connect(lambda i, t: received.append((i, t)))
    before = timeline.clips()
    frame = _clip_frame(timeline, "Gameplay")  # index 1
    _press(frame, QPointF(1.0, 1.0))
    # A tiny move (below the threshold) must not activate a drag.
    _move(frame, QPointF(2.0, 2.0))
    _release(frame, QPointF(2.0, 2.0))
    # Behaves as a plain click: selected, no move committed, model unchanged.
    assert timeline.selected_index() == 1
    assert received == []
    assert timeline.clips() == before


# ---------------------------------------------------------------------- #
# Clip trim (Phase 8H, Milestone 7; start/length edge resize)
# ---------------------------------------------------------------------- #
def test_trim_clip_updates_only_start_and_length(theme):
    timeline = _selectable_timeline(theme)
    # "Intro": index 0, track 0, start 0.0, length 12.0.
    timeline.trim_clip(0, start=2.0, length=8.0)
    clip = timeline.clips()[0]
    assert clip["start"] == pytest.approx(2.0)
    assert clip["length"] == pytest.approx(8.0)
    # Track and label are untouched.
    assert clip["track"] == 0
    assert clip["label"] == "Intro"


def test_trim_clip_track_unchanged(theme):
    timeline = _selectable_timeline(theme)
    # "Music": index 2, track 1.
    timeline.trim_clip(2, length=10.0)
    assert timeline.clips()[2]["track"] == 1


def test_trim_clip_emits_clip_trimmed_once(theme):
    timeline = _selectable_timeline(theme)
    received = []
    timeline.clip_trimmed.connect(lambda i, s, ln: received.append((i, s, ln)))
    timeline.trim_clip(0, start=1.0, length=5.0)
    assert received == [(0, pytest.approx(1.0), pytest.approx(5.0))]


def test_trim_clip_no_emit_when_unchanged(theme):
    timeline = _selectable_timeline(theme)
    received = []
    timeline.clip_trimmed.connect(lambda i, s, ln: received.append((i, s, ln)))
    # No arguments -> values keep their current value -> no-op.
    timeline.trim_clip(0)
    # Explicitly passing the current values is also a no-op.
    timeline.trim_clip(0, start=0.0, length=12.0)
    assert received == []


def test_trim_clip_out_of_range_raises(theme):
    timeline = _selectable_timeline(theme)
    with pytest.raises(ValueError):
        timeline.trim_clip(99, length=5.0)


def test_trim_clip_clamps_start_non_negative(theme):
    timeline = _selectable_timeline(theme)
    timeline.trim_clip(0, start=-5.0)
    assert timeline.clips()[0]["start"] == pytest.approx(0.0)


def test_trim_clip_clamps_min_length(theme):
    timeline = _selectable_timeline(theme)
    timeline.trim_clip(0, length=0.2)
    assert timeline.clips()[0]["length"] == pytest.approx(1.0)


def test_trim_clip_clamps_within_duration(theme):
    timeline = _selectable_timeline(theme)  # duration 60.0
    # start 55 + length 20 = 75 > 60: keep start, shrink length to fit.
    timeline.trim_clip(0, start=55.0, length=20.0)
    clip = timeline.clips()[0]
    assert clip["start"] == pytest.approx(55.0)
    assert clip["length"] == pytest.approx(5.0)
    assert clip["start"] + clip["length"] <= 60.0 + 1e-9


def test_trim_clip_min_length_wins_at_end_of_timeline(theme):
    timeline = _selectable_timeline(theme)  # duration 60.0
    # start 59.5 + length 20 = 79.5 > 60; fit would give length 0.5 < 1.0, so
    # length is held at 1.0 and start pulled back to 59.0.
    timeline.trim_clip(0, start=59.5, length=20.0)
    clip = timeline.clips()[0]
    assert clip["length"] == pytest.approx(1.0)
    assert clip["start"] == pytest.approx(59.0)


def test_trim_left_edge_keeps_right_edge_fixed(theme):
    timeline = _selectable_timeline(theme)
    # "Intro": start 0, length 12 -> right edge at 12. Move the left edge to 3.
    right_edge = 0.0 + 12.0
    timeline.trim_clip(0, start=3.0, length=right_edge - 3.0)
    clip = timeline.clips()[0]
    assert clip["start"] == pytest.approx(3.0)
    assert clip["start"] + clip["length"] == pytest.approx(right_edge)


def test_trim_right_edge_keeps_left_edge_fixed(theme):
    timeline = _selectable_timeline(theme)
    # "Intro": start 0, length 12. Extend the right edge (length only).
    timeline.trim_clip(0, length=15.0)
    clip = timeline.clips()[0]
    assert clip["start"] == pytest.approx(0.0)
    assert clip["length"] == pytest.approx(15.0)


def test_edge_drag_trims_and_emits_clip_trimmed(theme):
    timeline = _selectable_timeline(theme)
    frame = _clip_frame(timeline, "Intro")  # index 0, start 0, length 12
    # Give the frame a real width so the width-guarded classification treats a
    # near-left-edge press as a trim (does not depend on offscreen layout).
    frame.resize(200, 40)
    received = []
    timeline.clip_trimmed.connect(lambda i, s, ln: received.append((i, s, ln)))
    # Press near the left edge, drag right past the threshold (dx = 40px ->
    # +5.0s at 8 px/s). Left trim holds the right edge (12.0) fixed.
    _press(frame, QPointF(2.0, 5.0))
    _move(frame, QPointF(42.0, 5.0))
    _release(frame, QPointF(42.0, 5.0))
    clip = timeline.clips()[0]
    assert clip["start"] == pytest.approx(5.0)
    assert clip["start"] + clip["length"] == pytest.approx(12.0)
    assert len(received) >= 1
    # The final emission reflects the committed start/length.
    assert received[-1][0] == 0
    assert received[-1][1] == pytest.approx(5.0)
    assert received[-1][2] == pytest.approx(7.0)


def test_is_trimming_transitions(theme):
    timeline = _selectable_timeline(theme)
    frame = _clip_frame(timeline, "Intro")
    frame.resize(200, 40)
    assert timeline.is_trimming() is False
    _press(frame, QPointF(2.0, 5.0))
    _move(frame, QPointF(42.0, 5.0))
    # Mid-drag, before release, a trim is in progress.
    assert timeline.is_trimming() is True
    _release(frame, QPointF(42.0, 5.0))
    assert timeline.is_trimming() is False


def test_center_click_still_selects_after_trim_feature(theme):
    timeline = _selectable_timeline(theme)
    received = []
    timeline.clip_trimmed.connect(lambda i, s, ln: received.append((i, s, ln)))
    before = timeline.clips()
    _left_click(_clip_frame(timeline, "Gameplay"))  # index 1
    # M5 behavior intact: selects, no trim, model unchanged.
    assert timeline.selected_index() == 1
    assert received == []
    assert timeline.clips() == before


def test_center_drag_still_moves_after_trim_feature(theme):
    timeline = _selectable_timeline(theme)
    moved = []
    trimmed = []
    timeline.clip_moved.connect(lambda i, t: moved.append((i, t)))
    timeline.clip_trimmed.connect(lambda i, s, ln: trimmed.append((i, s, ln)))
    # A zero-width offscreen frame classifies as move (width guard), so the
    # existing drag helper still performs a track move (M6), not a trim.
    _drag_clip_to_lane(timeline, _clip_frame(timeline, "Intro"), _lane(timeline, 1))
    assert timeline.clips()[0]["track"] == 1
    assert moved == [(0, 1)]
    assert trimmed == []


# ---------------------------------------------------------------------- #
# Zoom (Phase 8H, Milestone 8; rendering-only)
# ---------------------------------------------------------------------- #
class _WheelStub:
    """Minimal stand-in for a wheel event.

    Exposes only what Timeline.wheelEvent reads: angleDelta().y() and accept().
    Used to drive the real production wheelEvent without depending on the
    version-specific QWheelEvent constructor.
    """

    class _Delta:
        def __init__(self, y):
            self._y = y

        def y(self):
            return self._y

    def __init__(self, y):
        self._delta = self._Delta(y)

    def angleDelta(self):  # noqa: N802 (mimics the Qt API)
        return self._delta

    def accept(self):
        pass


def _clip_min_width(timeline, label):
    """Return the minimum width of the TimelineClip frame captioned *label*."""
    return _clip_frame(timeline, label).minimumWidth()


def test_zoom_level_default(theme):
    timeline = _selectable_timeline(theme)
    assert timeline.zoom_level() == pytest.approx(1.0)


def test_zoom_in_increases_level_and_emits(theme):
    timeline = _selectable_timeline(theme)
    received = []
    timeline.zoom_changed.connect(received.append)
    timeline.zoom_in()
    assert timeline.zoom_level() == pytest.approx(1.25)
    assert received == [pytest.approx(1.25)]


def test_zoom_out_decreases_level_and_emits(theme):
    timeline = _selectable_timeline(theme)
    received = []
    timeline.zoom_changed.connect(received.append)
    timeline.zoom_out()
    assert timeline.zoom_level() == pytest.approx(1.0 / 1.25)
    assert received == [pytest.approx(1.0 / 1.25)]


def test_set_zoom_clamps_to_max(theme):
    timeline = _selectable_timeline(theme)
    timeline.set_zoom(100.0)
    assert timeline.zoom_level() == pytest.approx(4.0)


def test_set_zoom_clamps_to_min(theme):
    timeline = _selectable_timeline(theme)
    timeline.set_zoom(0.001)
    assert timeline.zoom_level() == pytest.approx(0.25)


def test_set_zoom_noop_when_unchanged(theme):
    timeline = _selectable_timeline(theme)
    received = []
    timeline.zoom_changed.connect(received.append)
    timeline.set_zoom(1.0)  # already the default
    assert received == []
    assert timeline.zoom_level() == pytest.approx(1.0)


def test_fit_to_contents_resets_and_emits(theme):
    timeline = _selectable_timeline(theme)
    timeline.set_zoom(2.0)
    received = []
    timeline.zoom_changed.connect(received.append)
    timeline.fit_to_contents()
    assert timeline.zoom_level() == pytest.approx(1.0)
    assert received == [pytest.approx(1.0)]


def test_fit_to_contents_noop_when_already_fit(theme):
    timeline = _selectable_timeline(theme)
    received = []
    timeline.zoom_changed.connect(received.append)
    timeline.fit_to_contents()  # already at 1.0
    assert received == []


def test_zoom_redraws_wider_clip_blocks(theme):
    timeline = _selectable_timeline(theme)
    base = _clip_min_width(timeline, "Intro")
    timeline.set_zoom(2.0)
    zoomed = _clip_min_width(timeline, "Intro")
    # Strategy A: a redraw at higher zoom widens the rendered clip block.
    assert zoomed > base


def test_wheel_up_zooms_in(theme):
    timeline = _selectable_timeline(theme)
    timeline.wheelEvent(_WheelStub(120))
    assert timeline.zoom_level() == pytest.approx(1.25)


def test_wheel_down_zooms_out(theme):
    timeline = _selectable_timeline(theme)
    timeline.wheelEvent(_WheelStub(-120))
    assert timeline.zoom_level() == pytest.approx(1.0 / 1.25)


def test_zoom_preserves_selection_and_emits_no_clip_signals(theme):
    timeline = _selectable_timeline(theme)
    timeline.select_clip(1)  # "Gameplay"
    selected = []
    moved = []
    trimmed = []
    timeline.clip_selected.connect(selected.append)
    timeline.clip_moved.connect(lambda i, t: moved.append((i, t)))
    timeline.clip_trimmed.connect(lambda i, s, ln: trimmed.append((i, s, ln)))
    timeline.set_zoom(2.0)
    # Zoom is rendering-only: selection survives the redraw and no clip signal
    # fires.
    assert timeline.selected_index() == 1
    assert timeline.selected_clip()["label"] == "Gameplay"
    assert selected == []
    assert moved == []
    assert trimmed == []


# ---------------------------------------------------------------------- #
# Playback & playhead (Phase 8H, Milestone 9)
# ---------------------------------------------------------------------- #
class _KeyStub:
    """Minimal stand-in for a key event (key() + accept())."""

    def __init__(self, key):
        self._key = key

    def key(self):
        return self._key

    def accept(self):
        pass


class _PosStub:
    """Minimal stand-in for a mouse event exposing position().x() / accept()."""

    class _Pos:
        def __init__(self, x):
            self._x = x

        def x(self):
            return self._x

    def __init__(self, x):
        self._pos = self._Pos(x)

    def position(self):
        return self._pos

    def accept(self):
        pass


def test_playback_state_default(theme):
    timeline = _selectable_timeline(theme)
    assert timeline.playback_state() == "stopped"
    assert timeline.is_playing() is False


def test_play_sets_playing_and_emits(theme):
    timeline = _selectable_timeline(theme)
    received = []
    timeline.playback_state_changed.connect(received.append)
    timeline.play()
    assert timeline.is_playing() is True
    assert timeline.playback_state() == "playing"
    assert received == ["playing"]
    # A second play is a no-op (no duplicate emission).
    timeline.play()
    assert received == ["playing"]
    timeline.stop()  # leave the timer stopped


def test_pause_from_playing_emits_once(theme):
    timeline = _selectable_timeline(theme)
    timeline.play()
    received = []
    timeline.playback_state_changed.connect(received.append)
    timeline.pause()
    assert timeline.playback_state() == "paused"
    assert received == ["paused"]
    # Pausing when not playing is a no-op.
    timeline.pause()
    assert received == ["paused"]


def test_stop_resets_playhead(theme):
    timeline = _selectable_timeline(theme)
    timeline.set_playhead(20.0)
    timeline.play()
    received = []
    timeline.playback_state_changed.connect(received.append)
    timeline.stop()
    assert timeline.playback_state() == "stopped"
    assert timeline.playhead() == pytest.approx(0.0)
    assert received == ["stopped"]


def test_toggle_play_toggles(theme):
    timeline = _selectable_timeline(theme)
    timeline.toggle_play()
    assert timeline.is_playing() is True
    timeline.toggle_play()
    assert timeline.playback_state() == "paused"
    timeline.stop()


def test_tick_advances_playhead(theme):
    timeline = _selectable_timeline(theme)
    timeline.set_playhead(0.0)
    received = []
    timeline.playhead_changed.connect(received.append)
    timeline._on_play_tick()
    assert timeline.playhead() > 0.0
    assert len(received) == 1


def test_tick_at_end_stops_and_finishes(theme):
    timeline = Timeline(theme, duration=10.0, tracks=["Video 1", "Audio 1"])
    timeline.set_clips(_demo_clips())
    timeline.set_playhead(10.0)
    timeline.play()
    finished = []
    states = []
    timeline.playback_finished.connect(lambda: finished.append(True))
    timeline.playback_state_changed.connect(states.append)
    timeline._on_play_tick()
    assert timeline.playhead() == pytest.approx(10.0)
    assert timeline.playback_state() == "stopped"
    assert finished == [True]
    assert states == ["stopped"]


def test_play_from_end_restarts_at_zero(theme):
    timeline = Timeline(theme, duration=10.0, tracks=["Video 1", "Audio 1"])
    timeline.set_clips(_demo_clips())
    timeline.set_playhead(10.0)
    timeline.play()
    assert timeline.playhead() == pytest.approx(0.0)
    timeline.stop()


def test_current_time_reflects_playhead(theme):
    timeline = _selectable_timeline(theme)
    timeline.set_playhead(7.5)
    assert timeline.current_time() == pytest.approx(7.5)


def test_space_key_toggles_play(theme):
    timeline = _selectable_timeline(theme)
    timeline.keyPressEvent(_KeyStub(Qt.Key.Key_Space))
    assert timeline.is_playing() is True
    timeline.keyPressEvent(_KeyStub(Qt.Key.Key_Space))
    assert timeline.playback_state() == "paused"
    timeline.stop()


def test_home_key_seeks_to_zero(theme):
    timeline = _selectable_timeline(theme)
    timeline.set_playhead(30.0)
    timeline.keyPressEvent(_KeyStub(Qt.Key.Key_Home))
    assert timeline.playhead() == pytest.approx(0.0)


def test_end_key_seeks_to_duration(theme):
    timeline = Timeline(theme, duration=45.0, tracks=["Video 1", "Audio 1"])
    timeline.set_clips(_demo_clips())
    timeline.keyPressEvent(_KeyStub(Qt.Key.Key_End))
    assert timeline.playhead() == pytest.approx(45.0)


def test_ruler_seek_maps_fraction_to_time(theme):
    timeline = Timeline(theme, duration=100.0, tracks=["Video 1", "Audio 1"])
    timeline.set_clips(_demo_clips())
    # Give the ruler a real width so the x -> time mapping is deterministic.
    timeline._ruler.resize(200, 20)
    timeline._seek_from_ruler(_PosStub(50.0))  # 50 / 200 = 0.25 -> 25.0s
    assert timeline.playhead() == pytest.approx(25.0)


def test_ruler_seek_zero_width_is_noop(theme):
    timeline = Timeline(theme, duration=100.0, tracks=["Video 1", "Audio 1"])
    timeline.set_clips(_demo_clips())
    timeline._ruler.resize(0, 20)
    timeline.set_playhead(10.0)
    timeline._seek_from_ruler(_PosStub(50.0))
    # No usable width -> no change.
    assert timeline.playhead() == pytest.approx(10.0)


def test_playback_emits_no_clip_signals_and_preserves_selection(theme):
    timeline = _selectable_timeline(theme)
    timeline.select_clip(1)  # "Gameplay"
    selected = []
    moved = []
    trimmed = []
    timeline.clip_selected.connect(selected.append)
    timeline.clip_moved.connect(lambda i, t: moved.append((i, t)))
    timeline.clip_trimmed.connect(lambda i, s, ln: trimmed.append((i, s, ln)))
    timeline.play()
    timeline._on_play_tick()
    timeline.pause()
    timeline.set_playhead(5.0)
    # Playback/seek is playhead-only: no clip signal fires, selection intact.
    assert selected == []
    assert moved == []
    assert trimmed == []
    assert timeline.selected_index() == 1
    timeline.stop()
