"""SectionHeader: a title, optional subtitle, and a trailing action slot.

A pure presentation widget for grouping content. Typography and colors come
from the injected :class:`ThemeManager`. It is not interactive itself, though
an interactive widget (e.g. a NeonButton) may be placed in its action slot.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from gui.theme.manager import ThemeManager
from gui.widgets import styling
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

        self._column = QVBoxLayout(self)
        self._column.setContentsMargins(0, 0, 0, 0)

        self._row = QHBoxLayout()
        self._column.addLayout(self._row)

        text_column = QVBoxLayout()
        title_row = QHBoxLayout()
        self._title_label = QLabel(title, self)
        self._badge_label = QLabel("", self)
        self._badge_label.setObjectName("SectionBadge")
        self._badge_label.setVisible(False)
        title_row.addWidget(self._title_label)
        title_row.addWidget(self._badge_label)
        title_row.addStretch(1)
        self._subtitle_label = QLabel(subtitle, self)
        self._subtitle_label.setVisible(bool(subtitle))
        text_column.addLayout(title_row)
        text_column.addWidget(self._subtitle_label)

        self._row.addLayout(text_column)
        self._row.addStretch(1)
        self._action_slot = QHBoxLayout()
        self._row.addLayout(self._action_slot)

        self._divider = QFrame(self)
        self._divider.setObjectName("SectionDivider")
        self._divider.setVisible(False)
        self._column.addWidget(self._divider)

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

    def set_badge(self, text: Optional[str], *, accent: str = "cyan") -> None:
        """Set (or clear with ``None``) a small badge next to the title."""
        self._badge_accent = accent
        if text:
            self._badge_label.setText(text)
            self._badge_label.setVisible(True)
        else:
            self._badge_label.setVisible(False)
        self.apply_theme()

    def set_divider(self, visible: bool) -> None:
        """Show or hide the bottom divider line."""
        self._divider.setVisible(visible)

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
        """Apply typography fonts, text colors, badge and divider styling."""
        tokens = self.tokens
        colors = tokens.colors
        self._title_label.setFont(self._theme.font("h2"))
        self._subtitle_label.setFont(self._theme.font("caption"))
        self._badge_label.setFont(self._theme.font("caption"))
        self._title_label.setStyleSheet(
            styling.label_color_qss(colors.text_primary)
        )
        self._subtitle_label.setStyleSheet(
            styling.label_color_qss(colors.text_muted)
        )
        self._badge_label.setStyleSheet(
            styling.badge_qss(
                colors,
                radius=self.scaled(tokens.radius.pill),
                pad_v=self.scaled(tokens.spacing.xxs),
                pad_h=self.scaled(tokens.spacing.sm),
                accent=getattr(self, "_badge_accent", "cyan"),
                selector="#SectionBadge",
            )
        )
        self._divider.setStyleSheet(
            styling.divider_qss(colors, selector="#SectionDivider")
        )
