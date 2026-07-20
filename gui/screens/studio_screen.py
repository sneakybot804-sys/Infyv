"""Full studio screen: the complete AI Gaming Video Editor workspace.

A production-style, single-screen composition that mirrors a professional
gaming video editor layout:

* a top menu bar (logo, menus, project selector, quick search),
* a toolbar strip (file actions, AI actions, aspect selector),
* a left navigation sidebar (nav items, recent projects, system overview,
  AI engine status),
* a center column with the video preview stage, transport controls and a
  multi-track timeline (video thumbnails, overlay, text chips, FX chips and
  audio waveforms with a playhead),
* a right panel (AI assistant cards, properties, export queue, background
  tasks and render progress),
* a bottom status bar.

Integration Milestone 2 (additive; visuals unchanged): the screen now embeds
the existing :class:`~gui.widgets.media_browser.MediaBrowser` and
:class:`~gui.widgets.transport_bar.TransportBar` as hidden children (the same
pattern the media workspace uses), and wires media selection to the preview
stage: selecting a browser item loads the clip's real first frame (via the
injected/lazily constructed
:class:`~gui.integration.preview_media.PreviewMediaSource`), updates the
window title and the transport timecode, and the visible transport glyphs
drive the TransportBar's frozen playback state machine. No playback logic is
duplicated; :mod:`gui_core` is never imported; backend access is indirect via
the integration layer only. When no media is selected the original static/demo
presentation renders unchanged. The only public entry point is
:func:`build_studio_screen`.
"""
from __future__ import annotations

import math
from typing import List, Optional, Sequence, Tuple

from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QColor,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from gui.theme.manager import ThemeManager
from gui.widgets.media_browser import MediaBrowser
from gui.widgets.transport_bar import TransportBar

__all__ = ["build_studio_screen"]

_SIDEBAR_WIDTH = 232
_RIGHT_PANEL_WIDTH = 356
_PLAYHEAD_FRACTION = 0.44  # illustrative playhead position across the tracks

#: Fallback media labels used to seed the hidden MediaBrowser when the
#: backend discovers no real videos (empty ``videos`` dir or no ffmpeg).
_DEMO_MEDIA: Tuple[str, ...] = (
    "clip_01.mp4",
    "clip_02.mp4",
    "highlight_reel.mp4",
)

#: The demo transport timecode shown while no media is selected.
_DEMO_TIMECODE = "00:00:42:16 / 00:02:15:08"

#: The base window title (suffixed with the selected clip's name).
_WINDOW_TITLE = "AI Gaming Video Editor"


# --------------------------------------------------------------------------- #
# Small building blocks
# --------------------------------------------------------------------------- #
def _styled(widget: QWidget) -> QWidget:
    """Enable stylesheet backgrounds on a plain QWidget/QFrame."""
    widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    return widget


def _caption(theme: ThemeManager, text: str, *, accent: bool = False) -> QLabel:
    """A small upper-case section caption label."""
    label = QLabel(text.upper())
    label.setFont(theme.font("caption"))
    color = theme.tokens.colors.accent_cyan if accent else theme.tokens.colors.text_muted
    label.setStyleSheet(f"color: {color}; background: transparent;")
    return label


def _thin_progress(theme: ThemeManager, value: int, color: str) -> QProgressBar:
    """A thin, borderless progress bar with an accent chunk."""
    tokens = theme.tokens
    bar = QProgressBar()
    bar.setRange(0, 100)
    bar.setValue(value)
    bar.setTextVisible(False)
    bar.setFixedHeight(5)
    bar.setStyleSheet(
        f"QProgressBar {{ background: {tokens.colors.surface_overlay}; "
        f"border: none; border-radius: 2px; }} "
        f"QProgressBar::chunk {{ background: {color}; border-radius: 2px; }}"
    )
    return bar


def _hslider(theme: ThemeManager, value: int, *, accent: Optional[str] = None) -> QSlider:
    """A compact horizontal slider with a themed groove and round handle."""
    colors = theme.tokens.colors
    fill = accent or colors.accent_blue
    slider = QSlider(Qt.Orientation.Horizontal)
    slider.setRange(0, 100)
    slider.setValue(value)
    slider.setFixedHeight(18)
    slider.setStyleSheet(
        f"QSlider::groove:horizontal {{ height: 4px; border-radius: 2px; "
        f"background: {colors.surface_overlay}; }} "
        f"QSlider::sub-page:horizontal {{ background: {fill}; "
        f"border-radius: 2px; }} "
        f"QSlider::handle:horizontal {{ width: 12px; height: 12px; "
        f"margin: -4px 0; border-radius: 6px; background: {colors.text_primary}; "
        f"border: 1px solid {fill}; }}"
    )
    return slider


def _toggle_pill(theme: ThemeManager, *, checked: bool = True) -> QWidget:
    """A decorative on/off pill (static; the studio screen wires no logic)."""
    colors = theme.tokens.colors
    pill = _styled(QFrame())
    pill.setFixedSize(38, 18)
    knob_color = colors.text_primary
    if checked:
        pill.setStyleSheet(
            f"background: {colors.accent_blue}; border-radius: 9px;"
        )
        knob_x = 22
    else:
        pill.setStyleSheet(
            f"background: {colors.surface_overlay}; border-radius: 9px;"
        )
        knob_x = 2
    knob = _styled(QFrame(pill))
    knob.setGeometry(knob_x, 2, 14, 14)
    knob.setStyleSheet(f"background: {knob_color}; border-radius: 7px;")
    return pill


def _dot(theme: ThemeManager, color: str, size: int = 8) -> QWidget:
    """A small round status dot."""
    dot = _styled(QFrame())
    dot.setFixedSize(size, size)
    dot.setStyleSheet(f"background: {color}; border-radius: {size // 2}px;")
    return dot


class _Waveform(QWidget):
    """A deterministic decorative audio waveform (no real audio data)."""

    def __init__(
        self,
        theme: ThemeManager,
        *,
        color: str,
        seed: int = 0,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._color = QColor(theme.color(color))
        self._seed = seed
        self.setMinimumHeight(30)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

    @staticmethod
    def _noise(i: int, seed: int) -> float:
        """Deterministic pseudo-random amplitude in 0..1."""
        value = math.sin(i * 12.9898 + seed * 78.233) * 43758.5453
        return value - math.floor(value)

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt override)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        width = self.width()
        height = self.height()
        mid = height / 2.0
        bar_w = 2
        gap = 1
        pen = QPen(self._color)
        pen.setWidth(bar_w)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        x = 2
        i = 0
        while x < width - 2:
            noise = self._noise(i, self._seed)
            wave = 0.35 + 0.65 * abs(math.sin(i * 0.35 + self._seed))
            amp = max(1.5, (mid - 3) * noise * wave)
            painter.drawLine(int(x), int(mid - amp), int(x), int(mid + amp))
            x += bar_w + gap
            i += 1
        painter.end()


class _VideoThumb(QWidget):
    """A decorative gradient 'video thumbnail' block for timeline clips."""

    def __init__(
        self,
        theme: ThemeManager,
        *,
        seed: int = 0,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        colors = theme.tokens.colors
        self._top = QColor(theme.color(colors.accent_purple)).darker(160)
        self._bottom = QColor(theme.color(colors.accent_blue)).darker(220)
        self._seed = seed
        self.setMinimumSize(36, 30)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt override)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0.0, self._top)
        gradient.setColorAt(1.0, self._bottom)
        painter.fillRect(self.rect(), gradient)
        # Faint vertical frame separators so the block reads as film frames.
        pen = QPen(QColor(0, 0, 0, 90))
        pen.setWidth(1)
        painter.setPen(pen)
        step = 34
        x = step + (self._seed * 7) % step
        while x < self.width():
            painter.drawLine(x, 0, x, self.height())
            x += step
        painter.end()


# --------------------------------------------------------------------------- #
# Top menu bar
# --------------------------------------------------------------------------- #
def _build_menu_bar(theme: ThemeManager) -> QWidget:
    tokens = theme.tokens
    colors = tokens.colors

    bar = _styled(QFrame())
    bar.setObjectName("StudioMenuBar")
    bar.setFixedHeight(44)
    bar.setStyleSheet(
        f"#StudioMenuBar {{ background: {colors.background_deep}; "
        f"border-bottom: 1px solid {colors.border}; }}"
    )
    row = QHBoxLayout(bar)
    row.setContentsMargins(tokens.spacing.md, 0, tokens.spacing.md, 0)
    row.setSpacing(tokens.spacing.md)

    logo = QLabel("▲")
    logo.setFont(theme.font("h3"))
    logo.setStyleSheet(f"color: {colors.accent_cyan}; background: transparent;")
    row.addWidget(logo)

    title = QLabel("AI Gaming Video Editor")
    title.setFont(theme.font("h3"))
    title.setStyleSheet(f"color: {colors.text_primary}; background: transparent;")
    row.addWidget(title)

    row.addSpacing(tokens.spacing.md)
    for menu in ("File", "Edit", "View", "Timeline", "Tools", "AI", "Help"):
        item = QLabel(menu)
        item.setFont(theme.font("body_small"))
        item.setStyleSheet(
            f"QLabel {{ color: {colors.text_secondary}; background: transparent; "
            f"padding: 4px 6px; }} QLabel:hover {{ color: {colors.text_primary}; }}"
        )
        row.addWidget(item)

    row.addStretch(1)

    project = _styled(QFrame())
    project.setObjectName("StudioProjectChip")
    project.setStyleSheet(
        f"#StudioProjectChip {{ background: {colors.surface}; "
        f"border: 1px solid {colors.border}; border-radius: {tokens.radius.sm}px; }}"
    )
    chip_row = QHBoxLayout(project)
    chip_row.setContentsMargins(tokens.spacing.md, 4, tokens.spacing.md, 4)
    chip_row.setSpacing(tokens.spacing.sm)
    chip_col = QVBoxLayout()
    chip_col.setContentsMargins(0, 0, 0, 0)
    chip_col.setSpacing(0)
    chip_col.addWidget(_caption(theme, "Project"))
    name = QLabel("Valorant Montage 2026")
    name.setFont(theme.font("body_small"))
    name.setStyleSheet(f"color: {colors.text_primary}; background: transparent;")
    chip_col.addWidget(name)
    chip_row.addLayout(chip_col)
    arrow = QLabel("▾")
    arrow.setStyleSheet(f"color: {colors.text_muted}; background: transparent;")
    chip_row.addWidget(arrow)
    row.addWidget(project)

    search = _styled(QFrame())
    search.setObjectName("StudioSearch")
    search.setStyleSheet(
        f"#StudioSearch {{ background: {colors.surface}; "
        f"border: 1px solid {colors.border}; border-radius: {tokens.radius.sm}px; }}"
    )
    search_row = QHBoxLayout(search)
    search_row.setContentsMargins(tokens.spacing.md, 6, tokens.spacing.md, 6)
    search_row.setSpacing(tokens.spacing.sm)
    hint = QLabel("\U0001f50d  Quick Search")
    hint.setFont(theme.font("body_small"))
    hint.setStyleSheet(f"color: {colors.text_muted}; background: transparent;")
    search_row.addWidget(hint)
    search_row.addSpacing(tokens.spacing.xl)
    shortcut = QLabel("Ctrl + K")
    shortcut.setFont(theme.font("caption"))
    shortcut.setStyleSheet(
        f"color: {colors.text_muted}; background: {colors.surface_overlay}; "
        f"border-radius: 4px; padding: 1px 6px;"
    )
    search_row.addWidget(shortcut)
    row.addWidget(search)

    row.addStretch(1)
    for glyph in ("\U0001f514", "❓"):
        icon = QLabel(glyph)
        icon.setFont(theme.font("body_small"))
        icon.setStyleSheet(f"color: {colors.text_muted}; background: transparent;")
        row.addWidget(icon)
    return bar


# --------------------------------------------------------------------------- #
# Toolbar strip
# --------------------------------------------------------------------------- #
def _tool_button(
    theme: ThemeManager, glyph: str, label: str, *, active: bool = False
) -> QWidget:
    colors = theme.tokens.colors
    button = _styled(QFrame())
    button.setObjectName("StudioToolButton")
    if active:
        button.setStyleSheet(
            f"#StudioToolButton {{ background: {colors.surface_elevated}; "
            f"border: 1px solid {colors.accent_cyan}; border-radius: 8px; }}"
        )
    else:
        button.setStyleSheet(
            "#StudioToolButton { background: transparent; border: none; "
            "border-radius: 8px; } "
            f"#StudioToolButton:hover {{ background: {colors.surface}; }}"
        )
    col = QVBoxLayout(button)
    col.setContentsMargins(10, 4, 10, 4)
    col.setSpacing(1)
    icon = QLabel(glyph)
    icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
    icon.setFont(theme.font("body"))
    icon.setStyleSheet(
        f"color: {colors.accent_cyan if active else colors.text_secondary}; "
        f"background: transparent;"
    )
    col.addWidget(icon)
    text = QLabel(label)
    text.setAlignment(Qt.AlignmentFlag.AlignCenter)
    text.setFont(theme.font("caption"))
    text.setStyleSheet(
        f"color: {colors.accent_cyan if active else colors.text_muted}; "
        f"background: transparent;"
    )
    col.addWidget(text)
    return button


def _tool_separator(theme: ThemeManager) -> QFrame:
    sep = QFrame()
    sep.setFrameShape(QFrame.Shape.VLine)
    sep.setStyleSheet(
        f"color: {theme.tokens.colors.divider}; "
        f"background: {theme.tokens.colors.divider}; max-width: 1px;"
    )
    return sep


def _build_toolbar(theme: ThemeManager) -> QWidget:
    tokens = theme.tokens
    colors = tokens.colors

    bar = _styled(QFrame())
    bar.setObjectName("StudioToolbar")
    bar.setFixedHeight(58)
    bar.setStyleSheet(
        f"#StudioToolbar {{ background: {colors.background_base}; "
        f"border-bottom: 1px solid {colors.border}; }}"
    )
    row = QHBoxLayout(bar)
    row.setContentsMargins(tokens.spacing.md, 4, tokens.spacing.md, 4)
    row.setSpacing(tokens.spacing.sm)

    groups: Sequence[Sequence[Tuple[str, str, bool]]] = (
        (("\U0001f4c4", "New", False), ("\U0001f4c2", "Open", False),
         ("\U0001f4be", "Save", False)),
        (("⬇", "Import", False), ("⏺", "Record", False)),
        (("\U0001f9e0", "AI Analyze", True), ("✂", "Auto Cut", False),
         ("\U0001f39a", "Beat Sync", False), ("⚡", "AI Render", False)),
    )
    for gi, group in enumerate(groups):
        for glyph, label, active in group:
            row.addWidget(_tool_button(theme, glyph, label, active=active))
        if gi < len(groups) - 1:
            row.addWidget(_tool_separator(theme))

    row.addStretch(1)

    aspect = _styled(QFrame())
    aspect.setObjectName("StudioAspectChip")
    aspect.setStyleSheet(
        f"#StudioAspectChip {{ background: {colors.surface}; "
        f"border: 1px solid {colors.border}; border-radius: {tokens.radius.sm}px; }}"
    )
    aspect_row = QHBoxLayout(aspect)
    aspect_row.setContentsMargins(tokens.spacing.md, 6, tokens.spacing.md, 6)
    aspect_row.setSpacing(tokens.spacing.sm)
    ratio = QLabel("16:9")
    ratio.setFont(theme.font("body_small"))
    ratio.setStyleSheet(f"color: {colors.text_primary}; background: transparent;")
    aspect_row.addWidget(ratio)
    arrow = QLabel("▾")
    arrow.setStyleSheet(f"color: {colors.text_muted}; background: transparent;")
    aspect_row.addWidget(arrow)
    row.addWidget(aspect)

    for glyph in ("\U0001f4f7", "➕", "▦", "⛶"):
        icon = QLabel(glyph)
        icon.setFont(theme.font("body_small"))
        icon.setStyleSheet(
            f"QLabel {{ color: {colors.text_muted}; background: transparent; "
            f"padding: 4px; }} QLabel:hover {{ color: {colors.text_primary}; }}"
        )
        row.addWidget(icon)
    return bar


# --------------------------------------------------------------------------- #
# Left sidebar
# --------------------------------------------------------------------------- #
def _build_sidebar(theme: ThemeManager) -> QWidget:
    tokens = theme.tokens
    colors = tokens.colors

    panel = _styled(QFrame())
    panel.setObjectName("StudioSidebar")
    panel.setFixedWidth(_SIDEBAR_WIDTH)
    panel.setStyleSheet(
        f"#StudioSidebar {{ background: {colors.background_deep}; "
        f"border-right: 1px solid {colors.border}; }}"
    )
    outer = QVBoxLayout(panel)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(0)

    scroll = QScrollArea(panel)
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setStyleSheet("QScrollArea { background: transparent; }")

    body = _styled(QWidget())
    body.setStyleSheet("background: transparent;")
    col = QVBoxLayout(body)
    col.setContentsMargins(tokens.spacing.md, tokens.spacing.md,
                           tokens.spacing.md, tokens.spacing.md)
    col.setSpacing(tokens.spacing.md)

    # --- Navigation items ---
    nav = QVBoxLayout()
    nav.setSpacing(2)
    items = (
        ("\U0001f3e0", "Dashboard", True),
        ("\U0001f4c1", "Projects", False),
        ("\U0001f39e", "Media", False),
        ("\U0001f9e9", "Assets", False),
        ("\U0001f916", "AI Tools", False),
        ("\U0001f4d0", "Templates", False),
        ("✨", "Effects", False),
        ("\U0001f3b5", "Audio", False),
        ("⬆", "Export", False),
        ("⚙", "Settings", False),
    )
    for glyph, label, active in items:
        item = _styled(QFrame())
        item.setObjectName("StudioNavItem")
        if active:
            item.setStyleSheet(
                f"#StudioNavItem {{ background: {colors.surface_elevated}; "
                f"border-left: 2px solid {colors.accent_cyan}; "
                f"border-radius: {tokens.radius.sm}px; }}"
            )
        else:
            item.setStyleSheet(
                f"#StudioNavItem {{ background: transparent; border: none; "
                f"border-radius: {tokens.radius.sm}px; }} "
                f"#StudioNavItem:hover {{ background: {colors.surface}; }}"
            )
        item_row = QHBoxLayout(item)
        item_row.setContentsMargins(tokens.spacing.md, 7, tokens.spacing.md, 7)
        item_row.setSpacing(tokens.spacing.md)
        icon = QLabel(glyph)
        icon.setFont(theme.font("body_small"))
        icon.setStyleSheet(
            f"color: {colors.accent_cyan if active else colors.text_muted}; "
            f"background: transparent;"
        )
        item_row.addWidget(icon)
        text = QLabel(label)
        text.setFont(theme.font("body_small"))
        text.setStyleSheet(
            f"color: {colors.text_primary if active else colors.text_secondary}; "
            f"background: transparent;"
        )
        item_row.addWidget(text, 1)
        nav.addWidget(item)
    col.addLayout(nav)

    # --- Recent projects ---
    recent_card = _sidebar_card(theme)
    recent_col = recent_card.layout()
    recent_col.addWidget(_caption(theme, "Recent Projects"))
    for name, age in (
        ("Valorant Montage 2026", "Just now"),
        ("Funny Moments #47", "2 hours ago"),
        ("Warzone Highlights", "Yesterday"),
        ("Apex Legends Edit", "2 days ago"),
        ("CS2 Fragmovie", "3 days ago"),
    ):
        entry = QHBoxLayout()
        entry.setSpacing(tokens.spacing.sm)
        thumb = _styled(QFrame())
        thumb.setFixedSize(26, 20)
        thumb.setStyleSheet(
            f"background: qlineargradient(x1:0, y1:0, x2:1, y2:1, "
            f"stop:0 {colors.accent_purple}, stop:1 {colors.accent_blue}); "
            f"border-radius: 4px;"
        )
        entry.addWidget(thumb)
        text_col = QVBoxLayout()
        text_col.setSpacing(0)
        title = QLabel(name)
        title.setFont(theme.font("caption"))
        title.setStyleSheet(
            f"color: {colors.text_secondary}; background: transparent;"
        )
        text_col.addWidget(title)
        when = QLabel(age)
        when.setFont(theme.font("caption"))
        when.setStyleSheet(f"color: {colors.text_muted}; background: transparent;")
        text_col.addWidget(when)
        entry.addLayout(text_col, 1)
        recent_col.addLayout(entry)
    more = QLabel("Show More")
    more.setAlignment(Qt.AlignmentFlag.AlignCenter)
    more.setFont(theme.font("caption"))
    more.setStyleSheet(
        f"color: {colors.text_secondary}; background: {colors.surface_overlay}; "
        f"border-radius: {tokens.radius.sm}px; padding: 5px;"
    )
    recent_col.addWidget(more)
    col.addWidget(recent_card)

    # --- System overview ---
    system_card = _sidebar_card(theme)
    system_col = system_card.layout()
    system_col.addWidget(_caption(theme, "System Overview"))
    for label, value, detail, color in (
        ("GPU Usage", 68, "NVIDIA RTX 4070 Ti", colors.accent_cyan),
        ("RAM Usage", 54, "17.2 / 32 GB", colors.accent_purple),
        ("CPU Usage", 32, "12-Core | 4.2 GHz", colors.accent_blue),
    ):
        head = QHBoxLayout()
        name = QLabel(label)
        name.setFont(theme.font("body_small"))
        name.setStyleSheet(
            f"color: {colors.text_secondary}; background: transparent;"
        )
        head.addWidget(name, 1)
        pct = QLabel(f"{value}%")
        pct.setFont(theme.font("body_small"))
        pct.setStyleSheet(f"color: {colors.text_primary}; background: transparent;")
        head.addWidget(pct)
        system_col.addLayout(head)
        system_col.addWidget(_thin_progress(theme, value, color))
        sub = QLabel(detail)
        sub.setFont(theme.font("caption"))
        sub.setStyleSheet(f"color: {colors.text_muted}; background: transparent;")
        system_col.addWidget(sub)
    col.addWidget(system_card)

    # --- AI engine status ---
    engine_card = _sidebar_card(theme)
    engine_col = engine_card.layout()
    engine_col.addWidget(_caption(theme, "AI Engine Status"))
    for label, value, value_color in (
        ("Model", "Neural Vision v3.2", colors.text_primary),
        ("Status", "Active", colors.success),
    ):
        line = QHBoxLayout()
        key = QLabel(label)
        key.setFont(theme.font("body_small"))
        key.setStyleSheet(
            f"color: {colors.text_secondary}; background: transparent;"
        )
        line.addWidget(key, 1)
        val = QLabel(value)
        val.setFont(theme.font("body_small"))
        val.setStyleSheet(f"color: {value_color}; background: transparent;")
        line.addWidget(val)
        engine_col.addLayout(line)
    col.addWidget(engine_card)

    col.addStretch(1)
    scroll.setWidget(body)
    outer.addWidget(scroll)
    return panel


def _sidebar_card(theme: ThemeManager) -> QFrame:
    """A rounded sidebar card with a prepared vertical layout."""
    tokens = theme.tokens
    card = _styled(QFrame())
    card.setObjectName("StudioSidebarCard")
    card.setStyleSheet(
        f"#StudioSidebarCard {{ background: {tokens.colors.surface}; "
        f"border: 1px solid {tokens.colors.border}; "
        f"border-radius: {tokens.radius.md}px; }}"
    )
    col = QVBoxLayout(card)
    col.setContentsMargins(tokens.spacing.md, tokens.spacing.md,
                           tokens.spacing.md, tokens.spacing.md)
    col.setSpacing(tokens.spacing.sm)
    return card


# --------------------------------------------------------------------------- #
# Center: preview stage + transport
# --------------------------------------------------------------------------- #
class _PreviewStage(QFrame):
    """The preview stage frame: demo HUD art, or a real decoded frame.

    Visuals are unchanged from the static milestone: the gradient backdrop,
    scoreboard chip, ACE callout and HUD strip render exactly as before while
    no media is selected. :meth:`set_frame` switches the stage to display a
    real first frame (aspect-fit, painted under the rounded border); passing
    ``None`` restores the demo art. Object name and stylesheet are owned by
    :func:`_build_preview` exactly as before.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._frame: Optional[QImage] = None
        self._overlay_widgets: List[QWidget] = []

    def set_frame(self, image: Optional[QImage]) -> None:
        """Display ``image`` (aspect-fit), or restore the demo art on None."""
        self._frame = image
        # The demo HUD labels only make sense over the demo art; hide them
        # while a real frame is displayed.
        for widget in self._overlay_widgets:
            widget.setVisible(image is None)
        self.update()

    def has_frame(self) -> bool:
        """Return whether a real decoded frame is currently displayed."""
        return self._frame is not None

    def register_overlay(self, widget: QWidget) -> None:
        """Track a demo-HUD child to hide while a real frame is shown."""
        self._overlay_widgets.append(widget)

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt override)
        # The stylesheet paints the gradient/border; a decoded frame is
        # painted on top (inside the rounded rect), letterboxed to fit.
        super().paintEvent(event)
        if self._frame is None or self._frame.isNull():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        scaled = self._frame.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = (self.width() - scaled.width()) // 2
        y = (self.height() - scaled.height()) // 2
        path = QPainterPath()
        path.addRoundedRect(self.rect().adjusted(1, 1, -1, -1), 12, 12)
        painter.setClipPath(path)
        painter.drawImage(x, y, scaled)
        painter.end()


def _build_preview(theme: ThemeManager) -> QWidget:
    tokens = theme.tokens
    colors = tokens.colors

    stage = _styled(_PreviewStage())
    stage.setObjectName("StudioPreviewStage")
    stage.setMinimumHeight(300)
    stage.setSizePolicy(
        QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
    )
    stage.setStyleSheet(
        f"#StudioPreviewStage {{ background: qlineargradient("
        f"x1:0, y1:0, x2:0, y2:1, "
        f"stop:0 #10142a, stop:0.55 #1a1038, stop:1 #05070f); "
        f"border: 1px solid {colors.border}; "
        f"border-radius: {tokens.radius.md}px; }}"
    )
    col = QVBoxLayout(stage)
    col.setContentsMargins(tokens.spacing.lg, tokens.spacing.md,
                           tokens.spacing.lg, tokens.spacing.md)
    col.setSpacing(tokens.spacing.sm)

    # Top scoreboard strip.
    score_row = QHBoxLayout()
    score_row.addStretch(1)
    score = _styled(QFrame())
    score.setObjectName("StudioScoreChip")
    score.setStyleSheet(
        f"#StudioScoreChip {{ background: rgba(0, 0, 0, 0.45); "
        f"border: 1px solid {colors.glass_border}; border-radius: 14px; }}"
    )
    score_line = QHBoxLayout(score)
    score_line.setContentsMargins(tokens.spacing.lg, 4, tokens.spacing.lg, 4)
    score_line.setSpacing(tokens.spacing.lg)
    left_score = QLabel("13")
    left_score.setFont(theme.font("h3"))
    left_score.setStyleSheet(
        f"color: {colors.accent_cyan}; background: transparent;"
    )
    score_line.addWidget(left_score)
    clock = QLabel("0:06")
    clock.setFont(theme.font("h3"))
    clock.setStyleSheet(f"color: {colors.text_primary}; background: transparent;")
    score_line.addWidget(clock)
    right_score = QLabel("9")
    right_score.setFont(theme.font("h3"))
    right_score.setStyleSheet(f"color: {colors.error}; background: transparent;")
    score_line.addWidget(right_score)
    score_row.addWidget(score)
    score_row.addStretch(1)
    col.addLayout(score_row)
    stage.register_overlay(score)

    col.addStretch(1)

    # Center callout.
    ace = QLabel("ACE")
    ace.setAlignment(Qt.AlignmentFlag.AlignCenter)
    ace.setFont(theme.font("display"))
    ace.setStyleSheet(
        f"color: {colors.text_primary}; background: transparent; "
        f"letter-spacing: 10px;"
    )
    col.addWidget(ace)
    stage.register_overlay(ace)
    headshot = QLabel("◈  HEADSHOT")
    headshot.setAlignment(Qt.AlignmentFlag.AlignCenter)
    headshot.setFont(theme.font("caption"))
    headshot.setStyleSheet(
        f"color: {colors.accent_purple}; background: transparent;"
    )
    col.addWidget(headshot)
    stage.register_overlay(headshot)

    col.addStretch(1)

    # Bottom HUD strip.
    hud_row = QHBoxLayout()
    hp = QLabel("❤ 87")
    hp.setFont(theme.font("body_small"))
    hp.setStyleSheet(f"color: {colors.success}; background: transparent;")
    hud_row.addWidget(hp)
    hud_row.addStretch(1)
    ammo = QLabel("16 | 50")
    ammo.setFont(theme.font("body_small"))
    ammo.setStyleSheet(f"color: {colors.text_secondary}; background: transparent;")
    hud_row.addWidget(ammo)
    col.addLayout(hud_row)
    stage.register_overlay(hp)
    stage.register_overlay(ammo)
    return stage


def _build_transport(theme: ThemeManager) -> QWidget:
    tokens = theme.tokens
    colors = tokens.colors

    bar = _styled(QFrame())
    bar.setObjectName("StudioTransport")
    bar.setFixedHeight(40)
    bar.setStyleSheet(
        f"#StudioTransport {{ background: {colors.surface}; "
        f"border: 1px solid {colors.border}; "
        f"border-radius: {tokens.radius.sm}px; }}"
    )
    row = QHBoxLayout(bar)
    row.setContentsMargins(tokens.spacing.md, 0, tokens.spacing.md, 0)
    row.setSpacing(tokens.spacing.md)

    timecode = QLabel(_DEMO_TIMECODE)
    timecode.setObjectName("StudioTimecode")
    timecode.setFont(theme.font("mono"))
    timecode.setStyleSheet(f"color: {colors.text_secondary}; background: transparent;")
    row.addWidget(timecode)

    row.addStretch(1)
    # The three real playback glyphs are named and clickable (wired to the
    # hidden TransportBar's frozen state machine during screen assembly);
    # the rest remain decorative. Visuals are unchanged.
    for glyph, accent, name in (
        ("⏮", False, None), ("⏪", False, None), ("▶", False, "play"),
        ("⏹", False, "stop"), ("⏸", True, "pause"), ("⏩", False, None),
        ("⏭", False, None), ("\U0001f501", False, None),
    ):
        button = QLabel(glyph)
        button.setFont(theme.font("body"))
        button.setStyleSheet(
            f"QLabel {{ color: "
            f"{colors.accent_cyan if accent else colors.text_secondary}; "
            f"background: transparent; padding: 2px 6px; }} "
            f"QLabel:hover {{ color: {colors.text_primary}; }}"
        )
        if name is not None:
            button.setObjectName(f"StudioTransport{name.capitalize()}")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
        row.addWidget(button)
    row.addStretch(1)

    for glyph in ("\U0001f4f7", "\U0001f3a4", "\U0001f4f9"):
        icon = QLabel(glyph)
        icon.setFont(theme.font("body_small"))
        icon.setStyleSheet(f"color: {colors.text_muted}; background: transparent;")
        row.addWidget(icon)
    volume_icon = QLabel("\U0001f50a")
    volume_icon.setFont(theme.font("body_small"))
    volume_icon.setStyleSheet(f"color: {colors.text_muted}; background: transparent;")
    row.addWidget(volume_icon)
    volume = _hslider(theme, 80, accent=colors.accent_cyan)
    volume.setFixedWidth(90)
    row.addWidget(volume)
    return bar


# --------------------------------------------------------------------------- #
# Center: timeline
# --------------------------------------------------------------------------- #
class _TracksArea(QWidget):
    """Hosts the track lanes and overlays a vertical playhead line."""

    def __init__(self, theme: ThemeManager, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._playhead = _styled(QFrame(self))
        self._playhead.setObjectName("StudioPlayhead")
        self._playhead.setStyleSheet(
            f"background: {theme.tokens.colors.accent_cyan};"
        )
        self._playhead.setFixedWidth(2)

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        super().resizeEvent(event)
        x = int(self.width() * _PLAYHEAD_FRACTION)
        self._playhead.setGeometry(x, 0, 2, self.height())
        self._playhead.raise_()


def _timeline_chip(theme: ThemeManager, text: str, *, kind: str) -> QWidget:
    """A small rounded chip used on the Text and FX tracks."""
    tokens = theme.tokens
    colors = tokens.colors
    if kind == "text":
        bg = "rgba(251, 191, 36, 0.16)"
        border = colors.warning
        fg = colors.warning
    else:  # fx
        bg = "rgba(181, 105, 255, 0.16)"
        border = colors.accent_purple
        fg = colors.text_secondary
    chip = _styled(QFrame())
    chip.setObjectName("StudioTimelineChip")
    chip.setStyleSheet(
        f"#StudioTimelineChip {{ background: {bg}; "
        f"border: 1px solid {border}; border-radius: {tokens.radius.sm}px; }}"
    )
    row = QHBoxLayout(chip)
    row.setContentsMargins(tokens.spacing.sm, 2, tokens.spacing.sm, 2)
    row.setSpacing(tokens.spacing.xs)
    label = QLabel(text)
    label.setFont(theme.font("caption"))
    label.setStyleSheet(f"color: {fg}; background: transparent;")
    row.addWidget(label)
    close = QLabel("×")
    close.setFont(theme.font("caption"))
    close.setStyleSheet(f"color: {colors.text_muted}; background: transparent;")
    row.addWidget(close)
    return chip


def _track_header(theme: ThemeManager, badge: str, name: str) -> QWidget:
    tokens = theme.tokens
    colors = tokens.colors
    header = _styled(QFrame())
    header.setObjectName("StudioTrackHeader")
    header.setFixedWidth(120)
    header.setStyleSheet(
        f"#StudioTrackHeader {{ background: {colors.surface}; "
        f"border: 1px solid {colors.border}; "
        f"border-radius: {tokens.radius.sm}px; }}"
    )
    row = QHBoxLayout(header)
    row.setContentsMargins(tokens.spacing.sm, 2, tokens.spacing.sm, 2)
    row.setSpacing(tokens.spacing.sm)
    tag = QLabel(badge)
    tag.setFont(theme.font("caption"))
    tag.setAlignment(Qt.AlignmentFlag.AlignCenter)
    tag.setFixedSize(24, 16)
    tag.setStyleSheet(
        f"color: {colors.text_primary}; background: {colors.surface_overlay}; "
        f"border-radius: 4px;"
    )
    row.addWidget(tag)
    label = QLabel(name)
    label.setFont(theme.font("caption"))
    label.setStyleSheet(f"color: {colors.text_secondary}; background: transparent;")
    row.addWidget(label, 1)
    lock = QLabel("\U0001f512")
    lock.setFont(theme.font("caption"))
    lock.setStyleSheet(f"color: {colors.text_disabled}; background: transparent;")
    row.addWidget(lock)
    return header


def _clip_block(
    theme: ThemeManager, label: str, *, stretch_body: QWidget, height: int
) -> QWidget:
    """A labelled clip container hosting a decorative body widget."""
    tokens = theme.tokens
    colors = tokens.colors
    block = _styled(QFrame())
    block.setObjectName("StudioClip")
    block.setFixedHeight(height)
    block.setStyleSheet(
        f"#StudioClip {{ background: {colors.surface_elevated}; "
        f"border: 1px solid {colors.glass_border}; "
        f"border-radius: {tokens.radius.sm}px; }}"
    )
    col = QVBoxLayout(block)
    col.setContentsMargins(2, 2, 2, 2)
    col.setSpacing(0)
    if label:
        caption = QLabel(label)
        caption.setFont(theme.font("caption"))
        caption.setStyleSheet(
            f"color: {colors.text_secondary}; background: rgba(0, 0, 0, 0.35); "
            f"border-radius: 3px; padding: 0px 4px;"
        )
        col.addWidget(caption, 0, Qt.AlignmentFlag.AlignLeft)
    col.addWidget(stretch_body, 1)
    return block


def _build_timeline(theme: ThemeManager) -> QWidget:
    tokens = theme.tokens
    colors = tokens.colors

    panel = _styled(QFrame())
    panel.setObjectName("StudioTimeline")
    panel.setStyleSheet(
        f"#StudioTimeline {{ background: {colors.background_deep}; "
        f"border: 1px solid {colors.border}; "
        f"border-radius: {tokens.radius.md}px; }}"
    )
    col = QVBoxLayout(panel)
    col.setContentsMargins(tokens.spacing.sm, tokens.spacing.sm,
                           tokens.spacing.sm, tokens.spacing.sm)
    col.setSpacing(tokens.spacing.xs)

    # Timeline toolbar.
    tool_row = QHBoxLayout()
    tool_row.setSpacing(tokens.spacing.sm)
    for glyph in ("↶", "↷", "✂", "\U0001f5d1", "▤",
                  "▶", "⬌", "T", "⚡", "\U0001f9f2", "⤡"):
        tool = QLabel(glyph)
        tool.setFont(theme.font("caption"))
        tool.setStyleSheet(
            f"QLabel {{ color: {colors.text_muted}; background: transparent; "
            f"padding: 2px 5px; }} QLabel:hover {{ color: {colors.accent_cyan}; }}"
        )
        tool_row.addWidget(tool)
    tool_row.addStretch(1)
    zoom = _hslider(theme, 55, accent=colors.accent_cyan)
    zoom.setFixedWidth(110)
    tool_row.addWidget(zoom)
    col.addLayout(tool_row)

    # Ruler.
    ruler = _styled(QFrame())
    ruler.setObjectName("StudioRuler")
    ruler.setFixedHeight(20)
    ruler.setStyleSheet(
        f"#StudioRuler {{ background: {colors.surface}; "
        f"border-radius: 4px; }}"
    )
    ruler_row = QHBoxLayout(ruler)
    ruler_row.setContentsMargins(126, 0, tokens.spacing.sm, 0)
    ruler_row.setSpacing(0)
    ticks = ("00:00:00", "00:00:15", "00:00:30", "00:00:45", "00:01:00",
             "00:01:15", "00:01:30", "00:01:45", "00:02:00", "00:02:15")
    for i, tick in enumerate(ticks):
        label = QLabel(tick)
        label.setFont(theme.font("caption"))
        label.setStyleSheet(f"color: {colors.text_muted}; background: transparent;")
        ruler_row.addWidget(label)
        if i < len(ticks) - 1:
            ruler_row.addStretch(1)
    col.addWidget(ruler)

    # Track lanes inside the playhead overlay area.
    tracks = _TracksArea(theme)
    tracks.setObjectName("StudioTracks")
    lanes = QVBoxLayout(tracks)
    lanes.setContentsMargins(0, 0, 0, 0)
    lanes.setSpacing(tokens.spacing.xs)

    lanes.addLayout(_video_lane(theme))
    lanes.addLayout(_overlay_lane(theme))
    lanes.addLayout(_chip_lane(
        theme, "T", "Text Track", kind="text",
        chips=("ACE!", "WHAT A PLAY!", "UNSTOPPABLE", "GG WP!", "NICE SHOT!"),
    ))
    lanes.addLayout(_chip_lane(
        theme, "FX", "Effects Track", kind="fx",
        chips=("Glow", "Shake", "Zoom Blur", "Flash", "Neon", "Color Grade"),
    ))
    lanes.addLayout(_audio_lane(
        theme, "A1", "Audio Track 1", label="Music Track.mp3",
        color=theme.tokens.colors.accent_blue, seed=3,
    ))
    lanes.addLayout(_audio_lane(
        theme, "A2", "Audio Track 2", label="Voice Commentary.wav",
        color=theme.tokens.colors.success, seed=8,
    ))
    col.addWidget(tracks, 1)
    return panel


def _lane_row(theme: ThemeManager, badge: str, name: str) -> Tuple[QHBoxLayout, QHBoxLayout]:
    """A lane layout: header + a content strip; returns (row, content)."""
    tokens = theme.tokens
    colors = tokens.colors
    row = QHBoxLayout()
    row.setSpacing(tokens.spacing.xs)
    row.addWidget(_track_header(theme, badge, name))
    strip = _styled(QFrame())
    strip.setObjectName("StudioLane")
    strip.setStyleSheet(
        f"#StudioLane {{ background: {colors.surface}; "
        f"border-radius: {tokens.radius.sm}px; }}"
    )
    content = QHBoxLayout(strip)
    content.setContentsMargins(tokens.spacing.xs, tokens.spacing.xs,
                               tokens.spacing.xs, tokens.spacing.xs)
    content.setSpacing(tokens.spacing.xs)
    row.addWidget(strip, 1)
    return row, content


def _video_lane(theme: ThemeManager) -> QHBoxLayout:
    row, content = _lane_row(theme, "V1", "Video Track 1")
    clips = (
        ("Valorant 2026-05-08 14-35-23.mp4", 5, 0),
        ("", 4, 1),
        ("Valorant 2026-05-08 14-35-45.mp4", 6, 2),
        ("", 3, 3),
    )
    for label, weight, seed in clips:
        block = _clip_block(
            theme, label,
            stretch_body=_VideoThumb(theme, seed=seed), height=44,
        )
        content.addWidget(block, weight)
    return row


def _overlay_lane(theme: ThemeManager) -> QHBoxLayout:
    tokens = theme.tokens
    colors = tokens.colors
    row, content = _lane_row(theme, "OV", "Overlay Track")
    for label, weight in (("Facecam_01.mp4", 4), ("Facecam_01.mp4", 5),
                          ("Facecam_01.mp4", 3)):
        block = _styled(QFrame())
        block.setObjectName("StudioOverlayClip")
        block.setFixedHeight(30)
        block.setStyleSheet(
            f"#StudioOverlayClip {{ background: rgba(79, 141, 255, 0.18); "
            f"border: 1px solid {colors.accent_blue}; "
            f"border-radius: {tokens.radius.sm}px; }}"
        )
        line = QHBoxLayout(block)
        line.setContentsMargins(tokens.spacing.sm, 0, tokens.spacing.sm, 0)
        label_widget = QLabel(label)
        label_widget.setFont(theme.font("caption"))
        label_widget.setStyleSheet(
            f"color: {colors.text_secondary}; background: transparent;"
        )
        line.addWidget(label_widget)
        line.addStretch(1)
        content.addWidget(block, weight)
        content.addSpacing(tokens.spacing.md)
    content.addStretch(1)
    return row


def _chip_lane(
    theme: ThemeManager,
    badge: str,
    name: str,
    *,
    kind: str,
    chips: Sequence[str],
) -> QHBoxLayout:
    row, content = _lane_row(theme, badge, name)
    for chip in chips:
        content.addWidget(_timeline_chip(theme, chip, kind=kind))
        content.addStretch(1)
    return row


def _audio_lane(
    theme: ThemeManager,
    badge: str,
    name: str,
    *,
    label: str,
    color: str,
    seed: int,
) -> QHBoxLayout:
    tokens = theme.tokens
    colors = tokens.colors
    row, content = _lane_row(theme, badge, name)
    block = _styled(QFrame())
    block.setObjectName("StudioAudioClip")
    block.setFixedHeight(38)
    block.setStyleSheet(
        f"#StudioAudioClip {{ background: rgba(0, 0, 0, 0.35); "
        f"border: 1px solid {colors.border}; "
        f"border-radius: {tokens.radius.sm}px; }}"
    )
    inner = QVBoxLayout(block)
    inner.setContentsMargins(tokens.spacing.sm, 1, tokens.spacing.sm, 1)
    inner.setSpacing(0)
    caption = QLabel(label)
    caption.setFont(theme.font("caption"))
    caption.setStyleSheet(f"color: {colors.text_muted}; background: transparent;")
    inner.addWidget(caption)
    inner.addWidget(_Waveform(theme, color=color, seed=seed), 1)
    content.addWidget(block, 1)
    return row


# --------------------------------------------------------------------------- #
# Right panel
# --------------------------------------------------------------------------- #
def _right_card(theme: ThemeManager) -> QFrame:
    tokens = theme.tokens
    card = _styled(QFrame())
    card.setObjectName("StudioRightCard")
    card.setStyleSheet(
        f"#StudioRightCard {{ background: {tokens.colors.surface}; "
        f"border: 1px solid {tokens.colors.border}; "
        f"border-radius: {tokens.radius.md}px; }}"
    )
    col = QVBoxLayout(card)
    col.setContentsMargins(tokens.spacing.md, tokens.spacing.md,
                           tokens.spacing.md, tokens.spacing.md)
    col.setSpacing(tokens.spacing.sm)
    return card


def _ai_card(theme: ThemeManager, glyph: str, title: str, subtitle: str) -> QWidget:
    tokens = theme.tokens
    colors = tokens.colors
    card = _styled(QFrame())
    card.setObjectName("StudioAICard")
    card.setStyleSheet(
        f"#StudioAICard {{ background: {colors.surface_elevated}; "
        f"border: 1px solid {colors.border}; "
        f"border-radius: {tokens.radius.md}px; }} "
        f"#StudioAICard:hover {{ border: 1px solid {colors.accent_cyan}; }}"
    )
    row = QHBoxLayout(card)
    row.setContentsMargins(tokens.spacing.sm, tokens.spacing.sm,
                           tokens.spacing.sm, tokens.spacing.sm)
    row.setSpacing(tokens.spacing.sm)

    icon = QLabel(glyph)
    icon.setFont(theme.font("body"))
    icon.setFixedSize(30, 30)
    icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
    icon.setStyleSheet(
        f"color: {colors.text_primary}; "
        f"background: qlineargradient(x1:0, y1:0, x2:1, y2:1, "
        f"stop:0 {colors.accent_cyan}, stop:1 {colors.accent_blue}); "
        f"border-radius: 8px;"
    )
    row.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)

    text_col = QVBoxLayout()
    text_col.setSpacing(0)
    name = QLabel(title)
    name.setFont(theme.font("body_small"))
    name.setStyleSheet(f"color: {colors.text_primary}; background: transparent;")
    text_col.addWidget(name)
    sub = QLabel(subtitle)
    sub.setFont(theme.font("caption"))
    sub.setWordWrap(True)
    sub.setStyleSheet(f"color: {colors.text_muted}; background: transparent;")
    text_col.addWidget(sub)
    row.addLayout(text_col, 1)

    badge = QLabel("AI")
    badge.setFont(theme.font("caption"))
    badge.setStyleSheet(
        f"color: {colors.accent_cyan}; background: rgba(46, 230, 255, 0.12); "
        f"border-radius: 4px; padding: 0px 4px;"
    )
    row.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)
    return card


def _property_value_row(
    theme: ThemeManager, label: str, values: Sequence[str]
) -> QHBoxLayout:
    tokens = theme.tokens
    colors = tokens.colors
    row = QHBoxLayout()
    row.setSpacing(tokens.spacing.sm)
    key = QLabel(label)
    key.setFont(theme.font("body_small"))
    key.setFixedWidth(64)
    key.setStyleSheet(f"color: {colors.text_secondary}; background: transparent;")
    row.addWidget(key)
    for value in values:
        chip = QLabel(value)
        chip.setFont(theme.font("caption"))
        chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        chip.setStyleSheet(
            f"color: {colors.text_primary}; background: {colors.surface_overlay}; "
            f"border: 1px solid {colors.border}; border-radius: 5px; "
            f"padding: 3px 8px;"
        )
        row.addWidget(chip, 1)
    return row


def _slider_row(
    theme: ThemeManager, label: str, value: int, display: str,
    *, accent: Optional[str] = None, checkbox: bool = False, checked: bool = True,
) -> QHBoxLayout:
    tokens = theme.tokens
    colors = tokens.colors
    row = QHBoxLayout()
    row.setSpacing(tokens.spacing.sm)
    if checkbox:
        mark = QLabel("☑" if checked else "☐")
        mark.setFont(theme.font("body_small"))
        mark.setStyleSheet(
            f"color: {colors.accent_purple if checked else colors.text_muted}; "
            f"background: transparent;"
        )
        row.addWidget(mark)
    key = QLabel(label)
    key.setFont(theme.font("body_small"))
    key.setFixedWidth(52 if checkbox else 64)
    key.setStyleSheet(f"color: {colors.text_secondary}; background: transparent;")
    row.addWidget(key)
    row.addWidget(_hslider(theme, value, accent=accent), 1)
    amount = QLabel(display)
    amount.setFont(theme.font("caption"))
    amount.setAlignment(Qt.AlignmentFlag.AlignCenter)
    amount.setFixedWidth(52)
    amount.setStyleSheet(
        f"color: {colors.text_primary}; background: {colors.surface_overlay}; "
        f"border-radius: 5px; padding: 3px 2px;"
    )
    row.addWidget(amount)
    return row


def _group_header(theme: ThemeManager, title: str) -> QHBoxLayout:
    colors = theme.tokens.colors
    row = QHBoxLayout()
    chevron = QLabel("▾")
    chevron.setFont(theme.font("caption"))
    chevron.setStyleSheet(f"color: {colors.text_muted}; background: transparent;")
    row.addWidget(chevron)
    label = QLabel(title)
    label.setFont(theme.font("body_small"))
    label.setStyleSheet(f"color: {colors.text_primary}; background: transparent;")
    row.addWidget(label, 1)
    return row


def _task_row(
    theme: ThemeManager, glyph: str, title: str, subtitle: str, value: int,
    *, color: Optional[str] = None,
) -> QVBoxLayout:
    tokens = theme.tokens
    colors = tokens.colors
    fill = color or colors.accent_cyan
    block = QVBoxLayout()
    block.setSpacing(4)
    head = QHBoxLayout()
    head.setSpacing(tokens.spacing.sm)
    icon = QLabel(glyph)
    icon.setFont(theme.font("body_small"))
    icon.setFixedSize(26, 26)
    icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
    icon.setStyleSheet(
        f"color: {colors.text_primary}; background: {colors.surface_overlay}; "
        f"border-radius: 6px;"
    )
    head.addWidget(icon)
    text_col = QVBoxLayout()
    text_col.setSpacing(0)
    name = QLabel(title)
    name.setFont(theme.font("body_small"))
    name.setStyleSheet(f"color: {colors.text_primary}; background: transparent;")
    text_col.addWidget(name)
    sub = QLabel(subtitle)
    sub.setFont(theme.font("caption"))
    sub.setStyleSheet(f"color: {colors.text_muted}; background: transparent;")
    text_col.addWidget(sub)
    head.addLayout(text_col, 1)
    pct = QLabel(f"{value}%")
    pct.setFont(theme.font("caption"))
    pct.setStyleSheet(f"color: {colors.text_secondary}; background: transparent;")
    head.addWidget(pct)
    block.addLayout(head)
    block.addWidget(_thin_progress(theme, value, fill))
    return block


def _build_right_panel(theme: ThemeManager) -> QWidget:
    tokens = theme.tokens
    colors = tokens.colors

    panel = _styled(QFrame())
    panel.setObjectName("StudioRightPanel")
    panel.setFixedWidth(_RIGHT_PANEL_WIDTH)
    panel.setStyleSheet(
        f"#StudioRightPanel {{ background: {colors.background_deep}; "
        f"border-left: 1px solid {colors.border}; }}"
    )
    outer = QVBoxLayout(panel)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(0)

    scroll = QScrollArea(panel)
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setStyleSheet("QScrollArea { background: transparent; }")

    body = _styled(QWidget())
    body.setStyleSheet("background: transparent;")
    col = QVBoxLayout(body)
    col.setContentsMargins(tokens.spacing.md, tokens.spacing.md,
                           tokens.spacing.md, tokens.spacing.md)
    col.setSpacing(tokens.spacing.md)

    # Header: AI ASSISTANT + Export button.
    head = QHBoxLayout()
    head.addWidget(_caption(theme, "AI Assistant"))
    head.addStretch(1)
    export = QLabel("⬆  Export")
    export.setFont(theme.font("body_small"))
    export.setStyleSheet(
        f"color: {colors.text_on_accent}; "
        f"background: qlineargradient(x1:0, y1:0, x2:1, y2:0, "
        f"stop:0 {colors.accent_cyan}, stop:1 {colors.accent_blue}); "
        f"border-radius: {tokens.radius.sm}px; padding: 6px 16px;"
    )
    head.addWidget(export)
    col.addLayout(head)

    # AI feature cards (2-column grid).
    grid = QGridLayout()
    grid.setSpacing(tokens.spacing.sm)
    features = (
        ("✂", "Auto Edit", "Create edit automatically"),
        ("\U0001f3af", "Highlight Detection", "Find best moments"),
        ("\U0001f602", "Funny Moment", "Detect funny moments"),
        ("\U0001f39a", "Beat Sync", "Sync to music beat"),
        ("\U0001f4dd", "Subtitle Generator", "Auto generate subtitles"),
        ("\U0001f5bc", "Thumbnail Generator", "Create thumbnails"),
        ("\U0001f4c4", "Script Assistant", "Generate video scripts"),
        ("\U0001f3a4", "Voice Cleanup", "Enhance voice quality"),
    )
    for i, (glyph, title, subtitle) in enumerate(features):
        grid.addWidget(_ai_card(theme, glyph, title, subtitle), i // 2, i % 2)
    col.addLayout(grid)

    # Properties.
    props = _right_card(theme)
    props_col = props.layout()
    props_head = QHBoxLayout()
    props_head.addWidget(_caption(theme, "Properties"))
    props_head.addStretch(1)
    close = QLabel("×")
    close.setStyleSheet(f"color: {colors.text_muted}; background: transparent;")
    props_head.addWidget(close)
    props_col.addLayout(props_head)

    props_col.addLayout(_group_header(theme, "Transform"))
    props_col.addLayout(_property_value_row(theme, "Scale", ("X  100.0%", "Y  100.0%")))
    props_col.addLayout(_property_value_row(theme, "Position", ("X  0.0", "Y  0.0")))
    props_col.addLayout(_property_value_row(theme, "Rotation", ("0.0°",)))
    props_col.addLayout(_slider_row(theme, "Opacity", 100, "100%"))

    props_col.addSpacing(tokens.spacing.sm)
    props_col.addLayout(_group_header(theme, "Audio"))
    props_col.addLayout(_slider_row(theme, "Volume", 85, "0.0 dB",
                                    accent=colors.accent_blue))
    props_col.addLayout(_property_value_row(theme, "Pan", ("0.0",)))
    enhance_row = QHBoxLayout()
    enhance_label = QLabel("AI Voice Enhance")
    enhance_label.setFont(theme.font("body_small"))
    enhance_label.setStyleSheet(
        f"color: {colors.text_secondary}; background: transparent;"
    )
    enhance_row.addWidget(enhance_label, 1)
    enhance_row.addWidget(_toggle_pill(theme, checked=True))
    props_col.addLayout(enhance_row)

    props_col.addSpacing(tokens.spacing.sm)
    props_col.addLayout(_group_header(theme, "Effects"))
    props_col.addLayout(_slider_row(theme, "Glow", 45, "45%",
                                    accent=colors.accent_purple,
                                    checkbox=True, checked=True))
    props_col.addLayout(_slider_row(theme, "Shake", 0, "0%",
                                    accent=colors.accent_purple,
                                    checkbox=True, checked=False))
    col.addWidget(props)

    # Export queue.
    queue = _right_card(theme)
    queue_col = queue.layout()
    queue_head = QHBoxLayout()
    queue_head.addWidget(_caption(theme, "Export Queue"))
    queue_head.addStretch(1)
    add_new = QLabel("Add New ▾")
    add_new.setFont(theme.font("caption"))
    add_new.setStyleSheet(
        f"color: {colors.text_secondary}; background: {colors.surface_overlay}; "
        f"border-radius: 5px; padding: 3px 8px;"
    )
    queue_head.addWidget(add_new)
    queue_col.addLayout(queue_head)
    item = _task_row(theme, "\U0001f3ac", "Valorant Montage 2026",
                     "1080p 60fps   H.264", 45, color=colors.accent_purple)
    queue_col.addLayout(item)
    eta = QLabel("ETA: 00:02:35")
    eta.setFont(theme.font("caption"))
    eta.setAlignment(Qt.AlignmentFlag.AlignRight)
    eta.setStyleSheet(f"color: {colors.text_muted}; background: transparent;")
    queue_col.addWidget(eta)
    col.addWidget(queue)

    # Background tasks.
    tasks = _right_card(theme)
    tasks_col = tasks.layout()
    tasks_col.addWidget(_caption(theme, "Background Tasks"))
    tasks_col.addLayout(_task_row(theme, "\U0001f9e0", "AI Analyzing",
                                  "Analyzing audio & video…", 78))
    tasks_col.addLayout(_task_row(theme, "\U0001f5bc", "Generating Thumbnails",
                                  "Creating thumbnail…", 65))
    col.addWidget(tasks)

    # Render progress.
    render = _right_card(theme)
    render_col = render.layout()
    render_col.addWidget(_caption(theme, "Render Progress"))
    render_col.addLayout(_task_row(theme, "⚡", "Final Render",
                                   "Rendering 1080p 60fps…", 31,
                                   color=colors.accent_blue))
    col.addWidget(render)

    col.addStretch(1)
    scroll.setWidget(body)
    outer.addWidget(scroll)
    return panel


# --------------------------------------------------------------------------- #
# Bottom status bar
# --------------------------------------------------------------------------- #
def _build_status_bar(theme: ThemeManager) -> QWidget:
    tokens = theme.tokens
    colors = tokens.colors

    bar = _styled(QFrame())
    bar.setObjectName("StudioStatusBar")
    bar.setFixedHeight(26)
    bar.setStyleSheet(
        f"#StudioStatusBar {{ background: {colors.background_deep}; "
        f"border-top: 1px solid {colors.border}; }}"
    )
    row = QHBoxLayout(bar)
    row.setContentsMargins(tokens.spacing.md, 0, tokens.spacing.md, 0)
    row.setSpacing(tokens.spacing.xl)

    def status_label(text: str, color: str) -> QLabel:
        label = QLabel(text)
        label.setFont(theme.font("caption"))
        label.setStyleSheet(f"color: {color}; background: transparent;")
        return label

    engine = QHBoxLayout()
    engine.setSpacing(tokens.spacing.xs)
    engine.addWidget(status_label("AI Engine:", colors.text_muted))
    engine.addWidget(status_label("Active", colors.success))
    row.addLayout(engine)

    row.addWidget(status_label("Mode: Full Edit", colors.text_muted))
    row.addWidget(status_label("Frame: 1276 / 6450", colors.text_muted))
    row.addStretch(1)
    row.addWidget(status_label("Saved 2 minutes ago", colors.text_muted))
    row.addWidget(_dot(theme, colors.success))
    return bar


# --------------------------------------------------------------------------- #
# Screen assembly
# --------------------------------------------------------------------------- #
def build_studio_screen(theme: ThemeManager, *, media_source=None) -> QWidget:
    """Build and return the full studio workspace screen.

    Constructed without running a Qt event loop so it can be asserted
    headlessly in tests. All visual values come from the injected ``theme``.

    Integration Milestone 2: the screen embeds the existing
    :class:`MediaBrowser` and :class:`TransportBar` as hidden children and
    wires media selection to the preview stage (first frame, title,
    timecode). Without a selection, the original static/demo presentation
    renders unchanged.

    Args:
        theme: The injected theme manager (sole source of visual values).
        media_source: Optional preview media source (duck-typed like
            :class:`~gui.integration.preview_media.PreviewMediaSource`).
            When omitted, the real source is constructed lazily; tests
            inject a fake.

    Returns:
        The fully composed studio screen as a :class:`QWidget`.
    """
    tokens = theme.tokens

    screen = _styled(QWidget())
    screen.setObjectName("StudioScreen")
    screen.setWindowTitle(_WINDOW_TITLE)
    screen.setStyleSheet(
        f"#StudioScreen {{ background: {tokens.colors.background_deep}; }}"
    )

    root = QVBoxLayout(screen)
    root.setContentsMargins(0, 0, 0, 0)
    root.setSpacing(0)

    root.addWidget(_build_menu_bar(theme))
    root.addWidget(_build_toolbar(theme))

    body = QHBoxLayout()
    body.setContentsMargins(0, 0, 0, 0)
    body.setSpacing(0)
    body.addWidget(_build_sidebar(theme))

    center = _styled(QWidget())
    center.setObjectName("StudioCenter")
    center.setStyleSheet(
        f"#StudioCenter {{ background: {tokens.colors.background_base}; }}"
    )
    center_col = QVBoxLayout(center)
    center_col.setContentsMargins(tokens.spacing.md, tokens.spacing.md,
                                  tokens.spacing.md, tokens.spacing.md)
    center_col.setSpacing(tokens.spacing.sm)
    stage = _build_preview(theme)
    center_col.addWidget(stage, 5)
    center_col.addWidget(_build_transport(theme))
    center_col.addWidget(_build_timeline(theme), 4)
    body.addWidget(center, 1)

    body.addWidget(_build_right_panel(theme))
    root.addLayout(body, 1)

    root.addWidget(_build_status_bar(theme))

    _wire_media_preview(screen, stage, theme, media_source)
    return screen


# --------------------------------------------------------------------------- #
# Integration Milestone 2: media -> preview wiring (additive; visuals frozen)
# --------------------------------------------------------------------------- #
def _wire_media_preview(
    screen: QWidget,
    stage: "_PreviewStage",
    theme: ThemeManager,
    media_source,
) -> None:
    """Embed the hidden MediaBrowser + TransportBar and wire the preview.

    The browser and transport are parented to the screen but hidden (the
    approved Milestone 1 pattern): discoverable via ``findChildren``, fully
    wired, and invisible so the frozen studio layout is untouched. The
    existing TransportBar owns all playback state; the visible studio glyphs
    only call its public API and restyle themselves from ``state_changed``.
    """
    colors = theme.tokens.colors

    if media_source is None:
        from gui.integration.preview_media import PreviewMediaSource

        media_source = PreviewMediaSource()

    # Real media when available; the frozen demo labels otherwise.
    items = media_source.list_items() or list(_DEMO_MEDIA)

    browser = MediaBrowser(theme, items=items)
    browser.setParent(screen)
    browser.setVisible(False)

    transport = TransportBar(theme)
    transport.setParent(screen)
    transport.setVisible(False)

    timecode: QLabel = screen.findChild(QLabel, "StudioTimecode")
    glyphs = {
        state: screen.findChild(QLabel, f"StudioTransport{state.capitalize()}")
        for state in ("play", "pause", "stop")
    }
    #: Maps each glyph to the TransportBar state it drives.
    glyph_states = {"play": "playing", "pause": "paused", "stop": "stopped"}

    def on_selection_changed(index: int) -> None:
        """Load the selected clip's first frame; restore demo art on clear."""
        name = browser.current_item()
        if index < 0 or name is None:
            stage.set_frame(None)
            screen.setWindowTitle(_WINDOW_TITLE)
            timecode.setText(_DEMO_TIMECODE)
            return
        stage.set_frame(media_source.load_first_frame(name))
        screen.setWindowTitle(f"{_WINDOW_TITLE} — {name}")
        duration = media_source.duration_timecode(name)
        timecode.setText(
            f"00:00:00:00 / {duration}" if duration else _DEMO_TIMECODE
        )

    browser.selection_changed.connect(on_selection_changed)

    def on_state_changed(state: str) -> None:
        """Mirror the TransportBar state onto the visible glyph styling."""
        for key, label in glyphs.items():
            if label is None:
                continue
            active = glyph_states[key] == state
            label.setStyleSheet(
                f"QLabel {{ color: "
                f"{colors.accent_cyan if active else colors.text_secondary}; "
                f"background: transparent; padding: 2px 6px; }} "
                f"QLabel:hover {{ color: {colors.text_primary}; }}"
            )

    transport.state_changed.connect(on_state_changed)

    # Visible glyphs drive the frozen TransportBar state machine (reuse, not
    # reimplementation). QLabels carry no clicked signal; the release-event
    # lambda is the same UI-only pattern NavigationSidebar uses.
    for key, label in glyphs.items():
        if label is None:
            continue
        label.mouseReleaseEvent = (  # type: ignore[assignment]
            lambda _event, s=glyph_states[key]: transport.set_state(s)
        )
