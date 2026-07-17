"""Priority-aware, framework-agnostic event bus for gui_core.

The bus is the central communication channel between core services and any
number of front-end subscribers (the GUI today; a future AI assistant, REST
layer, or plugin later). It deliberately uses plain Python callables rather
than Qt signals so the core stays independent of PySide6.

Design points
-------------
* **Priorities.** Handlers may subscribe at :class:`EventPriority` ``HIGH``,
  ``NORMAL`` or ``LOW``. For a given event, handlers fire high-to-low, in
  registration order within a priority band. This gives deterministic
  ordering for future rendering/AI pipelines.
* **Replay of persistent state only.** The bus caches the most recent payload
  for the *persistent state* events (:attr:`Event.ProjectLoaded`,
  :attr:`Event.VideoSelected`, :attr:`Event.SettingsChanged`). A subscriber
  may opt into replay to synchronize immediately with current state. Volatile
  events (progress, logs) are never cached or replayed.

No Qt symbol is imported here.
"""
from __future__ import annotations

import enum
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List

EventHandler = Callable[["EventMessage"], None]
"""A handler receives a single :class:`EventMessage` and returns nothing."""


class Event(enum.Enum):
    """All events published on the bus.

    The members marked *persistent state* are the only ones eligible for
    replay (see :data:`REPLAYABLE_EVENTS`).
    """

    #: Persistent state: a project/workspace was opened.
    ProjectLoaded = "project_loaded"
    #: Persistent state: the active video selection changed.
    VideoSelected = "video_selected"
    #: Persistent state: a setting changed.
    SettingsChanged = "settings_changed"
    #: Persistent state: the timeline model changed.
    TimelineChanged = "timeline_changed"

    #: Volatile: a phase started running.
    PhaseStarted = "phase_started"
    #: Volatile: incremental progress for a running phase.
    PhaseProgress = "phase_progress"
    #: Volatile: a phase finished (success or failure).
    PhaseCompleted = "phase_completed"
    #: Volatile: a new output artifact was produced.
    ArtifactCreated = "artifact_created"
    #: Volatile: a structured log record was emitted.
    LogMessage = "log_message"
    #: Volatile: a render finished (fired alongside PhaseCompleted for render).
    RenderFinished = "render_finished"


#: The persistent state events whose latest payload is cached for replay.
REPLAYABLE_EVENTS: frozenset[Event] = frozenset(
    {
        Event.ProjectLoaded,
        Event.VideoSelected,
        Event.SettingsChanged,
        Event.TimelineChanged,
    }
)


class EventPriority(enum.IntEnum):
    """Dispatch priority; higher integer value fires first."""

    HIGH = 30
    NORMAL = 20
    LOW = 10


@dataclass(frozen=True)
class EventMessage:
    """Immutable envelope delivered to every handler.

    Attributes:
        event: Which :class:`Event` this message represents.
        payload: Arbitrary, read-only event data. Producers should treat the
            contents as immutable once published.
    """

    event: Event
    payload: Dict[str, Any] = field(default_factory=dict)


@dataclass(order=True)
class _Subscription:
    """Internal record for one handler subscription.

    Ordered by descending priority then ascending sequence so the sort in
    :meth:`EventBus.publish` yields deterministic high-to-low dispatch.
    """

    sort_priority: int
    sequence: int
    handler: EventHandler = field(compare=False)


class EventBus:
    """A synchronous, priority-aware publish/subscribe bus.

    The bus is intentionally simple and side-effect free beyond invoking
    handlers; threading is a front-end concern and is not handled here.
    """

    def __init__(self) -> None:
        """Create an empty bus with no subscribers and an empty replay cache."""
        self._subscribers: Dict[Event, List[_Subscription]] = defaultdict(list)
        self._replay_cache: Dict[Event, EventMessage] = {}
        self._sequence: int = 0

    def subscribe(
        self,
        event: Event,
        handler: EventHandler,
        priority: EventPriority = EventPriority.NORMAL,
        replay: bool = False,
    ) -> Callable[[], None]:
        """Register ``handler`` for ``event`` and return an unsubscribe callable.

        Args:
            event: The event to listen for.
            handler: Callable invoked with an :class:`EventMessage`.
            priority: Dispatch band; higher fires first.
            replay: When ``True`` and ``event`` is a persistent state event
                with a cached payload, the handler is invoked immediately with
                that cached message so the caller synchronizes with current
                state. Ignored for non-replayable events.

        Returns:
            A zero-argument callable that removes this subscription.
        """
        self._sequence += 1
        subscription = _Subscription(
            sort_priority=-int(priority),
            sequence=self._sequence,
            handler=handler,
        )
        self._subscribers[event].append(subscription)

        if replay and event in REPLAYABLE_EVENTS:
            cached = self._replay_cache.get(event)
            if cached is not None:
                handler(cached)

        def _unsubscribe() -> None:
            bucket = self._subscribers.get(event)
            if bucket and subscription in bucket:
                bucket.remove(subscription)

        return _unsubscribe

    def publish(self, event: Event, payload: Dict[str, Any] | None = None) -> None:
        """Publish ``event`` to all subscribers, high priority first.

        Persistent state events update the replay cache before dispatch so a
        subscriber that joins later can synchronize. Volatile events are never
        cached.

        Args:
            event: The event to publish.
            payload: Optional read-only event data.
        """
        message = EventMessage(event=event, payload=dict(payload or {}))

        if event in REPLAYABLE_EVENTS:
            self._replay_cache[event] = message

        for subscription in sorted(self._subscribers.get(event, [])):
            subscription.handler(message)

    def cached_state(self, event: Event) -> EventMessage | None:
        """Return the last cached message for a replayable ``event``, if any.

        Returns ``None`` for volatile events or when nothing has been cached.
        """
        return self._replay_cache.get(event)

    def clear(self) -> None:
        """Remove all subscribers and the replay cache (mainly for tests)."""
        self._subscribers.clear()
        self._replay_cache.clear()
        self._sequence = 0
