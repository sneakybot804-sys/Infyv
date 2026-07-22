"""Custom frameless-window title bar for the media workspace shell.

A premium desktop header that replaces the native OS title bar: application
logo + name, a decorative top-level menu strip, a centered project selector, a
quick-search field, notification/help actions, and the min / maximize / close
window controls. Purely presentational — it drives only window state
(minimize, maximize/restore, close) and window dragging; it wires no
application logic and owns no backend.

Object names are stable for tests/integration:

* ``WorkspaceTitleBar`` -- the bar itself
* ``WorkspaceTitleBarMenuItem`` -- each decorative menu button
* ``WorkspaceProjectSelector`` -- the centered project pill
* ``WorkspaceQuickSearch`` -- the search field
* ``WorkspaceWindowMinimize`` / ``WorkspaceWindowMaximize`` /
  ``WorkspaceWindowClose`` -- the window controls
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QToolButton,
    QWidget,
)

from gui.widgets.base import ThemedWidget

#: Top-level menu labels shown in the header (decorative; the real QMenuBar on
#: the host window keeps its own frozen set for tests).
_MENU_ITEMS = (
    "File", "Edit", "Clip", "Timeline", "View", "Playback",
    "Fusion", "Color", "Fairlight", "Workspace", "Help",
)

_BAR_HEIGHT = 50


class TitleBar(ThemedWidget):
    """Frameless-window header bar (visual chrome + window controls)."""

    def __init__(
        self,
        theme,
        *,
        project_name: str = "Untitled Project",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(theme, parent)
        self.setObjectName("WorkspaceTitleBar")
        self.setFixedHeight(_BAR_HEIGHT)
        self._project_name = project_name
        self._maximize_btn: Optional[QToolButton] = None
        self._build()
        self.apply_theme()

    # ------------------------------------------------------------------ #
    # Construction
    # ------------------------------------------------------------------ #
    def _build(self) -> None:
        c = self.tokens.colors
        s = self.tokens.spacing

        row = QHBoxLayout(self)
        row.setContentsMargins(s.md, 0, s.sm, 0)
        row.setSpacing(s.sm)

        # --- Logo + app name ---
        logo = QLabel("I", self)
        logo.setObjectName("WorkspaceTitleBarLogo")
        logo.setFixedSize(30, 30)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(logo)

        title = QLabel("AI Gaming Video Editor", self)
        title.setObjectName("WorkspaceTitleBarName")
        title.setMinimumWidth(120)
        row.addWidget(title)

        row.addSpacing(s.lg)

        # --- Project selector pill (left of the menus, like the mock) ---
        project = QToolButton(self)
        project.setObjectName("WorkspaceProjectSelector")
        project.setText(f"{self._project_name}")
        project.setCursor(Qt.CursorShape.PointingHandCursor)
        project.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        try:
            project.setIcon(self.icon("chevron-down", c.text_muted, 14))
            project.setIconSize(QSize(14, 14))
            project.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            project.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        except Exception:  # pragma: no cover - icon optional
            pass
        row.addWidget(project)

        row.addSpacing(s.md)

        # --- Decorative top-level menu strip ---
        for label in _MENU_ITEMS:
            item = QPushButton(label, self)
            item.setObjectName("WorkspaceTitleBarMenuItem")
            item.setFlat(True)
            item.setCursor(Qt.CursorShape.PointingHandCursor)
            item.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            row.addWidget(item)

        row.addStretch(1)

        # --- Quick search ---
        search = QLineEdit(self)
        search.setObjectName("WorkspaceQuickSearch")
        search.setPlaceholderText("Search (Ctrl + K)")
        search.setFixedWidth(200)
        search.setClearButtonEnabled(False)
        try:
            from PySide6.QtWidgets import QLineEdit as _QLE

            search.addAction(
                self.icon("search", c.text_muted, 16),
                _QLE.ActionPosition.LeadingPosition,
            )
        except Exception:  # pragma: no cover - icon optional
            pass
        row.addWidget(search)

        row.addSpacing(s.xs)

        # --- AI Assistant primary pill + Record / Import / Export actions ---
        specs = (
            ("sparkles", "AI Assistant", "WorkspaceAIAssistant", "primary"),
            ("disc", "Record", "WorkspaceRecordAction", "chrome"),
            ("download", "Import", "WorkspaceImportAction", "chrome"),
            ("upload", "Export", "WorkspaceExportAction", "accent"),
        )
        for icon_name, text, obj, kind in specs:
            btn = QToolButton(self)
            btn.setObjectName(obj)
            btn.setProperty("chrome", f"action_{kind}")
            btn.setText(text)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            try:
                tint = (
                    c.text_on_accent if kind in ("primary", "accent")
                    else (c.error if obj == "WorkspaceRecordAction"
                          else c.text_secondary)
                )
                btn.setIcon(self.icon(icon_name, tint, 15))
                btn.setIconSize(QSize(15, 15))
                btn.setToolButtonStyle(
                    Qt.ToolButtonStyle.ToolButtonTextBesideIcon
                )
            except Exception:  # pragma: no cover
                pass
            row.addWidget(btn)

        row.addSpacing(s.sm)

        # --- Window controls ---
        self._add_window_controls(row)

    def _add_window_controls(self, row: QHBoxLayout) -> None:
        c = self.tokens.colors
        specs = (
            ("minus", "WorkspaceWindowMinimize", self._on_minimize),
            ("square", "WorkspaceWindowMaximize", self._on_toggle_max),
            ("x", "WorkspaceWindowClose", self._on_close),
        )
        for name, obj, handler in specs:
            btn = QToolButton(self)
            btn.setObjectName(obj)
            btn.setProperty("chrome", "windowCtl")
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setFixedSize(40, 30)
            color = c.error if obj == "WorkspaceWindowClose" else c.text_secondary
            try:
                btn.setIcon(self.icon(name, color, 16))
                btn.setIconSize(QSize(15, 15))
            except Exception:  # pragma: no cover
                btn.setText({"minus": "–", "square": "□", "x": "✕"}[name])
            btn.clicked.connect(handler)
            row.addWidget(btn)
            if obj == "WorkspaceWindowMaximize":
                self._maximize_btn = btn

    # ------------------------------------------------------------------ #
    # Window control handlers
    # ------------------------------------------------------------------ #
    def _on_minimize(self) -> None:
        win = self.window()
        if win is not None:
            win.showMinimized()

    def _on_toggle_max(self) -> None:
        win = self.window()
        if win is None:
            return
        if win.isMaximized():
            win.showNormal()
        else:
            win.showMaximized()
        self._refresh_maximize_icon()

    def _on_close(self) -> None:
        win = self.window()
        if win is not None:
            win.close()

    def _refresh_maximize_icon(self) -> None:
        if self._maximize_btn is None:
            return
        win = self.window()
        name = "restore" if (win is not None and win.isMaximized()) else "square"
        try:
            self._maximize_btn.setIcon(
                self.icon(name, self.tokens.colors.text_secondary, 15)
            )
        except Exception:  # pragma: no cover
            pass

    # ------------------------------------------------------------------ #
    # Window drag / double-click maximize
    # ------------------------------------------------------------------ #
    def _on_empty_area(self, event: QMouseEvent) -> bool:
        """True when the press is on the bar background, not a child control."""
        child = self.childAt(event.position().toPoint())
        if child is None:
            return True
        # Static labels (logo/title) are draggable; interactive controls are not.
        return child.objectName() in {
            "WorkspaceTitleBar",
            "WorkspaceTitleBarLogo",
            "WorkspaceTitleBarName",
        }

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self._on_empty_area(event):
            win = self.window()
            handle = win.windowHandle() if win is not None else None
            if handle is not None:
                handle.startSystemMove()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self._on_empty_area(event):
            self._on_toggle_max()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    # ------------------------------------------------------------------ #
    # Styling
    # ------------------------------------------------------------------ #
    def apply_theme(self) -> None:
        c = self.tokens.colors
        r = self.tokens.radius
        s = self.tokens.spacing
        t = self.tokens.typography
        self.setStyleSheet(
            f"#WorkspaceTitleBar {{ background-color: {c.background_base}; "
            f"border-bottom: 1px solid {c.border}; }} "
            # Logo tile: purple->magenta gradient chip.
            f"#WorkspaceTitleBarLogo {{ color: {c.text_primary}; "
            f"font-size: 17px; font-weight: 800; border-radius: {r.sm}px; "
            f"background: qlineargradient(x1:0, y1:0, x2:1, y2:1, "
            f"stop:0 {c.accent_blue}, stop:1 {c.accent_purple}); }} "
            f"#WorkspaceTitleBarName {{ color: {c.text_primary}; "
            f"font-size: 14px; font-weight: 700; letter-spacing: 1px; "
            f"background: transparent; }} "
            # Decorative menu items.
            f"#WorkspaceTitleBarMenuItem {{ color: {c.text_secondary}; "
            f"background: transparent; border: none; "
            f"padding: {s.xs}px {s.sm}px; border-radius: {r.sm}px; "
            f"font-size: 13px; }} "
            f"#WorkspaceTitleBarMenuItem:hover {{ color: {c.text_primary}; "
            f"background-color: {c.surface_overlay}; }} "
            # Project selector pill.
            f"#WorkspaceProjectSelector {{ color: {c.text_primary}; "
            f"background-color: {c.surface_elevated}; "
            f"border: 1px solid {c.border}; border-radius: {r.sm}px; "
            f"padding: {s.xs}px {s.md}px; font-size: 12px; font-weight: 600; }} "
            f"#WorkspaceProjectSelector:hover {{ border: 1px solid {c.accent_blue}; }} "
            f"#WorkspaceProjectSelector::menu-indicator {{ image: none; width: 0; }} "
            # Quick search.
            f"#WorkspaceQuickSearch {{ background-color: {c.surface}; "
            f"color: {c.text_secondary}; border: 1px solid {c.border}; "
            f"border-radius: {r.sm}px; padding: {s.xs}px {s.sm}px; "
            f"font-size: 12px; }} "
            f"#WorkspaceQuickSearch:focus {{ border: 1px solid {c.focus_ring}; }} "
            # Header action pills.
            f"QToolButton[chrome=\"action_primary\"] {{ "
            f"color: {c.text_primary}; font-size: 12px; font-weight: 600; "
            f"padding: {s.xs + 1}px {s.md}px; border-radius: {r.sm}px; "
            f"border: 1px solid {c.glass_highlight}; "
            f"background: qlineargradient(x1:0, y1:0, x2:1, y2:1, "
            f"stop:0 {c.accent_blue}, stop:1 {c.accent_purple}); }} "
            f"QToolButton[chrome=\"action_primary\"]:hover {{ "
            f"border: 1px solid {c.accent_cyan}; }} "
            f"QToolButton[chrome=\"action_accent\"] {{ "
            f"color: {c.text_primary}; font-size: 12px; font-weight: 600; "
            f"padding: {s.xs + 1}px {s.md}px; border-radius: {r.sm}px; "
            f"border: 1px solid rgba(168, 85, 247, 0.55); "
            f"background: rgba(168, 85, 247, 0.20); }} "
            f"QToolButton[chrome=\"action_accent\"]:hover {{ "
            f"background: rgba(168, 85, 247, 0.32); }} "
            f"QToolButton[chrome=\"action_chrome\"] {{ "
            f"color: {c.text_secondary}; font-size: 12px; "
            f"padding: {s.xs + 1}px {s.md}px; border-radius: {r.sm}px; "
            f"border: 1px solid {c.border}; "
            f"background-color: {c.surface_elevated}; }} "
            f"QToolButton[chrome=\"action_chrome\"]:hover {{ "
            f"color: {c.text_primary}; border: 1px solid {c.accent_blue}; }} "
            # Window controls.
            f"QToolButton[chrome=\"windowCtl\"] {{ background: transparent; "
            f"border: none; border-radius: {r.sm}px; }} "
            f"QToolButton[chrome=\"windowCtl\"]:hover {{ "
            f"background-color: {c.surface_overlay}; }} "
            f"#WorkspaceWindowClose:hover {{ background-color: {c.error}; }} "
        )
        _ = t  # typography reserved for future tuning
