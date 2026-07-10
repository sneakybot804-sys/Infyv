"""ThemeManager: the single authority for the active theme.

All front-end code obtains theme values through this manager rather than
importing token modules directly. This keeps a single switch point and makes
future multi-theme support trivial. Only the Dark theme is registered in
Phase 8B; requesting any other theme raises a clear error (no placeholder
light palette exists).

The manager touches Qt only to *apply* a theme to a :class:`QApplication`
(stylesheet + palette + fonts). Theme-change notification uses a plain Python
callback list rather than a Qt signal so it can be unit-tested headlessly.
"""
from __future__ import annotations

from typing import Callable, Dict, List

from PySide6.QtWidgets import QApplication

from gui.theme.fonts import make_qfont, register_bundled_fonts
from gui.theme.icons import IconLoader
from gui.theme.palette_builder import build_qpalette
from gui.theme.palettes import DARK_TOKENS
from gui.theme.qss import build_stylesheet
from gui.theme.tokens import DesignTokens

ThemeChangedHandler = Callable[[DesignTokens], None]


class ThemeManager:
    """Owns the active :class:`DesignTokens` and applies them to Qt.

    This is the only public entry point for theme access. Future widgets must
    request colors, spacing, typography and motion through this manager (via
    :attr:`tokens`), never by importing token modules directly.
    """

    def __init__(self) -> None:
        """Create a manager with the dark theme registered and active."""
        self._themes: Dict[str, DesignTokens] = {DARK_TOKENS.name: DARK_TOKENS}
        self._active: DesignTokens = DARK_TOKENS
        self._handlers: List[ThemeChangedHandler] = []
        self._icons = IconLoader()

    # ------------------------------------------------------------------ #
    # Theme registry / access
    # ------------------------------------------------------------------ #
    @property
    def tokens(self) -> DesignTokens:
        """Return the active theme's design tokens."""
        return self._active

    @property
    def icons(self) -> IconLoader:
        """Return the shared icon loader (icons recolor from tokens)."""
        return self._icons

    def available_themes(self) -> List[str]:
        """Return the names of all registered themes."""
        return list(self._themes.keys())

    def set_theme(self, name: str) -> DesignTokens:
        """Activate the theme ``name`` and notify handlers.

        Only registered themes may be activated. Requesting a known-future but
        unimplemented theme (e.g. ``"light"``) raises :class:`NotImplementedError`
        rather than falling back to a placeholder palette.

        Raises:
            NotImplementedError: If ``name`` is not a registered theme.
        """
        theme = self._themes.get(name)
        if theme is None:
            raise NotImplementedError(
                f"Theme '{name}' is not implemented. Registered themes: "
                f"{', '.join(self._themes)}."
            )
        self._active = theme
        for handler in list(self._handlers):
            handler(theme)
        return theme

    def on_theme_changed(self, handler: ThemeChangedHandler) -> Callable[[], None]:
        """Register ``handler`` for theme changes; return an unsubscribe call."""
        self._handlers.append(handler)

        def _unsubscribe() -> None:
            if handler in self._handlers:
                self._handlers.remove(handler)

        return _unsubscribe

    # ------------------------------------------------------------------ #
    # Qt application
    # ------------------------------------------------------------------ #
    def apply(self, app: QApplication) -> None:
        """Apply the active theme to ``app`` (fonts, palette, stylesheet)."""
        register_bundled_fonts()
        app.setStyle("Fusion")
        app.setPalette(build_qpalette(self._active))
        app.setFont(make_qfont(self._active))
        app.setStyleSheet(build_stylesheet(self._active))
