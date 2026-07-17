"""Unit tests for the immutable Sequence model."""
from __future__ import annotations

import pytest

from gui_core.sequence import Sequence, SequenceEntry
from gui_core.timeline import Clip, Timeline, Track


def _tl(dur: float = 30.0) -> Timeline:
    return Timeline(duration=dur, tracks=(Track(index=0, name="V1"),))


def test_entry_validation():
    SequenceEntry(name="main", timeline=_tl())
    with pytest.raises(ValueError):
        SequenceEntry(name="", timeline=_tl())


def test_sequence_unique_and_active_validation():
    with pytest.raises(ValueError):
        Sequence(
            entries=(
                SequenceEntry("a", _tl()),
                SequenceEntry("a", _tl()),
            )
        )
    with pytest.raises(ValueError):
        Sequence(entries=(SequenceEntry("a", _tl()),), active_name="missing")


def test_add_sets_active_when_first():
    seq = Sequence().add("main", _tl())
    assert seq.active_name == "main"
    assert seq.count() == 1
    seq2 = seq.add("alt", _tl())
    assert seq2.active_name == "main"  # unchanged for subsequent adds
    assert seq2.names() == ("main", "alt")


def test_queries():
    seq = Sequence().add("main", _tl(30.0)).add("alt", _tl(60.0))
    assert seq.timeline_for("alt").duration == 60.0
    assert seq.timeline_for("missing") is None
    assert seq.active_timeline().duration == 30.0
    assert seq.is_empty() is False


def test_replace_and_update():
    seq = Sequence().add("main", _tl(30.0))
    updated = seq.timeline_for("main").add_clip(
        Clip(id="c", track_index=0, start=0.0, length=5.0)
    )
    seq2 = seq.with_timeline_update("main", updated)
    assert seq.timeline_for("main").clip_count() == 0  # original pure
    assert seq2.timeline_for("main").clip_count() == 1
    with pytest.raises(ValueError):
        seq.replace_entry("missing", _tl())


def test_remove_clears_active():
    seq = Sequence().add("main", _tl()).add("alt", _tl())
    seq2 = seq.remove("main")  # main was active
    assert seq2.active_name is None
    assert seq2.names() == ("alt",)
    with pytest.raises(ValueError):
        seq.remove("missing")


def test_set_active_and_roundtrip():
    seq = Sequence().add("main", _tl()).add("alt", _tl()).set_active("alt")
    assert seq.active_name == "alt"
    assert Sequence.from_dict(seq.to_dict()) == seq
