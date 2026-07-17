"""Unit tests for the immutable, Qt-free gui_core Timeline data model."""
from __future__ import annotations

import pytest

from gui_core.timeline import Clip, Marker, Timeline, Track


# ---------------------------------------------------------------------- #
# Value-type validation
# ---------------------------------------------------------------------- #
def test_marker_validation():
    Marker(id="m1", time=0.0)
    with pytest.raises(ValueError):
        Marker(id="", time=1.0)
    with pytest.raises(ValueError):
        Marker(id="m1", time=-1.0)


def test_clip_validation_and_end():
    clip = Clip(id="c1", track_index=0, start=2.0, length=3.0)
    assert clip.end == 5.0
    with pytest.raises(ValueError):
        Clip(id="", track_index=0, start=0.0, length=1.0)
    with pytest.raises(ValueError):
        Clip(id="c", track_index=-1, start=0.0, length=1.0)
    with pytest.raises(ValueError):
        Clip(id="c", track_index=0, start=-1.0, length=1.0)
    with pytest.raises(ValueError):
        Clip(id="c", track_index=0, start=0.0, length=0.0)


def test_clip_overlaps():
    a = Clip(id="a", track_index=0, start=0.0, length=10.0)
    b = Clip(id="b", track_index=0, start=5.0, length=10.0)
    c = Clip(id="c", track_index=0, start=10.0, length=5.0)  # touches a.end
    d = Clip(id="d", track_index=1, start=0.0, length=10.0)  # other track
    assert a.overlaps(b) is True
    assert a.overlaps(c) is False  # touching edges do not overlap
    assert a.overlaps(d) is False  # different track


def test_track_validation():
    Track(index=0, name="Video 1", kind="video")
    Track(index=1, name="Audio 1", kind="audio")
    with pytest.raises(ValueError):
        Track(index=-1, name="x")
    with pytest.raises(ValueError):
        Track(index=0, name="x", kind="subtitle")


# ---------------------------------------------------------------------- #
# Timeline construction / validation
# ---------------------------------------------------------------------- #
def _base() -> Timeline:
    return Timeline(
        duration=60.0,
        tracks=(Track(index=0, name="V1"), Track(index=1, name="A1", kind="audio")),
    )


def test_timeline_duration_must_be_positive():
    with pytest.raises(ValueError):
        Timeline(duration=0.0)
    assert Timeline.empty(30.0).duration == 30.0


def test_timeline_rejects_duplicate_track_indices():
    with pytest.raises(ValueError):
        Timeline(
            duration=10.0,
            tracks=(Track(index=0, name="a"), Track(index=0, name="b")),
        )


def test_timeline_rejects_unknown_clip_track():
    with pytest.raises(ValueError):
        _base().add_clip(Clip(id="c", track_index=5, start=0.0, length=1.0))


def test_timeline_rejects_clip_beyond_duration():
    with pytest.raises(ValueError):
        _base().add_clip(Clip(id="c", track_index=0, start=59.0, length=5.0))


def test_timeline_rejects_overlapping_clips():
    tl = _base().add_clip(Clip(id="a", track_index=0, start=0.0, length=10.0))
    with pytest.raises(ValueError):
        tl.add_clip(Clip(id="b", track_index=0, start=5.0, length=10.0))
    # Non-overlapping on the same track is fine.
    ok = tl.add_clip(Clip(id="b", track_index=0, start=10.0, length=5.0))
    assert len(ok.clips) == 2


def test_timeline_rejects_duplicate_clip_ids():
    tl = _base().add_clip(Clip(id="a", track_index=0, start=0.0, length=5.0))
    with pytest.raises(ValueError):
        tl.add_clip(Clip(id="a", track_index=1, start=0.0, length=5.0))


def test_timeline_rejects_marker_beyond_duration():
    with pytest.raises(ValueError):
        _base().add_marker(Marker(id="m", time=61.0))


# ---------------------------------------------------------------------- #
# Queries
# ---------------------------------------------------------------------- #
def test_queries():
    tl = (
        _base()
        .add_clip(Clip(id="c2", track_index=0, start=20.0, length=5.0))
        .add_clip(Clip(id="c1", track_index=0, start=0.0, length=5.0))
        .add_marker(Marker(id="m2", time=30.0))
        .add_marker(Marker(id="m1", time=10.0))
    )
    assert tl.track_by_index(1).name == "A1"
    assert tl.track_by_index(9) is None
    assert tl.clip_by_id("c1").start == 0.0
    assert tl.clip_by_id("missing") is None
    assert [c.id for c in tl.clips_on_track(0)] == ["c1", "c2"]
    assert [m.id for m in tl.sorted_markers()] == ["m1", "m2"]


# ---------------------------------------------------------------------- #
# Transformations are pure (return new snapshots)
# ---------------------------------------------------------------------- #
def test_transformations_are_pure():
    tl0 = _base()
    tl1 = tl0.add_clip(Clip(id="a", track_index=0, start=0.0, length=5.0))
    assert len(tl0.clips) == 0  # original unchanged
    assert len(tl1.clips) == 1

    tl2 = tl1.move_clip("a", track_index=1, start=10.0)
    assert tl1.clip_by_id("a").track_index == 0
    assert tl2.clip_by_id("a").track_index == 1
    assert tl2.clip_by_id("a").start == 10.0

    tl3 = tl2.trim_clip("a", length=2.0)
    assert tl2.clip_by_id("a").length == 5.0
    assert tl3.clip_by_id("a").length == 2.0

    tl4 = tl3.remove_clip("a")
    assert len(tl3.clips) == 1
    assert len(tl4.clips) == 0


def test_marker_transformations():
    tl = _base().add_marker(Marker(id="m", time=5.0))
    assert tl.marker_by_id("m").time == 5.0
    tl2 = tl.remove_marker("m")
    assert tl.marker_by_id("m") is not None
    assert tl2.marker_by_id("m") is None
    with pytest.raises(ValueError):
        tl.remove_marker("missing")


def test_with_duration_revalidates():
    tl = _base().add_clip(Clip(id="a", track_index=0, start=0.0, length=50.0))
    # Shrinking below the clip end is rejected by validation.
    with pytest.raises(ValueError):
        tl.with_duration(10.0)
    assert tl.with_duration(120.0).duration == 120.0


# ---------------------------------------------------------------------- #
# Queries added in Milestone 2
# ---------------------------------------------------------------------- #
def test_count_and_duration_helpers():
    tl = _base()
    assert tl.is_empty() is True
    assert tl.track_count() == 2
    assert tl.clip_count() == 0
    assert tl.marker_count() == 0
    assert tl.duration_used() == 0.0

    tl = tl.add_clip(Clip(id="a", track_index=0, start=0.0, length=12.0))
    tl = tl.add_clip(Clip(id="b", track_index=1, start=5.0, length=20.0))
    tl = tl.add_marker(Marker(id="m", time=3.0))
    assert tl.is_empty() is False
    assert tl.clip_count() == 2
    assert tl.marker_count() == 1
    assert tl.duration_used() == 25.0  # b: 5 + 20


# ---------------------------------------------------------------------- #
# Serialization (plain-dict round-trip)
# ---------------------------------------------------------------------- #
def test_value_type_roundtrip():
    clip = Clip(id="c", track_index=1, start=2.0, length=3.0, source="g.mp4", label="L")
    assert Clip.from_dict(clip.to_dict()) == clip
    marker = Marker(id="m", time=4.0, label="beat", kind="beat")
    assert Marker.from_dict(marker.to_dict()) == marker
    track = Track(index=2, name="A2", kind="audio", enabled=False, locked=True)
    assert Track.from_dict(track.to_dict()) == track


def test_timeline_roundtrip():
    tl = (
        _base()
        .add_clip(Clip(id="a", track_index=0, start=0.0, length=10.0))
        .add_clip(Clip(id="b", track_index=1, start=0.0, length=8.0))
        .add_marker(Marker(id="m", time=5.0, label="x"))
    )
    restored = Timeline.from_dict(tl.to_dict())
    assert restored == tl


def test_from_dict_validates():
    bad = {"duration": 10.0, "clips": [{"id": "a", "track_index": 0,
            "start": -1.0, "length": 2.0}], "tracks": [{"index": 0, "name": "V"}]}
    with pytest.raises(ValueError):
        Timeline.from_dict(bad)
