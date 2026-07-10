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

from typing import Callable, Dict, List, Optional

from PySide6.QtGui import QColor, QFont
from PySide6.QtCore import QEasingCurve
from PySide6.QtWidgets import QApplication

from gui.theme.colorutils import parse_color
from gui.theme.fonts import make_qfont, register_bundled_fonts
from gui.theme.icons import IconLoader
from gui.theme.motion import easing_curve
from gui.theme.palette_builder import build_qpalette
from gui.theme.palettes import DARK_TOKENS
from gui.theme.qss import build_stylesheet
from gui.theme.tokens import DesignTokens, TypeStyle

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
    # Resolved-value accessors (single source of resolved Qt objects)
    # ------------------------------------------------------------------ #
    # These let the widget layer obtain concrete Qt objects (QColor, QFont,
    # QEasingCurve) and numeric durations without importing token modules,
    # colorutils, motion or fonts, and without duplicating any conversion.
    def color(self, value: str) -> QColor:
        """Resolve ``value`` to a :class:`QColor`.

        Args:
            value: Either a raw color token string (``#RRGGBB`` / ``rgba(...)``)
                or a semantic role name. Recognized role names are
                ``blue``, ``cyan``, ``purple``, ``success``, ``warning``,
                ``error`` and their ``<role>_glow`` variants.

        Returns:
            The corresponding :class:`QColor`.
        """
        token = self._resolve_color_token(value)
        return parse_color(token)

    def _resolve_color_token(self, value: str) -> str:
        """Map a semantic role name to its color token, else return ``value``."""
        c = self._active.colors
        roles = {
            "blue": c.accent_blue,
            "cyan": c.accent_cyan,
            "purple": c.accent_purple,
            "success": c.success,
            "warning": c.warning,
            "error": c.error,
            "blue_glow": c.accent_blue_glow,
            "cyan_glow": c.accent_cyan_glow,
            "purple_glow": c.accent_purple_glow,
            "success_glow": c.success_glow,
            "warning_glow": c.warning_glow,
            "error_glow": c.error_glow,
        }
        return roles.get(value, value)

    def font(self, style: str = "body") -> QFont:
        """Build a :class:`QFont` for a typography ``style`` name.

        Args:
            style: One of the typography style names: ``display``, ``h1``,
                ``h2``, ``h3``, ``body``, ``body_small``, ``caption``,
                ``mono``. Defaults to ``body``.

        Raises:
            KeyError: If ``style`` is not a known typography style.
        """
        type_style: TypeStyle = getattr(self._active.typography, style)
        return make_qfont(self._active, type_style)

    def easing(self, name: Optional[str] = None) -> QEasingCurve:
        """Resolve an easing token ``name`` to a :class:`QEasingCurve`.

        Args:
            name: A motion easing token name (e.g. ``in_out_cubic``). When
                ``None``, the active theme's standard easing is used.
        """
        resolved = name if name is not None else self._active.motion.easing_standard
        return easing_curve(resolved)

    def duration(self, name: str = "normal") -> int:
        """Return a motion duration in milliseconds by ``name``.

        Args:
            name: One of ``instant``, ``fast``, ``normal``, ``slow``.

        Raises:
            KeyError: If ``name`` is not a known duration.
        """
        motion = self._active.motion
        durations = {
            "instant": motion.duration_instant_ms,
            "fast": motion.duration_fast_ms,
            "normal": motion.duration_normal_ms,
            "slow": motion.duration_slow_ms,
        }
        return durations[name]

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
