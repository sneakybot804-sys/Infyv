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
from gui.widgets.checkbox import Checkbox
from gui.widgets.dropdown import Dropdown
from gui.widgets.glass_card import GlassCard
from gui.widgets.icon_button import IconButton
from gui.widgets.meta_label import MetaLabel
from gui.widgets.neon_button import NeonButton
from gui.widgets.progress_bar import ProgressBar
from gui.widgets.section_header import SectionHeader
from gui.widgets.segmented_control import SegmentedControl
from gui.widgets.slider import Slider
from gui.widgets.stat_block import StatBlock
from gui.widgets.status_badge import StatusBadge
from gui.widgets.text_field import TextField
from gui.widgets.toggle_switch import ToggleSwitch

__all__ = [
    "ThemedWidget",
    "GlassCard",
    "NeonButton",
    "IconButton",
    "SectionHeader",
    "StatusBadge",
    "MetaLabel",
    "ProgressBar",
    "StatBlock",
    "ToggleSwitch",
    "Checkbox",
    "TextField",
    "Dropdown",
    "Slider",
    "SegmentedControl",
]
