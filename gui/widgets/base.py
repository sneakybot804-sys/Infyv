"""ThemedWidget: the single thin base for themed widgets.

This base exists purely to remove boilerplate; it contains **no business
logic**. It provides:

* a stored :class:`~gui.theme.manager.ThemeManager` reference (injected);
* automatic restyle on theme change (subscribe on construct, unsubscribe on
  destroy);
* DPI scaling helpers (delegating to :mod:`gui.theme.dpi`);
* icon helpers (delegating to ``ThemeManager.icons``).

Widgets obtain every visual value through the injected manager and must never
import token modules directly. Complex widgets should *compose* instances of
other themed widgets rather than deepening the inheritance chain.
"""
from __future__ import annotations

from typing import Any, Optional

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QWidget

from gui.theme.dpi import scale as dpi_scale
from gui.theme.manager import ThemeManager


class ThemedWidget(QWidget):
    """A QWidget that stays in sync with an injected :class:`ThemeManager`.

    Args:
        theme: The theme manager this widget reads all visual values from.
        parent: Optional Qt parent widget.
    """

    def __init__(self, theme: ThemeManager, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._theme = theme
        # Subscribe to theme changes; keep the unsubscribe handle for cleanup.
        self._theme_unsubscribe = theme.on_theme_changed(self._on_theme_changed)
        self.destroyed.connect(lambda: self._cleanup_theme_subscription())

    # ------------------------------------------------------------------ #
    # Theme access
    # ------------------------------------------------------------------ #
    @property
    def theme(self) -> ThemeManager:
        """Return the injected theme manager (the only theme access point)."""
        return self._theme

    @property
    def tokens(self) -> Any:
        """Return the active design tokens via the manager.

        Typed as ``Any`` deliberately: the widget layer must not import the
        token module, so the concrete ``DesignTokens`` type is not referenced
        here. Callers access the same attributes ``ThemeManager.tokens``
        exposes.
        """
        return self._theme.tokens

    def _on_theme_changed(self, _tokens: Any) -> None:
        """Re-apply styling when the active theme changes.

        Subclasses override :meth:`apply_theme`; this indirection lets the
        base manage subscription lifecycle while subclasses only implement the
        actual restyle.
        """
        self.apply_theme()

    def apply_theme(self) -> None:
        """Apply the active theme to this widget.

        The base implementation does nothing; subclasses override it to set
        their stylesheet/palette from :attr:`tokens` (typically via
        :mod:`gui.widgets.styling`). It is safe to call at any time.
        """

    # ------------------------------------------------------------------ #
    # DPI helpers
    # ------------------------------------------------------------------ #
    def scaled(self, value: float) -> int:
        """Return ``value`` scaled by the current device pixel ratio."""
        return dpi_scale(value)

    # ------------------------------------------------------------------ #
    # Icon helpers
    # ------------------------------------------------------------------ #
    def icon(self, name: str, color: str, size: int) -> QIcon:
        """Return a themed :class:`QIcon` recolored to ``color`` at ``size``."""
        return self._theme.icons.icon(name, color, size)

    # ------------------------------------------------------------------ #
    # Cleanup
    # ------------------------------------------------------------------ #
    def _cleanup_theme_subscription(self) -> None:
        """Unsubscribe from theme changes (idempotent)."""
        if getattr(self, "_theme_unsubscribe", None) is not None:
            self._theme_unsubscribe()
            self._theme_unsubscribe = None

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        """Ensure the theme subscription is released when the widget closes."""
        self._cleanup_theme_subscription()
        super().closeEvent(event)
