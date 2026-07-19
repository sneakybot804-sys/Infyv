"""AIWorker: background executor for a single AIManager call.

Mirrors :class:`gui.integration.phase_worker.PhaseWorker` exactly: one
synchronous ``AIManager`` method runs on a private QThread and the outcome
is reported through Qt signals (queued back to the GUI thread by the
connecting owner). The UI never blocks on an AI request, and no Qt symbol
is added to ``ai_core``.

Thread-lifetime contract (identical to PhaseWorker): teardown is the
exclusive responsibility of the owning GUI thread, which joins the thread
before deleting either QObject.
"""
from __future__ import annotations

from typing import Any, Callable, Optional

from PySide6.QtCore import QObject, QThread, Signal


class AIWorker(QObject):
    """Runs one AI call on a private QThread.

    Args:
        call: A zero-arg callable executing the AIManager method (built by
            the owner with ``functools.partial`` / lambda).
        parent: Optional Qt parent.

    Signals:
        finished(object): Emitted with the call's typed result.
        failed(str): Emitted with an error message when the call raises.
        done(): Emitted after finished/failed, whatever the outcome.
    """

    finished = Signal(object)
    failed = Signal(str)
    done = Signal()

    def __init__(
        self,
        call: Callable[[], Any],
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._call = call
        self._thread: Optional[QThread] = None

    def start(self) -> None:
        """Move to a fresh QThread and begin execution."""
        thread = QThread()
        self._thread = thread
        self.moveToThread(thread)
        thread.started.connect(self._run)
        self.done.connect(thread.quit)
        thread.start()

    def teardown(self) -> None:
        """Join the worker thread and delete both QObjects (owner thread)."""
        thread = self._thread
        self.wait()
        if thread is not None:
            try:
                thread.deleteLater()
            except RuntimeError:
                pass
        self.deleteLater()

    def _run(self) -> None:
        """Invoke the synchronous AI call and report the outcome."""
        try:
            result = self._call()
        except Exception as exc:
            self.failed.emit(str(exc))
            self.done.emit()
            return
        self.finished.emit(result)
        self.done.emit()

    def wait(self) -> None:
        """Block until the worker thread has finished, then release it."""
        thread = self._thread
        if thread is None:
            return
        try:
            if thread.isRunning():
                thread.quit()
                thread.wait()
        except RuntimeError:
            pass
        finally:
            self._thread = None
