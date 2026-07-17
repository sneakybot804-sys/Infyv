"""Unit tests for the LogStream consumer over the existing EventBus."""
from __future__ import annotations

from gui_core.events import EventBus
from gui_core.log_stream import LogStream
from gui_core.logs import CoreLogger, LogLevel


def test_stream_buffers_records():
    bus = EventBus()
    logger = CoreLogger("test", bus)
    stream = LogStream(bus)
    stream.start()

    logger.info("hello")
    logger.error("boom", phase="analysis")

    all_records = stream.records()
    assert len(all_records) == 2
    assert all_records[0].message == "hello"
    assert stream.latest().message == "boom"

    errors = stream.records(level=LogLevel.ERROR)
    assert len(errors) == 1
    assert errors[0].phase == "analysis"


def test_stream_lifecycle():
    bus = EventBus()
    logger = CoreLogger("test", bus)
    stream = LogStream(bus)
    assert stream.is_running() is False
    stream.start()
    stream.start()  # idempotent
    assert stream.is_running() is True

    logger.info("one")
    stream.stop()
    logger.info("two")  # not received after stop
    assert len(stream.records()) == 1
    stream.stop()  # idempotent


def test_stream_clear_and_bound():
    bus = EventBus()
    logger = CoreLogger("test", bus)
    stream = LogStream(bus, max_records=3)
    stream.start()
    for i in range(5):
        logger.info(f"m{i}")
    records = stream.records()
    assert len(records) == 3  # bounded ring buffer
    assert records[0].message == "m2"
    stream.clear()
    assert stream.records() == []
