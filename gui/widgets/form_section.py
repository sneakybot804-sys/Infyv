"""FormSection: a titled group of FormFields.

A composite presentation widget (Phase 8C-6) that pairs a :class:`SectionHeader`
with a vertical stack of :class:`FormField` members. It composes existing
widgets only, exposes no signals and performs no validation beyond type
checking added fields. Installs no :class:`QGraphicsEffect`, so it is safe
inside an effect-bearing container such as ``GlassCard``.
"""
from __future__ import annotations

from typing import List, Optional

from PySide6.QtWidgets import QVBoxLayout, QWidget

from gui.theme.manager import ThemeManager
from gui.widgets.base import ThemedWidget
from gui.widgets.form_field import FormField
from gui.widgets.section_header import SectionHeader


class FormSection(ThemedWidget):
    """A titled section grouping a stack of :class:`FormField` widgets.

    Args:
        theme: Injected theme manager (sole source of visual values).
        title: The section title text.
        subtitle: Optional secondary text under the title.
        parent: Optional Qt parent.
    """

    def __init__(
        self,
        theme: ThemeManager,
        title: str,
        *,
        subtitle: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(theme, parent)
        self._fields: List[FormField] = []

        self._column = QVBoxLayout(self)
        self._column.setContentsMargins(0, 0, 0, 0)
        self._column.setSpacing(self.scaled(self.tokens.spacing.md))

        self._header = SectionHeader(theme, title, subtitle=subtitle)
        self._column.addWidget(self._header)

        # Inner layout holding the fields; kept separate from the header so
        # clear() only affects fields.
        self._fields_layout = QVBoxLayout()
        self._fields_layout.setContentsMargins(0, 0, 0, 0)
        self._fields_layout.setSpacing(self.scaled(self.tokens.spacing.md))
        self._column.addLayout(self._fields_layout)

        self.setAccessibleName(title or "form section")
        self.apply_theme()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def add_field(self, field: FormField) -> None:
        """Append a :class:`FormField` to the section.

        Raises:
            TypeError: If ``field`` is not a :class:`FormField`.
        """
        if not isinstance(field, FormField):
            raise TypeError(
                f"field must be a FormField, got {type(field).__name__}."
            )
        field.setParent(self)
        self._fields.append(field)
        self._fields_layout.addWidget(field)

    def fields(self) -> List[FormField]:
        """Return the added fields in insertion order."""
        return list(self._fields)

    def clear(self) -> None:
        """Remove and detach all fields from the section."""
        for field in self._fields:
            self._fields_layout.removeWidget(field)
            field.setParent(None)
        self._fields.clear()

    def title(self) -> str:
        """Return the section title."""
        return self._header.title()

    def set_title(self, title: str) -> None:
        """Set the section title."""
        self._header.set_title(title)
        self.setAccessibleName(title or "form section")

    def subtitle(self) -> str:
        """Return the section subtitle."""
        return self._header.subtitle()

    def set_subtitle(self, subtitle: str) -> None:
        """Set the section subtitle."""
        self._header.set_subtitle(subtitle)

    def set_divider(self, visible: bool) -> None:
        """Show or hide the header's bottom divider line."""
        self._header.set_divider(visible)

    # ------------------------------------------------------------------ #
    # Theming
    # ------------------------------------------------------------------ #
    def apply_theme(self) -> None:
        """Re-apply themed spacing (composed children restyle themselves)."""
        gap = self.scaled(self.tokens.spacing.md)
        self._column.setSpacing(gap)
        self._fields_layout.setSpacing(gap)
