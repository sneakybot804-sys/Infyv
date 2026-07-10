"""IconButton: a compact, icon-only button (composes a QToolButton).

Composition over inheritance: wraps an inner :class:`QToolButton`. Because it
shows no text, an accessible name is required (derived from the tooltip or an
explicit name) so screen readers can identify it. All visuals come from the
injected :class:`ThemeManager`.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QMenu, QToolButton, QVBoxLayout, QWidget

from gui.theme.manager import ThemeManager
from gui.widgets import styling
from gui.widgets.base import ThemedWidget


class IconButton(ThemedWidget):
    """A compact icon-only button.

    Args:
        theme: Injected theme manager.
        icon_name: SVG icon name (under gui/assets/icons).
        accent: Accent role ``blue`` / ``cyan`` / ``purple``. Default ``cyan``.
        checkable: Whether the button toggles. Default ``False``.
        tooltip: Tooltip text; also seeds the accessible name.
        accessible_name: Explicit accessible name (overrides ``tooltip``).
        animated: Reserved for optional hover animation. Default ``True``.
        parent: Optional Qt parent.

    Signals:
        clicked: Emitted on activation.
        toggled(bool): Emitted when the checked state changes (if checkable).
    """

    clicked = Signal()
    toggled = Signal(bool)

    def __init__(
        self,
        theme: ThemeManager,
        icon_name: str,
        *,
        accent: str = "cyan",
        checkable: bool = False,
        tooltip: str = "",
        accessible_name: str = "",
        animated: bool = True,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(theme, parent)
        self._icon_name = icon_name
        self._accent = accent
        self._animated = animated

        self._button = QToolButton(self)
        self._button.setObjectName("IconButton")
        self._button.setCheckable(checkable)
        self._button.setCursor(Qt.CursorShape.PointingHandCursor)
        if tooltip:
            self._button.setToolTip(tooltip)
        self._button.clicked.connect(self.clicked.emit)
        self._button.toggled.connect(self.toggled.emit)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._button)

        # Icon-only controls must expose an accessible name.
        name = accessible_name or tooltip or icon_name
        self.setAccessibleName(name)
        self._button.setAccessibleName(name)

        self.apply_theme()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def set_icon(self, name: str) -> None:
        """Set the icon by name."""
        self._icon_name = name
        self.apply_theme()

    def set_accent(self, accent: str) -> None:
        """Set the accent role."""
        self._accent = accent
        self.apply_theme()

    def set_checked(self, checked: bool) -> None:
        """Set the checked state (only meaningful when checkable)."""
        self._button.setChecked(checked)

    def is_checked(self) -> bool:
        """Return whether the button is currently checked."""
        return self._button.isChecked()

    def set_tooltip(self, tooltip: str) -> None:
        """Set the tooltip text."""
        self._button.setToolTip(tooltip)

    def set_context_menu(self, menu: Optional[QMenu]) -> None:
        """Attach (or clear with ``None``) a right-click context menu.

        Future-friendly hook: menu content is the caller's responsibility;
        the widget only wires the custom context-menu policy and display.
        """
        self._context_menu = menu
        if menu is not None:
            self._button.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            self._button.customContextMenuRequested.connect(self._show_context_menu)
        else:
            self._button.setContextMenuPolicy(Qt.ContextMenuPolicy.DefaultContextMenu)

    def _show_context_menu(self, pos) -> None:
        """Display the attached context menu at ``pos`` (button coordinates)."""
        if getattr(self, "_context_menu", None) is not None:
            self._context_menu.exec(self._button.mapToGlobal(pos))

    def has_context_menu(self) -> bool:
        """Return whether a context menu is currently attached."""
        return getattr(self, "_context_menu", None) is not None

    @property
    def accent(self) -> str:
        """Return the current accent role."""
        return self._accent

    @property
    def checkable(self) -> bool:
        """Return whether the button is checkable."""
        return self._button.isCheckable()

    @property
    def checked(self) -> bool:
        """Return the current checked state."""
        return self._button.isChecked()

    # ------------------------------------------------------------------ #
    # Theming
    # ------------------------------------------------------------------ #
    def apply_theme(self) -> None:
        """Rebuild the icon-button styling and icon from the theme."""
        tokens = self.tokens
        box = self.scaled(tokens.spacing.xl)
        icon_px = self.scaled(tokens.spacing.lg)
        self._button.setStyleSheet(
            styling.icon_button_qss(
                tokens.colors,
                radius=self.scaled(tokens.radius.md),
                accent=self._accent,
                selector="#IconButton",
            )
        )
        self._button.setFixedSize(box, box)
        self._button.setIconSize(QSize(icon_px, icon_px))
        self._button.setIcon(
            self.icon(
                self._icon_name,
                styling.accent_color(tokens.colors, self._accent),
                icon_px,
            )
        )
