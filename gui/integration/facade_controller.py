"""FacadeController: read-only GUI synchronization with ApplicationFacade.

Phase 8F, Shape 1. The controller is a thin, GUI-side, **read-only** observer
of :class:`gui_core.ApplicationFacade`:

* it receives an already-constructed facade by dependency injection (it never
  builds the facade or touches ``app_config``);
* on :meth:`start` it subscribes -- with ``replay=True`` -- to the three
  persistent, replayable state events (``ProjectLoaded``, ``VideoSelected``,
  ``SettingsChanged``) and to nothing else;
* it exposes read-only accessors that pass through to the facade, plus the
  latest received :class:`EventMessage` per subscribed event;
* it wires no writes, runs no phases, starts no workers, and updates no
  widgets.

A minimal private Qt bridge (a ``QObject`` with one ``Signal``) marshals bus
callbacks -- which the synchronous, framework-agnostic bus invokes on the
publishing thread -- onto a Qt signal, keeping all Qt usage inside the ``gui``
package. ``gui_core`` remains Qt-free.
"""
from __future__ import annotations

from typing import Callable, Dict, List, Optional

from PySide6.QtCore import QObject, Signal

from gui_core import (
    ApplicationFacade,
    ArtifactInfo,
    Event,
    EventMessage,
    LogRecord,
    PhasePlugin,
    ProjectState,
)
from gui_core.logs import LogLevel

#: The persistent, replayable state events this controller observes. No
#: volatile events (LogMessage, phase/artifact/render events) are subscribed
#: to in Phase 8F.
_PERSISTENT_EVENTS = (
    Event.ProjectLoaded,
    Event.VideoSelected,
    Event.SettingsChanged,
)


class _BridgeSignal(QObject):
    """Private Qt bridge: re-emits a bus message as a Qt signal.

    The gui_core event bus is synchronous and framework-agnostic; it invokes
    handlers on whichever thread publishes. Emitting a Qt signal here isolates
    the single hop onto the Qt world in one place, so no Qt symbol is required
    inside gui_core. No worker or QThread is involved.
    """

    #: Carries the received :class:`EventMessage` (typed loosely as object so
    #: the Qt meta-type system needs no custom registration).
    received = Signal(object)


class FacadeController:
    """Read-only observer of an injected :class:`ApplicationFacade`.

    Args:
        facade: An already-constructed application facade. The controller does
            not build it and never calls any write/execution method on it.
    """

    def __init__(self, facade: ApplicationFacade) -> None:
        self._facade = facade
        self._bridge = _BridgeSignal()
        self._bridge.received.connect(self._on_bridge_received)
        self._unsubscribes: List[Callable[[], None]] = []
        self._latest: Dict[Event, Optional[EventMessage]] = {
            event: None for event in _PERSISTENT_EVENTS
        }
        self._running = False

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    def start(self) -> None:
        """Subscribe (with replay) to the persistent state events.

        Idempotent: calling :meth:`start` while already running does nothing
        and creates no duplicate subscriptions.
        """
        if self._running:
            return
        for event in _PERSISTENT_EVENTS:
            unsubscribe = self._facade.subscribe(
                event, self._make_handler(event), replay=True
            )
            self._unsubscribes.append(unsubscribe)
        self._running = True

    def stop(self) -> None:
        """Unsubscribe from all events. Idempotent and safe before start."""
        for unsubscribe in self._unsubscribes:
            unsubscribe()
        self._unsubscribes.clear()
        self._running = False

    def is_running(self) -> bool:
        """Return whether the controller is currently subscribed."""
        return self._running

    # ------------------------------------------------------------------ #
    # Event delivery (bus thread -> Qt signal -> recording slot)
    # ------------------------------------------------------------------ #
    def _make_handler(self, event: Event) -> Callable[[EventMessage], None]:
        """Return a bus handler that forwards messages through the Qt bridge."""

        def _handler(message: EventMessage) -> None:
            # Emit onto the Qt signal; the connected slot records the latest
            # message. No widget is touched.
            self._bridge.received.emit(message)

        return _handler

    def _on_bridge_received(self, message: object) -> None:
        """Record the latest message for a subscribed persistent event."""
        if isinstance(message, EventMessage) and message.event in self._latest:
            self._latest[message.event] = message

    # ------------------------------------------------------------------ #
    # Read-only accessors (thin pass-throughs; never mutate)
    # ------------------------------------------------------------------ #
    def project_state(self) -> ProjectState:
        """Return the current immutable project state snapshot."""
        return self._facade.project_state()

    def artifacts(self) -> List[ArtifactInfo]:
        """Return the artifacts discovered for the selected video."""
        return self._facade.artifacts()

    def settings(self) -> Dict[str, object]:
        """Return a copy of the current settings mapping."""
        return self._facade.settings()

    def available_phases(self) -> List[PhasePlugin]:
        """Return the phases currently runnable for the selected video."""
        return self._facade.available_phases()

    def logs(
        self,
        *,
        level: Optional[LogLevel] = None,
        module: Optional[str] = None,
        phase: Optional[str] = None,
        category: Optional[str] = None,
        artifact: Optional[str] = None,
    ) -> List[LogRecord]:
        """Return retained log records filtered by field (read-only)."""
        return self._facade.logs(
            level=level,
            module=module,
            phase=phase,
            category=category,
            artifact=artifact,
        )

    # ------------------------------------------------------------------ #
    # Latest persistent-state snapshots (populated by replay + publishes)
    # ------------------------------------------------------------------ #
    def latest_project_loaded(self) -> Optional[EventMessage]:
        """Return the most recent ProjectLoaded message, or ``None``."""
        return self._latest[Event.ProjectLoaded]

    def latest_video_selected(self) -> Optional[EventMessage]:
        """Return the most recent VideoSelected message, or ``None``."""
        return self._latest[Event.VideoSelected]

    def latest_settings_changed(self) -> Optional[EventMessage]:
        """Return the most recent SettingsChanged message, or ``None``."""
        return self._latest[Event.SettingsChanged]
