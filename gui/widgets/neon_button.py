"""NeonButton: a neon-accented action button (composes a QPushButton).

Composition over inheritance: the widget wraps an inner :class:`QPushButton`
so styling is fully controlled while native button behaviour (keyboard
activation, click) is preserved. All visual values come from the injected
:class:`ThemeManager`.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget

from gui.theme.manager import ThemeManager
from gui.widgets import styling
from gui.widgets.base import ThemedWidget

_VARIANTS = ("primary", "secondary", "ghost")


class NeonButton(ThemedWidget):
    """A themed action button.

    Args:
        theme: Injected theme manager.
        text: Button label.
        variant: ``primary`` / ``secondary`` / ``ghost``. Default ``primary``.
        accent: Accent role ``blue`` / ``cyan`` / ``purple``. Default ``cyan``.
        icon_name: Optional leading icon name (an SVG under gui/assets/icons).
        animated: Reserved for optional hover/press animation. Default True.
        parent: Optional Qt parent.

    Signals:
        clicked: Emitted when the button is activated (mouse or keyboard).
    """

    clicked = Signal()

    def __init__(
        self,
        theme: ThemeManager,
        text: str = "",
        *,
        variant: str = "primary",
        accent: str = "cyan",
        icon_name: Optional[str] = None,
        animated: bool = True,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(theme, parent)
        if variant not in _VARIANTS:
            raise ValueError(f"Unknown variant: {variant!r}")
        self._variant = variant
        self._accent = accent
        self._icon_name = icon_name
        self._animated = animated
        self._loading = False
        self._text = text

        self._button = QPushButton(text, self)
        self._button.setObjectName("NeonButton")
        self._button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._button.clicked.connect(self.clicked.emit)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._button)

        self.setAccessibleName(text or "button")
        self.apply_theme()

    # Hover / pressed / disabled feedback is provided by the QSS state rules
    # in ``neon_button_qss`` (``:hover`` / ``:pressed`` / ``:disabled``). No
    # QGraphicsEffect is used on the button: a graphics effect here would be
    # nested inside GlassCard's drop-shadow effect source tree, which Qt
    # cannot render (it causes 'Painter not active' warnings and blank
    # cards).

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def set_text(self, text: str) -> None:
        """Set the button label."""
        self._text = text
        self._button.setText(text)
        self.setAccessibleName(text or "button")

    def text(self) -> str:
        """Return the button label."""
        return self._text

    def set_icon(self, name: Optional[str]) -> None:
        """Set (or clear with ``None``) the leading icon."""
        self._icon_name = name
        self.apply_theme()

    def set_variant(self, variant: str) -> None:
        """Set the visual variant (``primary``/``secondary``/``ghost``).

        No-op (no restyle) when the variant is unchanged.
        """
        if variant not in _VARIANTS:
            raise ValueError(f"Unknown variant: {variant!r}")
        if variant == self._variant:
            return
        self._variant = variant
        self.apply_theme()

    def set_accent(self, accent: str) -> None:
        """Set the accent role (``blue``/``cyan``/``purple``).

        No-op (no restyle) when the accent is unchanged.
        """
        if accent == self._accent:
            return
        self._accent = accent
        self.apply_theme()

    def set_loading(self, loading: bool) -> None:
        """Set a lightweight loading state (disables + marks busy)."""
        self._loading = loading
        self._button.setEnabled(not loading)
        self._button.setText("…" if loading else self._text)
        self.setAccessibleDescription("busy" if loading else "")

    @property
    def variant(self) -> str:
        """Return the current variant."""
        return self._variant

    @property
    def accent(self) -> str:
        """Return the current accent role."""
        return self._accent

    @property
    def loading(self) -> bool:
        """Return whether the button is in the loading state."""
        return self._loading

    # ------------------------------------------------------------------ #
    # Theming
    # ------------------------------------------------------------------ #
    def apply_theme(self) -> None:
        """Rebuild the button styling, icon and font from the theme."""
        tokens = self.tokens
        self._button.setStyleSheet(
            styling.neon_button_qss(
                tokens.colors,
                radius=self.scaled(tokens.radius.md),
                pad_v=self.scaled(tokens.spacing.sm),
                pad_h=self.scaled(tokens.spacing.lg),
                accent=self._accent,
                variant=self._variant,
                selector="#NeonButton",
            )
        )
        self._button.setFont(self._theme.font("body"))
        if self._icon_name is not None:
            size = self.scaled(tokens.spacing.lg)
            self._button.setIcon(
                self.icon(self._icon_name, self._theme_accent_token(), size)
            )

    def _theme_accent_token(self) -> str:
        """Return the accent color string for the current accent role."""
        return styling.accent_color(self.tokens.colors, self._accent)
