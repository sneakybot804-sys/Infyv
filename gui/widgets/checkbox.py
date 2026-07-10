"""Checkbox: a themed labeled checkbox (composes an inner QCheckBox).

Composition over inheritance: an inner :class:`QCheckBox` provides native
keyboard toggling (Space), checked semantics and the label. All visuals come
from the injected :class:`ThemeManager` via QSS. No animation and no
:class:`QGraphicsEffect` are used, honoring the frozen no-effect policy.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QCheckBox, QVBoxLayout, QWidget

from gui.theme.manager import ThemeManager
from gui.widgets import styling
from gui.widgets.base import ThemedWidget

#: The frozen accent vocabulary (Phase 8C-4).
ACCENTS = ("blue", "cyan", "purple")


class Checkbox(ThemedWidget):
    """A themed labeled checkbox.

    Args:
        theme: Injected theme manager.
        text: The label text.
        checked: Initial state. Default ``False``.
        accent: Accent role, one of :data:`ACCENTS`. Default ``cyan``.
        parent: Optional Qt parent.

    Signals:
        toggled(bool): Emitted when the checked state changes.

    Raises:
        ValueError: If ``accent`` is not in :data:`ACCENTS`.
    """

    toggled = Signal(bool)

    def __init__(
        self,
        theme: ThemeManager,
        text: str = "",
        *,
        checked: bool = False,
        accent: str = "cyan",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(theme, parent)
        self._accent = self._validate_accent(accent)
        self._text = text
        self._explicit_name = ""

        self._checkbox = QCheckBox(text, self)
        self._checkbox.setObjectName("Checkbox")
        self._checkbox.setChecked(checked)
        self._checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        self._checkbox.toggled.connect(self._on_toggled)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._checkbox)

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
        """Apply text (or 'checkbox') when no explicit name was set."""
        if self._explicit_name:
            return
        super().setAccessibleName(self._text or "checkbox")

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def set_checked(self, checked: bool) -> None:
        """Set the checked state; no-op when unchanged."""
        if bool(checked) == self._checkbox.isChecked():
            return
        self._checkbox.setChecked(bool(checked))  # emits _on_toggled

    def is_checked(self) -> bool:
        """Return whether the checkbox is checked."""
        return self._checkbox.isChecked()

    def set_text(self, text: str) -> None:
        """Set the label text."""
        self._text = text
        self._checkbox.setText(text)
        self._sync_accessible_name()

    def text(self) -> str:
        """Return the label text."""
        return self._text

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
    def checked(self) -> bool:
        """Return the current checked state."""
        return self._checkbox.isChecked()

    @property
    def accent(self) -> str:
        """Return the current accent role."""
        return self._accent

    # ------------------------------------------------------------------ #
    # Internal behaviour
    # ------------------------------------------------------------------ #
    def _on_toggled(self, checked: bool) -> None:
        """Re-emit the inner toggle as this widget's signal."""
        self.toggled.emit(checked)

    # ------------------------------------------------------------------ #
    # Theming
    # ------------------------------------------------------------------ #
    def apply_theme(self) -> None:
        """Rebuild the checkbox styling and font from the theme."""
        tokens = self.tokens
        self._checkbox.setFont(self._theme.font("body"))
        self._checkbox.setStyleSheet(
            styling.checkbox_qss(
                tokens.colors,
                accent=self._accent,
                box=self.scaled(tokens.spacing.md),
                radius=self.scaled(tokens.radius.sm),
                spacing=self.scaled(tokens.spacing.sm),
                selector="#Checkbox",
            )
        )
