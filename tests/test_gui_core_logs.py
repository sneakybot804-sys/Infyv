"""Tests for structured logging and field-based filtering (Qt-free)."""
from __future__ import annotations

from gui_core.events import Event, EventBus
from gui_core.logs import CoreLogger, LogLevel, LogRecord, filter_records


def _make_logger() -> tuple[CoreLogger, list[dict]]:
    bus = EventBus()
    published: list[dict] = []
    bus.subscribe(Event.LogMessage, lambda m: published.append(m.payload))
    counter = {"n": 0.0}

    def clock() -> float:
        counter["n"] += 1.0
        return counter["n"]

    return CoreLogger("runner", bus, clock=clock), published


def test_log_creates_structured_record() -> None:
    logger, _ = _make_logger()
    record = logger.info("started", phase="analysis", category="analysis")
    assert record.module == "runner"
    assert record.level == LogLevel.INFO
    assert record.phase == "analysis"
    assert record.category == "analysis"
    assert record.message == "started"


def test_log_is_republished_on_bus() -> None:
    logger, published = _make_logger()
    logger.error("boom", phase="render", artifact="/out/reel.mp4")
    assert len(published) == 1
    assert published[0]["phase"] == "render"
    assert published[0]["artifact"] == "/out/reel.mp4"
    assert published[0]["level"] == int(LogLevel.ERROR)


def test_filter_by_level_is_inclusive_of_higher() -> None:
    records = [
        LogRecord(1.0, "m", LogLevel.DEBUG, "d"),
        LogRecord(2.0, "m", LogLevel.WARNING, "w"),
        LogRecord(3.0, "m", LogLevel.ERROR, "e"),
    ]
    out = filter_records(records, level=LogLevel.WARNING)
    assert [r.message for r in out] == ["w", "e"]


def test_filter_by_fields() -> None:
    records = [
        LogRecord(1.0, "runner", LogLevel.INFO, "a", phase="ocr", category="analysis"),
        LogRecord(2.0, "runner", LogLevel.INFO, "b", phase="render", category="rendering"),
    ]
    assert [r.message for r in filter_records(records, phase="ocr")] == ["a"]
    assert [r.message for r in filter_records(records, category="rendering")] == ["b"]


def test_history_is_bounded() -> None:
    bus = EventBus()
    logger = CoreLogger("m", bus, max_history=3)
    for i in range(5):
        logger.info(f"msg{i}")
    history = logger.history()
    assert len(history) == 3
    assert [r.message for r in history] == ["msg2", "msg3", "msg4"]
