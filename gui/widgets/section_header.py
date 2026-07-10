"""SectionHeader: a title, optional subtitle, and a trailing action slot.

A pure presentation widget for grouping content. Typography and colors come
from the injected :class:`ThemeManager`. It is not interactive itself, though
an interactive widget (e.g. a NeonButton) may be placed in its action slot.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from gui.theme.manager import ThemeManager
from gui.widgets.base import ThemedWidget


class SectionHeader(ThemedWidget):
    """A section title with optional subtitle and trailing action.

    Args:
        theme: Injected theme manager.
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
        self._title = title
        self._subtitle = subtitle
        self._action: Optional[QWidget] = None

        self._row = QHBoxLayout(self)
        self._row.setContentsMargins(0, 0, 0, 0)

        text_column = QVBoxLayout()
        self._title_label = QLabel(title, self)
        self._subtitle_label = QLabel(subtitle, self)
        self._subtitle_label.setVisible(bool(subtitle))
        text_column.addWidget(self._title_label)
        text_column.addWidget(self._subtitle_label)

        self._row.addLayout(text_column)
        self._row.addStretch(1)
        self._action_slot = QHBoxLayout()
        self._row.addLayout(self._action_slot)

        # Title acts as a heading for assistive technology.
        self._title_label.setAccessibleName(title)
        self.apply_theme()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def set_title(self, title: str) -> None:
        """Set the title text."""
        self._title = title
        self._title_label.setText(title)
        self._title_label.setAccessibleName(title)

    def set_subtitle(self, subtitle: str) -> None:
        """Set the subtitle text (hidden when empty)."""
        self._subtitle = subtitle
        self._subtitle_label.setText(subtitle)
        self._subtitle_label.setVisible(bool(subtitle))

    def set_action(self, widget: Optional[QWidget]) -> None:
        """Set (or clear with ``None``) the trailing action widget."""
        if self._action is not None:
            self._action_slot.removeWidget(self._action)
            self._action.setParent(None)
        self._action = widget
        if widget is not None:
            self._action_slot.addWidget(widget)

    def title(self) -> str:
        """Return the title text."""
        return self._title

    def subtitle(self) -> str:
        """Return the subtitle text."""
        return self._subtitle

    # ------------------------------------------------------------------ #
    # Theming
    # ------------------------------------------------------------------ #
    def apply_theme(self) -> None:
        """Apply typography fonts and text colors from the theme."""
        colors = self.tokens.colors
        self._title_label.setFont(self._theme.font("h2"))
        self._subtitle_label.setFont(self._theme.font("caption"))
        self._title_label.setStyleSheet(f"color: {colors.text_primary};")
        self._subtitle_label.setStyleSheet(f"color: {colors.text_muted};")
