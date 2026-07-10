"""Tests for the priority-aware event bus (Qt-free, no external deps)."""
from __future__ import annotations

from gui_core.events import Event, EventBus, EventPriority


def test_priority_dispatch_order_high_to_low() -> None:
    bus = EventBus()
    calls: list[str] = []
    bus.subscribe(Event.VideoSelected, lambda m: calls.append("low"), EventPriority.LOW)
    bus.subscribe(
        Event.VideoSelected, lambda m: calls.append("high"), EventPriority.HIGH
    )
    bus.subscribe(
        Event.VideoSelected, lambda m: calls.append("normal"), EventPriority.NORMAL
    )

    bus.publish(Event.VideoSelected, {"video_path": "a.mp4"})

    assert calls == ["high", "normal", "low"]


def test_registration_order_within_same_priority() -> None:
    bus = EventBus()
    calls: list[str] = []
    bus.subscribe(Event.VideoSelected, lambda m: calls.append("first"))
    bus.subscribe(Event.VideoSelected, lambda m: calls.append("second"))

    bus.publish(Event.VideoSelected)

    assert calls == ["first", "second"]


def test_unsubscribe_removes_handler() -> None:
    bus = EventBus()
    calls: list[int] = []
    unsubscribe = bus.subscribe(Event.VideoSelected, lambda m: calls.append(1))

    bus.publish(Event.VideoSelected)
    unsubscribe()
    bus.publish(Event.VideoSelected)

    assert calls == [1]


def test_replay_delivers_last_persistent_state_to_late_subscriber() -> None:
    bus = EventBus()
    bus.publish(Event.VideoSelected, {"video_path": "clip.mp4"})

    received: list[str] = []
    bus.subscribe(
        Event.VideoSelected,
        lambda m: received.append(m.payload["video_path"]),
        replay=True,
    )

    assert received == ["clip.mp4"]


def test_volatile_events_are_not_replayed() -> None:
    bus = EventBus()
    bus.publish(Event.PhaseProgress, {"pct": 50})
    bus.publish(Event.LogMessage, {"message": "hello"})

    progress_seen: list[object] = []
    log_seen: list[object] = []
    bus.subscribe(Event.PhaseProgress, lambda m: progress_seen.append(m), replay=True)
    bus.subscribe(Event.LogMessage, lambda m: log_seen.append(m), replay=True)

    assert progress_seen == []
    assert log_seen == []
    assert bus.cached_state(Event.PhaseProgress) is None


def test_replay_without_prior_publish_does_not_call_handler() -> None:
    bus = EventBus()
    received: list[object] = []
    bus.subscribe(Event.SettingsChanged, lambda m: received.append(m), replay=True)
    assert received == []
