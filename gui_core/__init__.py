"""gui_core: the permanent Qt-free application layer.

``gui_core`` is the single source of truth between any front end (the PySide6
GUI, a future AI assistant, a future REST API, a plugin system, or the CLI)
and the frozen backend producers.

Architectural contract:

* :class:`~gui_core.facade.ApplicationFacade` is the ONLY public entry point.
  Outside callers must not import internal services (runner, registry,
  pipeline, state store, event bus) directly.
* No module in this package imports PySide6 or any Qt symbol. Qt begins only
  inside the ``gui/`` package.
* Business logic lives in dedicated services; the facade only orchestrates.

This module is built incrementally over Phase 8A. During early sub-steps only
the already-implemented foundation types are re-exported; the facade is added
in a later sub-step of the same phase.
"""
from __future__ import annotations

from gui_core.errors import (
    GuiCoreError,
    PhaseGatedError,
    ProjectNotLoadedError,
    UnknownPhaseError,
)
from gui_core.events import Event, EventBus, EventPriority
from gui_core.logs import CoreLogger, LogLevel, LogRecord

__all__ = [
    "GuiCoreError",
    "ProjectNotLoadedError",
    "UnknownPhaseError",
    "PhaseGatedError",
    "Event",
    "EventPriority",
    "EventBus",
    "LogLevel",
    "LogRecord",
    "CoreLogger",
]
