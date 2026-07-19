"""NavigationSidebar: the premium left navigation region (NEXUS layout).

An additive, UI-only application navigation sidebar composed for the media
workspace's left column. It renders TWO visual columns, matching the NEXUS
EDIT PRO reference:

* a narrow nav rail (Dashboard, Projects, Media, ... Settings) with an
  active item that carries a rounded violet fill, plus a user chip pinned to
  the rail's bottom; and
* a projects panel with a "Recent Projects" list (gradient thumbnail +
  name + timestamp, active row highlighted), a "+ New Project" action, and
  a SYSTEM block (GPU / RAM meters + AI ENGINE / RENDER ENGINE readouts).

Everything is decorative and token-derived. Selecting a nav item is UI-only
state: the sidebar tracks the current index and emits
:attr:`navigation_changed`. No backend, no telemetry, no :mod:`gui_core`.

Stable object names for later integration and tests:

* ``NavigationSidebar``       -- the root widget
* ``NavigationSidebarNav``    -- the nav rail container
* ``NavigationItem``          -- each nav row button
* ``NavigationSidebarRecent`` -- the Recent Projects container
* ``NavigationRecentItem``    -- each recent-project row
* ``NavigationSidebarSystem`` -- the System block container
* ``NavigationSystemBar``     -- each ultra-thin metric bar
* ``NavigationSidebarAiStatus`` -- the AI engine status readout
"""
from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

from PySide6.QtCore import QEasingCurve, QParallelAnimationGroup, QPropertyAnimation, QVariantAnimation, Qt, Signal
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QStyleOption,
    QVBoxLayout,
    QWidget,
)

from gui.theme.manager import ThemeManager
from gui.widgets.base import ThemedWidget
from gui.widgets.meta_label import MetaLabel

#: Nav rail items, in the exact reference order.
_NAV_ITEMS: Tuple[str, ...] = (
    "Dashboard",
    "Projects",
    "Media",
    "Assets",
    "Timeline",
    "Effects",
    "Transitions",
    "Audio",
    "Captions",
    "Templates",
    "AI Studio",
    "Export",
    "Settings",
)

#: Lucide icon name for each nav item (index-aligned with _NAV_ITEMS).
_NAV_ICONS: Tuple[str, ...] = (
    "layout-dashboard",
    "folder",
    "image",
    "package",
    "clapperboard",
    "zap",
    "repeat",
    "audio-lines",
    "type",
    "layout-template",
    "bot",
    "upload",
    "settings",
)

#: Decorative Recent Projects seed data: (name, timestamp, thumb-gradient).
_RECENT_PROJECTS: Tuple[Tuple[str, str, str], ...] = (
    ("Valorant Montage", "Today, 2:35 PM", "magenta"),
    ("Radiant Moments", "Yesterday, 11:20 PM", "violet"),
    ("Clutch Compilation", "May 14, 2025", "blue"),
    ("Funny & Fails", "May 12, 2025", "pink"),
    ("Edit Practice", "May 10, 2025", "violet"),
)

#: Decorative SYSTEM metrics: (label, sub-label, percent, accent).
_SYSTEM_METRICS: Tuple[Tuple[str, str, int, str], ...] = (
    ("GPU", "NVIDIA RTX 4070 Ti", 78, "green"),
    ("RAM", "22.4 / 32 GB", 70, "violet"),
    ("CPU", "12-Core | 4.2 GHz", 41, "violet"),
)

#: Decorative engine readouts: (label, sub-label).
_SYSTEM_ENGINES: Tuple[Tuple[str, str], ...] = (
    ("AI ENGINE", "INFY AI v3.2.1"),
    ("RENDER ENGINE", "CUDA / OPTIX"),
)


class _ThinBar(QFrame):
    """An ultra-thin (3px) decorative meter with a neon fill on a dark track.

    Fill width is expressed via a QPropertyAnimation on the fill widget's
    maximumWidth so it animates from 0 → target on construction, and can be
    updated live via :meth:`set_percent`. Colors and radius are injected
    (token-derived by the caller); this frame stores none of its own theme
    state.
    """

    def __init__(
        self,
        *,
        fill_color: str,
        track_color: str,
        radius: int,
        percent: int,
        animated: bool = True,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("NavigationSystemBar")
        self.setFixedHeight(3)
        self._percent = max(0, min(100, int(percent)))
        self._animated = animated

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        self._fill = QFrame(self)
        self._fill.setObjectName("NavigationSystemBarFill")
        # Start at zero width; animation will expand to the target percent.
        self._fill.setMaximumWidth(0)
        row.addWidget(self._fill, self._percent)
        row.addStretch(max(1, 100 - self._percent))

        self.setStyleSheet(
            f"#NavigationSystemBar {{ background: {track_color}; "
            f"border-radius: {radius}px; }} "
            f"#NavigationSystemBarFill {{ background: {fill_color}; "
            f"border-radius: {radius}px; }}"
        )

        # Persistent animation driven by showEvent so the bar fills after
        # the sidebar is laid out and has a real pixel width.
        self._fill_anim = QPropertyAnimation(self._fill, b"maximumWidth", self)
        self._fill_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def showEvent(self, event) -> None:  # noqa: N802
        """Animate the fill from 0 → target width on first show."""
        super().showEvent(event)
        if not self._animated:
            self._fill.setMaximumWidth(16777215)
            return
        if getattr(self, "_bar_shown", False):
            return
        self._bar_shown = True
        # Delay one frame so the widget has a real width after layout.
        from PySide6.QtCore import QTimer
        QTimer.singleShot(60, self._run_fill_anim)

    def _run_fill_anim(self) -> None:
        total = self.width()
        if total <= 0:
            self._fill.setMaximumWidth(16777215)
            return
        target = int(total * self._percent / 100)
        self._fill_anim.stop()
        self._fill_anim.setDuration(700)
        self._fill_anim.setStartValue(0)
        self._fill_anim.setEndValue(target)
        self._fill_anim.start()
        # After animation finishes, unlock the maximum so resize works.
        self._fill_anim.finished.connect(lambda: self._fill.setMaximumWidth(16777215))


class NavigationSidebar(ThemedWidget):
    """The premium left navigation region (UI-only, additive).

    Args:
        theme: Injected theme manager (sole source of visual values).
        current: Initially active nav index. Default ``1`` (Projects).
        parent: Optional Qt parent.

    Signals:
        navigation_changed(int): Emitted with the new active index whenever
            the active nav item changes. UI-only; no routing, no backend.
    """

    navigation_changed = Signal(int)

    #: Total fixed width of the two-column region (rail + projects panel).
    #: Sized so the longest strings ("Clutch Compilation", "INFY USER",
    #: "RENDER ENGINE") render fully without eliding.
    TOTAL_WIDTH = 376
    #: Width of the icon+label nav rail column.
    RAIL_WIDTH = 168

    def __init__(
        self,
        theme: ThemeManager,
        *,
        current: int = 1,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(theme, parent)
        self.setObjectName("NavigationSidebar")

        self._current = current
        self._nav_buttons: List[QWidget] = []

        # Lock the region to the reference's two-column width (DPI-scaled).
        self.setFixedWidth(self.scaled(self.TOTAL_WIDTH))

        # WA_StyledBackground: required so Qt honours background-color in QSS
        # for plain QWidget subclasses. Without it the panel never paints.
        self.setAttribute(Qt.WA_StyledBackground, True)

        tokens = self.tokens
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_rail(), 0)
        root.addWidget(self._build_projects_panel(), 1)
        _ = tokens

        # apply_theme sets the panel background and calls _update_nav_styles.
        # The showEvent override below re-applies nav styles after Qt's first
        # layout pass so the active highlight is never wiped by a cascade reset.
        self.apply_theme()

    # ------------------------------------------------------------------ #
    # Qt overrides
    # ------------------------------------------------------------------ #
    def paintEvent(self, event) -> None:  # noqa: N802
        """Paint the styled background explicitly.

        QWidget subclasses with WA_StyledBackground still need a paintEvent
        that calls drawPrimitive(PE_Widget) for the background-color rule to
        render. Without this override the panel surface stays transparent even
        when the attribute and QSS rule are both correctly set.
        """
        opt = QStyleOption()
        opt.initFrom(self)
        painter = QPainter(self)
        self.style().drawPrimitive(
            self.style().PrimitiveElement.PE_Widget, opt, painter, self
        )

    def showEvent(self, event) -> None:  # noqa: N802
        """Re-apply nav styles after Qt's first layout and stylesheet pass.

        Qt defers stylesheet application until the widget is shown. Any
        setStyleSheet call made before show() can be overwritten by the
        cascade reset that happens during the initial paint cycle. Calling
        _update_nav_styles() here guarantees the active-item highlight is
        applied after that reset has settled.
        """
        super().showEvent(event)
        self._update_nav_styles()

    # ------------------------------------------------------------------ #
    # Region builders
    # ------------------------------------------------------------------ #
    def _build_rail(self) -> QWidget:
        """Build the left nav rail: icon+label stack + bottom user chip."""
        tokens = self.tokens
        rail = QWidget(self)
        rail.setObjectName("NavigationSidebarRail")
        rail.setAttribute(Qt.WA_StyledBackground, True)
        rail.setFixedWidth(self.scaled(self.RAIL_WIDTH))
        col = QVBoxLayout(rail)
        m = self.scaled(tokens.spacing.sm)
        col.setContentsMargins(m, self.scaled(tokens.spacing.md), m, m)
        col.setSpacing(self.scaled(tokens.spacing.md))

        nav = QWidget(rail)
        nav.setObjectName("NavigationSidebarNav")
        layout = QVBoxLayout(nav)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(self.scaled(tokens.spacing.xs))  # tight 4px gap

        row_h = self.scaled(34)
        icon_side = self.scaled(16)
        pad_h = self.scaled(tokens.spacing.sm + 2)  # 10px inner padding
        for index, label in enumerate(_NAV_ITEMS):
            item = QWidget(nav)
            item.setObjectName("NavigationItem")
            item.setAttribute(Qt.WA_StyledBackground, True)
            item.setFixedHeight(row_h)
            item.setCursor(Qt.CursorShape.PointingHandCursor)
            row = QHBoxLayout(item)
            row.setContentsMargins(pad_h, 0, pad_h, 0)
            row.setSpacing(self.scaled(tokens.spacing.sm + 2))  # 10px

            icon = QLabel(item)
            icon.setObjectName("NavigationItemIcon")
            icon.setFixedSize(icon_side, icon_side)
            icon.setScaledContents(True)
            row.addWidget(icon, 0, Qt.AlignmentFlag.AlignVCenter)

            text = QLabel(label, item)
            text.setObjectName("NavigationItemText")
            text.setFont(self._theme.font("body_small"))
            row.addWidget(text, 1, Qt.AlignmentFlag.AlignVCenter)

            # UI-only click handling via a lambda-bound mouse release.
            item.mouseReleaseEvent = (  # type: ignore[assignment]
                lambda _event, i=index: self.select(i)
            )
            layout.addWidget(item)
            self._nav_buttons.append(item)

        col.addWidget(nav, 0)
        col.addStretch(1)
        col.addWidget(self._build_user_chip(rail), 0)
        return rail

    def _build_user_chip(self, parent: QWidget) -> QWidget:
        """Build the bottom-of-rail user chip (avatar + name + plan)."""
        tokens = self.tokens
        c = tokens.colors
        chip = QFrame(parent)
        chip.setObjectName("NavigationUserChip")
        row = QHBoxLayout(chip)
        pad = self.scaled(tokens.spacing.sm)
        row.setContentsMargins(pad, pad, pad, pad)
        row.setSpacing(self.scaled(tokens.spacing.sm))

        avatar = QLabel("I", chip)
        avatar.setObjectName("NavigationUserAvatar")
        side = self.scaled(26)
        avatar.setFixedSize(side, side)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setStyleSheet(
            f"#NavigationUserAvatar {{ color: {c.text_primary}; "
            f"font-size: 12px; font-weight: 800; "
            f"border-radius: {side // 2}px; "
            f"background: qlineargradient(x1:0, y1:0, x2:1, y2:1, "
            f"stop:0 {c.accent_blue}, stop:1 {c.accent_purple}); }}"
        )
        row.addWidget(avatar, 0)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(0)
        name = QLabel("INFY USER", chip)
        name.setObjectName("NavigationUserName")
        name.setFont(self._theme.font("caption"))
        name.setMinimumWidth(self.scaled(80))
        name.setStyleSheet(
            f"#NavigationUserName {{ color: {c.text_primary}; "
            f"background: transparent; font-weight: 700; }}"
        )
        plan = QLabel("Pro Plan", chip)
        plan.setObjectName("NavigationUserPlan")
        plan.setFont(self._theme.font("caption"))
        plan.setMinimumWidth(self.scaled(60))
        plan.setStyleSheet(
            f"#NavigationUserPlan {{ color: {c.text_muted}; "
            f"background: transparent; }}"
        )
        text_col.addWidget(name)
        text_col.addWidget(plan)
        row.addLayout(text_col, 1)

        gear = QLabel(chip)
        gear.setObjectName("NavigationUserSettings")
        gside = self.scaled(14)
        gear.setFixedSize(gside, gside)
        gear.setScaledContents(True)
        try:
            gear.setPixmap(
                self.icon("settings", c.text_muted, gside).pixmap(gside, gside)
            )
        except Exception:  # pragma: no cover - icon optional
            pass
        row.addWidget(gear, 0, Qt.AlignmentFlag.AlignVCenter)

        chip.setStyleSheet(
            f"#NavigationUserChip {{ background: {c.surface_elevated}; "
            f"border: 1px solid {c.glass_border}; "
            f"border-radius: {self.scaled(tokens.radius.md)}px; }}"
        )
        return chip

    def _build_projects_panel(self) -> QWidget:
        """Build the second column: Recent Projects + SYSTEM block."""
        tokens = self.tokens
        panel = QWidget(self)
        panel.setObjectName("NavigationSidebarPanel")
        panel.setAttribute(Qt.WA_StyledBackground, True)
        col = QVBoxLayout(panel)
        m = self.scaled(tokens.spacing.md)
        col.setContentsMargins(m, self.scaled(tokens.spacing.md), m, m)
        col.setSpacing(self.scaled(tokens.spacing.md))

        col.addWidget(self._build_recent(panel), 0)
        col.addStretch(1)
        col.addWidget(self._build_system(panel), 0)
        return panel

    def _build_recent(self, parent: QWidget) -> QWidget:
        """Build the Recent Projects list with the caption header row."""
        tokens = self.tokens
        c = tokens.colors
        wrap = QWidget(parent)
        wrap.setObjectName("NavigationSidebarRecent")
        layout = QVBoxLayout(wrap)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(self.scaled(tokens.spacing.sm))  # 8px

        # Caption header: "RECENT PROJECTS" + trailing "+".
        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        title = QLabel("RECENT PROJECTS", wrap)
        title.setObjectName("NavigationRecentTitle")
        title.setFont(self._theme.font("caption"))
        title.setMinimumWidth(self.scaled(120))
        title.setStyleSheet(
            f"#NavigationRecentTitle {{ color: {c.text_muted}; "
            f"background: transparent; font-weight: 700; "
            f"letter-spacing: 1px; }}"
        )
        plus = QLabel("+", wrap)
        plus.setObjectName("NavigationRecentPlus")
        plus.setStyleSheet(
            f"#NavigationRecentPlus {{ color: {c.text_muted}; "
            f"background: transparent; font-size: 14px; }}"
        )
        head.addWidget(title, 1)
        head.addWidget(plus, 0)
        layout.addLayout(head)

        # "+ New Project" ghost action.
        new_project = QLabel("+  New Project", wrap)
        new_project.setObjectName("NavigationRecentNewProject")
        new_project.setFont(self._theme.font("body_small"))
        new_project.setFixedHeight(self.scaled(30))
        new_project.setCursor(Qt.CursorShape.PointingHandCursor)
        new_project.setStyleSheet(
            f"#NavigationRecentNewProject {{ color: {c.text_secondary}; "
            f"background: transparent; padding-left: {self.scaled(6)}px; "
            f"border: 1px dashed {c.glass_border}; "
            f"border-radius: {self.scaled(tokens.radius.sm)}px; }} "
            f"#NavigationRecentNewProject:hover {{ "
            f"color: {c.text_primary}; border-color: {c.accent_blue}; }}"
        )
        layout.addWidget(new_project)

        for index, (name, when, grad) in enumerate(_RECENT_PROJECTS):
            layout.addWidget(
                self._recent_row(name, when, grad, active=(index == 0))
            )
        return wrap

    def _recent_row(
        self, name: str, when: str, grad: str, *, active: bool = False
    ) -> QWidget:
        """Build a recent-project row: gradient thumb + name over timestamp."""
        tokens = self.tokens
        c = tokens.colors
        row = QWidget(self)
        row.setObjectName("NavigationRecentItem")
        row.setAttribute(Qt.WA_StyledBackground, True)
        row.setCursor(Qt.CursorShape.PointingHandCursor)
        layout = QHBoxLayout(row)
        pad = self.scaled(tokens.spacing.xs + 2)
        layout.setContentsMargins(pad, pad, pad, pad)
        layout.setSpacing(self.scaled(tokens.spacing.sm))

        grads = {
            "magenta": (c.accent_purple, "#511543"),
            "violet": (c.accent_blue, "#2A1650"),
            "blue": ("#6366f1", "#1E1B4B"),
            "pink": (c.accent_pink, "#500F2E"),
        }
        g0, g1 = grads.get(grad, grads["violet"])
        thumb = QFrame(row)
        thumb.setObjectName("NavigationRecentThumb")
        thumb.setFixedSize(self.scaled(40), self.scaled(28))
        thumb.setStyleSheet(
            f"#NavigationRecentThumb {{ "
            f"background: qlineargradient(x1:0, y1:0, x2:1, y2:1, "
            f"stop:0 {g0}, stop:1 {g1}); "
            f"border: 1px solid {c.glass_border}; "
            f"border-radius: {self.scaled(tokens.radius.sm)}px; }}"
        )
        layout.addWidget(thumb, 0)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(0)
        name_label = QLabel(name, row)
        name_label.setObjectName("NavigationRecentName")
        name_label.setFont(self._theme.font("body_small"))
        name_label.setMinimumWidth(self.scaled(80))
        text_col.addWidget(name_label)
        time_label = MetaLabel(
            self._theme, when, role="muted", style="caption"
        )
        time_label.setObjectName("NavigationRecentTime")
        text_col.addWidget(time_label)
        layout.addLayout(text_col, 1)

        radius = self.scaled(tokens.radius.sm)
        if active:
            row.setStyleSheet(
                f"#NavigationRecentItem {{ "
                f"background: rgba(168, 85, 247, 0.14); "
                f"border: 1px solid rgba(168, 85, 247, 0.55); "
                f"border-radius: {radius}px; }} "
                f"#NavigationRecentName {{ color: {c.text_primary}; "
                f"background: transparent; font-weight: 600; }}"
            )
        else:
            row.setStyleSheet(
                f"#NavigationRecentItem {{ background: transparent; "
                f"border: 1px solid transparent; "
                f"border-radius: {radius}px; }} "
                f"#NavigationRecentItem:hover {{ "
                f"background: rgba(255, 255, 255, 0.05); }} "
                f"#NavigationRecentName {{ color: {c.text_secondary}; "
                f"background: transparent; }}"
            )
        return row

    def _build_system(self, parent: QWidget) -> QWidget:
        """Build the SYSTEM block: meters + engine readouts."""
        tokens = self.tokens
        c = tokens.colors
        wrap = QWidget(parent)
        wrap.setObjectName("NavigationSidebarSystem")
        layout = QVBoxLayout(wrap)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(self.scaled(tokens.spacing.sm))  # explicit 8px gap

        title = QLabel("SYSTEM", wrap)
        title.setObjectName("NavigationSystemTitle")
        title.setFont(self._theme.font("caption"))
        title.setStyleSheet(
            f"#NavigationSystemTitle {{ color: {c.text_muted}; "
            f"background: transparent; font-weight: 700; "
            f"letter-spacing: 1px; }}"
        )
        layout.addWidget(title)

        accent_map = {
            "violet": (
                f"qlineargradient(x1:0, y1:0, x2:1, y2:0, "
                f"stop:0 {c.accent_blue}, stop:1 {c.accent_purple})"
            ),
            "green": (
                f"qlineargradient(x1:0, y1:0, x2:1, y2:0, "
                f"stop:0 {c.success}, stop:1 {c.accent_cyan})"
            ),
        }
        for label, sub, percent, accent in _SYSTEM_METRICS:
            layout.addWidget(
                self._system_row(label, sub, percent, accent_map[accent])
            )

        # Engine readouts: label + sub-label + trailing "Active" badge.
        for label, sub in _SYSTEM_ENGINES:
            layout.addWidget(self._engine_row(wrap, label, sub))
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
        pct.setMinimumWidth(self.scaled(34))
        pct.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        line.addWidget(name, 1)
        line.addWidget(pct, 0)
        col.addLayout(line)

        # Sub-label: tiny, low-opacity hardware descriptor.
        sub_label = MetaLabel(self._theme, sub, role="disabled", style="caption")
        sub_label.setObjectName("NavigationSystemSubLabel")
        sub_label.setMinimumHeight(self.scaled(20))
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

    def _engine_row(self, parent: QWidget, label: str, sub: str) -> QWidget:
        """Build one engine readout row: label over sub + trailing badge."""
        tokens = self.tokens
        c = tokens.colors
        row = QWidget(parent)
        row.setObjectName("NavigationSidebarAiStatus")
        line = QHBoxLayout(row)
        line.setContentsMargins(0, self.scaled(tokens.spacing.xxs), 0, 0)
        line.setSpacing(self.scaled(tokens.spacing.sm))

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(0)
        title = QLabel(label, row)
        title.setObjectName("NavigationAiTitle")
        title.setFont(self._theme.font("caption"))
        title.setMinimumWidth(self.scaled(96))
        title.setStyleSheet(
            f"#NavigationAiTitle {{ color: {c.text_secondary}; "
            f"background: transparent; font-weight: 700; "
            f"letter-spacing: 1px; }}"
        )
        model = QLabel(sub, row)
        model.setObjectName("NavigationAiModel")
        model.setFont(self._theme.font("caption"))
        model.setMinimumWidth(self.scaled(96))
        model.setStyleSheet(
            f"#NavigationAiModel {{ color: {c.text_muted}; "
            f"background: transparent; }}"
        )
        text_col.addWidget(title)
        text_col.addWidget(model)
        line.addLayout(text_col, 1)

        state = QLabel("Active", row)
        state.setObjectName("NavigationAiState")
        state.setFont(self._theme.font("caption"))
        state.setMinimumWidth(self.scaled(46))
        state.setStyleSheet(
            f"#NavigationAiState {{ color: {c.success}; "
            f"background: transparent; font-weight: 600; }}"
        )
        line.addWidget(state, 0, Qt.AlignmentFlag.AlignVCenter)
        return row

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
        old = self._current
        self._current = index
        self._animate_nav_selection(old, index)
        self.navigation_changed.emit(self._current)

    def _animate_nav_selection(self, old_index: int, new_index: int) -> None:
        """Smoothly cross-fade the active highlight between nav items.

        Uses a QParallelAnimationGroup to simultaneously fade the old item's
        background alpha out and the new item's background alpha in.
        """
        c = self.tokens.colors
        radius = self.scaled(self.tokens.radius.sm)
        side = self.scaled(16)
        dur = self._theme.duration("fast")
        easing = self._theme.easing("out_cubic")

        group = QParallelAnimationGroup(self)

        def _make_style(text_color: str, bg_alpha: str, border_alpha: str, is_active: bool) -> str:
            weight = "600" if is_active else ""
            border = f"1px solid rgba(168, 85, 247, {border_alpha});" if is_active else "1px solid transparent;"
            bg = f"rgba(168, 85, 247, {bg_alpha});" if is_active else "rgba(0,0,0,0);"
            if not is_active:
                hover_bg = "rgba(255, 255, 255, 0.05);"
                return (
                    f"#NavigationItem {{ border: 1px solid transparent; "
                    f"border-radius: {radius}px; background: transparent; }} "
                    f"#NavigationItem:hover {{ background: {hover_bg}; }} "
                    f"#NavigationItemText {{ color: {c.text_secondary}; "
                    f"background: transparent; {('font-weight: ' + weight + ';') if weight else ''}}} "
                    f"#NavigationItemIcon {{ background: transparent; }}"
                )
            return (
                f"#NavigationItem {{ border: {border} "
                f"border-radius: {radius}px; background: {bg} }} "
                f"#NavigationItemText {{ color: {text_color}; "
                f"background: transparent; font-weight: {weight}; }} "
                f"#NavigationItemIcon {{ background: transparent; }}"
            )

        # New item: animate background in
        new_item = self._nav_buttons[new_index]
        new_icon = new_item.findChild(QLabel, "NavigationItemIcon")

        def _on_new_alpha(v, item=new_item, ic=new_icon, ni=new_index):
            a = max(0.0, min(1.0, float(v)))
            bg = f"{a * 0.18:.3f}"
            border = f"{a * 0.55:.3f}"
            item.setStyleSheet(_make_style(c.text_primary, bg, border, True))
            ic_color = c.text_primary if a > 0.5 else c.text_muted
            if ic is not None:
                ic.setPixmap(self.icon(_NAV_ICONS[ni], ic_color, side).pixmap(side, side))

        anim_new = QVariantAnimation(self)
        anim_new.setDuration(dur)
        anim_new.setStartValue(0.0)
        anim_new.setEndValue(1.0)
        anim_new.setEasingCurve(easing)
        anim_new.valueChanged.connect(_on_new_alpha)
        group.addAnimation(anim_new)

        # Old item: animate background out
        if 0 <= old_index < len(self._nav_buttons):
            old_item = self._nav_buttons[old_index]
            old_icon = old_item.findChild(QLabel, "NavigationItemIcon")

            def _on_old_alpha(v, item=old_item, ic=old_icon, oi=old_index):
                a = max(0.0, min(1.0, float(v)))
                item.setStyleSheet(_make_style(c.text_secondary, "0", "0", False))
                if ic is not None:
                    ic.setPixmap(self.icon(_NAV_ICONS[oi], c.text_muted, side).pixmap(side, side))

            anim_old = QVariantAnimation(self)
            anim_old.setDuration(dur)
            anim_old.setStartValue(1.0)
            anim_old.setEndValue(0.0)
            anim_old.setEasingCurve(self._theme.easing("in_cubic"))
            anim_old.valueChanged.connect(_on_old_alpha)
            group.addAnimation(anim_old)

        group.start()
        self._nav_sel_group = group

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
        radius = self.scaled(self.tokens.radius.sm)   # rounded pill corners
        side = self.scaled(16)

        for index, item in enumerate(self._nav_buttons):
            icon_label = item.findChild(QLabel, "NavigationItemIcon")
            text_label = item.findChild(QLabel, "NavigationItemText")
            active = index == self._current
            icon_color = c.text_primary if active else c.text_muted
            if icon_label is not None:
                icon_label.setPixmap(
                    self.icon(_NAV_ICONS[index], icon_color, side).pixmap(
                        side, side
                    )
                )
            if active:
                item.setStyleSheet(
                    f"#NavigationItem {{ "
                    f"border: 1px solid rgba(168, 85, 247, 0.55); "
                    f"border-radius: {radius}px; "
                    f"background: rgba(168, 85, 247, 0.18); }} "
                    f"#NavigationItemText {{ color: {c.text_primary}; "
                    f"background: transparent; font-weight: 600; }} "
                    f"#NavigationItemIcon {{ background: transparent; }}"
                )
            else:
                item.setStyleSheet(
                    f"#NavigationItem {{ "
                    f"border: 1px solid transparent; "
                    f"border-radius: {radius}px; "
                    f"background: transparent; }} "
                    f"#NavigationItem:hover {{ "
                    f"background: rgba(255, 255, 255, 0.05); }} "
                    f"#NavigationItemText {{ color: {c.text_secondary}; "
                    f"background: transparent; }} "
                    f"#NavigationItemIcon {{ background: transparent; }}"
                )
            _ = text_label

    def apply_theme(self) -> None:
        """Apply the two-column backing surfaces and refresh nav styling."""
        c = self.tokens.colors
        self.setStyleSheet(
            f"QWidget#NavigationSidebar {{ "
            f"background-color: {c.background_base}; "
            f"border: none; }} "
            f"#NavigationSidebarRail {{ "
            f"background-color: {c.background_base}; "
            f"border-right: 1px solid {c.border}; }} "
            f"#NavigationSidebarPanel {{ "
            f"background-color: {c.surface}; "
            f"border-right: 1px solid {c.border}; }} "
            f"#NavigationSidebarNav {{ background: transparent; }} "
            f"#NavigationSidebarRecent {{ background: transparent; }} "
            f"#NavigationSidebarSystem {{ background: transparent; }} "
            f"#NavigationSystemRow {{ background: transparent; }} "
            f"#NavigationSidebarAiStatus {{ background: transparent; }}"
        )
        self._update_nav_styles()
