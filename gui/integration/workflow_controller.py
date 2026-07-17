"""WorkflowController: the interactive read/write + background execution engine.

Phase 8G-1. This controller is the single object a (future) interactive screen
talks to. It composes the read-only :class:`FacadeController` (Phase 8F) for
state reads and persistent-event synchronization, adds the minimum interactive
write surface (``select_video`` / ``set_setting``), and runs phases in the
background via an internal :class:`PhaseWorker`.

Threading contract
------------------
The ``gui_core`` event bus is synchronous and invokes handlers on the
publishing thread. A phase runs on a worker thread, so its volatile events
(PhaseStarted / ArtifactCreated / PhaseCompleted) are published on that worker
thread. This controller therefore re-emits background outcomes through Qt
signals delivered with a queued connection, so consumers always observe them on
the GUI thread. Facade writes (``select_video`` / ``set_setting``) are expected
to be called on the GUI thread.

Single-flight: only one phase may run at a time; ``run_phase`` is a no-op-return
while a phase is already executing.

No Qt symbol is added to ``gui_core``; this class references no screen or window.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtCore import QObject, Qt, Signal

from gui.integration.facade_controller import FacadeController
from gui.integration.phase_worker import PhaseWorker
from gui_core import (
    ApplicationFacade,
    ArtifactInfo,
    Event,
    EventMessage,
    LogRecord,
    PhasePlugin,
    PhaseResult,
    ProjectState,
    Timeline,
)
from gui_core.logs import LogLevel


class _ArtifactBridge(QObject):
    """Private Qt bridge marshaling a bus callback onto the GUI thread.

    The gui_core event bus is synchronous and framework-agnostic: it invokes
    subscribers inline on the publishing thread. During a phase run that
    thread is the worker thread, so the ArtifactCreated callback must not
    touch a GUI-thread QObject directly. This bridge lives on the GUI thread;
    the worker-thread callback only ``emit``s :attr:`received`, and a queued
    connection guarantees the connected slot runs on the GUI thread before any
    public signal is emitted.
    """

    received = Signal(object)


class WorkflowController(QObject):
    """Interactive workflow engine over an injected :class:`ApplicationFacade`.

    Args:
        facade: An already-constructed application facade.
        parent: Optional Qt parent.

    Signals:
        phase_started(str): Emitted (GUI thread) when a phase run begins.
        phase_completed(object): Emitted with the :class:`PhaseResult`.
        phase_failed(str): Emitted with an error message when the run raises.
        artifact_created(object): Emitted with an :class:`EventMessage` for
            each ArtifactCreated event observed during a run.
    """

    phase_started = Signal(str)
    phase_completed = Signal(object)
    phase_failed = Signal(str)
    artifact_created = Signal(object)

    def __init__(
        self, facade: ApplicationFacade, parent: Optional[QObject] = None
    ) -> None:
        super().__init__(parent)
        self._facade = facade
        self._reader = FacadeController(facade)
        self._worker: Optional[PhaseWorker] = None
        self._connected_worker: Optional[PhaseWorker] = None
        self._phase_running = False
        self._exec_unsubscribes: List = []
        # GUI-thread bridge: the worker-thread ArtifactCreated bus callback
        # emits onto this, and a queued connection re-delivers on the GUI
        # thread before the public artifact_created signal is emitted.
        self._artifact_bridge = _ArtifactBridge()
        self._artifact_bridge.received.connect(
            self._emit_artifact_created, Qt.ConnectionType.QueuedConnection
        )

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    def start(self) -> None:
        """Start read-only synchronization and subscribe to run-time events.

        Idempotent via the owned FacadeController. Subscribes to the volatile
        ArtifactCreated event so per-artifact notifications can be surfaced;
        the handler only re-emits a Qt signal (queued) and touches no widget.
        """
        self._reader.start()

    def stop(self) -> None:
        """Stop synchronization and ensure any running phase is torn down.

        Idempotent: safe to call repeatedly and before any run. Releases the
        run-scoped bus subscription, joins the worker thread, disconnects the
        worker's signals before dropping the reference (so no queued delivery
        can outlive it), and stops read-only synchronization.
        """
        for unsubscribe in self._exec_unsubscribes:
            unsubscribe()
        self._exec_unsubscribes.clear()
        if self._worker is not None:
            worker = self._worker
            self._disconnect_worker(worker)
            self._worker = None
            # Sole owner (GUI thread) joins the thread and deletes both the
            # worker and the QThread here, so no wrapper is finalized on the
            # worker thread concurrently with the C++ ~QThread.
            worker.teardown()
        self._phase_running = False
        self._reader.stop()

    def is_running(self) -> bool:
        """Return whether read-only synchronization is active."""
        return self._reader.is_running()

    # ------------------------------------------------------------------ #
    # Read accessors (delegate to the owned FacadeController)
    # ------------------------------------------------------------------ #
    def project_state(self) -> ProjectState:
        """Return the current immutable project state snapshot."""
        return self._reader.project_state()

    def settings(self) -> Dict[str, object]:
        """Return a copy of the current settings mapping."""
        return self._reader.settings()

    def artifacts(self) -> List[ArtifactInfo]:
        """Return the artifacts discovered for the selected video."""
        return self._reader.artifacts()

    def available_phases(self) -> List[PhasePlugin]:
        """Return the phases currently runnable for the selected video."""
        return self._reader.available_phases()

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
        return self._reader.logs(
            level=level,
            module=module,
            phase=phase,
            category=category,
            artifact=artifact,
        )

    # ------------------------------------------------------------------ #
    # Write operations (GUI thread; delegate to the facade)
    # ------------------------------------------------------------------ #
    def select_video(self, path: str | Path) -> ProjectState:
        """Select the active source video via the facade."""
        return self._facade.select_video(path)

    def set_setting(self, key: str, value: object) -> ProjectState:
        """Update a single setting via the facade."""
        return self._facade.update_settings(key, value)

    def timeline(self) -> Optional[Timeline]:
        """Return the current immutable timeline, or ``None`` if unset."""
        return self._facade.timeline()

    def update_timeline(self, timeline: Timeline) -> ProjectState:
        """Replace the timeline via the facade (publishes TimelineChanged)."""
        return self._facade.update_timeline(timeline)

    # ------------------------------------------------------------------ #
    # Execution (background, single-flight)
    # ------------------------------------------------------------------ #
    def run_phase(self, phase_id: str) -> bool:
        """Run ``phase_id`` in the background; return whether it was started.

        Single-flight: if a phase is already running this returns ``False`` and
        does nothing. The run executes on a worker thread; results are reported
        via the queued ``phase_completed`` / ``phase_failed`` signals so
        consumers observe them on the GUI thread. Volatile ArtifactCreated
        events observed during the run are re-emitted via ``artifact_created``.
        """
        if self._phase_running:
            return False
        self._phase_running = True

        # Subscribe to ArtifactCreated for the duration of the run; the handler
        # only re-emits a queued Qt signal (safe across the worker thread).
        self._exec_unsubscribes.append(
            self._facade.subscribe(Event.ArtifactCreated, self._on_artifact_created)
        )

        worker = PhaseWorker(self._facade, phase_id)
        self._worker = worker
        # Queued connections guarantee GUI-thread delivery of results.
        worker.finished.connect(self._on_phase_finished, Qt.ConnectionType.QueuedConnection)
        worker.failed.connect(self._on_phase_failed, Qt.ConnectionType.QueuedConnection)
        worker.done.connect(self._on_phase_done, Qt.ConnectionType.QueuedConnection)
        self._connected_worker = worker

        self.phase_started.emit(phase_id)
        worker.start()
        return True

    def is_phase_running(self) -> bool:
        """Return whether a phase is currently executing."""
        return self._phase_running

    # ------------------------------------------------------------------ #
    # Internal signal handlers (GUI thread via queued connections)
    # ------------------------------------------------------------------ #
    def _on_phase_finished(self, result: object) -> None:
        """Re-emit a completed phase result to consumers."""
        self.phase_completed.emit(result)

    def _on_phase_failed(self, message: str) -> None:
        """Re-emit a failed phase run to consumers."""
        self.phase_failed.emit(message)

    def _on_phase_done(self) -> None:
        """Clear single-flight state and release run-scoped subscriptions.

        Disconnects the worker's signals before dropping the reference so no
        queued delivery can fire after the worker is gone. Idempotent.
        """
        for unsubscribe in self._exec_unsubscribes:
            unsubscribe()
        self._exec_unsubscribes.clear()
        worker = self._worker
        if worker is not None:
            self._disconnect_worker(worker)
            # This slot runs on the GUI thread (queued). It is the single
            # owner responsible for the complete worker/QThread lifetime: join
            # the finished worker thread and delete both QObjects here so every
            # lifetime transition is serialized onto this thread.
            worker.teardown()
        self._worker = None
        self._phase_running = False

    def _disconnect_worker(self, worker: PhaseWorker) -> None:
        """Disconnect this controller's slots from ``worker`` (idempotent)."""
        if self._connected_worker is not worker:
            return
        for signal, slot in (
            (worker.finished, self._on_phase_finished),
            (worker.failed, self._on_phase_failed),
            (worker.done, self._on_phase_done),
        ):
            try:
                signal.disconnect(slot)
            except (RuntimeError, TypeError):
                # Already disconnected or underlying C++ object gone.
                pass
        self._connected_worker = None

    def _on_artifact_created(self, message: EventMessage) -> None:
        """Bus callback (may run on the worker thread).

        Does not touch this GUI-thread QObject directly: it only emits the
        bridge signal, whose queued connection re-delivers on the GUI thread.
        """
        self._artifact_bridge.received.emit(message)

    def _emit_artifact_created(self, message: object) -> None:
        """GUI-thread slot: emit the public artifact_created signal."""
        self.artifact_created.emit(message)
