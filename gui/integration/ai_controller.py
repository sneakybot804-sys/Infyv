"""AIController: the GUI-thread seam for AIManager (async, single-flight).

Mirrors :class:`~gui.integration.workflow_controller.WorkflowController`'s
execution pattern: screens call :meth:`submit` with an AIManager method
name; the call runs on an :class:`AIWorker` thread and the typed result (or
error message) comes back on the GUI thread through queued Qt signals.

Screens hold this controller — never the AIManager's providers — so the
"everything goes through AIManager" rule holds across the Qt boundary too.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QObject, Qt, Signal

from ai_core import AIManager
from gui.integration.ai_worker import AIWorker


class AIController(QObject):
    """Runs AIManager calls in the background, one at a time.

    Args:
        manager: The composed :class:`ai_core.AIManager`.
        parent: Optional Qt parent.

    Signals:
        request_started(str): Emitted (GUI thread) with the capability name.
        request_completed(str, object): Capability name + typed result.
        request_failed(str, str): Capability name + error message.
    """

    request_started = Signal(str)
    request_completed = Signal(str, object)
    request_failed = Signal(str, str)

    def __init__(
        self, manager: AIManager, parent: Optional[QObject] = None
    ) -> None:
        super().__init__(parent)
        self._manager = manager
        self._worker: Optional[AIWorker] = None
        self._busy = False
        self._current = ""

    @property
    def manager(self) -> AIManager:
        """Return the underlying AIManager (read-only surfaces only)."""
        return self._manager

    def is_busy(self) -> bool:
        """Return whether an AI request is currently executing."""
        return self._busy

    def submit(self, capability: str, *args, **kwargs) -> bool:
        """Run ``AIManager.<capability>(*args, **kwargs)`` in the background.

        Single-flight: returns ``False`` (and does nothing) while a request
        is executing or when the capability does not exist. Results arrive
        via the queued ``request_completed`` / ``request_failed`` signals.
        """
        if self._busy:
            return False
        method = getattr(self._manager, capability, None)
        if method is None or not callable(method):
            return False
        self._busy = True
        self._current = capability
        worker = AIWorker(lambda: method(*args, **kwargs))
        self._worker = worker
        worker.finished.connect(
            self._on_finished, Qt.ConnectionType.QueuedConnection
        )
        worker.failed.connect(
            self._on_failed, Qt.ConnectionType.QueuedConnection
        )
        worker.done.connect(
            self._on_done, Qt.ConnectionType.QueuedConnection
        )
        self.request_started.emit(capability)
        worker.start()
        return True

    def stop(self) -> None:
        """Tear down any in-flight worker (idempotent)."""
        if self._worker is not None:
            worker = self._worker
            self._worker = None
            worker.teardown()
        self._busy = False

    # ------------------------------------------------------------------ #
    # Internal slots (GUI thread via queued connections)
    # ------------------------------------------------------------------ #
    def _on_finished(self, result: object) -> None:
        self.request_completed.emit(self._current, result)

    def _on_failed(self, message: str) -> None:
        self.request_failed.emit(self._current, message)

    def _on_done(self) -> None:
        worker = self._worker
        self._worker = None
        if worker is not None:
            worker.teardown()
        self._busy = False
