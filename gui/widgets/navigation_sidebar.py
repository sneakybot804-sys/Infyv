"""NavigationSidebar: the premium left navigation rail (Milestone 2).

An additive, UI-only application navigation sidebar composed for the media
workspace's left column. It renders, top to bottom:

* a top navigation stack (Dashboard, Projects, Media, ... Settings) with an
  active item that carries a left cyan accent border and a cyan gradient glow;
* a Recent Projects list (rounded thumbnail + elided name + muted timestamp);
* a System Overview block (CPU / GPU / Memory) with stacked ultra-thin neon
  progress bars; and
* a compact AI Status card ("Neural Vision v3.2" / "Active").

Everything is decorative and token-derived. Selecting a nav item is UI-only
state: the sidebar tracks the current index and emits
:attr:`navigation_changed`. No backend, no telemetry, no :mod:`gui_core`.

Stable object names for later integration and tests:

* ``NavigationSidebar``       -- the root widget
* ``NavigationSidebarNav``    -- the top nav container
* ``NavigationItem``          -- each nav row button
* ``NavigationSidebarRecent`` -- the Recent Projects container
* ``NavigationRecentItem``    -- each recent-project row
* ``NavigationSidebarSystem`` -- the System Overview container
* ``NavigationSystemBar``     -- each ultra-thin metric bar
* ``NavigationSidebarAiStatus`` -- the bottom AI status card
"""
from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from gui.theme.manager import ThemeManager
from gui.widgets.base import ThemedWidget
from gui.widgets.meta_label import MetaLabel
from gui.widgets.section_header import SectionHeader

#: Top navigation items, in the exact blueprint order.
_NAV_ITEMS: Tuple[str, ...] = (
    "Dashboard",
    "Projects",
    "Media",
    "Assets",
    "AI Tools",
    "Templates",
    "Effects",
    "Audio",
    "Export",
    "Settings",
)

#: Decorative Recent Projects seed data: (name, timestamp).
_RECENT_PROJECTS: Tuple[Tuple[str, str], ...] = (
    ("Launch Trailer Cut", "Just now"),
    ("Boss Fight Highlights", "2 hours ago"),
    ("Season 3 Montage", "Yesterday"),
    ("Tournament Recap", "3 days ago"),
)

#: Decorative System Overview metrics: (label, sub-label, percent, accent).
_SYSTEM_METRICS: Tuple[Tuple[str, str, int, str], ...] = (
    ("CPU", "12-Core | 4.2 GHz", 54, "cyan"),
    ("GPU", "NVIDIA RTX 4070 Ti", 68, "green"),
    ("Memory", "32 GB | 18.4 GB used", 57, "cyan"),
)


class _ThinBar(QFrame):
    """An ultra-thin (3px) decorative meter with a neon fill on a dark track.

    Fill width is expressed via layout stretch so it tracks the widget width
    without any painting. Colors and radius are injected (token-derived by the
    caller); this frame stores none of its own theme state.
    """

    def __init__(
        self,
        *,
        fill_color: str,
        track_color: str,
        radius: int,
        percent: int,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("NavigationSystemBar")
        self.setFixedHeight(3)
        pct = max(0, min(100, int(percent)))

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        self._fill = QFrame(self)
        self._fill.setObjectName("NavigationSystemBarFill")
        row.addWidget(self._fill, pct)
        # Remainder of the track (kept transparent) fills the rest.
        row.addStretch(max(1, 100 - pct))

        self.setStyleSheet(
            f"#NavigationSystemBar {{ background: {track_color}; "
            f"border-radius: {radius}px; }} "
            f"#NavigationSystemBarFill {{ background: {fill_color}; "
            f"border-radius: {radius}px; }}"
        )


class NavigationSidebar(ThemedWidget):
    """The premium left navigation rail (UI-only, additive).

    Args:
        theme: Injected theme manager (sole source of visual values).
        current: Initially active nav index. Default ``0`` (Dashboard).
        parent: Optional Qt parent.

    Signals:
        navigation_changed(int): Emitted with the new active index whenever
            the active nav item changes. UI-only; no routing, no backend.
    """

    navigation_changed = Signal(int)

    def __init__(
        self,
        theme: ThemeManager,
        *,
        current: int = 0,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(theme, parent)
        self.setObjectName("NavigationSidebar")

        self._current = current
        self._nav_buttons: List[QWidget] = []

        # Lock the rail to exactly 240px (DPI-scaled) so the splitter never
        # compresses or expands it and Qt's geometry engine has an unambiguous
        # fixed size to work with.
        fixed_w = self.scaled(240)
        self.setFixedWidth(fixed_w)

        tokens = self.tokens
        root = QVBoxLayout(self)
        margin = self.scaled(tokens.spacing.lg)  # 16px outer padding
        root.setContentsMargins(margin, margin, margin, margin)
        root.setSpacing(self.scaled(tokens.spacing.xl))  # 24px between blocks

        root.addWidget(self._build_nav(), 0)
        root.addWidget(self._build_recent(), 1)
        root.addWidget(self._build_system(), 0)
        root.addWidget(self._build_ai_status(), 0)

        self._update_nav_styles()
        self.apply_theme()

    # ------------------------------------------------------------------ #
    # Region builders
    # ------------------------------------------------------------------ #
    def _build_nav(self) -> QWidget:
        """Build the top navigation stack with 8px vertical gaps."""
        tokens = self.tokens
        nav = QWidget(self)
        nav.setObjectName("NavigationSidebarNav")
        layout = QVBoxLayout(nav)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(self.scaled(tokens.spacing.sm))  # 8px gap

        row_h = self.scaled(36)  # explicit row height so QSS padding never
        # collapses the geometry; 36px matches the blueprint spec.
        for index, label in enumerate(_NAV_ITEMS):
            item = QLabel(label, nav)
            item.setObjectName("NavigationItem")
            item.setFont(self._theme.font("body"))
            item.setFixedHeight(row_h)
            item.setCursor(Qt.CursorShape.PointingHandCursor)
            # UI-only click handling via a lambda-bound mouse release.
            item.mouseReleaseEvent = (  # type: ignore[assignment]
                lambda _event, i=index: self.select(i)
            )
            layout.addWidget(item)
            self._nav_buttons.append(item)
        return nav

    def _build_recent(self) -> QWidget:
        """Build the Recent Projects list (24px below nav, 8px row gap)."""
        tokens = self.tokens
        wrap = QWidget(self)
        wrap.setObjectName("NavigationSidebarRecent")
        layout = QVBoxLayout(wrap)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(self.scaled(tokens.spacing.sm))  # 8px

        header = SectionHeader(self._theme, "Recent Projects")
        layout.addWidget(header)

        rows = QWidget(wrap)
        rows.setObjectName("NavigationRecentRows")
        rows_layout = QVBoxLayout(rows)
        rows_layout.setContentsMargins(0, 0, 0, 0)
        rows_layout.setSpacing(self.scaled(tokens.spacing.sm))  # explicit 8px

        for name, when in _RECENT_PROJECTS:
            rows_layout.addWidget(self._recent_row(name, when))
        rows_layout.addStretch(1)
        layout.addWidget(rows, 1)
        return wrap

    def _recent_row(self, name: str, when: str) -> QWidget:
        """Build a single recent-project row: thumb + elided name + time."""
        tokens = self.tokens
        row = QWidget(self)
        row.setObjectName("NavigationRecentItem")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(self.scaled(tokens.spacing.sm))

        thumb = QFrame(row)
        thumb.setObjectName("NavigationRecentThumb")
        side = self.scaled(24)
        thumb.setFixedSize(side, side)
        layout.addWidget(thumb, 0)

        name_label = QLabel(name, row)
        name_label.setObjectName("NavigationRecentName")
        name_label.setFont(self._theme.font("body_small"))
        name_label.setMinimumWidth(0)
        layout.addWidget(name_label, 1)

        time_label = MetaLabel(
            self._theme, when, role="muted", style="caption"
        )
        time_label.setObjectName("NavigationRecentTime")
        layout.addWidget(time_label, 0)
        return row

    def _build_system(self) -> QWidget:
        """Build the System Overview block (stacked labels over thin bars)."""
        tokens = self.tokens
        c = tokens.colors
        wrap = QWidget(self)
        wrap.setObjectName("NavigationSidebarSystem")
        layout = QVBoxLayout(wrap)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(self.scaled(tokens.spacing.sm))  # explicit 8px row gap

        header = SectionHeader(self._theme, "System Overview")
        layout.addWidget(header)

        accent_map = {"cyan": c.accent_cyan, "green": c.success}
        for label, sub, percent, accent in _SYSTEM_METRICS:
            layout.addWidget(
                self._system_row(label, sub, percent, accent_map[accent])
            )
        return wrap

    def _system_row(
        self, label: str, sub: str, percent: int, fill_color: str
    ) -> QWidget:
        """Build one stacked metric row: label + %, sub-label, thin bar."""
        tokens = self.tokens
        c = tokens.colors
        row = QWidget(self)
        row.setObjectName("NavigationSystemRow")
        col = QVBoxLayout(row)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(self.scaled(tokens.spacing.xxs))

        # Line 1: label (left) + percentage (right).
        line = QHBoxLayout()
        line.setContentsMargins(0, 0, 0, 0)
        name = QLabel(label, row)
        name.setObjectName("NavigationSystemLabel")
        name.setFont(self._theme.font("caption"))
        pct = QLabel(f"{percent}%", row)
        pct.setObjectName("NavigationSystemPercent")
        pct.setFont(self._theme.font("caption"))
        pct.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        line.addWidget(name, 1)
        line.addWidget(pct, 0)
        col.addLayout(line)

        # Sub-label: tiny, low-opacity hardware descriptor.
        sub_label = MetaLabel(self._theme, sub, role="disabled", style="caption")
        sub_label.setObjectName("NavigationSystemSubLabel")
        col.addWidget(sub_label)

        # Line 2: ultra-thin neon meter underneath the text.
        # Track uses a faint white groove so it reads as a carved-in channel
        # rather than disappearing into the dark panel background.
        bar = _ThinBar(
            fill_color=fill_color,
            track_color="rgba(255, 255, 255, 0.05)",
            radius=self.scaled(tokens.radius.sm) // 4 or 1,
            percent=percent,
            parent=row,
        )
        col.addWidget(bar)

        name.setStyleSheet(
            f"#NavigationSystemLabel {{ color: {c.text_secondary}; "
            f"background: transparent; }}"
        )
        pct.setStyleSheet(
            f"#NavigationSystemPercent {{ color: {c.text_primary}; "
            f"background: transparent; }}"
        )
        return row

    def _build_ai_status(self) -> QWidget:
        """Build the compact AI status card at the very bottom."""
        tokens = self.tokens
        c = tokens.colors
        card = QFrame(self)
        card.setObjectName("NavigationSidebarAiStatus")
        card.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QHBoxLayout(card)
        pad = self.scaled(tokens.spacing.sm)
        layout.setContentsMargins(pad, pad, pad, pad)
        layout.setSpacing(self.scaled(tokens.spacing.sm))

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(self.scaled(tokens.spacing.xxs))
        model = QLabel("Neural Vision v3.2", card)
        model.setObjectName("NavigationAiModel")
        model.setFont(self._theme.font("body_small"))
        model.setStyleSheet(
            f"#NavigationAiModel {{ color: {c.text_primary}; "
            f"background: transparent; }}"
        )
        status = QLabel("Active", card)
        status.setObjectName("NavigationAiState")
        status.setFont(self._theme.font("caption"))
        status.setStyleSheet(
            f"#NavigationAiState {{ color: {c.success}; "
            f"background: transparent; }}"
        )
        text_col.addWidget(model)
        text_col.addWidget(status)
        layout.addLayout(text_col, 1)

        dot = QFrame(card)
        dot.setObjectName("NavigationAiDot")
        dot.setFixedSize(self.scaled(8), self.scaled(8))
        dot.setStyleSheet(
            f"#NavigationAiDot {{ background: {c.success}; "
            f"border-radius: {self.scaled(4)}px; }}"
        )
        layout.addWidget(dot, 0, Qt.AlignmentFlag.AlignVCenter)

        card.setStyleSheet(
            f"#NavigationSidebarAiStatus {{ background: {c.surface_overlay}; "
            f"border: 1px solid {c.glass_border}; "
            f"border-radius: {self.scaled(tokens.radius.md)}px; }}"
        )
        return card

    # ------------------------------------------------------------------ #
    # Public API (UI-only state)
    # ------------------------------------------------------------------ #
    def select(self, index: int) -> None:
        """Activate the nav item at ``index``; no-op when already active.

        Emits :attr:`navigation_changed` when the active index changes.
        Out-of-range indices raise.
        """
        if not (0 <= index < len(self._nav_buttons)):
            raise ValueError(f"navigation index out of range: {index}")
        if index == self._current:
            return
        self._current = index
        self._update_nav_styles()
        self.navigation_changed.emit(self._current)

    def current_index(self) -> int:
        """Return the active nav index."""
        return self._current

    def current_item(self) -> str:
        """Return the active nav item label."""
        return _NAV_ITEMS[self._current]

    def items(self) -> Sequence[str]:
        """Return the nav item labels (a copy)."""
        return tuple(_NAV_ITEMS)

    # ------------------------------------------------------------------ #
    # Theming
    # ------------------------------------------------------------------ #
    def _update_nav_styles(self) -> None:
        """Apply active/inactive styling to each nav item."""
        c = self.tokens.colors
        # Border-radius 8px on the right corners only (blueprint spec).
        radius = self.scaled(self.tokens.radius.sm)   # 8px
        # 16px left/right padding so text is never squished against the edge.
        pad_h = self.scaled(self.tokens.spacing.lg)   # 16px
        accent = self.tokens.colors.accent_cyan

        for index, item in enumerate(self._nav_buttons):
            if index == self._current:
                item.setStyleSheet(
                    # padding-left/right only: geometry is owned by
                    # setFixedHeight(36px) so vertical padding is irrelevant
                    # and would fight the fixed height.
                    f"#NavigationItem {{ color: {accent}; "
                    f"padding-left: {pad_h}px; padding-right: {pad_h}px; "
                    f"border-left: 3px solid {accent}; "
                    f"border-top-right-radius: {radius}px; "
                    f"border-bottom-right-radius: {radius}px; "
                    f"background: qlineargradient(x1:0, y1:0, x2:1, y2:0, "
                    f"stop:0 {c.accent_cyan_glow}, stop:1 transparent); }}"
                )
            else:
                item.setStyleSheet(
                    f"#NavigationItem {{ color: {c.text_secondary}; "
                    f"padding-left: {pad_h}px; padding-right: {pad_h}px; "
                    f"border-left: 3px solid transparent; "
                    f"border-top-right-radius: {radius}px; "
                    f"border-bottom-right-radius: {radius}px; "
                    f"background: transparent; }} "
                    f"#NavigationItem:hover {{ "
                    f"background: rgba(255, 255, 255, 0.05); "
                    f"color: {c.text_primary}; }}"
                )

    def apply_theme(self) -> None:
        """Apply the glassmorphic rail backing and refresh nav styling."""
        c = self.tokens.colors
        radius = self.scaled(self.tokens.radius.md)  # 12px
        thumb_radius = self.scaled(self.tokens.radius.sm)  # 8px
        self.setStyleSheet(
            # Deep semi-opaque surface so the rail reads as a solid premium
            # panel rather than a transparent overlay. The border is a faint
            # white edge that separates it from the workspace background.
            f"#NavigationSidebar {{ "
            f"background: rgba(18, 22, 33, 0.75); "
            f"border: 1px solid rgba(255, 255, 255, 0.06); "
            f"border-radius: {radius}px; }} "
            f"#NavigationSidebarNav {{ background: transparent; }} "
            f"#NavigationRecentThumb {{ background: {c.surface_overlay}; "
            f"border-radius: {thumb_radius}px; }} "
            f"#NavigationRecentName {{ color: {c.text_secondary}; "
            f"background: transparent; }} "
            f"#NavigationRecentRows {{ background: transparent; }} "
            f"#NavigationSidebarRecent {{ background: transparent; }} "
            f"#NavigationSidebarSystem {{ background: transparent; }} "
            f"#NavigationSystemRow {{ background: transparent; }}"
        )
        self._update_nav_styles()
