"""Application screens composed from the frozen widget library.

A screen is a production-quality composition of the reusable widgets under
:mod:`gui.widgets`. Screens receive a :class:`~gui.theme.manager.ThemeManager`
by dependency injection, use composition only, and never import
:mod:`gui_core` or any backend module. Phase 8D adds the first screen.
"""
from __future__ import annotations

from gui.screens.editor_screen import build_editor_screen

__all__ = ["build_editor_screen"]
