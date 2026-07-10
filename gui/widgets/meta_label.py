"""MetaLabel: a typography- and color-role-aware text label.

A thin themed :class:`QLabel` wrapper whose font comes from a typography style
and whose color comes from a text role, both resolved through the injected
:class:`ThemeManager`. It removes the need for callers to hand-style plain
labels. Non-interactive; installs no :class:`QGraphicsEffect`.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from gui.theme.manager import ThemeManager
from gui.widgets import styling
from gui.widgets.base import ThemedWidget

#: The text color roles (Phase 8C-3).
ROLES = ("primary", "secondary", "muted", "disabled")

#: Typography styles are exactly those exposed by ThemeManager.font(...).
STYLES = (
    "display",
    "h1",
    "h2",
    "h3",
    "body",
    "body_small",
    "caption",
    "mono",
)

_ROLE_COLOR = {
    "primary": "text_primary",
    "secondary": "text_secondary",
    "muted": "text_muted",
    "disabled": "text_disabled",
}


class MetaLabel(ThemedWidget):
    """A themed text label bound to a typography style and a color role.

    Args:
        theme: Injected theme manager.
        text: The label text.
        role: Text color role, one of :data:`ROLES`. Default ``secondary``.
        style: Typography style, one of :data:`STYLES`. Default ``body``.
        parent: Optional Qt parent.

    Raises:
        ValueError: If ``role`` is not in :data:`ROLES` or ``style`` is not in
            :data:`STYLES`.
    """

    def __init__(
        self,
        theme: ThemeManager,
        text: str = "",
        *,
        role: str = "secondary",
        style: str = "body",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(theme, parent)
        self._role = self._validate_role(role)
        self._style = self._validate_style(style)
        self._text = text

        self._label = QLabel(text, self)
        self._label.setObjectName("MetaLabel")
        self._label.setWordWrap(True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._label)

        self.setAccessibleName(text or "label")
        self.apply_theme()

    # ------------------------------------------------------------------ #
    # Validation
    # ------------------------------------------------------------------ #
    @staticmethod
    def _validate_role(role: str) -> str:
        """Return ``role`` if valid, else raise :class:`ValueError`."""
        if role not in ROLES:
            raise ValueError(
                f"Unknown role: {role!r}. Valid roles: {', '.join(ROLES)}."
            )
        return role

    @staticmethod
    def _validate_style(style: str) -> str:
        """Return ``style`` if valid, else raise :class:`ValueError`."""
        if style not in STYLES:
            raise ValueError(
                f"Unknown typography style: {style!r}. Valid styles: "
                f"{', '.join(STYLES)}."
            )
        return style

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def set_text(self, text: str) -> None:
        """Set the label text."""
        self._text = text
        self._label.setText(text)
        self.setAccessibleName(text or "label")

    def text(self) -> str:
        """Return the label text."""
        return self._text

    def set_role(self, role: str) -> None:
        """Set the text color role; no-op (no restyle) when unchanged.

        Raises:
            ValueError: If ``role`` is not in :data:`ROLES`.
        """
        role = self._validate_role(role)
        if role == self._role:
            return
        self._role = role
        self.apply_theme()

    def role(self) -> str:
        """Return the current text color role."""
        return self._role

    def set_style(self, style: str) -> None:
        """Set the typography style; no-op (no restyle) when unchanged.

        Raises:
            ValueError: If ``style`` is not in :data:`STYLES`.
        """
        style = self._validate_style(style)
        if style == self._style:
            return
        self._style = style
        self.apply_theme()

    def style(self) -> str:
        """Return the current typography style."""
        return self._style

    # ------------------------------------------------------------------ #
    # Theming
    # ------------------------------------------------------------------ #
    def apply_theme(self) -> None:
        """Apply the typography font and role color from the theme."""
        colors = self.tokens.colors
        self._label.setFont(self._theme.font(self._style))
        self._label.setStyleSheet(
            styling.label_color_qss(
                getattr(colors, _ROLE_COLOR[self._role]), selector="#MetaLabel"
            )
        )
