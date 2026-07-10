"""Dropdown: a themed single-select control (composes an inner QComboBox).

Composition over inheritance: an inner :class:`QComboBox` provides native
selection, keyboard navigation and the popup list. All visuals come from the
injected :class:`ThemeManager` via QSS. No animation and no
:class:`QGraphicsEffect` are used (the native popup is a top-level window,
outside any effect subtree), honoring the frozen no-effect policy.
"""
from __future__ import annotations

from typing import List, Optional, Sequence

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QVBoxLayout, QWidget

from gui.theme.manager import ThemeManager
from gui.widgets import styling
from gui.widgets.base import ThemedWidget

#: The frozen accent vocabulary (Phase 8C-5).
ACCENTS = ("blue", "cyan", "purple")


class Dropdown(ThemedWidget):
    """A themed single-select dropdown.

    Args:
        theme: Injected theme manager (sole source of visual values).
        items: Initial option labels.
        current: Initial selected index (must be valid for ``items``, or 0
            when ``items`` is empty).
        accent: Accent role, one of :data:`ACCENTS`. Default ``cyan``.
        parent: Optional Qt parent.

    Signals:
        changed(int): Emitted with the new current index when it changes.

    Raises:
        ValueError: If ``accent`` is invalid or ``current`` is out of range.
    """

    changed = Signal(int)

    def __init__(
        self,
        theme: ThemeManager,
        *,
        items: Sequence[str] = (),
        current: int = 0,
        accent: str = "cyan",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(theme, parent)
        self._accent = self._validate_accent(accent)
        self._explicit_name = ""

        self._combo = QComboBox(self)
        self._combo.setObjectName("Dropdown")
        self._combo.addItems(list(items))
        if items:
            if not 0 <= current < len(items):
                raise ValueError(
                    f"current index {current} out of range for {len(items)} items."
                )
            self._combo.setCurrentIndex(current)
        self._combo.currentIndexChanged.connect(self._on_index_changed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._combo)

        self._sync_accessible_name()
        self.apply_theme()

    # ------------------------------------------------------------------ #
    # Validation
    # ------------------------------------------------------------------ #
    @staticmethod
    def _validate_accent(accent: str) -> str:
        """Return ``accent`` if valid, else raise :class:`ValueError`."""
        if accent not in ACCENTS:
            raise ValueError(
                f"Unknown accent: {accent!r}. Valid accents: "
                f"{', '.join(ACCENTS)}."
            )
        return accent

    # ------------------------------------------------------------------ #
    # Accessibility
    # ------------------------------------------------------------------ #
    def setAccessibleName(self, name: str) -> None:  # noqa: N802 (Qt override)
        """Record an explicit accessible name; it takes precedence."""
        self._explicit_name = name or ""
        super().setAccessibleName(name)

    def _sync_accessible_name(self) -> None:
        """Apply current text (or 'dropdown') when no explicit name is set."""
        if self._explicit_name:
            return
        super().setAccessibleName(self.current_text() or "dropdown")

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def set_items(self, items: Sequence[str]) -> None:
        """Replace the option list. Resets selection to first item (or none)."""
        self._combo.blockSignals(True)
        self._combo.clear()
        self._combo.addItems(list(items))
        self._combo.blockSignals(False)
        self._sync_accessible_name()

    def items(self) -> List[str]:
        """Return the current option labels."""
        return [self._combo.itemText(i) for i in range(self._combo.count())]

    def set_current_index(self, index: int) -> None:
        """Set the selected index; no-op when unchanged.

        Raises:
            ValueError: If ``index`` is out of range (and items are present).
        """
        count = self._combo.count()
        if count == 0:
            raise ValueError("Cannot set current index: dropdown has no items.")
        if not 0 <= index < count:
            raise ValueError(
                f"current index {index} out of range for {count} items."
            )
        if index == self._combo.currentIndex():
            return
        self._combo.setCurrentIndex(index)  # emits _on_index_changed

    def current_index(self) -> int:
        """Return the selected index, or ``-1`` when there are no items."""
        return self._combo.currentIndex()

    def current_text(self) -> str:
        """Return the selected option text, or ``''`` when there are no items."""
        return self._combo.currentText()

    def set_accent(self, accent: str) -> None:
        """Set the accent role; no-op (no restyle) when unchanged.

        Raises:
            ValueError: If ``accent`` is not in :data:`ACCENTS`.
        """
        accent = self._validate_accent(accent)
        if accent == self._accent:
            return
        self._accent = accent
        self.apply_theme()

    @property
    def accent(self) -> str:
        """Return the current accent role."""
        return self._accent

    # ------------------------------------------------------------------ #
    # Internal behaviour
    # ------------------------------------------------------------------ #
    def _on_index_changed(self, index: int) -> None:
        """Re-emit selection changes and refresh the accessible name."""
        self._sync_accessible_name()
        self.changed.emit(index)

    # ------------------------------------------------------------------ #
    # Theming
    # ------------------------------------------------------------------ #
    def apply_theme(self) -> None:
        """Rebuild the dropdown styling and font from the theme."""
        tokens = self.tokens
        self._combo.setFont(self._theme.font("body"))
        self._combo.setStyleSheet(
            styling.dropdown_qss(
                tokens.colors,
                accent=self._accent,
                radius=self.scaled(tokens.radius.md),
                pad_v=self.scaled(tokens.spacing.sm),
                pad_h=self.scaled(tokens.spacing.md),
                height=self.scaled(tokens.spacing.lg),
                selector="#Dropdown",
            )
        )
