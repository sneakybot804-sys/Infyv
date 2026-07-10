"""Reusable, themed presentation widgets.

Every widget in this package:

* receives a :class:`~gui.theme.manager.ThemeManager` via dependency injection
  (no global singleton) and obtains all visual values through it;
* never imports token modules (``gui.theme.tokens`` / ``gui.theme.palettes``)
  directly, and never imports :mod:`gui_core` or any backend module;
* is independent, composition-based, fully type-hinted, and exposes a clean
  public API;
* supports high-DPI, accessibility and keyboard navigation, with animations
  optional and configurable.

Phase 8C is built in verified sub-steps. This module re-exports the public
widgets available so far; 8C-1 ships infrastructure only (no widgets yet).
"""
from __future__ import annotations

from gui.widgets.base import ThemedWidget
from gui.widgets.glass_card import GlassCard
from gui.widgets.icon_button import IconButton
from gui.widgets.neon_button import NeonButton
from gui.widgets.section_header import SectionHeader

__all__ = [
    "ThemedWidget",
    "GlassCard",
    "NeonButton",
    "IconButton",
    "SectionHeader",
]
