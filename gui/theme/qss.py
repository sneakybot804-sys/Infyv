"""Build the global Qt style sheet (.qss) from design tokens.

Qt Style Sheets have no variable support, so design tokens are the single
source of truth and :func:`build_stylesheet` is the *only* place token values
are emitted into stylesheet text. Widgets in later phases must not embed
colors; they either inherit this global sheet or query the theme manager.

Phase 8B styles generic Qt classes only (no custom widget selectors yet).
"""
from __future__ import annotations

from gui.theme.colorutils import to_qss
from gui.theme.tokens import DesignTokens


def build_stylesheet(tokens: DesignTokens) -> str:
    """Return the global application style sheet derived from ``tokens``.

    Args:
        tokens: The active theme's design tokens.

    Returns:
        A QSS string ready to pass to ``QApplication.setStyleSheet``.
    """
    c = tokens.colors
    r = tokens.radius
    s = tokens.spacing
    t = tokens.typography

    return f"""
/* ---- Base ------------------------------------------------------------- */
QWidget {{
    background-color: {to_qss(c.background_base)};
    color: {to_qss(c.text_primary)};
    font-family: {t.family_stack()};
    font-size: {t.body.size_px}px;
    font-weight: {t.body.weight};
}}

QWidget:disabled {{
    color: {to_qss(c.text_disabled)};
}}

/* ---- Headings / labels ------------------------------------------------ */
QLabel {{
    background-color: transparent;
    color: {to_qss(c.text_primary)};
}}

/* ---- Tooltips --------------------------------------------------------- */
QToolTip {{
    background-color: {to_qss(c.surface_overlay)};
    color: {to_qss(c.text_primary)};
    border: 1px solid {to_qss(c.glass_border)};
    border-radius: {r.sm}px;
    padding: {s.xs}px {s.sm}px;
}}

/* ---- Buttons (base, neon-accented) ------------------------------------ */
QPushButton {{
    background-color: {to_qss(c.surface_elevated)};
    color: {to_qss(c.text_primary)};
    border: 1px solid {to_qss(c.border)};
    border-radius: {r.md}px;
    padding: {s.sm}px {s.lg}px;
}}

QPushButton:hover {{
    border: 1px solid {to_qss(c.accent_cyan)};
    color: {to_qss(c.text_primary)};
}}

QPushButton:pressed {{
    background-color: {to_qss(c.surface_overlay)};
}}

QPushButton:disabled {{
    color: {to_qss(c.text_disabled)};
    border: 1px solid {to_qss(c.divider)};
}}

/* ---- Text inputs ------------------------------------------------------ */
QLineEdit, QPlainTextEdit, QTextEdit {{
    background-color: {to_qss(c.surface)};
    color: {to_qss(c.text_primary)};
    border: 1px solid {to_qss(c.border)};
    border-radius: {r.md}px;
    padding: {s.xs}px {s.sm}px;
    selection-background-color: {to_qss(c.accent_blue)};
    selection-color: {to_qss(c.text_on_accent)};
}}

QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {{
    border: 1px solid {to_qss(c.focus_ring)};
}}

/* ---- Scrollbars ------------------------------------------------------- */
QScrollBar:vertical {{
    background: transparent;
    width: {s.sm}px;
    margin: 0px;
}}

QScrollBar::handle:vertical {{
    background: {to_qss(c.surface_overlay)};
    border-radius: {r.sm}px;
    min-height: {s.xl}px;
}}

QScrollBar::handle:vertical:hover {{
    background: {to_qss(c.accent_purple)};
}}

QScrollBar:horizontal {{
    background: transparent;
    height: {s.sm}px;
    margin: 0px;
}}

QScrollBar::handle:horizontal {{
    background: {to_qss(c.surface_overlay)};
    border-radius: {r.sm}px;
    min-width: {s.xl}px;
}}

QScrollBar::handle:horizontal:hover {{
    background: {to_qss(c.accent_purple)};
}}

QScrollBar::add-line, QScrollBar::sub-line {{
    width: 0px;
    height: 0px;
}}

QScrollBar::add-page, QScrollBar::sub-page {{
    background: transparent;
}}
""".strip()
