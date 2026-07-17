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

``ApplicationFacade`` is the intended public entry point; the value types are
re-exported for callers that need to type-annotate handlers and results.
"""
from __future__ import annotations

from gui_core.artifacts import ArtifactInfo, ArtifactKind
from gui_core.commands import PhaseResult
from gui_core.errors import (
    GuiCoreError,
    PhaseGatedError,
    ProjectNotLoadedError,
    UnknownPhaseError,
)
from gui_core.events import Event, EventBus, EventMessage, EventPriority
from gui_core.export import (
    ExportFormat,
    ExportPlan,
    ExportSegment,
    ExportSpec,
    build_export_plan,
)
from gui_core.facade import ApplicationFacade
from gui_core.frame_provider import (
    FrameProvider,
    FrameProviderError,
    VideoFrame,
    VideoMetadata,
)
from gui_core.log_stream import LogStream
from gui_core.logs import CoreLogger, LogLevel, LogRecord
from gui_core.registry import PhaseCategory, PhaseId, PhasePlugin
from gui_core.playback import PlaybackState
from gui_core.render_queue import RenderJob, RenderJobStatus, RenderQueue
from gui_core.sequence import Sequence, SequenceEntry
from gui_core.state import ProjectState
from gui_core.timeline import (
    Clip,
    EditDecision,
    EditDecisionList,
    Marker,
    Timeline,
    Track,
)

__all__ = [
    "ApplicationFacade",
    "GuiCoreError",
    "ProjectNotLoadedError",
    "UnknownPhaseError",
    "PhaseGatedError",
    "Event",
    "EventMessage",
    "EventPriority",
    "EventBus",
    "LogLevel",
    "LogRecord",
    "CoreLogger",
    "ArtifactInfo",
    "ArtifactKind",
    "PhaseResult",
    "PhaseCategory",
    "PhaseId",
    "PhasePlugin",
    "ProjectState",
    "Timeline",
    "Track",
    "Clip",
    "Marker",
    "EditDecision",
    "EditDecisionList",
    "PlaybackState",
    "Sequence",
    "SequenceEntry",
    "RenderJob",
    "RenderJobStatus",
    "RenderQueue",
    "ExportSpec",
    "ExportFormat",
    "ExportSegment",
    "ExportPlan",
    "build_export_plan",
    "LogStream",
    "FrameProvider",
    "FrameProviderError",
    "VideoFrame",
    "VideoMetadata",
]
