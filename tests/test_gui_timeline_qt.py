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
