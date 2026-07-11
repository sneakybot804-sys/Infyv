"""SettingsGroup: a transparent, reusable container of FormSections.

A composite widget (Phase 8C-6) that stacks :class:`FormSection` members
vertically with themed spacing. It is intentionally minimal and container
agnostic: it owns no title, no header, no background and no card, so it can be
placed inside a ``GlassCard``, a dialog, a sidebar, a scroll area or a future
page without forcing any presentation shell.

Strict hierarchy: a ``SettingsGroup`` contains ``FormSection`` widgets, which
in turn contain ``FormField`` widgets. There is no field-level convenience API
here. Exposes no signals, forwards nothing, performs no validation beyond
type checking added sections. Installs no :class:`QGraphicsEffect`.
"""
from __future__ import annotations

from typing import List, Optional

from PySide6.QtWidgets import QVBoxLayout, QWidget

from gui.theme.manager import ThemeManager
from gui.widgets.base import ThemedWidget
from gui.widgets.form_section import FormSection


class SettingsGroup(ThemedWidget):
    """A transparent vertical container of :class:`FormSection` widgets.

    Args:
        theme: Injected theme manager (sole source of visual values).
        parent: Optional Qt parent.
    """

    def __init__(
        self,
        theme: ThemeManager,
        *,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(theme, parent)
        self._sections: List[FormSection] = []

        self._column = QVBoxLayout(self)
        self._column.setContentsMargins(0, 0, 0, 0)
        self._column.setSpacing(self.scaled(self.tokens.spacing.lg))

        self.setAccessibleName("settings group")
        self.apply_theme()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def add_section(self, section: FormSection) -> None:
        """Append a :class:`FormSection` to the group.

        Raises:
            TypeError: If ``section`` is not a :class:`FormSection`.
        """
        if not isinstance(section, FormSection):
            raise TypeError(
                f"section must be a FormSection, got {type(section).__name__}."
            )
        section.setParent(self)
        self._sections.append(section)
        self._column.addWidget(section)

    def sections(self) -> List[FormSection]:
        """Return the added sections in insertion order."""
        return list(self._sections)

    def clear(self) -> None:
        """Remove and detach all sections from the group."""
        for section in self._sections:
            self._column.removeWidget(section)
            section.setParent(None)
        self._sections.clear()

    # ------------------------------------------------------------------ #
    # Theming
    # ------------------------------------------------------------------ #
    def apply_theme(self) -> None:
        """Re-apply themed spacing (composed sections restyle themselves)."""
        self._column.setSpacing(self.scaled(self.tokens.spacing.lg))
