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
        """Move to a fresh QThread and begin execution.

        Teardown is intentionally NOT wired to ``thread.finished``. Destroying
        the worker and the QThread is the exclusive responsibility of the
        owning GUI thread (the controller's ``_on_phase_done`` / ``stop``),
        which joins the thread before deleting either object. This guarantees
        every lifetime transition of both wrapped QObjects happens on a single
        thread, so the C++ ``~QThread`` can never race a worker-thread wrapper
        deallocation. The worker thread only runs ``_run`` and Qt's own loop
        exit.
        """
        thread = QThread()
        self._thread = thread
        self.moveToThread(thread)
        thread.started.connect(self._run)
        # Stop the worker event loop when the run reports completion so the
        # owning thread can join it. No object is deleted from this thread.
        self.done.connect(thread.quit)
        thread.start()

    def teardown(self) -> None:
        """Join the worker thread and delete both QObjects on the caller thread.

        Must be called on the object's owning (GUI) thread. Joins the thread
        (via :meth:`wait`), then schedules deletion of the QThread and this
        worker with ``deleteLater`` so both wrappers are finalized only on the
        owning thread. Idempotent: safe to call when already torn down.
        """
        thread = self._thread
        self.wait()  # joins if running; clears self._thread
        if thread is not None:
            try:
                thread.deleteLater()
            except RuntimeError:
                # Underlying C++ QThread already gone; nothing to schedule.
                pass
        self.deleteLater()

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
