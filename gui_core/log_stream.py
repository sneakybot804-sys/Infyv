"""Live log-stream consumer built on the existing EventBus (Qt-free).

Milestone 8 of the backend architecture. This adds no new messaging system: it
subscribes to the existing :attr:`gui_core.events.Event.LogMessage` on the
shared :class:`~gui_core.events.EventBus`, reconstructs an immutable
:class:`~gui_core.logs.LogRecord` from each payload, and buffers the most
recent records for a live consumer (e.g. a future log view).

The stream owns no timer or thread and publishes nothing; it is a read-only
observer of the bus, mirroring the read-only pattern used elsewhere. Filtering
reuses :func:`gui_core.logs.filter_records`.

No Qt symbol is imported here.
"""
from __future__ import annotations

from typing import List, Optional

from gui_core.events import Event, EventBus, EventMessage
from gui_core.logs import LogLevel, LogRecord, filter_records


class LogStream:
    """Buffered, read-only consumer of ``LogMessage`` events.

    Args:
        bus: The shared event bus to observe.
        max_records: Maximum number of records retained (ring buffer).
    """

    def __init__(self, bus: EventBus, *, max_records: int = 1000) -> None:
        self._bus = bus
        self._max_records = max_records
        self._records: List[LogRecord] = []
        self._unsubscribe = None

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    def start(self) -> None:
        """Begin observing ``LogMessage`` events. Idempotent."""
        if self._unsubscribe is not None:
            return
        self._unsubscribe = self._bus.subscribe(Event.LogMessage, self._on_message)

    def stop(self) -> None:
        """Stop observing. Idempotent and safe before :meth:`start`."""
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None

    def is_running(self) -> bool:
        """Return whether the stream is currently subscribed."""
        return self._unsubscribe is not None

    # ------------------------------------------------------------------ #
    # Event handling
    # ------------------------------------------------------------------ #
    def _on_message(self, message: EventMessage) -> None:
        """Rebuild a LogRecord from the payload and buffer it (bounded)."""
        payload = message.payload
        record = LogRecord(
            timestamp=float(payload.get("timestamp", 0.0)),
            module=str(payload.get("module", "")),
            level=LogLevel(int(payload.get("level", int(LogLevel.INFO)))),
            message=str(payload.get("message", "")),
            phase=payload.get("phase"),
            category=payload.get("category"),
            artifact=payload.get("artifact"),
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            del self._records[: len(self._records) - self._max_records]

    # ------------------------------------------------------------------ #
    # Read access
    # ------------------------------------------------------------------ #
    def records(
        self,
        *,
        level: Optional[LogLevel] = None,
        module: Optional[str] = None,
        phase: Optional[str] = None,
        category: Optional[str] = None,
        artifact: Optional[str] = None,
        since: Optional[float] = None,
        until: Optional[float] = None,
    ) -> List[LogRecord]:
        """Return buffered records filtered by field (reuses filter_records)."""
        return filter_records(
            self._records,
            level=level,
            module=module,
            phase=phase,
            category=category,
            artifact=artifact,
            since=since,
            until=until,
        )

    def latest(self) -> Optional[LogRecord]:
        """Return the most recent buffered record, or ``None``."""
        return self._records[-1] if self._records else None

    def clear(self) -> None:
        """Empty the buffer (does not affect the bus or subscription)."""
        self._records.clear()
