"""Offscreen Qt tests for the AIController/AIWorker integration seam.

Verifies the async contract: calls run off the GUI thread, results come
back through queued signals, single-flight is enforced, and failures are
reported (never raised into the UI). Uses AIManager with a fake provider —
no network access.
"""
from __future__ import annotations

import json
import os
from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEventLoop, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from ai_core import AIConfig, AIManager, AIRetryConfig  # noqa: E402
from ai_core.config import AIProviderConfig  # noqa: E402
from ai_core.errors import ProviderUnavailableError  # noqa: E402
from ai_core.providers.base import AIProvider  # noqa: E402
from ai_core.types import AIResponse  # noqa: E402
from gui.integration.ai_controller import AIController  # noqa: E402


@pytest.fixture(scope="module")
def app():
    yield QApplication.instance() or QApplication([])


class _FakeProvider(AIProvider):
    def __init__(self, script=None):
        super().__init__(AIProviderConfig(name="fake"), api_key="k")
        self.script = list(script or [])

    def supports(self, task):
        return True

    def complete(self, request):
        action = self.script.pop(0) if self.script else "pong"
        if isinstance(action, Exception):
            raise action
        return AIResponse(text=action, model=request.model, provider="fake")


def _make_controller(script=None):
    config = AIConfig(
        providers={"fake": AIProviderConfig(name="fake")},
        default_provider="fake",
        retry=AIRetryConfig(max_attempts=1, use_fallbacks=False),
    )
    manager = AIManager(
        config,
        providers={"fake": _FakeProvider(script)},
        sleep=lambda _s: None,
    )
    return AIController(manager)


def _pump_until(predicate, timeout_ms=5000):
    loop = QEventLoop()
    poll = QTimer()
    poll.setInterval(10)
    poll.timeout.connect(lambda: loop.quit() if predicate() else None)
    poll.start()
    guard = QTimer()
    guard.setSingleShot(True)
    guard.timeout.connect(loop.quit)
    guard.start(timeout_ms)
    if not predicate():
        loop.exec()
    poll.stop()
    guard.stop()


def test_submit_runs_async_and_delivers_result(app):
    controller = _make_controller()
    results = []
    controller.request_completed.connect(
        lambda name, result: results.append((name, result))
    )
    assert controller.submit("chat", "ping") is True
    _pump_until(lambda: results)
    assert results and results[0][0] == "chat"
    assert results[0][1] == "pong"
    controller.stop()


def test_single_flight_rejects_second_submit(app):
    controller = _make_controller()
    done = []
    controller.request_completed.connect(lambda *a: done.append(a))
    assert controller.submit("chat", "one") is True
    # Busy until the queued completion lands.
    assert controller.submit("chat", "two") is False
    _pump_until(lambda: done)
    controller.stop()


def test_failure_reports_signal_not_exception(app):
    controller = _make_controller(
        script=[ProviderUnavailableError("down", provider="fake")]
    )
    failures = []
    controller.request_failed.connect(
        lambda name, message: failures.append((name, message))
    )
    assert controller.submit("chat", "ping") is True
    _pump_until(lambda: failures)
    assert failures and failures[0][0] == "chat"
    assert "down" in failures[0][1]
    controller.stop()


def test_unknown_capability_rejected(app):
    controller = _make_controller()
    assert controller.submit("no_such_method") is False
    controller.stop()


def test_typed_result_crosses_thread(app):
    plan_json = json.dumps(
        {"segments": [{"start": 0, "end": 2, "label": "Hook"}]}
    )
    controller = _make_controller(script=[plan_json])
    results = []
    controller.request_completed.connect(
        lambda name, result: results.append(result)
    )
    controller.submit("generate_edit_plan", "cinematic")
    _pump_until(lambda: results)
    from ai_core import EditPlan

    assert isinstance(results[0], EditPlan)
    assert results[0].segments[0].label == "Hook"
    controller.stop()
