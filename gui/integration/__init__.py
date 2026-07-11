"""GUI-side integration layer between the front end and gui_core.

Phase 8F introduces a strictly read-only bridge: :class:`FacadeController`
owns an injected :class:`gui_core.ApplicationFacade`, subscribes to the three
persistent, replayable state events, and exposes read-only accessors. It
performs no writes, no backend execution and no widget updates. All Qt usage
lives here in the ``gui`` package; :mod:`gui_core` remains Qt-free.
"""
from __future__ import annotations

from gui.integration.facade_controller import FacadeController

__all__ = ["FacadeController"]
