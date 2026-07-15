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
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {to_qss(c.surface_elevated)}, stop:1 {to_qss(c.surface)});
    color: {to_qss(c.text_primary)};
    border: 1px solid {to_qss(c.border)};
    border-radius: {r.md}px;
    padding: {s.sm}px {s.lg}px;
}}

QPushButton:hover {{
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {to_qss(c.surface_overlay)}, stop:1 {to_qss(c.surface_elevated)});
    border: 1px solid {to_qss(c.accent_cyan)};
    color: {to_qss(c.text_primary)};
}}

QPushButton:pressed {{
    background-color: {to_qss(c.surface_overlay)};
    border: 1px solid {to_qss(c.accent_cyan)};
}}

QPushButton:disabled {{
    background-color: {to_qss(c.surface)};
    color: {to_qss(c.text_disabled)};
    border: 1px solid {to_qss(c.divider)};
}}

/* ---- Text inputs ------------------------------------------------------ */
QLineEdit, QPlainTextEdit, QTextEdit {{
    background-color: {to_qss(c.background_deep)};
    color: {to_qss(c.text_primary)};
    border: 1px solid {to_qss(c.border)};
    border-radius: {r.md}px;
    padding: {s.sm}px {s.md}px;
    selection-background-color: {to_qss(c.accent_blue)};
    selection-color: {to_qss(c.text_on_accent)};
}}

QLineEdit:hover, QPlainTextEdit:hover, QTextEdit:hover {{
    border: 1px solid {to_qss(c.glass_border)};
}}

QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {{
    border: 1px solid {to_qss(c.focus_ring)};
    background-color: {to_qss(c.surface)};
}}

/* ---- Combo boxes ------------------------------------------------------ */
QComboBox {{
    background-color: {to_qss(c.background_deep)};
    color: {to_qss(c.text_primary)};
    border: 1px solid {to_qss(c.border)};
    border-radius: {r.md}px;
    padding: {s.xs}px {s.md}px;
}}

QComboBox:hover {{
    border: 1px solid {to_qss(c.accent_cyan)};
}}

QComboBox::drop-down {{
    border: none;
    width: {s.lg}px;
}}

QComboBox QAbstractItemView {{
    background-color: {to_qss(c.surface_elevated)};
    color: {to_qss(c.text_primary)};
    border: 1px solid {to_qss(c.glass_border)};
    border-radius: {r.md}px;
    selection-background-color: {to_qss(c.surface_overlay)};
    selection-color: {to_qss(c.accent_cyan)};
    outline: none;
    padding: {s.xxs}px;
}}

/* ---- Check boxes / radios --------------------------------------------- */
QCheckBox, QRadioButton {{
    background: transparent;
    color: {to_qss(c.text_secondary)};
    spacing: {s.sm}px;
}}

QCheckBox::indicator, QRadioButton::indicator {{
    width: {s.md}px;
    height: {s.md}px;
    border: 1px solid {to_qss(c.border)};
    background: {to_qss(c.background_deep)};
}}

QCheckBox::indicator {{
    border-radius: {r.sm}px;
}}

QRadioButton::indicator {{
    border-radius: {s.md}px;
}}

QCheckBox::indicator:hover, QRadioButton::indicator:hover {{
    border: 1px solid {to_qss(c.accent_cyan)};
}}

QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
    background: {to_qss(c.accent_cyan)};
    border: 1px solid {to_qss(c.accent_cyan)};
}}

/* ---- Scrollbars (thin overlay) ---------------------------------------- */
QScrollBar:vertical {{
    background: transparent;
    width: {s.xs}px;
    margin: {s.xxs}px;
}}

QScrollBar::handle:vertical {{
    background: {to_qss(c.surface_overlay)};
    border-radius: {r.sm}px;
    min-height: {s.xl}px;
}}

QScrollBar:horizontal {{
    background: transparent;
    height: {s.xs}px;
    margin: {s.xxs}px;
}}

QScrollBar::handle:horizontal {{
    background: {to_qss(c.surface_overlay)};
    border-radius: {r.sm}px;
    min-width: {s.xl}px;
}}

QScrollBar::add-line, QScrollBar::sub-line {{
    width: 0px;
    height: 0px;
}}

QScrollBar::add-page, QScrollBar::sub-page {{
    background: transparent;
}}

QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {{
    background: {to_qss(c.accent_cyan)};
}}

/* ---- Group boxes (section grouping) ----------------------------------- */
QGroupBox {{
    background-color: {to_qss(c.surface)};
    border: 1px solid {to_qss(c.border)};
    border-radius: {r.lg}px;
    margin-top: {s.md}px;
    padding: {s.md}px;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: {s.md}px;
    padding: 0px {s.xs}px;
    color: {to_qss(c.text_secondary)};
}}

/* ---- Tabs ------------------------------------------------------------- */
QTabWidget::pane {{
    border: none;
    top: -1px;
}}

QTabBar::tab {{
    background: {to_qss(c.surface)};
    color: {to_qss(c.text_muted)};
    border: 1px solid {to_qss(c.border)};
    border-top-left-radius: {r.sm}px;
    border-top-right-radius: {r.sm}px;
    padding: {s.xs}px {s.md}px;
    margin-right: {s.xxs}px;
}}

QTabBar::tab:hover {{
    color: {to_qss(c.text_secondary)};
}}

QTabBar::tab:selected {{
    background: {to_qss(c.surface_elevated)};
    color: {to_qss(c.accent_cyan)};
    border: 1px solid {to_qss(c.accent_cyan)};
}}

/* ---- Menu bar / menus (premium glass) --------------------------------- */
QMenuBar {{
    background-color: {to_qss(c.surface)};
    color: {to_qss(c.text_secondary)};
    border-bottom: 1px solid {to_qss(c.border)};
    padding: {s.xxs}px {s.xs}px;
}}

QMenuBar::item {{
    background: transparent;
    color: {to_qss(c.text_secondary)};
    padding: {s.xs}px {s.sm}px;
    border-radius: {r.sm}px;
}}

QMenuBar::item:selected {{
    background-color: {to_qss(c.surface_overlay)};
    color: {to_qss(c.text_primary)};
}}

QMenuBar::item:pressed {{
    background-color: {to_qss(c.surface_overlay)};
    color: {to_qss(c.accent_cyan)};
}}

QMenu {{
    background-color: {to_qss(c.surface_elevated)};
    color: {to_qss(c.text_primary)};
    border: 1px solid {to_qss(c.glass_border)};
    border-radius: {r.md}px;
    padding: {s.xs}px;
}}

QMenu::item {{
    background: transparent;
    padding: {s.xs}px {s.lg}px;
    border-radius: {r.sm}px;
}}

QMenu::item:selected {{
    background-color: {to_qss(c.surface_overlay)};
    color: {to_qss(c.accent_cyan)};
}}

QMenu::separator {{
    height: 1px;
    background: {to_qss(c.divider)};
    margin: {s.xs}px {s.sm}px;
}}

/* ---- Toolbar ---------------------------------------------------------- */
QToolBar {{
    background-color: {to_qss(c.surface)};
    border: none;
    border-bottom: 1px solid {to_qss(c.border)};
    spacing: {s.xs}px;
    padding: {s.xs}px {s.sm}px;
}}

QToolBar::separator {{
    width: 1px;
    background: {to_qss(c.divider)};
    margin: {s.xs}px {s.xs}px;
}}

QToolButton {{
    background: transparent;
    color: {to_qss(c.text_secondary)};
    border: 1px solid transparent;
    border-radius: {r.sm}px;
    padding: {s.xs}px {s.sm}px;
}}

QToolButton:hover {{
    background-color: {to_qss(c.surface_overlay)};
    color: {to_qss(c.text_primary)};
    border: 1px solid {to_qss(c.accent_cyan)};
}}

QToolButton:pressed, QToolButton:checked {{
    background-color: {to_qss(c.surface_overlay)};
    color: {to_qss(c.accent_cyan)};
}}

/* ---- Status bar ------------------------------------------------------- */
QStatusBar {{
    background-color: {to_qss(c.surface)};
    color: {to_qss(c.text_muted)};
    border-top: 1px solid {to_qss(c.border)};
}}

QStatusBar::item {{
    border: none;
}}

/* ---- Dock widgets ----------------------------------------------------- */
QDockWidget {{
    color: {to_qss(c.text_secondary)};
    titlebar-close-icon: none;
    titlebar-normal-icon: none;
}}

QDockWidget::title {{
    background-color: {to_qss(c.surface_elevated)};
    color: {to_qss(c.text_secondary)};
    padding: {s.xs}px {s.sm}px;
    border: 1px solid {to_qss(c.border)};
    border-top-left-radius: {r.md}px;
    border-top-right-radius: {r.md}px;
}}

/* ---- Splitter handles ------------------------------------------------- */
QSplitter::handle {{
    background: {to_qss(c.divider)};
}}

QSplitter::handle:horizontal {{
    width: {s.xxs}px;
}}

QSplitter::handle:vertical {{
    height: {s.xxs}px;
}}

QSplitter::handle:hover {{
    background: {to_qss(c.accent_cyan)};
}}
""".strip()
