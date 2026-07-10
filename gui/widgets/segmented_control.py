"""SegmentedControl: a themed single-choice inline selector.

Composition over inheritance: builds an exclusive set of checkable
:class:`QPushButton` segments managed by a :class:`QButtonGroup`. Exactly one
segment is selected at a time. All visuals come from the injected
:class:`ThemeManager` via QSS. No animation and no :class:`QGraphicsEffect`
are used (frozen policy).
"""
from __future__ import annotations

from typing import List, Optional, Sequence

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QPushButton,
    QWidget,
)

from gui.theme.manager import ThemeManager
from gui.widgets import styling
from gui.widgets.base import ThemedWidget

#: The frozen accent vocabulary (Phase 8C-5).
ACCENTS = ("blue", "cyan", "purple")


class SegmentedControl(ThemedWidget):
    """A themed single-choice segmented control.

    Args:
        theme: Injected theme manager (sole source of visual values).
        options: Segment labels; at least two are required.
        current: Initial selected index (must be valid for ``options``).
        accent: Accent role, one of :data:`ACCENTS`. Default ``cyan``.
        parent: Optional Qt parent.

    Signals:
        changed(int): Emitted with the new current index when it changes.

    Raises:
        ValueError: If ``accent`` is invalid, fewer than two ``options`` are
            given, or ``current`` is out of range.
    """

    changed = Signal(int)

    def __init__(
        self,
        theme: ThemeManager,
        options: Sequence[str],
        *,
        current: int = 0,
        accent: str = "cyan",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(theme, parent)
        self._accent = self._validate_accent(accent)
        self._options = self._validate_options(options)
        if not 0 <= current < len(self._options):
            raise ValueError(
                f"current index {current} out of range for "
                f"{len(self._options)} options."
            )
        self._explicit_name = ""
        self._current = current

        self._row = QHBoxLayout(self)
        self._row.setContentsMargins(0, 0, 0, 0)
        self._row.setSpacing(0)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: List[QPushButton] = []
        self._build_segments()

        self._group.idClicked.connect(self._on_id_clicked)

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

    @staticmethod
    def _validate_options(options: Sequence[str]) -> List[str]:
        """Return options as a list, else raise :class:`ValueError`."""
        opts = list(options)
        if len(opts) < 2:
            raise ValueError(
                f"SegmentedControl requires at least 2 options; got {len(opts)}."
            )
        return opts

    # ------------------------------------------------------------------ #
    # Segment construction
    # ------------------------------------------------------------------ #
    def _build_segments(self) -> None:
        """(Re)build the segment buttons for the current options."""
        for button in self._buttons:
            self._group.removeButton(button)
            self._row.removeWidget(button)
            button.setParent(None)
        self._buttons = []

        for index, label in enumerate(self._options):
            button = QPushButton(label, self)
            button.setObjectName("Segment")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setAccessibleName(label)
            button.setChecked(index == self._current)
            self._group.addButton(button, index)
            self._row.addWidget(button)
            self._buttons.append(button)

    # ------------------------------------------------------------------ #
    # Accessibility
    # ------------------------------------------------------------------ #
    def setAccessibleName(self, name: str) -> None:  # noqa: N802 (Qt override)
        """Record an explicit accessible name; it takes precedence."""
        self._explicit_name = name or ""
        super().setAccessibleName(name)

    def _sync_accessible_name(self) -> None:
        """Apply current text (or a default) when no explicit name is set."""
        if self._explicit_name:
            return
        super().setAccessibleName(self.current_text() or "segmented control")

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def set_options(self, options: Sequence[str]) -> None:
        """Replace the segments; resets selection to the first segment.

        Raises:
            ValueError: If fewer than two options are given.
        """
        self._options = self._validate_options(options)
        self._current = 0
        self._build_segments()
        self._sync_accessible_name()
        self.apply_theme()

    def options(self) -> List[str]:
        """Return the segment labels."""
        return list(self._options)

    def set_current_index(self, index: int) -> None:
        """Set the selected segment; no-op when unchanged.

        Raises:
            ValueError: If ``index`` is out of range.
        """
        if not 0 <= index < len(self._options):
            raise ValueError(
                f"current index {index} out of range for "
                f"{len(self._options)} options."
            )
        if index == self._current:
            return
        self._current = index
        self._buttons[index].setChecked(True)
        self.changed.emit(index)
        self._sync_accessible_name()

    def current_index(self) -> int:
        """Return the selected segment index."""
        return self._current

    def current_text(self) -> str:
        """Return the selected segment label."""
        return self._options[self._current]

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
    def _on_id_clicked(self, index: int) -> None:
        """Handle a user segment click; no-op when unchanged."""
        if index == self._current:
            return
        self._current = index
        self._sync_accessible_name()
        self.changed.emit(index)

    # ------------------------------------------------------------------ #
    # Theming
    # ------------------------------------------------------------------ #
    def apply_theme(self) -> None:
        """Rebuild the segment styling and fonts from the theme."""
        tokens = self.tokens
        qss = styling.segmented_control_qss(
            tokens.colors,
            accent=self._accent,
            radius=self.scaled(tokens.radius.sm),
            pad_v=self.scaled(tokens.spacing.sm),
            pad_h=self.scaled(tokens.spacing.md),
            selector="#Segment",
        )
        font = self._theme.font("body")
        for button in self._buttons:
            button.setFont(font)
            button.setStyleSheet(qss)
