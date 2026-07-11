"""Offscreen Qt tests for the internal PhaseWorker (Phase 8G-1).

Runs a fake facade's ``run_phase`` on the worker thread and asserts the
finished/failed/done signals fire. Skipped without PySide6; offscreen platform.
"""
from __future__ import annotations

import os

import pytest

pytest.importorskip("PySide6")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from gui.integration.phase_worker import PhaseWorker  # noqa: E402
from gui_core import PhaseResult  # noqa: E402


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance() or QApplication([])
    yield application


def _pump_until(predicate, timeout_ms=2000):
    """Run the Qt event loop until predicate() is true or timeout elapses."""
    loop = QEventLoop()
    timer = QTimer()
    timer.setInterval(10)
    timer.timeout.connect(lambda: loop.quit() if predicate() else None)
    timer.start()
    guard = QTimer()
    guard.setSingleShot(True)
    guard.timeout.connect(loop.quit)
    guard.start(timeout_ms)
    if not predicate():
        loop.exec()
    timer.stop()
    guard.stop()


class _OkFacade:
    """Fake facade whose run_phase returns a successful result."""

    def run_phase(self, phase_id: str) -> PhaseResult:
        return PhaseResult(phase_id=phase_id, success=True, message="ok")


class _RaisingFacade:
    """Fake facade whose run_phase raises (e.g. gating error)."""

    def run_phase(self, phase_id: str) -> PhaseResult:
        raise ValueError("blocked")


def test_worker_emits_finished(app):
    worker = PhaseWorker(_OkFacade(), "analysis")
    received = {}
    worker.finished.connect(lambda r: received.update(result=r))
    worker.start()
    _pump_until(lambda: "result" in received)
    worker.wait()
    assert received["result"].success is True
    assert received["result"].phase_id == "analysis"


def test_worker_emits_failed(app):
    worker = PhaseWorker(_RaisingFacade(), "render")
    received = {}
    worker.failed.connect(lambda m: received.update(message=m))
    worker.start()
    _pump_until(lambda: "message" in received)
    worker.wait()
    assert received["message"] == "blocked"


def test_worker_emits_done(app):
    worker = PhaseWorker(_OkFacade(), "analysis")
    flags = {"done": False}
    worker.done.connect(lambda: flags.update(done=True))
    worker.start()
    _pump_until(lambda: flags["done"])
    worker.wait()
    assert flags["done"] is True
