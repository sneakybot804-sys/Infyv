"""Error hierarchy for the gui_core application layer.

Every error raised by ``gui_core`` derives from :class:`GuiCoreError` so a
front end can catch the whole layer with a single ``except``. Backend
producer errors (e.g. ``VideoAnalyzerError``) are never re-raised as-is across
the facade boundary; the runner normalizes them into a structured result
instead (see ``gui_core.runner``).

This module has no dependencies beyond the standard library and imports no Qt
symbol.
"""
from __future__ import annotations


class GuiCoreError(RuntimeError):
    """Base class for every error raised by the gui_core layer."""


class ProjectNotLoadedError(GuiCoreError):
    """Raised when an operation needs a project/video that is not loaded yet."""


class UnknownPhaseError(GuiCoreError):
    """Raised when a phase id is not present in the plugin registry."""


class PhaseGatedError(GuiCoreError):
    """Raised when a phase is requested before its dependencies are satisfied.

    The GUI uses the pipeline gating graph to disable such phases, so this is
    a defensive guard for programmatic callers (and future AI agents) that
    bypass the visual gating.
    """
