"""ClipInspector: a UI-only, read-only clip properties panel (Phase 8H, M4).

Displays the properties of a selected timeline clip: its label, track index,
start time and length. It is a pure presentation widget -- read-only, with an
explicit empty state when nothing is selected. It depends only on the injected
:class:`ThemeManager` and composes the frozen :class:`SectionHeader` and
:class:`MetaLabel` widgets.

Milestone 4 is UI-only: there is NO backend, NO :mod:`gui_core`, NO playback,
NO drag-and-drop, NO trim/split and NO editing. The inspector merely reflects
whatever clip mapping it is given via :meth:`show_clip`; it emits no signals.

Stable object names for later integration and tests:

* ``ClipInspector`` -- the root widget
* ``ClipInspectorHeader`` -- the section header
* ``ClipInspectorEmpty`` -- the empty-state label (visible when no clip)
* ``ClipInspectorField`` -- each property row (a MetaLabel)
"""
from __future__ import annotations

from typing import Dict, List, Optional

from PySide6.QtWidgets import QVBoxLayout, QWidget

from gui.theme.manager import ThemeManager
from gui.widgets.base import ThemedWidget
from gui.widgets.meta_label import MetaLabel
from gui.widgets.section_header import SectionHeader

#: A clip is a plain mapping (as produced by the Timeline widget).
Clip = Dict[str, object]


class ClipInspector(ThemedWidget):
    """A read-only panel showing the selected clip's properties.

    Args:
        theme: Injected theme manager (sole source of visual values).
        parent: Optional Qt parent.

    The inspector starts in the empty state. Call :meth:`show_clip` with a clip
    mapping to populate it, or with ``None`` to return to the empty state.
    """

    def __init__(
        self,
        theme: ThemeManager,
        *,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(theme, parent)
        self.setObjectName("ClipInspector")
        self._current: Optional[Clip] = None

        tokens = self.tokens
        self._column = QVBoxLayout(self)
        self._column.setContentsMargins(0, 0, 0, 0)
        self._column.setSpacing(tokens.spacing.sm)

        self._header = SectionHeader(
            self._theme, "Clip Inspector", subtitle="Selected clip"
        )
        self._header.setObjectName("ClipInspectorHeader")
        self._header.set_divider(True)
        self._column.addWidget(self._header)

        # Empty-state label (shown when no clip is selected).
        self._empty = MetaLabel(self._theme, "No clip selected")
        self._empty.setObjectName("ClipInspectorEmpty")
        self._column.addWidget(self._empty)

        # Property rows (hidden until a clip is shown).
        self._field_label = MetaLabel(self._theme, "Label: \u2014")
        self._field_track = MetaLabel(self._theme, "Track: \u2014")
        self._field_start = MetaLabel(self._theme, "Start: \u2014")
        self._field_length = MetaLabel(self._theme, "Length: \u2014")
        self._fields: List[MetaLabel] = [
            self._field_label,
            self._field_track,
            self._field_start,
            self._field_length,
        ]
        for field in self._fields:
            field.setObjectName("ClipInspectorField")
            field.setVisible(False)
            self._column.addWidget(field)

        self._column.addStretch(1)
        self.setAccessibleName("clip inspector")
        self.apply_theme()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def show_clip(self, clip: Optional[Clip]) -> None:
        """Display ``clip``'s properties, or the empty state when falsy.

        Args:
            clip: A clip mapping (keys ``label``/``track``/``start``/``length``)
                or ``None``. An empty mapping is treated as no selection.
        """
        if not clip:
            self.clear()
            return
        self._current = dict(clip)
        self._field_label.set_text(f"Label: {clip.get('label', '\u2014')}")
        self._field_track.set_text(f"Track: {clip.get('track', '\u2014')}")
        self._field_start.set_text(f"Start: {clip.get('start', '\u2014')}")
        self._field_length.set_text(f"Length: {clip.get('length', '\u2014')}")
        self._empty.setVisible(False)
        for field in self._fields:
            field.setVisible(True)

    def current(self) -> Optional[Clip]:
        """Return a copy of the currently shown clip, or ``None``."""
        return dict(self._current) if self._current is not None else None

    def clear(self) -> None:
        """Return to the empty state (no clip shown). Idempotent."""
        self._current = None
        for field in self._fields:
            field.setVisible(False)
        self._empty.setVisible(True)

    def is_empty(self) -> bool:
        """Return whether the inspector is currently in the empty state."""
        return self._current is None

    # ------------------------------------------------------------------ #
    # Theming
    # ------------------------------------------------------------------ #
    def apply_theme(self) -> None:
        """No extra styling: composed children theme themselves."""
