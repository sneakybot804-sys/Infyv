"""PhaseWorker: internal background executor for a single phase run.

Phase 8G-1. This module runs the synchronous :meth:`ApplicationFacade.run_phase`
off the Qt GUI thread on a worker thread, and reports the outcome back through
Qt signals. It is an internal primitive used only by
:class:`~gui.integration.workflow_controller.WorkflowController`; it is not part
of the public workflow API.

The backend event bus is synchronous and framework-agnostic: it invokes handlers
on the publishing thread. Because the facade call runs here on a worker thread,
any bus event published during the run is delivered on this worker thread. The
signals emitted here cross back to the GUI thread only when connected with a
queued connection (the controller does exactly that). No Qt symbol is added to
``gui_core``.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QObject, QThread, Signal

from gui_core import ApplicationFacade, PhaseResult


class PhaseWorker(QObject):
    """Runs one ``facade.run_phase(phase_id)`` call on a private QThread.

    Args:
        facade: The application facade whose ``run_phase`` is invoked.
        phase_id: The phase to run.
        parent: Optional Qt parent.

    Signals:
        finished(object): Emitted with the :class:`PhaseResult` on success
            (including a normalized failed result, which the facade returns
            rather than raising for producer errors).
        failed(str): Emitted with an error message when ``run_phase`` raises
            (e.g. ProjectNotLoadedError / UnknownPhaseError / PhaseGatedError).
        done(): Emitted after finished/failed, whatever the outcome, so the
            controller can tear the thread down and clear single-flight state.
    """

    finished = Signal(object)
    failed = Signal(str)
    done = Signal()

    def __init__(
        self,
        facade: ApplicationFacade,
        phase_id: str,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._facade = facade
        self._phase_id = phase_id
        self._thread: Optional[QThread] = None

    # ------------------------------------------------------------------ #
    # Execution
    # ------------------------------------------------------------------ #
    def start(self) -> None:
        """Move to a fresh QThread and begin execution."""
        thread = QThread()
        self._thread = thread
        self.moveToThread(thread)
        thread.started.connect(self._run)
        # Tear the thread down once the worker signals completion.
        self.done.connect(thread.quit)
        # When the thread finishes, drop our stale reference *before* the C++
        # object is scheduled for deletion, so a later wait()/stop() never
        # touches a destroyed QThread. Order matters: _clear_thread runs first.
        thread.finished.connect(self._clear_thread)
        # End the worker QObject's lifetime with its thread so it cannot linger
        # with affinity to a destroyed QThread across later event-loop pumps.
        thread.finished.connect(self.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.start()

    def _run(self) -> None:
        """Invoke the synchronous facade call and report the outcome."""
        try:
            result: PhaseResult = self._facade.run_phase(self._phase_id)
        except Exception as exc:  # facade raises for gating/unknown/no-project
            self.failed.emit(str(exc))
            self.done.emit()
            return
        self.finished.emit(result)
        self.done.emit()

    def _clear_thread(self) -> None:
        """Drop the QThread reference once it has finished (idempotent)."""
        self._thread = None

    def wait(self) -> None:
        """Block until the worker thread has finished, then release it.

        Safe to call when the worker is still running, has already finished, or
        the underlying C++ QThread has already been destroyed. After this call
        the internal reference is cleared so repeated wait()/stop() calls are
        idempotent.
        """
        thread = self._thread
        if thread is None:
            return
        try:
            if thread.isRunning():
                thread.quit()
                thread.wait()
        except RuntimeError:
            # The underlying C++ QThread was already deleted (finished and
            # deleteLater'd). Nothing to wait on; just release the reference.
            pass
        finally:
            self._thread = None
