"""Pure, compute-only playback engine for gui_core (Qt-free).

Milestone 4 of the backend architecture. This engine owns **no** timer, thread,
event loop, or event bus. It is a set of pure functions over an immutable
:class:`PlaybackState`: given the current state, the authoritative
:class:`~gui_core.timeline.Timeline` and an elapsed-time delta, it computes the
next state deterministically. The front end owns the timer/loop and feeds
elapsed time in; ``gui_core`` owns only the playback *logic*.

No Qt symbol is imported here.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from gui_core.timeline import Timeline


@dataclass(frozen=True)
class PlaybackState:
    """Immutable playback state.

    Attributes:
        playhead: Current position in seconds (``>= 0``).
        playing: Whether playback is advancing.
        rate: Playback rate multiplier (``> 0``; ``1.0`` is real time).
        loop: Whether playback wraps to 0 at the end instead of stopping.
    """

    playhead: float = 0.0
    playing: bool = False
    rate: float = 1.0
    loop: bool = False

    def __post_init__(self) -> None:
        if float(self.playhead) < 0.0:
            raise ValueError(
                f"PlaybackState.playhead must be >= 0, got {self.playhead!r}."
            )
        if float(self.rate) <= 0.0:
            raise ValueError(
                f"PlaybackState.rate must be > 0, got {self.rate!r}."
            )


def _clamp(value: float, upper: float) -> float:
    """Clamp ``value`` to ``[0, upper]``."""
    return max(0.0, min(upper, value))


def seek(state: PlaybackState, timeline: Timeline, seconds: float) -> PlaybackState:
    """Return a new state with the playhead moved to ``seconds`` (clamped).

    Pure; does not change ``playing``/``rate``/``loop``.
    """
    return replace(state, playhead=_clamp(float(seconds), timeline.duration))


def play(state: PlaybackState) -> PlaybackState:
    """Return a new state marked playing (playhead unchanged)."""
    return replace(state, playing=True)


def pause(state: PlaybackState) -> PlaybackState:
    """Return a new state marked paused (playhead unchanged)."""
    return replace(state, playing=False)


def stop(state: PlaybackState) -> PlaybackState:
    """Return a new stopped state with the playhead reset to 0."""
    return replace(state, playing=False, playhead=0.0)


def advance(
    state: PlaybackState, timeline: Timeline, elapsed: float
) -> PlaybackState:
    """Compute the next state after ``elapsed`` real seconds (pure).

    Behavior:

    * When not playing, the state is returned unchanged.
    * The playhead advances by ``elapsed * rate`` (``elapsed`` is clamped to
      ``>= 0``; negative deltas do not rewind).
    * On reaching or passing the timeline duration: when ``loop`` is set the
      playhead wraps within ``[0, duration)``; otherwise it clamps to the
      duration and ``playing`` becomes ``False``.
    """
    if not state.playing:
        return state
    duration = timeline.duration
    delta = max(0.0, float(elapsed)) * state.rate
    target = state.playhead + delta
    if target < duration:
        return replace(state, playhead=target)
    if state.loop:
        # Wrap into [0, duration). duration > 0 is guaranteed by Timeline.
        wrapped = target % duration
        return replace(state, playhead=wrapped)
    return replace(state, playhead=duration, playing=False)


def frame_at(playhead: float, fps: float) -> int:
    """Return the 0-based frame index for ``playhead`` seconds at ``fps``.

    Raises:
        ValueError: If ``fps`` is not strictly positive.
    """
    if float(fps) <= 0.0:
        raise ValueError(f"fps must be > 0, got {fps!r}.")
    return int(max(0.0, float(playhead)) * float(fps))
