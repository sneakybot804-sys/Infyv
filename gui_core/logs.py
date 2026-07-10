"""Structured logging for the gui_core application layer.

All core log output flows through :class:`CoreLogger`, which wraps the
existing project ``logger.get_logger`` (so file/console behaviour is
unchanged) and additionally emits a structured :class:`LogRecord` on the
event bus as an :attr:`~gui_core.events.Event.LogMessage`. Front ends render
and filter those records by *field*, never by parsing raw log strings.

No Qt symbol is imported here.
"""
from __future__ import annotations

import enum
import logging
import time
from dataclasses import dataclass
from typing import Callable, Iterable, List, Optional

from gui_core.events import Event, EventBus


class LogLevel(enum.IntEnum):
    """Log severity, mirroring the standard ``logging`` levels."""

    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR


@dataclass(frozen=True)
class LogRecord:
    """An immutable, structured log entry.

    Front ends filter by these typed fields directly; there is no need to
    parse the ``message`` string. ``phase``, ``category`` and ``artifact`` are
    optional so generic (non-phase) log lines are still expressible.

    Attributes:
        timestamp: Unix epoch seconds when the record was created.
        module: The logical source module (e.g. ``"runner"``).
        level: Severity as a :class:`LogLevel`.
        message: Human-readable message text.
        phase: Owning phase id, if the record relates to a phase.
        category: Owning phase category name, if applicable.
        artifact: Related output artifact path, if any.
    """

    timestamp: float
    module: str
    level: LogLevel
    message: str
    phase: Optional[str] = None
    category: Optional[str] = None
    artifact: Optional[str] = None


def filter_records(
    records: Iterable[LogRecord],
    *,
    level: Optional[LogLevel] = None,
    module: Optional[str] = None,
    phase: Optional[str] = None,
    category: Optional[str] = None,
    artifact: Optional[str] = None,
    since: Optional[float] = None,
    until: Optional[float] = None,
) -> List[LogRecord]:
    """Return the subset of ``records`` matching every provided field filter.

    All filters are field-based (no raw-string inspection). ``level`` matches
    records at or above the given severity; ``since``/``until`` bound the
    timestamp inclusively. Unspecified filters are ignored.
    """
    result: List[LogRecord] = []
    for record in records:
        if level is not None and record.level < level:
            continue
        if module is not None and record.module != module:
            continue
        if phase is not None and record.phase != phase:
            continue
        if category is not None and record.category != category:
            continue
        if artifact is not None and record.artifact != artifact:
            continue
        if since is not None and record.timestamp < since:
            continue
        if until is not None and record.timestamp > until:
            continue
        result.append(record)
    return result


class CoreLogger:
    """Structured logger that also republishes records on the event bus.

    The logger keeps an in-memory ring buffer of the most recent records so a
    newly opened log view can render history without re-running anything. The
    buffer is bounded to avoid unbounded growth during long sessions.
    """

    def __init__(
        self,
        module: str,
        bus: EventBus,
        *,
        max_history: int = 1000,
        clock: Callable[[], float] = time.time,
    ) -> None:
        """Create a core logger.

        Args:
            module: Logical module name attached to every record.
            bus: The shared event bus records are republished on.
            max_history: Maximum number of records retained in memory.
            clock: Injectable time source (eases deterministic tests).
        """
        self._module = module
        self._bus = bus
        self._max_history = max_history
        self._clock = clock
        self._history: List[LogRecord] = []
        self._backing = logging.getLogger(f"gui_core.{module}")

    def log(
        self,
        level: LogLevel,
        message: str,
        *,
        phase: Optional[str] = None,
        category: Optional[str] = None,
        artifact: Optional[str] = None,
    ) -> LogRecord:
        """Emit a structured record: buffer it, back it, and publish it.

        Returns the created :class:`LogRecord` for convenience/testing.
        """
        record = LogRecord(
            timestamp=self._clock(),
            module=self._module,
            level=level,
            message=message,
            phase=phase,
            category=category,
            artifact=artifact,
        )
        self._history.append(record)
        if len(self._history) > self._max_history:
            del self._history[: len(self._history) - self._max_history]

        self._backing.log(int(level), message)
        self._bus.publish(
            Event.LogMessage,
            {
                "timestamp": record.timestamp,
                "module": record.module,
                "level": int(record.level),
                "message": record.message,
                "phase": record.phase,
                "category": record.category,
                "artifact": record.artifact,
            },
        )
        return record

    def debug(self, message: str, **kwargs: Optional[str]) -> LogRecord:
        """Emit a DEBUG record."""
        return self.log(LogLevel.DEBUG, message, **kwargs)  # type: ignore[arg-type]

    def info(self, message: str, **kwargs: Optional[str]) -> LogRecord:
        """Emit an INFO record."""
        return self.log(LogLevel.INFO, message, **kwargs)  # type: ignore[arg-type]

    def warning(self, message: str, **kwargs: Optional[str]) -> LogRecord:
        """Emit a WARNING record."""
        return self.log(LogLevel.WARNING, message, **kwargs)  # type: ignore[arg-type]

    def error(self, message: str, **kwargs: Optional[str]) -> LogRecord:
        """Emit an ERROR record."""
        return self.log(LogLevel.ERROR, message, **kwargs)  # type: ignore[arg-type]

    def history(self) -> List[LogRecord]:
        """Return a shallow copy of the retained log records (oldest first)."""
        return list(self._history)
