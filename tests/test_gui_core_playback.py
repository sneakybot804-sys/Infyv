"""Unit tests for the pure, Qt-free gui_core playback engine."""
from __future__ import annotations

import pytest

from gui_core.playback import (
    PlaybackState,
    advance,
    frame_at,
    pause,
    play,
    seek,
    stop,
)
from gui_core.timeline import Timeline


def _tl(duration: float = 10.0) -> Timeline:
    return Timeline.empty(duration)


def test_state_validation():
    PlaybackState()
    with pytest.raises(ValueError):
        PlaybackState(playhead=-1.0)
    with pytest.raises(ValueError):
        PlaybackState(rate=0.0)


def test_advance_noop_when_not_playing():
    s = PlaybackState(playhead=2.0, playing=False)
    assert advance(s, _tl(), 5.0) is s


def test_advance_scales_by_rate():
    s = PlaybackState(playhead=0.0, playing=True, rate=2.0)
    assert advance(s, _tl(), 1.0).playhead == 2.0


def test_advance_clamps_and_stops_at_end():
    s = PlaybackState(playhead=9.0, playing=True)
    out = advance(s, _tl(10.0), 5.0)
    assert out.playhead == 10.0
    assert out.playing is False


def test_advance_loops():
    s = PlaybackState(playhead=9.0, playing=True, loop=True)
    out = advance(s, _tl(10.0), 3.0)  # 12 % 10 == 2
    assert out.playhead == 2.0
    assert out.playing is True


def test_advance_ignores_negative_elapsed():
    s = PlaybackState(playhead=3.0, playing=True)
    assert advance(s, _tl(), -5.0).playhead == 3.0


def test_seek_clamps():
    s = PlaybackState()
    assert seek(s, _tl(10.0), 99.0).playhead == 10.0
    assert seek(s, _tl(10.0), -5.0).playhead == 0.0


def test_play_pause_stop():
    s = PlaybackState(playhead=4.0)
    assert play(s).playing is True
    assert pause(play(s)).playing is False
    stopped = stop(PlaybackState(playhead=4.0, playing=True))
    assert stopped.playing is False and stopped.playhead == 0.0


def test_frame_at():
    assert frame_at(2.0, 30.0) == 60
    assert frame_at(0.0, 24.0) == 0
    with pytest.raises(ValueError):
        frame_at(1.0, 0.0)
