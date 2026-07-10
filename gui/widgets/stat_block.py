"""StatBlock: a value + label (+ optional subtitle) presentation widget.

A pure, non-interactive widget that displays a prominent value with a label
and an optional subtitle. It composes :class:`MetaLabel` members (composition
over inheritance); all typography and colors come from the injected
:class:`ThemeManager`. Installs no :class:`QGraphicsEffect`.

When the subtitle is empty, the subtitle row is hidden AND its layout spacing
is collapsed so no vertical gap is reserved.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import QVBoxLayout, QWidget

from gui.theme.manager import ThemeManager
from gui.widgets.base import ThemedWidget
from gui.widgets.meta_label import MetaLabel


class StatBlock(ThemedWidget):
    """A stacked value/label/subtitle statistic block.

    Args:
        theme: Injected theme manager.
        label: The descriptive label under the value.
        value: The prominent value text.
        subtitle: Optional secondary text; when empty the row is hidden and
            its spacing collapses.
        parent: Optional Qt parent.
    """

    def __init__(
        self,
        theme: ThemeManager,
        label: str = "",
        value: str = "",
        *,
        subtitle: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(theme, parent)
        self._label_text = label
        self._value_text = value
        self._subtitle_text = subtitle

        self._column = QVBoxLayout(self)
        self._column.setContentsMargins(0, 0, 0, 0)

        # Composed themed labels (value prominent; label/subtitle secondary).
        self._value = MetaLabel(theme, value, role="primary", style="h2")
        self._label = MetaLabel(theme, label, role="secondary", style="caption")
        self._subtitle = MetaLabel(theme, subtitle, role="muted", style="caption")

        self._column.addWidget(self._value)
        self._column.addWidget(self._label)
        self._column.addWidget(self._subtitle)

        self.setAccessibleName(f"{value} {label}".strip() or "stat")
        self._apply_spacing()
        self._sync_subtitle_visibility()
        self.apply_theme()

    # ------------------------------------------------------------------ #
    # Internal layout helpers
    # ------------------------------------------------------------------ #
    def _apply_spacing(self) -> None:
        """Set column spacing, collapsing it when the subtitle is empty."""
        gap = self.scaled(self.tokens.spacing.xxs) if self._subtitle_text else 0
        self._column.setSpacing(gap)

    def _sync_subtitle_visibility(self) -> None:
        """Show the subtitle row only when it has text."""
        self._subtitle.setVisible(bool(self._subtitle_text))

    def _refresh_accessible_name(self) -> None:
        """Recompute the accessible name from value + label."""
        self.setAccessibleName(
            f"{self._value_text} {self._label_text}".strip() or "stat"
        )

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def set_label(self, label: str) -> None:
        """Set the descriptive label."""
        self._label_text = label
        self._label.set_text(label)
        self._refresh_accessible_name()

    def label(self) -> str:
        """Return the descriptive label."""
        return self._label_text

    def set_value(self, value: str) -> None:
        """Set the prominent value."""
        self._value_text = value
        self._value.set_text(value)
        self._refresh_accessible_name()

    def value(self) -> str:
        """Return the prominent value."""
        return self._value_text

    def set_subtitle(self, subtitle: str) -> None:
        """Set the subtitle; hides the row and collapses spacing when empty."""
        self._subtitle_text = subtitle
        self._subtitle.set_text(subtitle)
        self._sync_subtitle_visibility()
        self._apply_spacing()

    def subtitle(self) -> str:
        """Return the subtitle text."""
        return self._subtitle_text

    # ------------------------------------------------------------------ #
    # Theming
    # ------------------------------------------------------------------ #
    def apply_theme(self) -> None:
        """Re-apply spacing (composed MetaLabels restyle themselves)."""
        self._apply_spacing()
