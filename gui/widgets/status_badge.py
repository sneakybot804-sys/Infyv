"""StatusBadge: a generic, non-interactive status pill.

A pure presentation widget that shows a short label tinted by a status role.
Colors, radius and spacing come from the injected :class:`ThemeManager`. It is
not interactive, carries no animation and installs no :class:`QGraphicsEffect`.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from gui.theme.manager import ThemeManager
from gui.widgets import styling
from gui.widgets.base import ThemedWidget

#: The frozen status vocabulary (Phase 8C-3).
STATUSES = ("neutral", "info", "success", "warning", "error")


class StatusBadge(ThemedWidget):
    """A small status pill showing text tinted by a status role.

    Args:
        theme: Injected theme manager (sole source of visual values).
        text: The badge label.
        status: One of :data:`STATUSES`. Default ``neutral``.
        parent: Optional Qt parent.

    Raises:
        ValueError: If ``status`` is not in :data:`STATUSES`.
    """

    def __init__(
        self,
        theme: ThemeManager,
        text: str = "",
        *,
        status: str = "neutral",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(theme, parent)
        self._status = self._validate_status(status)
        self._text = text

        self._label = QLabel(text, self)
        self._label.setObjectName("StatusBadge")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._label)

        self.setAccessibleName(text or "status")
        self.apply_theme()

    # ------------------------------------------------------------------ #
    # Validation
    # ------------------------------------------------------------------ #
    @staticmethod
    def _validate_status(status: str) -> str:
        """Return ``status`` if valid, else raise :class:`ValueError`."""
        if status not in STATUSES:
            raise ValueError(
                f"Unknown status: {status!r}. Valid statuses: "
                f"{', '.join(STATUSES)}."
            )
        return status

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def set_text(self, text: str) -> None:
        """Set the badge label."""
        self._text = text
        self._label.setText(text)
        self.setAccessibleName(text or "status")

    def text(self) -> str:
        """Return the badge label."""
        return self._text

    def set_status(self, status: str) -> None:
        """Set the status role; no-op (no restyle) when unchanged.

        Raises:
            ValueError: If ``status`` is not in :data:`STATUSES`.
        """
        status = self._validate_status(status)
        if status == self._status:
            return
        self._status = status
        self.apply_theme()

    def status(self) -> str:
        """Return the current status role."""
        return self._status

    # ------------------------------------------------------------------ #
    # Theming
    # ------------------------------------------------------------------ #
    def apply_theme(self) -> None:
        """Rebuild the pill styling and font from the theme."""
        tokens = self.tokens
        self._label.setFont(self._theme.font("caption"))
        self._label.setStyleSheet(
            styling.status_badge_qss(
                tokens.colors,
                status=self._status,
                radius=self.scaled(tokens.radius.pill),
                pad_v=self.scaled(tokens.spacing.xxs),
                pad_h=self.scaled(tokens.spacing.sm),
                selector="#StatusBadge",
            )
        )
