"""TextField: a themed single-line text input (composes an inner QLineEdit).

Composition over inheritance: an inner :class:`QLineEdit` provides native text
entry, caret, selection, clipboard and IME behaviour. All visuals come from
the injected :class:`ThemeManager` via QSS. No animation and no
:class:`QGraphicsEffect` are used, honoring the frozen no-effect policy.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import QLineEdit, QVBoxLayout, QWidget

from gui.theme.manager import ThemeManager
from gui.widgets import styling
from gui.widgets.base import ThemedWidget


class TextField(ThemedWidget):
    """A themed single-line text field.

    Args:
        theme: Injected theme manager.
        text: Initial text.
        placeholder: Placeholder text shown when empty; also seeds the
            accessible name when no explicit name is set.
        parent: Optional Qt parent.

    Signals:
        text_changed(str): Emitted on each edit with the new text.
        return_pressed(): Emitted when Enter/Return is pressed.
        editing_finished(): Emitted on focus-out or commit.
    """

    text_changed = Signal(str)
    return_pressed = Signal()
    editing_finished = Signal()

    def __init__(
        self,
        theme: ThemeManager,
        *,
        text: str = "",
        placeholder: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(theme, parent)
        self._placeholder = placeholder
        self._explicit_name = ""

        self._edit = QLineEdit(text, self)
        self._edit.setObjectName("TextField")
        self._edit.setPlaceholderText(placeholder)
        self._edit.textChanged.connect(self.text_changed.emit)
        self._edit.returnPressed.connect(self.return_pressed.emit)
        self._edit.editingFinished.connect(self.editing_finished.emit)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._edit)

        self._sync_accessible_name()
        self.apply_theme()

    # ------------------------------------------------------------------ #
    # Accessibility
    # ------------------------------------------------------------------ #
    def setAccessibleName(self, name: str) -> None:  # noqa: N802 (Qt override)
        """Record an explicit accessible name; it takes precedence."""
        self._explicit_name = name or ""
        super().setAccessibleName(name)

    def _sync_accessible_name(self) -> None:
        """Apply placeholder (or 'text field') when no explicit name was set."""
        if self._explicit_name:
            return
        super().setAccessibleName(self._placeholder or "text field")

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def set_text(self, text: str) -> None:
        """Set the field text; no-op when unchanged (avoids re-emitting)."""
        if text == self._edit.text():
            return
        self._edit.setText(text)

    def text(self) -> str:
        """Return the current text."""
        return self._edit.text()

    def set_placeholder(self, placeholder: str) -> None:
        """Set the placeholder text."""
        self._placeholder = placeholder
        self._edit.setPlaceholderText(placeholder)
        self._sync_accessible_name()

    def placeholder(self) -> str:
        """Return the placeholder text."""
        return self._placeholder

    def clear(self) -> None:
        """Clear the field text."""
        self._edit.clear()

    # ------------------------------------------------------------------ #
    # Theming
    # ------------------------------------------------------------------ #
    def apply_theme(self) -> None:
        """Rebuild the field styling and font from the theme."""
        tokens = self.tokens
        self._edit.setFont(self._theme.font("body"))
        self._edit.setStyleSheet(
            styling.text_field_qss(
                tokens.colors,
                radius=self.scaled(tokens.radius.md),
                pad_v=self.scaled(tokens.spacing.sm),
                pad_h=self.scaled(tokens.spacing.md),
                height=self.scaled(tokens.spacing.lg),
                selector="#TextField",
            )
        )
