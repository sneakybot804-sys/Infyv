"""Build a Qt :class:`QPalette` from design tokens.

The global style sheet handles most theming, but a matching palette ensures
native or un-styled elements (and default text/selection colors) still align
with the theme. Colors are sourced only from tokens via
:func:`gui.theme.colorutils.parse_color`.
"""
from __future__ import annotations

from PySide6.QtGui import QPalette

from gui.theme.colorutils import parse_color
from gui.theme.tokens import DesignTokens


def build_qpalette(tokens: DesignTokens) -> QPalette:
    """Return a :class:`QPalette` mapping token colors onto Qt roles."""
    c = tokens.colors
    palette = QPalette()

    palette.setColor(QPalette.ColorRole.Window, parse_color(c.background_base))
    palette.setColor(QPalette.ColorRole.WindowText, parse_color(c.text_primary))
    palette.setColor(QPalette.ColorRole.Base, parse_color(c.surface))
    palette.setColor(QPalette.ColorRole.AlternateBase, parse_color(c.surface_elevated))
    palette.setColor(QPalette.ColorRole.Text, parse_color(c.text_primary))
    palette.setColor(QPalette.ColorRole.PlaceholderText, parse_color(c.text_muted))
    palette.setColor(QPalette.ColorRole.Button, parse_color(c.surface_elevated))
    palette.setColor(QPalette.ColorRole.ButtonText, parse_color(c.text_primary))
    palette.setColor(QPalette.ColorRole.ToolTipBase, parse_color(c.surface_overlay))
    palette.setColor(QPalette.ColorRole.ToolTipText, parse_color(c.text_primary))
    palette.setColor(QPalette.ColorRole.Highlight, parse_color(c.accent_blue))
    palette.setColor(QPalette.ColorRole.HighlightedText, parse_color(c.text_on_accent))
    palette.setColor(QPalette.ColorRole.Link, parse_color(c.accent_cyan))
    palette.setColor(QPalette.ColorRole.LinkVisited, parse_color(c.accent_purple))

    disabled = QPalette.ColorGroup.Disabled
    palette.setColor(disabled, QPalette.ColorRole.WindowText, parse_color(c.text_disabled))
    palette.setColor(disabled, QPalette.ColorRole.Text, parse_color(c.text_disabled))
    palette.setColor(disabled, QPalette.ColorRole.ButtonText, parse_color(c.text_disabled))

    return palette
