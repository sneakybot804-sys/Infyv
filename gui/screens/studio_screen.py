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

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import (
    QColor,
    QImage,
    QLinearGradient,
    QPainter,
    QPen,
    QPixmap,
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
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from gui.theme.manager import ThemeManager
from gui.widgets.media_browser import MediaBrowser

__all__ = ["build_studio_screen"]

_SIDEBAR_WIDTH = 185
_RIGHT_PANEL_WIDTH = 400
_PLAYHEAD_FRACTION = 0.0  # No media loaded; playhead at start

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


def _empty_state(
    theme: ThemeManager,
    icon: str,
    title: str,
    description: str,
    *,
    action_label: Optional[str] = None,
    action_callback=None,
) -> QWidget:
    """Build a professional empty state widget with icon, title, description, and optional action."""
    tokens = theme.tokens
    colors = tokens.colors
    container = QWidget()
    container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    container.setStyleSheet("background: transparent;")
    layout = QVBoxLayout(container)
    layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.setSpacing(tokens.spacing.sm)

    icon_label = QLabel(icon)
    icon_label.setFont(theme.font("h1"))
    icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    icon_label.setStyleSheet(f"color: {colors.text_muted}; background: transparent;")
    layout.addWidget(icon_label)

    title_label = QLabel(title)
    title_label.setFont(theme.font("h3"))
    title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    title_label.setStyleSheet(f"color: {colors.text_primary}; background: transparent;")
    layout.addWidget(title_label)

    desc_label = QLabel(description)
    desc_label.setFont(theme.font("body_small"))
    desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    desc_label.setWordWrap(True)
    desc_label.setStyleSheet(f"color: {colors.text_muted}; background: transparent;")
    layout.addWidget(desc_label)

    if action_label:
        from gui.widgets.neon_button import NeonButton
        btn = NeonButton(theme, action_label, variant="primary", accent="cyan")
        if action_callback:
            btn.clicked.connect(action_callback)
        layout.addWidget(btn)

    return container


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
        self.setMinimumSize(36, 36)
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

    # Left: logo triangle + title
    logo = QLabel("▲")
    logo.setFont(theme.font("h3"))
    logo.setStyleSheet(f"color: {colors.accent_cyan}; background: transparent;")
    row.addWidget(logo)

    title = QLabel("AI Gaming Video Editor")
    title.setFont(theme.font("h3"))
    title.setStyleSheet(
        f"color: {colors.text_primary}; background: transparent; "
        f"margin-left: 4px;"
    )
    row.addWidget(title)

    row.addSpacing(tokens.spacing.lg)

    # Center: menu items
    for menu in ("File", "Edit", "Clip", "Sequence", "Markers",
                 "Graphics and Titles", "View", "Window", "Help"):
        item = QLabel(menu)
        item.setFont(theme.font("body_small"))
        item.setStyleSheet(
            f"QLabel {{ color: {colors.text_secondary}; background: transparent; "
            f"padding: 4px 6px; }} QLabel:hover {{ color: {colors.text_primary}; }}"
        )
        row.addWidget(item)

    row.addStretch(1)

    # Right side: "Editing" dropdown pill
    editing_pill = _styled(QFrame())
    editing_pill.setObjectName("StudioEditingPill")
    editing_pill.setStyleSheet(
        f"#StudioEditingPill {{ background: {colors.surface}; "
        f"border: 1px solid {colors.border}; border-radius: {tokens.radius.sm}px; }}"
    )
    pill_row = QHBoxLayout(editing_pill)
    pill_row.setContentsMargins(tokens.spacing.md, 4, tokens.spacing.sm, 4)
    pill_row.setSpacing(tokens.spacing.sm)
    pill_label = QLabel("Editing")
    pill_label.setFont(theme.font("body_small"))
    pill_label.setStyleSheet(
        f"color: {colors.text_primary}; background: transparent;"
    )
    pill_row.addWidget(pill_label)
    pill_arrow = QLabel("▾")
    pill_arrow.setStyleSheet(f"color: {colors.text_muted}; background: transparent;")
    pill_row.addWidget(pill_arrow)
    row.addWidget(editing_pill)

    row.addSpacing(tokens.spacing.sm)

    # Right side: blue "Export" button
    export_btn = _styled(QFrame())
    export_btn.setObjectName("StudioMenuExport")
    export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    export_btn.setStyleSheet(
        f"#StudioMenuExport {{ background: {colors.accent_blue}; "
        f"border-radius: {tokens.radius.sm}px; }}"
    )
    export_btn_row = QHBoxLayout(export_btn)
    export_btn_row.setContentsMargins(tokens.spacing.lg, 5, tokens.spacing.lg, 5)
    export_btn_row.setSpacing(0)
    export_label = QLabel("Export")
    export_label.setFont(theme.font("body_small"))
    export_label.setStyleSheet(
        f"color: {colors.text_on_accent}; background: transparent;"
    )
    export_btn_row.addWidget(export_label)
    row.addWidget(export_btn)

    return bar


# --------------------------------------------------------------------------- #
# Toolbar strip
# --------------------------------------------------------------------------- #
def _tool_button(
    theme: ThemeManager, glyph: str, label: str, *, active: bool = False, object_name: Optional[str] = None
) -> QWidget:
    colors = theme.tokens.colors
    button = _styled(QFrame())
    button.setObjectName(object_name or "StudioToolButton")
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    if active:
        button.setStyleSheet(
            f"#{object_name or 'StudioToolButton'} {{ background: {colors.surface_elevated}; "
            f"border: 1px solid {colors.accent_cyan}; border-radius: 8px; }}"
        )
    else:
        button.setStyleSheet(
            f"#{object_name or 'StudioToolButton'} {{ background: transparent; border: none; "
            f"border-radius: 8px; }} "
            f"#{object_name or 'StudioToolButton'}:hover {{ background: {colors.surface}; }}"
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

    # File operations group
    btn_new = _tool_button(theme, "\U0001f4c4", "New", object_name="ToolbarNew")
    btn_open = _tool_button(theme, "\U0001f4c2", "Open", object_name="ToolbarOpen")
    btn_save = _tool_button(theme, "\U0001f4be", "Save", object_name="ToolbarSave")
    row.addWidget(btn_new)
    row.addWidget(btn_open)
    row.addWidget(btn_save)
    row.addWidget(_tool_separator(theme))

    # Media operations group
    btn_import = _tool_button(theme, "⬇", "Import", object_name="ToolbarImport")
    btn_record = _tool_button(theme, "⏺", "Record", object_name="ToolbarRecord")
    row.addWidget(btn_import)
    row.addWidget(btn_record)
    row.addWidget(_tool_separator(theme))

    # AI operations group
    btn_ai_analyze = _tool_button(theme, "\U0001f9e0", "AI Analyze", active=True, object_name="ToolbarAIAnalyze")
    btn_auto_cut = _tool_button(theme, "✂", "Auto Cut", object_name="ToolbarAutoCut")
    btn_beat_sync = _tool_button(theme, "\U0001f39a", "Beat Sync", object_name="ToolbarBeatSync")
    btn_ai_render = _tool_button(theme, "⚡", "AI Render", object_name="ToolbarAIRender")
    row.addWidget(btn_ai_analyze)
    row.addWidget(btn_auto_cut)
    row.addWidget(btn_beat_sync)
    row.addWidget(btn_ai_render)

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

    # Scroll area so all sidebar content (including user profile) is accessible
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

    inner_widget = _styled(QWidget())
    inner_widget.setStyleSheet("background: transparent;")
    col = QVBoxLayout(inner_widget)
    col.setContentsMargins(tokens.spacing.xs, tokens.spacing.xs,
                           tokens.spacing.xs, tokens.spacing.xs)
    col.setSpacing(0)

    # --- Navigation items ---
    nav = QVBoxLayout()
    nav.setSpacing(0)
    items = (
        ("\U0001f3e0", "Dashboard", True),
        ("\U0001f4c1", "Projects", False),
        ("\U0001f39e", "Media", False),
        ("\U0001f9e9", "Assets", False),
        ("\U0001f4fd", "Timeline", False),
        ("✨", "Effects", False),
        ("\U0001f500", "Transitions", False),
        ("\U0001f3b5", "Audio", False),
        ("\U0001f4dd", "Captions", False),
        ("\U0001f4d0", "Templates", False),
        ("\U0001f916", "AI Studio", False),
        ("⬆", "Export", False),
        ("⚙", "Settings", False),
    )
    for glyph, label, active in items:
        item = _styled(QFrame())
        item.setObjectName("StudioNavItem")
        if active:
            item.setStyleSheet(
                f"#StudioNavItem {{ background: {colors.surface_elevated}; "
                f"border-left: 3px solid {colors.accent_cyan}; "
                f"border-radius: {tokens.radius.sm}px; }}"
            )
        else:
            item.setStyleSheet(
                f"#StudioNavItem {{ background: transparent; border: none; "
                f"border-radius: {tokens.radius.sm}px; }} "
                f"#StudioNavItem:hover {{ background: {colors.surface}; }}"
            )
        item_row = QHBoxLayout(item)
        item_row.setContentsMargins(tokens.spacing.md, 5, tokens.spacing.md, 5)
        item_row.setSpacing(tokens.spacing.sm)
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

    col.addSpacing(tokens.spacing.xs)

    # --- System Overview card ---
    system_card = _sidebar_card(theme)
    system_col = system_card.layout()
    system_col.addWidget(_caption(theme, "System Overview"))
    for label, value, detail, color in (
        ("GPU", 0, "Not detected", colors.accent_cyan),
        ("RAM", 0, "Not detected", colors.accent_purple),
        ("CPU", 0, "Not detected", colors.accent_blue),
    ):
        head = QHBoxLayout()
        name = QLabel(label)
        name.setFont(theme.font("body_small"))
        name.setStyleSheet(
            f"color: {colors.text_secondary}; background: transparent;"
        )
        head.addWidget(name, 1)
        pct = QLabel("--")
        pct.setFont(theme.font("body_small"))
        pct.setStyleSheet(f"color: {colors.text_muted}; background: transparent;")
        head.addWidget(pct)
        system_col.addLayout(head)
        system_col.addWidget(_thin_progress(theme, value, color))
        sub = QLabel(detail)
        sub.setFont(theme.font("caption"))
        sub.setStyleSheet(f"color: {colors.text_muted}; background: transparent;")
        system_col.addWidget(sub)
    col.addWidget(system_card)

    col.addSpacing(tokens.spacing.sm)

    # --- AI Engine / Render Engine status card ---
    engine_card = _sidebar_card(theme)
    engine_col = engine_card.layout()
    # AI ENGINE row
    ai_line = QHBoxLayout()
    ai_label = QLabel("AI ENGINE")
    ai_label.setFont(theme.font("caption"))
    ai_label.setStyleSheet(
        f"color: {colors.text_secondary}; background: transparent;"
    )
    ai_line.addWidget(ai_label, 1)
    ai_status = QLabel("--")
    ai_status.setFont(theme.font("caption"))
    ai_status.setStyleSheet(
        f"color: {colors.text_muted}; background: transparent;"
    )
    ai_line.addWidget(ai_status)
    engine_col.addLayout(ai_line)
    # NPU / AI row
    npu_line = QHBoxLayout()
    npu_label = QLabel("NPU / AI >")
    npu_label.setFont(theme.font("caption"))
    npu_label.setStyleSheet(
        f"color: {colors.text_secondary}; background: transparent;"
    )
    npu_line.addWidget(npu_label, 1)
    npu_val = QLabel("--")
    npu_val.setFont(theme.font("caption"))
    npu_val.setStyleSheet(
        f"color: {colors.text_muted}; background: transparent;"
    )
    npu_line.addWidget(npu_val)
    engine_col.addLayout(npu_line)
    # RENDER ENGINE row
    render_line = QHBoxLayout()
    render_label = QLabel("RENDER ENGINE")
    render_label.setFont(theme.font("caption"))
    render_label.setStyleSheet(
        f"color: {colors.text_secondary}; background: transparent;"
    )
    render_line.addWidget(render_label, 1)
    render_status = QLabel("--")
    render_status.setFont(theme.font("caption"))
    render_status.setStyleSheet(
        f"color: {colors.text_muted}; background: transparent;"
    )
    render_line.addWidget(render_status)
    engine_col.addLayout(render_line)
    # Render detail row
    render_detail = QLabel("--")
    render_detail.setFont(theme.font("caption"))
    render_detail.setStyleSheet(
        f"color: {colors.text_muted}; background: transparent;"
    )
    engine_col.addWidget(render_detail)
    col.addWidget(engine_card)

    # --- User profile card at bottom ---
    user_card = _styled(QFrame())
    user_card.setObjectName("StudioUserProfile")
    user_card.setStyleSheet(
        f"#StudioUserProfile {{ background: {colors.surface_elevated}; "
        f"border: 1px solid {colors.border}; "
        f"border-radius: {tokens.radius.md}px; }}"
    )
    user_row = QHBoxLayout(user_card)
    user_row.setContentsMargins(tokens.spacing.md, tokens.spacing.sm,
                                tokens.spacing.md, tokens.spacing.sm)
    user_row.setSpacing(tokens.spacing.md)

    # User avatar (circular with generic initial, gradient)
    avatar = _styled(QFrame())
    avatar.setFixedSize(36, 36)
    avatar.setStyleSheet(
        f"background: qlineargradient(x1:0, y1:0, x2:1, y2:1, "
        f"stop:0 {colors.accent_cyan}, stop:1 {colors.accent_purple}); "
        f"border-radius: 18px;"
    )
    avatar_label = QLabel("U", avatar)
    avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    avatar_label.setFont(theme.font("h3"))
    avatar_label.setStyleSheet(
        f"color: {colors.text_on_accent}; background: transparent;"
    )
    avatar_label.setGeometry(0, 0, 36, 36)
    user_row.addWidget(avatar)

    # User info (name and plan)
    user_info = QVBoxLayout()
    user_info.setSpacing(0)
    user_name = QLabel("User")
    user_name.setFont(theme.font("body_small"))
    user_name.setStyleSheet(
        f"color: {colors.text_primary}; background: transparent;"
    )
    user_info.addWidget(user_name)
    user_plan = QLabel("No plan")
    user_plan.setFont(theme.font("caption"))
    user_plan.setStyleSheet(
        f"color: {colors.text_muted}; background: transparent;"
    )
    user_info.addWidget(user_plan)
    user_row.addLayout(user_info, 1)

    # Chevron/arrow
    chevron = QLabel(">")
    chevron.setFont(theme.font("body"))
    chevron.setStyleSheet(
        f"color: {colors.text_muted}; background: transparent;"
    )
    user_row.addWidget(chevron)

    col.addWidget(user_card)

    # Wrap in scroll area
    scroll.setWidget(inner_widget)
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
        f"border-radius: {tokens.radius.sm}px; }}"
    )
    col = QVBoxLayout(card)
    col.setContentsMargins(tokens.spacing.sm, tokens.spacing.xs,
                           tokens.spacing.sm, tokens.spacing.xs)
    col.setSpacing(tokens.spacing.xs)
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
        # The stylesheet paints the gradient/border.
        # Frame display is handled by the QLabel overlay in _wire_playback.
        super().paintEvent(event)


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

    # Empty state: no media loaded (hidden when frame is displayed)
    empty_icon = QLabel("🎬")
    empty_icon.setObjectName("PreviewEmptyIcon")
    empty_icon.setFont(theme.font("display"))
    empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
    empty_icon.setStyleSheet(f"color: {colors.text_muted}; background: transparent;")
    col.addWidget(empty_icon)

    empty_title = QLabel("No media loaded")
    empty_title.setObjectName("PreviewEmptyTitle")
    empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
    empty_title.setFont(theme.font("h3"))
    empty_title.setStyleSheet(f"color: {colors.text_secondary}; background: transparent;")
    col.addWidget(empty_title)

    empty_desc = QLabel("Import a video to begin editing")
    empty_desc.setObjectName("PreviewEmptyDesc")
    empty_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
    empty_desc.setFont(theme.font("body_small"))
    empty_desc.setStyleSheet(f"color: {colors.text_muted}; background: transparent;")
    col.addWidget(empty_desc)

    col.addStretch(1)
    return stage


def _build_transport(theme: ThemeManager) -> QWidget:
    tokens = theme.tokens
    colors = tokens.colors

    # Container for transport + progress bar
    container = _styled(QWidget())
    container.setObjectName("TransportContainer")
    container.setStyleSheet("background: transparent;")
    container_layout = QVBoxLayout(container)
    container_layout.setContentsMargins(0, 0, 0, 0)
    container_layout.setSpacing(4)

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

    # Left timecode
    timecode = QLabel("00:00:00:00")
    timecode.setObjectName("StudioTimecode")
    timecode.setFont(theme.font("mono"))
    timecode.setStyleSheet(f"color: {colors.text_secondary}; background: transparent;")
    row.addWidget(timecode)

    # Fit dropdown
    fit_chip = _styled(QFrame())
    fit_chip.setObjectName("FitChip")
    fit_chip.setStyleSheet(
        f"#FitChip {{ background: {colors.surface_overlay}; "
        f"border: 1px solid {colors.border}; border-radius: 4px; }}"
    )
    fit_row = QHBoxLayout(fit_chip)
    fit_row.setContentsMargins(8, 3, 8, 3)
    fit_row.setSpacing(4)
    fit_label = QLabel("Fit")
    fit_label.setFont(theme.font("body_small"))
    fit_label.setStyleSheet(f"color: {colors.text_primary}; background: transparent;")
    fit_row.addWidget(fit_label)
    fit_arrow = QLabel("▾")
    fit_arrow.setStyleSheet(f"color: {colors.text_muted}; background: transparent;")
    fit_row.addWidget(fit_arrow)
    row.addWidget(fit_chip)

    row.addSpacing(16)

    # Playback buttons (matching screenshot)
    for glyph, accent, name in (
        ("⏮", False, "PrevFrame"), ("◀◀", False, "Rewind"),
        ("▶", True, "Play"), ("⏸", False, "Pause"),
        ("⏭", False, "NextFrame"),
    ):
        button = QLabel(glyph)
        button.setFont(theme.font("body"))
        button.setStyleSheet(
            f"QLabel {{ color: "
            f"{colors.accent_cyan if accent else colors.text_secondary}; "
            f"background: transparent; padding: 2px 6px; }} "
            f"QLabel:hover {{ color: {colors.text_primary}; }}"
        )
        button.setObjectName(f"StudioTransport{name}")
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        row.addWidget(button)

    row.addSpacing(16)

    # Speed dropdown
    speed_chip = _styled(QFrame())
    speed_chip.setObjectName("SpeedChip")
    speed_chip.setStyleSheet(
        f"#SpeedChip {{ background: {colors.surface_overlay}; "
        f"border: 1px solid {colors.border}; border-radius: 4px; }}"
    )
    speed_row = QHBoxLayout(speed_chip)
    speed_row.setContentsMargins(8, 3, 8, 3)
    speed_row.setSpacing(4)
    speed_label = QLabel("1.0x")
    speed_label.setFont(theme.font("body_small"))
    speed_label.setStyleSheet(f"color: {colors.text_primary}; background: transparent;")
    speed_row.addWidget(speed_label)
    speed_arrow = QLabel("▾")
    speed_arrow.setStyleSheet(f"color: {colors.text_muted}; background: transparent;")
    speed_row.addWidget(speed_arrow)
    row.addWidget(speed_chip)

    # Zoom dropdown
    zoom_chip = _styled(QFrame())
    zoom_chip.setObjectName("ZoomDropdown")
    zoom_chip.setStyleSheet(
        f"#ZoomDropdown {{ background: {colors.surface_overlay}; "
        f"border: 1px solid {colors.border}; border-radius: 4px; }}"
    )
    zoom_row = QHBoxLayout(zoom_chip)
    zoom_row.setContentsMargins(8, 3, 8, 3)
    zoom_row.setSpacing(4)
    zoom_label = QLabel("Full")
    zoom_label.setFont(theme.font("body_small"))
    zoom_label.setStyleSheet(f"color: {colors.text_primary}; background: transparent;")
    zoom_row.addWidget(zoom_label)
    zoom_arrow = QLabel("▾")
    zoom_arrow.setStyleSheet(f"color: {colors.text_muted}; background: transparent;")
    zoom_row.addWidget(zoom_arrow)
    row.addWidget(zoom_chip)

    row.addSpacing(16)

    # Right timecode (total duration)
    duration = QLabel("--:--:--:--")
    duration.setObjectName("StudioDuration")
    duration.setFont(theme.font("mono"))
    duration.setStyleSheet(f"color: {colors.text_secondary}; background: transparent;")
    row.addWidget(duration)

    # Settings and fullscreen icons
    settings = QLabel("⛶")
    settings.setFont(theme.font("body_small"))
    settings.setStyleSheet(f"color: {colors.text_muted}; background: transparent;")
    row.addWidget(settings)
    fullscreen = QLabel("⛶")
    fullscreen.setFont(theme.font("body_small"))
    fullscreen.setStyleSheet(f"color: {colors.text_muted}; background: transparent;")
    row.addWidget(fullscreen)

    container_layout.addWidget(bar)

    # Progress bar below transport
    progress = QProgressBar()
    progress.setObjectName("StudioProgress")
    progress.setRange(0, 100)
    progress.setValue(0)  # No media loaded
    progress.setTextVisible(False)
    progress.setFixedHeight(4)
    progress.setStyleSheet(
        f"QProgressBar {{ background: {colors.surface_overlay}; "
        f"border: none; border-radius: 2px; }} "
        f"QProgressBar::chunk {{ background: {colors.accent_cyan}; border-radius: 2px; }}"
    )
    container_layout.addWidget(progress)

    return container


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


def _timeline_chip(theme: ThemeManager, text: str, *, kind: str = "subtitle") -> QWidget:
    """A small rounded chip used on the Subtitles track."""
    tokens = theme.tokens
    colors = tokens.colors
    if kind == "subtitle":
        bg = "rgba(251, 191, 36, 0.14)"
        border = colors.warning
        fg = colors.warning
    else:
        bg = "rgba(181, 105, 255, 0.14)"
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
    return chip


def _track_header(
    theme: ThemeManager,
    badge: str,
    name: str,
    *,
    show_ms: bool = False,
    badge_color: Optional[str] = None,
) -> QWidget:
    tokens = theme.tokens
    colors = tokens.colors
    header = _styled(QFrame())
    header.setObjectName("StudioTrackHeader")
    header.setFixedWidth(140)
    header.setStyleSheet(
        f"#StudioTrackHeader {{ background: {colors.surface}; "
        f"border: 1px solid {colors.border}; "
        f"border-radius: {tokens.radius.sm}px; }}"
    )
    row = QHBoxLayout(header)
    row.setContentsMargins(tokens.spacing.sm, 2, tokens.spacing.sm, 2)
    row.setSpacing(tokens.spacing.sm)
    # Badge (V1/A1/etc.)
    tag = QLabel(badge)
    tag.setFont(theme.font("caption"))
    tag.setAlignment(Qt.AlignmentFlag.AlignCenter)
    tag.setFixedSize(24, 16)
    tag.setStyleSheet(
        f"color: {colors.text_primary}; "
        f"background: {badge_color or colors.surface_overlay}; "
        f"border-radius: 4px;"
    )
    row.addWidget(tag)
    # Name
    label = QLabel(name)
    label.setFont(theme.font("caption"))
    label.setStyleSheet(f"color: {colors.text_secondary}; background: transparent;")
    row.addWidget(label, 1)
    if show_ms:
        # Mute / Solo buttons
        for letter, tip in (("M", "Mute"), ("S", "Solo")):
            btn = QLabel(letter)
            btn.setFont(theme.font("caption"))
            btn.setAlignment(Qt.AlignmentFlag.AlignCenter)
            btn.setFixedSize(16, 14)
            btn.setToolTip(tip)
            btn.setStyleSheet(
                f"color: {colors.text_muted}; background: {colors.surface_overlay}; "
                f"border-radius: 3px;"
            )
            row.addWidget(btn)
    else:
        # Lock icon
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


class _TimelinePanel(QFrame):
    """Visual timeline panel with compatibility API for playback engine."""

    def __init__(self, theme: ThemeManager, parent=None) -> None:
        super().__init__(parent)
        self._duration = 60.0
        self._playhead = 0.0

    def set_playhead(self, position: float) -> None:
        self._playhead = max(0.0, min(position, self._duration))

    def playhead(self) -> float:
        return self._playhead

    def duration(self) -> float:
        return self._duration

    def set_duration(self, duration: float) -> None:
        self._duration = max(0.0, duration)

    def pause(self) -> None:
        """No-op pause for playback engine compatibility."""
        pass


def _build_timeline(theme: ThemeManager) -> QWidget:
    tokens = theme.tokens
    colors = tokens.colors

    panel = _styled(_TimelinePanel(theme))
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

    # Timeline header: title + hamburger menu
    header_row = QHBoxLayout()
    header_row.setSpacing(tokens.spacing.sm)
    hamburger = QLabel("☰")
    hamburger.setFont(theme.font("body"))
    hamburger.setStyleSheet(
        f"color: {colors.text_secondary}; background: transparent;"
    )
    header_row.addWidget(hamburger)
    title = QLabel("Timeline")
    title.setFont(theme.font("body_small"))
    title.setStyleSheet(
        f"color: {colors.text_primary}; background: transparent;"
    )
    header_row.addWidget(title)
    header_row.addStretch(1)
    col.addLayout(header_row)

    # Timeline toolbar.
    tool_row = QHBoxLayout()
    tool_row.setSpacing(tokens.spacing.xs)
    for glyph in ("↶", "↷", "✂", "\U0001f5d1", "⤢",
                  "⭕", "⤓"):
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
    ruler_row.setContentsMargins(146, 0, tokens.spacing.sm, 0)
    ruler_row.setSpacing(0)
    ticks = (
        "00:00:00.00", "00:00:05.00", "00:00:10.00", "00:00:15.00",
        "00:00:20.00", "00:00:25.00", "00:00:30.00", "00:00:35.00",
        "00:00:40.00",
    )
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

    # --- Video tracks (top to bottom: V3, V2, V1) - empty until media loaded ---
    lanes.addLayout(_empty_video_lane(theme, "V3", "Video 3"))
    lanes.addLayout(_empty_video_lane(theme, "V2", "Video 2"))
    lanes.addLayout(_empty_video_lane(theme, "V1", "Video 1"))

    # --- Audio tracks (A1-A4) - empty until media loaded ---
    lanes.addLayout(_empty_video_lane(theme, "A1", "Music"))
    lanes.addLayout(_empty_video_lane(theme, "A2", "SFX"))
    lanes.addLayout(_empty_video_lane(theme, "A3", "Voice"))
    lanes.addLayout(_empty_video_lane(theme, "A4", "Subtitles"))

    col.addWidget(tracks, 1)
    return panel


def _lane_row(
    theme: ThemeManager,
    badge: str,
    name: str,
    *,
    show_ms: bool = False,
    badge_color: Optional[str] = None,
) -> Tuple[QHBoxLayout, QHBoxLayout]:
    """A lane layout: header + a content strip; returns (row, content)."""
    tokens = theme.tokens
    colors = tokens.colors
    row = QHBoxLayout()
    row.setSpacing(tokens.spacing.xs)
    row.addWidget(_track_header(
        theme, badge, name, show_ms=show_ms, badge_color=badge_color,
    ))
    strip = _styled(QFrame())
    strip.setObjectName("StudioLane")
    strip.setMinimumHeight(38)
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


def _empty_video_lane(
    theme: ThemeManager, badge: str, name: str,
) -> QHBoxLayout:
    """An empty video track (V2/V3) with no clips."""
    row, content = _lane_row(theme, badge, name)
    content.addStretch(1)
    return row


def _video_lane_v1(theme: ThemeManager) -> QHBoxLayout:
    """V1 video lane with a single gameplay clip spanning most of the timeline."""
    tokens = theme.tokens
    colors = tokens.colors
    row, content = _lane_row(theme, "V1", "Video 1")
    # Clip block: "gameplay.mp4 [V]" spanning the track
    clip = _clip_block(
        theme, "gameplay.mp4 [V]",
        stretch_body=_VideoThumb(theme, seed=0), height=44,
    )
    content.addWidget(clip, 8)
    content.addStretch(1)
    return row


def _audio_lane(
    theme: ThemeManager,
    badge: str,
    name: str,
    *,
    show_ms: bool = False,
    label: str,
    color: str,
    seed: int,
) -> QHBoxLayout:
    tokens = theme.tokens
    colors = tokens.colors
    row, content = _lane_row(theme, badge, name, show_ms=show_ms)
    block = _styled(QFrame())
    block.setObjectName("StudioAudioClip")
    block.setMinimumHeight(34)
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


def _subtitle_lane(theme: ThemeManager) -> QHBoxLayout:
    """A4 Subtitles lane with subtitle chips."""
    tokens = theme.tokens
    colors = tokens.colors
    row, content = _lane_row(theme, "A4", "Subtitles", show_ms=True)
    subtitles = (
        "Welcome back to the video...",
        "Today we are playing...",
        "This fight is insane!",
        "Double kill!",
        "That was close...",
        "Let's go!",
        "GG!",
        "On to the next one!",
    )
    for text in subtitles:
        chip = _timeline_chip(theme, text, kind="subtitle")
        content.addWidget(chip)
    content.addStretch(1)
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
    key.setFixedWidth(100)
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

    # Properties header (above tabs, matching target screenshot)
    props_header = _styled(QFrame())
    props_header.setObjectName("PropsHeader")
    props_header.setStyleSheet(f"#PropsHeader {{ background: {colors.surface}; }}")
    ph_row = QHBoxLayout(props_header)
    ph_row.setContentsMargins(tokens.spacing.md, tokens.spacing.sm,
                              tokens.spacing.md, tokens.spacing.sm)
    props_title = QLabel("Properties")
    props_title.setFont(theme.font("h3"))
    props_title.setStyleSheet(f"color: {colors.text_primary}; background: transparent;")
    ph_row.addWidget(props_title)
    ph_row.addStretch(1)
    outer.addWidget(props_header)

    # Tab bar (Edit, Audio, Effects, Graphics, Captions, Libraries)
    tabs_bar = _styled(QFrame())
    tabs_bar.setObjectName("StudioTabsBar")
    tabs_bar.setStyleSheet(
        f"#StudioTabsBar {{ background: {colors.surface}; "
        f"border-bottom: 1px solid {colors.border}; }}"
    )
    tabs_row = QHBoxLayout(tabs_bar)
    tabs_row.setContentsMargins(tokens.spacing.xs, 0, tokens.spacing.xs, 0)
    tabs_row.setSpacing(0)

    for tab_name, is_active in (
        ("Edit", False), ("Audio", False), ("Effects", True),
        ("Graphics", False), ("Captions", False), ("Libraries", False),
    ):
        tab = QLabel(tab_name)
        tab.setFont(theme.font("caption"))
        tab.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tab.setStyleSheet(
            f"QLabel {{ color: {colors.accent_cyan if is_active else colors.text_secondary}; "
            f"background: {colors.surface_elevated if is_active else 'transparent'}; "
            f"padding: 6px 6px; "
            f"border-bottom: {'2px solid ' + colors.accent_cyan if is_active else 'none'}; }} "
            f"QLabel:hover {{ color: {colors.text_primary}; }}"
        )
        tabs_row.addWidget(tab)
    outer.addWidget(tabs_bar)

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

    # Video Effects section
    effects_card = _right_card(theme)
    effects_col = effects_card.layout()

    effects_head = QHBoxLayout()
    effects_head.addWidget(_caption(theme, "Video Effects"))
    effects_head.addStretch(1)
    add_effect = QLabel("+ Add Effect")
    add_effect.setFont(theme.font("caption"))
    add_effect.setStyleSheet(
        f"color: {colors.accent_cyan}; background: transparent; "
        f"padding: 4px 8px; border-radius: 4px;"
    )
    effects_head.addWidget(add_effect)
    effects_col.addLayout(effects_head)

    # Empty state: no clip selected
    effects_col.addWidget(_empty_state(
        theme, "✨", "No clip selected",
        "Select a clip to manage effects",
    ))

    col.addWidget(effects_card)

    # Effect Controls section
    controls_card = _right_card(theme)
    controls_col = controls_card.layout()

    controls_head = QHBoxLayout()
    controls_head.addWidget(_caption(theme, "Effect Controls"))
    controls_head.addStretch(1)
    controls_col.addLayout(controls_head)

    # Empty state: no effect selected
    controls_col.addWidget(_empty_state(
        theme, "🎛️", "No effect selected",
        "Select an effect to adjust parameters",
    ))

    col.addWidget(controls_card)

    # AI Analyze Logs section
    logs_card = _right_card(theme)
    logs_card.setObjectName("AILogsCard")
    logs_col = logs_card.layout()

    logs_head = QHBoxLayout()
    logs_head.addWidget(_caption(theme, "AI Analyze Logs"))
    logs_head.addStretch(1)
    clear_btn = QLabel("Clear")
    clear_btn.setFont(theme.font("caption"))
    clear_btn.setStyleSheet(
        f"color: {colors.text_secondary}; background: transparent; "
        f"padding: 2px 6px;"
    )
    logs_head.addWidget(clear_btn)
    logs_col.addLayout(logs_head)

    # Empty state: no logs yet
    logs_empty = _empty_state(
        theme, "📋", "No logs yet",
        "Run an AI task to see results",
    )
    logs_empty.setObjectName("AILogsEmpty")
    logs_col.addWidget(logs_empty)

    col.addWidget(logs_card)

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

    # Left: Status text
    row.addWidget(status_label("Ready", colors.text_muted))
    row.addStretch(1)
    return bar


# --------------------------------------------------------------------------- #
# Screen assembly
# --------------------------------------------------------------------------- #
class StudioScreen(QWidget):
    """Full studio screen with navigation support for Dashboard and Editor views.

    Manages page switching between Dashboard and Editor (preview + timeline).
    The sidebar navigation controls which view is displayed.
    """

    def __init__(
        self,
        theme: ThemeManager,
        *,
        media_source=None,
        controller=None,
        parent=None,
    ) -> None:
        """Initialize studio screen with page switching support.

        Args:
            theme: Theme manager for styling
            media_source: Optional preview media source
            controller: Optional WorkflowController for backend access
            parent: Parent widget
        """
        super().__init__(parent)
        self._theme = theme
        self._controller = controller

        # Playback engine
        from gui.integration.playback_engine import PlaybackEngine
        self._playback_engine = PlaybackEngine(controller=controller)

        # Media source for path resolution
        self._media_source = media_source
        if self._media_source is None and controller is not None:
            try:
                from gui.integration.preview_media import PreviewMediaSource
                self._media_source = PreviewMediaSource()
            except Exception:
                self._media_source = None
        self._current_page = 0  # 0 = Dashboard, 1 = Editor

        # Setup UI
        self._setup_ui()

        # Wire navigation
        self._wire_navigation()

        # Wire menu bar and toolbar
        self._wire_menu_and_toolbar()

    def _setup_ui(self) -> None:
        """Setup the complete studio screen UI.

        New layout (DaVinci Resolve / Premiere Pro style):
        ┌──────────────────────────────────────────────────────────┐
        │ Menu Bar                                                 │
        │ Toolbar                                                  │
        │ ┌──────┬──────────┬──────────────┬─────────────────┐    │
        │ │ Side │ Workspace│   Preview    │  Properties     │    │
        │ │ bar  │  Panel   │   Stage      │  Right Panel    │    │
        │ │232px │ (320px)  │  (flex)      │  (340px)        │    │
        │ └──────┴──────────┴──────────────┴─────────────────┘    │
        │ ┌──────────────────────────────────────────────────┐    │
        │ │              Timeline (full width)                │    │
        │ └──────────────────────────────────────────────────┘    │
        │ Status Bar                                               │
        └──────────────────────────────────────────────────────────┘
        """
        tokens = self._theme.tokens
        colors = tokens.colors

        self.setObjectName("StudioScreen")
        self.setWindowTitle(_WINDOW_TITLE)
        self.setStyleSheet(
            f"#StudioScreen {{ background: {colors.background_deep}; }}"
        )

        # Main layout
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Menu bar
        root.addWidget(_build_menu_bar(self._theme))

        # Upper area: Sidebar | Project Overview | Preview | Properties
        upper = QHBoxLayout()
        upper.setContentsMargins(0, 0, 0, 0)
        upper.setSpacing(0)

        # 1. Left Sidebar (232px fixed)
        self._sidebar = _build_sidebar(self._theme)
        upper.addWidget(self._sidebar)

        # 2. Workspace Panel (350px, QStackedWidget)
        self._workspace_stack = self._build_workspace_panel()
        upper.addWidget(self._workspace_stack)

        # 3. Center: Preview + Transport (takes remaining space)
        center_col = _styled(QWidget())
        center_col.setObjectName("StudioCenter")
        center_col.setStyleSheet(
            f"#StudioCenter {{ background: {colors.background_base}; }}"
        )
        center_layout = QVBoxLayout(center_col)
        center_layout.setContentsMargins(
            tokens.spacing.md, tokens.spacing.sm,
            tokens.spacing.md, tokens.spacing.sm
        )
        center_layout.setSpacing(tokens.spacing.sm)

        # Preview header with program info
        preview_header = self._build_preview_header()
        center_layout.addWidget(preview_header)

        # Preview stage
        self._stage = _build_preview(self._theme)
        center_layout.addWidget(self._stage, 1)

        # Transport controls
        self._transport = _build_transport(self._theme)
        center_layout.addWidget(self._transport)

        upper.addWidget(center_col, 1)  # Stretch factor 1 = take remaining

        # 4. Right Panel (356px fixed)
        self._right_panel = _build_right_panel(self._theme)
        upper.addWidget(self._right_panel)

        root.addLayout(upper, 1)  # Upper area gets vertical stretch

        # 5. Timeline (custom multi-track, fixed height, below upper area)
        self._timeline = _build_timeline(self._theme)
        self._timeline.setFixedHeight(300)
        root.addWidget(self._timeline, 0)  # stretch=0: don't expand

        # 6. Status bar
        self._status_bar = _build_status_bar(self._theme)
        root.addWidget(self._status_bar)

        # Start with Dashboard workspace page
        self._show_workspace_page(0)

        # Wire playback engine to preview, transport, and timeline
        self._wire_playback()

        # If media was imported during workspace build, load it now
        if hasattr(self, '_pending_media_path') and self._pending_media_path:
            self._load_pending_media()

    def _wire_playback(self) -> None:
        """Wire the playback engine to preview stage, transport bar, and timeline."""
        engine = self._playback_engine
        tokens = self._theme.tokens
        colors = tokens.colors

        # --- Preview stage: display decoded frames ---
        # The label fills the ENTIRE stage as an overlay (not in layout)
        self._preview_frame_label = QLabel(self._stage)
        self._preview_frame_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_frame_label.setStyleSheet("background: transparent;")
        # Resize with the stage
        self._preview_frame_label.setGeometry(self._stage.rect())
        self._preview_frame_label.lower()  # Behind overlay widgets()

        def _on_frame_ready(bgr_frame):
            """Convert BGR numpy frame to QPixmap and display."""
            # Hide empty state labels on first frame
            if not getattr(self, '_empty_state_hidden', False):
                for name in ("PreviewEmptyIcon", "PreviewEmptyTitle", "PreviewEmptyDesc"):
                    label = self._stage.findChild(QLabel, name)
                    if label:
                        label.setVisible(False)
                self._empty_state_hidden = True

            h, w, ch = bgr_frame.shape
            bytes_per_line = ch * w
            qimg = QImage(bgr_frame.data, w, h, bytes_per_line, QImage.Format.Format_BGR888).copy()
            pixmap = QPixmap.fromImage(qimg)
            scaled = pixmap.scaled(
                self._preview_frame_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._preview_frame_label.setPixmap(scaled)

        engine.frame_ready.connect(_on_frame_ready)

        # Handle pending pixmap when stage is first sized
        self._pending_pixmap = None
        original_resize = self._stage.resizeEvent
        def _on_stage_resize(event):
            original_resize(event)
            # Keep preview label sized to stage
            if self._preview_frame_label is not None:
                self._preview_frame_label.setGeometry(self._stage.rect())
            # Display pending pixmap if any
            if self._pending_pixmap is not None and self._preview_frame_label is not None:
                label_size = self._preview_frame_label.size()
                if label_size.width() > 10 and label_size.height() > 10:
                    scaled = self._pending_pixmap.scaled(
                        label_size,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    self._preview_frame_label.setPixmap(scaled)
                    self._pending_pixmap = None
        self._stage.resizeEvent = _on_stage_resize

        # --- Timecode display ---
        timecode_label = self._transport.findChild(QLabel, "StudioTimecode")
        if timecode_label is not None:
            engine.timecode_changed.connect(timecode_label.setText)

        # --- Set engine's timeline reference for sync ---
        engine.set_timeline(self._timeline)

        # --- Transport controls: connect buttons DIRECTLY to engine ---
        # Engine is the sole clock. Timeline is display-only.
        play_btn = self._transport.findChild(QLabel, "StudioTransportPlay")
        pause_btn = self._transport.findChild(QLabel, "StudioTransportPause")

        if play_btn is not None:
            play_btn.mouseReleaseEvent = lambda _e: engine.play()
        if pause_btn is not None:
            pause_btn.mouseReleaseEvent = lambda _e: engine.pause()

        # Frame stepping buttons - use engine methods for proper state update
        prev_frame = self._transport.findChild(QLabel, "StudioTransportPrevFrame")
        next_frame = self._transport.findChild(QLabel, "StudioTransportNextFrame")
        if prev_frame is not None:
            prev_frame.mouseReleaseEvent = lambda _e: engine.step_backward()
        if next_frame is not None:
            next_frame.mouseReleaseEvent = lambda _e: engine.step_forward()

        # Rewind - seek -5 seconds
        rewind_btn = self._transport.findChild(QLabel, "StudioTransportRewind")
        if rewind_btn is not None:
            rewind_btn.mouseReleaseEvent = lambda _e: engine.seek(max(0.0, engine.playhead() - 5.0))

        # Speed chip - cycle through playback rates
        speed_chip = self._transport.findChild(QFrame, "SpeedChip")
        speed_label_widget = speed_chip.findChild(QLabel) if speed_chip else None
        if speed_chip is not None and speed_label_widget is not None:
            _speeds = [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 4.0]
            _speed_idx = [3]  # mutable index, starts at 1.0x

            def _cycle_speed(_e):
                _speed_idx[0] = (_speed_idx[0] + 1) % len(_speeds)
                rate = _speeds[_speed_idx[0]]
                engine.set_playback_rate(rate)
                speed_label_widget.setText(f"{rate:.1f}x" if rate != int(rate) else f"{int(rate)}.0x")

            speed_chip.mouseReleaseEvent = _cycle_speed
            speed_chip.setCursor(Qt.CursorShape.PointingHandCursor)

        # --- Engine signals -> UI updates ---
        def _on_playback_state(state):
            """Update button highlights based on playback state."""
            cyan = colors.accent_cyan
            secondary = colors.text_secondary
            if play_btn is not None:
                play_btn.setStyleSheet(
                    f"QLabel {{ color: {cyan if state == 'playing' else secondary}; "
                    f"background: transparent; padding: 2px 6px; }} "
                    f"QLabel:hover {{ color: {colors.text_primary}; }}"
                )
            if pause_btn is not None:
                pause_btn.setStyleSheet(
                    f"QLabel {{ color: {cyan if state == 'paused' else secondary}; "
                    f"background: transparent; padding: 2px 6px; }} "
                    f"QLabel:hover {{ color: {colors.text_primary}; }}"
                )
            # Update status bar
            self._update_status_bar(state)

        engine.playback_state_changed.connect(_on_playback_state)

        # --- Progress bar updates from engine ---
        progress_bar = self._transport.findChild(QProgressBar, "StudioProgress")
        duration_label = self._transport.findChild(QLabel, "StudioDuration")

        def _on_playhead_update(seconds):
            """Update progress bar and duration display."""
            dur = engine.duration()
            if dur > 0 and progress_bar is not None:
                progress_bar.setValue(int((seconds / dur) * 100))
            if duration_label is not None:
                # Format duration as timecode
                total_secs = int(dur)
                h = total_secs // 3600
                m = (total_secs % 3600) // 60
                s = total_secs % 60
                duration_label.setText(f"{h:02d}:{m:02d}:{s:02d}:00")

        engine.playhead_updated.connect(_on_playhead_update)

    def _update_status_bar(self, state: str) -> None:
        """Update the status bar with current playback state."""
        # Find and update status bar labels
        status_labels = self._status_bar.findChildren(QLabel)
        for label in status_labels:
            # Update the first label (status text)
            if label.text() in ("Ready", "Playing", "Paused", "Stopped"):
                state_text = state.title() if state != "stopped" else "Ready"
                label.setText(state_text)
                break

    def _wire_navigation(self) -> None:
        """Wire sidebar navigation to page switching."""
        if hasattr(self._sidebar, 'navigation_changed'):
            self._sidebar.navigation_changed.connect(self._on_navigation_changed)
        else:
            # Fallback: find nav items by object name and connect click events
            self._nav_items = self._sidebar.findChildren(QFrame, "StudioNavItem")
            self._current_nav = 0
            self._update_nav_styles()

            for index, item in enumerate(self._nav_items):
                item.setCursor(Qt.CursorShape.PointingHandCursor)
                item.mouseReleaseEvent = lambda _event, i=index: self._on_nav_clicked(i)

    def _on_navigation_changed(self, index: int) -> None:
        """Handle navigation change from sidebar."""
        self._show_workspace_page(index)

    def _wire_menu_and_toolbar(self) -> None:
        """Wire menu bar export button and toolbar AI buttons to backend."""
        # Wire Export button in menu bar
        export_btn = self.findChild(QFrame, "StudioMenuExport")
        if export_btn:
            export_btn.mouseReleaseEvent = lambda _e: self._on_export()

        # Wire toolbar buttons
        for obj_name, handler in [
            ("ToolbarAIAnalyze", lambda: self._run_phase_if_loaded("analysis")),
            ("ToolbarAutoCut", lambda: self._run_phase_if_loaded("highlight")),
            ("ToolbarBeatSync", lambda: self._run_phase_if_loaded("audio")),
            ("ToolbarAIRender", lambda: self._run_phase_if_loaded("render")),
        ]:
            btn = self.findChild(QFrame, obj_name)
            if btn:
                btn.mouseReleaseEvent = lambda _e, h=handler: h()

    def _on_export(self) -> None:
        """Export video using the render phase."""
        if self._controller is None:
            return
        try:
            self._controller.run_phase("render")
        except Exception:
            pass

    def _run_phase_if_loaded(self, phase_id: str) -> None:
        """Run an AI phase if a video is loaded."""
        if self._controller is None:
            return
        try:
            self._controller.run_phase(phase_id)
        except Exception:
            pass

    def _on_dashboard_project_clicked(self, name: str) -> None:
        """Handle recent project click from dashboard - switch to Projects page."""
        self._show_workspace_page(1)  # Projects page

    def _on_dashboard_export_clicked(self, filename: str) -> None:
        """Handle recent export click from dashboard - switch to Export page."""
        self._show_workspace_page(11)  # Export page

    def _refresh_right_panel_logs(self) -> None:
        """Refresh the right panel AI logs section with real data from controller."""
        if self._controller is None:
            return

        try:
            logs = self._controller.logs()
            if not logs:
                return

            # Find the logs card
            logs_card = self.findChild(QFrame, "AILogsCard")
            if logs_card is None:
                return

            logs_col = logs_card.layout()

            # Remove empty state if present
            empty = logs_card.findChild(QWidget, "AILogsEmpty")
            if empty:
                logs_col.removeWidget(empty)
                empty.deleteLater()

            # Add real log entries (last 6 most recent)
            for record in logs[-6:]:
                log_row = QHBoxLayout()
                log_row.setSpacing(8)

                # Timestamp
                import datetime
                ts = datetime.datetime.fromtimestamp(record.timestamp).strftime("%H:%M:%S")
                time_label = QLabel(ts)
                time_label.setFont(self._theme.font("caption"))
                time_label.setStyleSheet(f"color: {self._theme.tokens.colors.text_muted}; background: transparent;")
                log_row.addWidget(time_label)

                # Status dot
                dot = QLabel("●")
                dot.setFont(self._theme.font("caption"))
                dot_color = self._theme.tokens.colors.success if record.level.value <= 20 else self._theme.tokens.colors.error
                dot.setStyleSheet(f"color: {dot_color}; background: transparent;")
                log_row.addWidget(dot)

                # Log text
                text_col = QVBoxLayout()
                text_col.setSpacing(0)
                title = QLabel(record.phase or record.module or "System")
                title.setFont(self._theme.font("body_small"))
                title.setStyleSheet(f"color: {self._theme.tokens.colors.text_primary}; background: transparent;")
                text_col.addWidget(title)
                detail = QLabel(record.message[:60])
                detail.setFont(self._theme.font("caption"))
                detail.setStyleSheet(f"color: {self._theme.tokens.colors.text_muted}; background: transparent;")
                text_col.addWidget(detail)
                log_row.addLayout(text_col, 1)

                # Status
                status = QLabel("Completed" if record.level.value <= 20 else "Error")
                status.setFont(self._theme.font("caption"))
                status.setStyleSheet(f"color: {dot_color}; background: transparent;")
                log_row.addWidget(status)

                logs_col.addLayout(log_row)

        except Exception:
            pass

    def _on_nav_clicked(self, index: int) -> None:
        """Handle nav item click (fallback for non-signal sidebar)."""
        if index == self._current_nav:
            return

        self._current_nav = index
        self._update_nav_styles()

        # Switch workspace page
        self._show_workspace_page(index)

    def _update_nav_styles(self) -> None:
        """Update visual state of nav items based on selection."""
        tokens = self._theme.tokens
        colors = tokens.colors

        for index, item in enumerate(self._nav_items):
            is_active = (index == self._current_nav)

            if is_active:
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

            # Update text and icon colors
            for label in item.findChildren(QLabel):
                text = label.text()
                is_icon = text in ("\U0001f3e0", "\U0001f4c1", "\U0001f39e", "\U0001f9e9",
                                   "\U0001f4fd", "✨", "\U0001f500", "\U0001f3b5",
                                   "\U0001f4dd", "\U0001f4d0", "\U0001f916", "⬆", "⚙")
                if is_active:
                    if is_icon:
                        label.setStyleSheet(f"color: {colors.accent_cyan}; background: transparent;")
                    else:
                        label.setStyleSheet(f"color: {colors.text_primary}; background: transparent;")
                else:
                    if is_icon:
                        label.setStyleSheet(f"color: {colors.text_muted}; background: transparent;")
                    else:
                        label.setStyleSheet(f"color: {colors.text_secondary}; background: transparent;")

    def _build_workspace_panel(self) -> QWidget:
        """Build the QStackedWidget workspace panel with pages for each nav item.

        Returns:
            QStackedWidget with workspace pages.
        """
        tokens = self._theme.tokens
        colors = tokens.colors

        # Panel container with fixed width (Project Overview panel)
        panel = _styled(QFrame())
        panel.setObjectName("WorkspacePanel")
        panel.setFixedWidth(320)
        panel.setStyleSheet(
            f"#WorkspacePanel {{ background: {colors.surface}; "
            f"border-right: 1px solid {colors.border}; }}"
        )
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(0)

        # Stacked widget for workspace pages
        self._workspace_stack = QStackedWidget()
        self._workspace_stack.setObjectName("WorkspaceStack")
        self._workspace_stack.setStyleSheet(
            f"#WorkspaceStack {{ background: {colors.surface}; }}"
        )

        # Page 0: Dashboard
        from gui.widgets.dashboard_widget import DashboardWidget
        self._dashboard = DashboardWidget(self._theme, controller=self._controller)
        self._dashboard.recent_project_activated.connect(self._on_dashboard_project_clicked)
        self._dashboard.recent_export_activated.connect(self._on_dashboard_export_clicked)
        self._workspace_stack.addWidget(self._dashboard)

        # Page 1: Projects
        self._workspace_stack.addWidget(self._build_projects_page())

        # Page 2: Media (reuse existing MediaBrowser with backend wiring)
        self._workspace_stack.addWidget(self._build_media_page())

        # Page 3: Assets
        self._workspace_stack.addWidget(self._build_assets_page())

        # Page 4: Timeline (placeholder - timeline is at bottom)
        self._workspace_stack.addWidget(self._build_generic_page("Timeline View"))

        # Page 5: Effects
        self._workspace_stack.addWidget(self._build_effects_page())

        # Page 6: Transitions
        self._workspace_stack.addWidget(self._build_transitions_page())

        # Page 7: Audio
        self._workspace_stack.addWidget(self._build_audio_page())

        # Page 8: Captions
        self._workspace_stack.addWidget(self._build_captions_page())

        # Page 9: Templates
        self._workspace_stack.addWidget(self._build_generic_page("Templates"))

        # Page 10: AI Studio
        self._workspace_stack.addWidget(self._build_ai_studio_page())

        # Page 11: Export
        self._workspace_stack.addWidget(self._build_export_page())

        # Page 12: Settings
        self._workspace_stack.addWidget(self._build_settings_page())

        panel_layout.addWidget(self._workspace_stack)
        self._workspace_pages = self._workspace_stack  # alias to QStackedWidget
        return panel

    def _build_projects_page(self) -> QWidget:
        """Build the Projects workspace page with real backend data."""
        tokens = self._theme.tokens
        colors = tokens.colors

        page = _styled(QWidget())
        page.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(
            tokens.spacing.md, tokens.spacing.md,
            tokens.spacing.md, tokens.spacing.md
        )
        layout.setSpacing(tokens.spacing.sm)

        # Header
        layout.addWidget(_caption(self._theme, "Projects", accent=True))

        # New Project button
        from gui.widgets.neon_button import NeonButton
        new_btn = NeonButton(self._theme, "+ New Project", variant="primary", accent="cyan")
        new_btn.clicked.connect(self._on_new_project)
        layout.addWidget(new_btn)

        # Search
        from gui.widgets.text_field import TextField
        search_field = TextField(self._theme, placeholder="Search projects...")
        layout.addWidget(search_field)

        # Project list (populated from recent.json)
        self._project_list_layout = QVBoxLayout()
        self._project_list_layout.setSpacing(tokens.spacing.sm)
        layout.addLayout(self._project_list_layout)

        self._refresh_projects_list()

        layout.addStretch(1)
        return page

    def _refresh_projects_list(self) -> None:
        """Populate the project list from recent.json."""
        import json
        from pathlib import Path

        # Clear existing items
        while self._project_list_layout.count():
            item = self._project_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        tokens = self._theme.tokens
        colors = tokens.colors

        projects_dir = Path("projects")
        recent_file = projects_dir / "recent.json"
        projects = []

        if recent_file.exists():
            try:
                with open(recent_file) as f:
                    data = json.load(f)
                if isinstance(data, list):
                    for entry in data[:10]:  # Max 10 recent
                        if isinstance(entry, dict):
                            name = entry.get("name", Path(entry.get("path", "")).stem)
                            path = entry.get("path", "")
                            age = entry.get("modified", "")
                            projects.append((name, path, age))
                        elif isinstance(entry, str):
                            projects.append((Path(entry).stem, entry, ""))
            except Exception:
                pass

        if not projects:
            # Show placeholder
            empty = QLabel("No projects yet. Click + New Project to start.")
            empty.setFont(self._theme.font("body_small"))
            empty.setStyleSheet(f"color: {colors.text_muted}; background: transparent;")
            empty.setWordWrap(True)
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._project_list_layout.addWidget(empty)
            return

        for name, path, age in projects:
            card = _styled(QFrame())
            card.setObjectName("ProjectCard")
            card.setCursor(Qt.CursorShape.PointingHandCursor)
            card.setStyleSheet(
                f"#ProjectCard {{ background: {colors.surface_elevated}; "
                f"border: 1px solid {colors.border}; "
                f"border-radius: {tokens.radius.sm}px; }} "
                f"#ProjectCard:hover {{ border: 1px solid {colors.accent_cyan}; }}"
            )
            card_row = QHBoxLayout(card)
            card_row.setContentsMargins(tokens.spacing.sm, tokens.spacing.sm,
                                        tokens.spacing.sm, tokens.spacing.sm)
            card_row.setSpacing(tokens.spacing.sm)

            thumb = _styled(QFrame())
            thumb.setFixedSize(48, 32)
            thumb.setStyleSheet(
                f"background: qlineargradient(x1:0, y1:0, x2:1, y2:1, "
                f"stop:0 {colors.accent_purple}, stop:1 {colors.accent_blue}); "
                f"border-radius: 4px;"
            )
            card_row.addWidget(thumb)

            text_col = QVBoxLayout()
            text_col.setSpacing(0)
            name_label = QLabel(name)
            name_label.setFont(self._theme.font("body_small"))
            name_label.setStyleSheet(f"color: {colors.text_primary}; background: transparent;")
            text_col.addWidget(name_label)
            info_text = age if age else "Unknown"
            info = QLabel(info_text)
            info.setFont(self._theme.font("caption"))
            info.setStyleSheet(f"color: {colors.text_muted}; background: transparent;")
            text_col.addWidget(info)
            card_row.addLayout(text_col, 1)

            # Double-click to open project
            card.mouseDoubleClickEvent = lambda _e, p=path: self._open_project(p)

            self._project_list_layout.addWidget(card)

    def _on_new_project(self) -> None:
        """Create a new project."""
        from PySide6.QtWidgets import QFileDialog, QLineEdit, QDialog, QDialogButtonBox

        dialog = QDialog()
        dialog.setWindowTitle("New Project")
        dialog.setMinimumWidth(400)
        dialog.setStyleSheet(f"background: {self._theme.tokens.colors.surface};")

        dlg_layout = QVBoxLayout(dialog)
        dlg_layout.addWidget(QLabel("Project Name:"))

        name_input = QLineEdit()
        name_input.setPlaceholderText("My Project")
        name_input.setStyleSheet(
            f"background: {self._theme.tokens.colors.surface_elevated}; "
            f"color: {self._theme.tokens.colors.text_primary}; "
            f"border: 1px solid {self._theme.tokens.colors.border}; "
            f"border-radius: 4px; padding: 6px;"
        )
        dlg_layout.addWidget(name_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        dlg_layout.addWidget(buttons)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            name = name_input.text().strip() or "Untitled Project"
            projects_dir = Path("projects")
            projects_dir.mkdir(exist_ok=True)
            project_path = projects_dir / f"{name}.ivproj.json"

            # Save empty project
            import json
            data = {"version": 1, "name": name, "video_path": None, "settings": {}, "timeline": None}
            with open(project_path, "w") as f:
                json.dump(data, f, indent=2)

            # Update recent.json
            recent_file = projects_dir / "recent.json"
            recent = []
            if recent_file.exists():
                try:
                    with open(recent_file) as f:
                        recent = json.load(f)
                except Exception:
                    recent = []
            recent.insert(0, {"name": name, "path": str(project_path), "modified": ""})
            with open(recent_file, "w") as f:
                json.dump(recent, f, indent=2)

            self._refresh_projects_list()

    def _open_project(self, path: str) -> None:
        """Open an existing project."""
        if self._controller is None:
            return
        try:
            import json
            with open(path) as f:
                data = json.load(f)

            video_path = data.get("video_path")
            if video_path:
                self._controller.select_video(video_path)

            settings = data.get("settings", {})
            for key, value in settings.items():
                self._controller.set_setting(key, value)

            self._playback_engine.load_media(
                video_path, 0.0, 30.0
            ) if video_path else None

        except Exception as exc:
            pass

    def _build_media_page(self) -> QWidget:
        """Build the Media workspace page with real backend wiring."""
        tokens = self._theme.tokens
        colors = tokens.colors

        page = _styled(QWidget())
        page.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(
            tokens.spacing.sm, tokens.spacing.sm,
            tokens.spacing.sm, tokens.spacing.sm
        )
        layout.setSpacing(tokens.spacing.sm)

        # Import button
        from gui.widgets.neon_button import NeonButton
        import_btn = NeonButton(self._theme, "⬇  Import Media", variant="primary", accent="cyan")
        import_btn.clicked.connect(self._on_import_media)
        layout.addWidget(import_btn)

        # MediaBrowser with real items
        from gui.widgets.media_browser import MediaBrowser
        items = []
        if self._media_source is not None:
            try:
                items = self._media_source.list_items() or []
            except Exception:
                items = []
        if not items:
            items = ["gameplay.mp4", "highlight_reel.mp4", "clip_01.mp4"]
        self._media_browser = MediaBrowser(self._theme, items=items)
        self._media_browser.selection_changed.connect(self._on_media_selected)
        self._media_browser.import_requested.connect(self._on_import_media)
        layout.addWidget(self._media_browser, 1)

        # Metadata display
        self._media_meta_frame = _styled(QFrame())
        self._media_meta_frame.setObjectName("MediaMeta")
        self._media_meta_frame.setStyleSheet(
            f"#MediaMeta {{ background: {colors.surface_elevated}; "
            f"border: 1px solid {colors.border}; "
            f"border-radius: {tokens.radius.sm}px; }}"
        )
        meta_layout = QVBoxLayout(self._media_meta_frame)
        meta_layout.setContentsMargins(tokens.spacing.sm, tokens.spacing.sm,
                                       tokens.spacing.sm, tokens.spacing.sm)
        meta_layout.setSpacing(tokens.spacing.xs)

        self._media_meta_name = QLabel("No selection")
        self._media_meta_name.setFont(self._theme.font("body_small"))
        self._media_meta_name.setStyleSheet(f"color: {colors.text_primary}; background: transparent;")
        meta_layout.addWidget(self._media_meta_name)

        self._media_meta_info = QLabel("")
        self._media_meta_info.setFont(self._theme.font("caption"))
        self._media_meta_info.setStyleSheet(f"color: {colors.text_muted}; background: transparent;")
        self._media_meta_info.setWordWrap(True)
        meta_layout.addWidget(self._media_meta_info)

        layout.addWidget(self._media_meta_frame)

        # Enable drag & drop on the page
        page.setAcceptDrops(True)
        page.dragEnterEvent = lambda e: self._media_drag_enter(e)
        page.dropEvent = lambda e: self._media_drop(e)

        return page

    def _on_import_media(self) -> None:
        """Open file dialog to import media files."""
        from PySide6.QtWidgets import QFileDialog

        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Import Media",
            "",
            "Media Files (*.mp4 *.mov *.mkv *.avi *.webm *.m4v *.mp3 *.wav *.flac *.ogg *.jpg *.jpeg *.png *.bmp);;All Files (*)"
        )
        if files:
            self._add_media_files(files)

    def _add_media_files(self, paths: list) -> None:
        """Add imported media files to the browser."""
        if not hasattr(self, '_media_browser') or self._media_browser is None:
            return

        current_items = self._media_browser.items()
        new_items = []
        for path in paths:
            from pathlib import Path
            name = Path(path).name
            if name not in current_items:
                new_items.append(name)
                current_items.append(name)

        if new_items:
            self._media_browser.set_items(current_items)
            # Register with media source in BOTH _paths and _imported
            if self._media_source is not None:
                try:
                    for path in paths:
                        from pathlib import Path as P
                        p = P(path)
                        name = p.name
                        # Register in _paths (used by path_for)
                        if not hasattr(self._media_source, '_paths'):
                            self._media_source._paths = {}
                        self._media_source._paths[name] = p
                        # Also register in _imported for lookup
                        if not hasattr(self._media_source, '_imported'):
                            self._media_source._imported = {}
                        self._media_source._imported[name] = path
                except Exception:
                    pass
            # Auto-select the first imported item
            if new_items:
                idx = current_items.index(new_items[0])
                # Store pending path for when wiring is complete
                self._pending_media_path = paths[0] if paths else None
                # Try selecting now (works if signal is connected)
                try:
                    self._media_browser.select(idx)
                except Exception:
                    pass

    def _on_media_selected(self, index: int) -> None:
        """Handle media selection - update metadata, load into preview, show first frame."""
        if index < 0 or not hasattr(self, '_media_browser'):
            return

        name = self._media_browser.current_item()
        if name is None:
            return

        # Update metadata display
        self._media_meta_name.setText(name)

        # Resolve path
        path = None

        # First try: media source path_for
        if self._media_source is not None:
            try:
                path = self._media_source.path_for(name)
            except Exception:
                pass

        # Second try: imported paths map
        if path is None and self._media_source is not None:
            imported = getattr(self._media_source, '_imported', {})
            if name in imported:
                path = imported[name]

        # Third try: direct filesystem lookup in videos/
        if path is None:
            from pathlib import Path
            videos_dir = Path("videos")
            candidate = videos_dir / name
            if candidate.exists():
                path = str(candidate)

        # Fourth try: find anywhere on disk relative to cwd
        if path is None:
            from pathlib import Path
            candidate = Path(name)
            if candidate.exists():
                path = str(candidate.absolute())

        if path is None:
            self._media_meta_info.setText(f"Path not resolved for: {name}")
            return

        # Get metadata from backend
        duration = 0.0
        fps = 30.0
        if self._controller is not None:
            try:
                meta = self._controller.media_metadata(path)
                if meta:
                    w = getattr(meta, 'width', '?')
                    h = getattr(meta, 'height', '?')
                    fps = float(getattr(meta, 'fps', 30) or 30)
                    dur = float(getattr(meta, 'duration', 0) or 0)
                    duration = dur
                    codec = getattr(meta, 'codec', '?')
                    info = f"Resolution: {w}×{h}\nFPS: {fps}\nDuration: {dur:.1f}s\nCodec: {codec}\nPath: {path}"
                    self._media_meta_info.setText(info)
            except Exception as exc:
                self._media_meta_info.setText(f"Metadata error: {exc}")
        else:
            self._media_meta_info.setText(f"Path: {path}\nNo controller connected")

        # Load into playback engine
        self._playback_engine.load_media(path, duration, fps)

        # Update Timeline duration to match video
        if duration > 0:
            self._timeline.set_duration(duration)
            self._timeline.set_playhead(0.0)

        # Decode and display the first frame immediately
        self._show_first_frame(path)

    def _show_first_frame(self, path: str) -> None:
        """Decode and display the first frame of a video file."""
        if self._controller is None:
            return
        try:
            # Hide empty state labels
            if not getattr(self, '_empty_state_hidden', False):
                for name in ("PreviewEmptyIcon", "PreviewEmptyTitle", "PreviewEmptyDesc"):
                    label = self._stage.findChild(QLabel, name)
                    if label:
                        label.setVisible(False)
                self._empty_state_hidden = True

            import numpy as np

            bgr = self._controller.decode_frame(path, 0.0)
            if bgr is None:
                return

            h, w, ch = bgr.shape
            bytes_per_line = ch * w
            qimg = QImage(bgr.data, w, h, bytes_per_line, QImage.Format.Format_BGR888).copy()
            pixmap = QPixmap.fromImage(qimg)

            label = getattr(self, '_preview_frame_label', None)
            if label is not None:
                label_size = label.size()
                if label_size.width() > 10 and label_size.height() > 10:
                    scaled = pixmap.scaled(
                        label_size,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    label.setPixmap(scaled)
                else:
                    self._pending_pixmap = pixmap
        except Exception:
            pass

    def _load_pending_media(self) -> None:
        """Load media that was imported before wiring was complete."""
        path = getattr(self, '_pending_media_path', None)
        if path is None:
            return
        self._pending_media_path = None

        try:
            from pathlib import Path
            p = Path(path)
            name = p.name

            # Update metadata
            self._media_meta_name.setText(name)

            # Get metadata
            duration = 0.0
            fps = 30.0
            if self._controller is not None:
                meta = self._controller.media_metadata(path)
                if meta:
                    w = getattr(meta, 'width', '?')
                    h = getattr(meta, 'height', '?')
                    fps = float(getattr(meta, 'fps', 30) or 30)
                    dur = float(getattr(meta, 'duration', 0) or 0)
                    duration = dur
                    codec = getattr(meta, 'codec', '?')
                    info = f"Resolution: {w}×{h}\nFPS: {fps}\nDuration: {dur:.1f}s\nCodec: {codec}\nPath: {path}"
                    self._media_meta_info.setText(info)

            # Load into playback engine
            self._playback_engine.load_media(path, duration, fps)

            # Update Timeline duration
            if duration > 0:
                self._timeline.set_duration(duration)
                self._timeline.set_playhead(0.0)

            # Show first frame
            self._show_first_frame(path)

            # Select in media browser
            if hasattr(self, '_media_browser') and self._media_browser is not None:
                items = self._media_browser.items()
                if name in items:
                    self._media_browser.select(items.index(name))

        except Exception:
            pass

    def _media_drag_enter(self, event) -> None:
        """Handle drag enter for media import."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def _media_drop(self, event) -> None:
        """Handle file drop for media import."""
        from pathlib import Path
        urls = event.mimeData().urls()
        paths = [url.toLocalFile() for url in urls if url.isLocalFile()]
        if paths:
            self._add_media_files(paths)

    def _build_assets_page(self) -> QWidget:
        """Build the Assets workspace page - scans assets/ directory."""
        tokens = self._theme.tokens
        colors = tokens.colors

        page = _styled(QWidget())
        page.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(
            tokens.spacing.md, tokens.spacing.md,
            tokens.spacing.md, tokens.spacing.md
        )
        layout.setSpacing(tokens.spacing.sm)

        layout.addWidget(_caption(self._theme, "Assets", accent=True))

        from gui.widgets.text_field import TextField
        search = TextField(self._theme, placeholder="Search assets...")
        layout.addWidget(search)

        # Scan assets directory for real files
        from pathlib import Path
        assets_dir = Path("assets")
        categories = {
            "LUTs": [".cube", ".3dl", ".olut"],
            "Overlays": [".png", ".mov", ".webm"],
            "Presets": [".json", ".preset"],
            "Icons": [".svg", ".png", ".ico"],
            "Motion Assets": [".mogrt", ".json"],
        }
        for cat, exts in categories.items():
            count = 0
            if assets_dir.exists():
                for f in assets_dir.iterdir():
                    if f.suffix.lower() in exts:
                        count += 1

            btn = _styled(QFrame())
            btn.setObjectName("AssetCat")
            btn.setStyleSheet(
                f"#AssetCat {{ background: {colors.surface_elevated}; "
                f"border: 1px solid {colors.border}; "
                f"border-radius: {tokens.radius.sm}px; }}"
            )
            btn_row = QHBoxLayout(btn)
            btn_row.setContentsMargins(tokens.spacing.md, tokens.spacing.sm,
                                       tokens.spacing.md, tokens.spacing.sm)
            icon = QLabel("📁")
            icon.setFont(self._theme.font("body_small"))
            icon.setStyleSheet(f"color: {colors.accent_cyan}; background: transparent;")
            btn_row.addWidget(icon)
            label = QLabel(cat)
            label.setFont(self._theme.font("body_small"))
            label.setStyleSheet(f"color: {colors.text_primary}; background: transparent;")
            btn_row.addWidget(label, 1)
            count_label = QLabel(str(count))
            count_label.setFont(self._theme.font("caption"))
            count_label.setStyleSheet(f"color: {colors.text_muted}; background: transparent;")
            btn_row.addWidget(count_label)
            layout.addWidget(btn)

        layout.addStretch(1)
        return page

    def _build_effects_page(self) -> QWidget:
        """Build the Effects workspace page - empty until effects are available."""
        tokens = self._theme.tokens
        colors = tokens.colors

        page = _styled(QWidget())
        page.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(
            tokens.spacing.sm, tokens.spacing.sm,
            tokens.spacing.sm, tokens.spacing.sm
        )
        layout.setSpacing(tokens.spacing.sm)

        layout.addWidget(_caption(self._theme, "Effects Library", accent=True))

        # Empty state
        layout.addWidget(_empty_state(
            self._theme, "✨", "No effects available",
            "Effects will appear here when a clip is selected",
        ))

        layout.addStretch(1)
        return page

    def _toggle_effect(self, toggle: QLabel, effect_name: str) -> None:
        """Toggle an effect on/off and persist to settings."""
        colors = self._theme.tokens.colors
        is_on = toggle.text() == "☑"
        toggle.setText("☐" if is_on else "☑")
        toggle.setStyleSheet(
            f"color: {colors.accent_purple if not is_on else colors.text_muted}; "
            f"background: transparent;"
        )
        # Persist to settings
        if self._controller is not None:
            self._controller.set_setting(f"effect.{effect_name.lower()}", not is_on)

    def _build_transitions_page(self) -> QWidget:
        """Build the Transitions workspace page - empty until transitions are available."""
        tokens = self._theme.tokens
        colors = tokens.colors

        page = _styled(QWidget())
        page.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(
            tokens.spacing.sm, tokens.spacing.sm,
            tokens.spacing.sm, tokens.spacing.sm
        )
        layout.setSpacing(tokens.spacing.sm)

        layout.addWidget(_caption(self._theme, "Transitions", accent=True))

        # Empty state
        layout.addWidget(_empty_state(
            self._theme, "🔀", "No transitions available",
            "Transitions will appear here when clips are on the timeline",
        ))

        layout.addStretch(1)
        return page

    def _build_audio_page(self) -> QWidget:
        """Build the Audio workspace page with real audio file discovery."""
        tokens = self._theme.tokens
        colors = tokens.colors

        page = _styled(QWidget())
        page.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(
            tokens.spacing.sm, tokens.spacing.sm,
            tokens.spacing.sm, tokens.spacing.sm
        )
        layout.setSpacing(tokens.spacing.sm)

        layout.addWidget(_caption(self._theme, "Audio Browser", accent=True))

        from gui.widgets.text_field import TextField
        search = TextField(self._theme, placeholder="Search audio...")
        layout.addWidget(search)

        # Import audio button
        from gui.widgets.neon_button import NeonButton
        import_btn = NeonButton(self._theme, "⬇  Import Audio", variant="primary", accent="cyan")
        import_btn.clicked.connect(self._on_import_audio)
        layout.addWidget(import_btn)

        # Discover audio files from videos/ directory
        from pathlib import Path
        audio_extensions = {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac"}
        videos_dir = Path("videos")
        audio_files = []

        if videos_dir.exists():
            for f in videos_dir.iterdir():
                if f.suffix.lower() in audio_extensions:
                    audio_files.append(f)

        # Also extract audio from video files
        video_extensions = {".mp4", ".mov", ".mkv", ".avi", ".webm"}
        if videos_dir.exists():
            for f in videos_dir.iterdir():
                if f.suffix.lower() in video_extensions:
                    # Show as potential audio source
                    audio_files.append(f)

        if not audio_files:
            empty = QLabel("No audio files found.\nImport audio or video files to see them here.")
            empty.setFont(self._theme.font("body_small"))
            empty.setStyleSheet(f"color: {colors.text_muted}; background: transparent;")
            empty.setWordWrap(True)
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(empty)
        else:
            for audio_file in audio_files[:20]:  # Max 20 items
                is_video = audio_file.suffix.lower() in video_extensions
                item = _styled(QFrame())
                item.setObjectName("AudioItem")
                item.setCursor(Qt.CursorShape.PointingHandCursor)
                item.setStyleSheet(
                    f"#AudioItem {{ background: {colors.surface_elevated}; "
                    f"border: 1px solid {colors.border}; "
                    f"border-radius: {tokens.radius.sm}px; }} "
                    f"#AudioItem:hover {{ border: 1px solid {colors.accent_cyan}; }}"
                )
                item_row = QHBoxLayout(item)
                item_row.setContentsMargins(tokens.spacing.sm, tokens.spacing.sm,
                                            tokens.spacing.sm, tokens.spacing.sm)
                item_row.setSpacing(tokens.spacing.sm)

                icon = QLabel("🎵" if not is_video else "🎬")
                icon.setFont(self._theme.font("body_small"))
                icon.setStyleSheet(f"color: {colors.accent_cyan}; background: transparent;")
                item_row.addWidget(icon)

                text_col = QVBoxLayout()
                text_col.setSpacing(0)
                name_label = QLabel(audio_file.name)
                name_label.setFont(self._theme.font("body_small"))
                name_label.setStyleSheet(f"color: {colors.text_primary}; background: transparent;")
                text_col.addWidget(name_label)
                size_kb = audio_file.stat().st_size // 1024
                size_text = f"{size_kb} KB" if size_kb < 1024 else f"{size_kb // 1024} MB"
                info = QLabel(f"{audio_file.suffix.upper()[1:]}  •  {size_text}")
                info.setFont(self._theme.font("caption"))
                info.setStyleSheet(f"color: {colors.text_muted}; background: transparent;")
                text_col.addWidget(info)
                item_row.addLayout(text_col, 1)

                layout.addWidget(item)

        layout.addStretch(1)
        return page

    def _on_import_audio(self) -> None:
        """Open file dialog to import audio files."""
        from PySide6.QtWidgets import QFileDialog

        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Import Audio",
            "",
            "Audio Files (*.mp3 *.wav *.flac *.ogg *.m4a *.aac);;All Files (*)"
        )
        if files:
            import shutil
            from pathlib import Path
            videos_dir = Path("videos")
            videos_dir.mkdir(exist_ok=True)
            for f in files:
                dest = videos_dir / Path(f).name
                if not dest.exists():
                    shutil.copy2(f, dest)
            # Rebuild audio page
            self._workspace_stack.addWidget(self._build_audio_page())
            self._workspace_stack.removeWidget(self._workspace_stack.widget(7))

    def _build_captions_page(self) -> QWidget:
        """Build the Captions workspace page with real subtitle backend."""
        tokens = self._theme.tokens
        colors = tokens.colors

        page = _styled(QWidget())
        page.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(
            tokens.spacing.sm, tokens.spacing.sm,
            tokens.spacing.sm, tokens.spacing.sm
        )
        layout.setSpacing(tokens.spacing.sm)

        layout.addWidget(_caption(self._theme, "Captions", accent=True))

        # Generate subtitles button
        from gui.widgets.neon_button import NeonButton
        gen_btn = NeonButton(self._theme, "🧠  Generate Subtitles", variant="primary", accent="purple")
        gen_btn.clicked.connect(self._on_generate_subtitles)
        layout.addWidget(gen_btn)

        # Import subtitles button
        import_btn = NeonButton(self._theme, "📂  Import SRT", variant="secondary", accent="cyan")
        import_btn.clicked.connect(self._on_import_subtitles)
        layout.addWidget(import_btn)

        # Subtitle list
        self._caption_list_layout = QVBoxLayout()
        self._caption_list_layout.setSpacing(tokens.spacing.sm)
        layout.addLayout(self._caption_list_layout)

        # Load existing subtitles if available
        self._load_subtitle_list()

        layout.addStretch(1)
        return page

    def _load_subtitle_list(self) -> None:
        """Load existing subtitles from output directory."""
        import json
        from pathlib import Path

        tokens = self._theme.tokens
        colors = tokens.colors

        # Clear existing
        while self._caption_list_layout.count():
            item = self._caption_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Look for subtitle files
        subtitle_files = list(Path("output").glob("*_subtitles.json"))
        srt_files = list(Path("output").glob("*.srt"))

        cues = []
        if subtitle_files:
            try:
                with open(subtitle_files[0]) as f:
                    data = json.load(f)
                cues = data.get("cues", [])
            except Exception:
                pass

        if not cues:
            empty = QLabel("No subtitles yet.\nClick Generate Subtitles to create from video.")
            empty.setFont(self._theme.font("body_small"))
            empty.setStyleSheet(f"color: {colors.text_muted}; background: transparent;")
            empty.setWordWrap(True)
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._caption_list_layout.addWidget(empty)
            return

        for cue in cues[:50]:  # Max 50 cues
            start = cue.get("start", 0)
            end = cue.get("end", 0)
            text = cue.get("text", "")

            item = _styled(QFrame())
            item.setObjectName("CaptionItem")
            item.setStyleSheet(
                f"#CaptionItem {{ background: {colors.surface_elevated}; "
                f"border: 1px solid {colors.border}; "
                f"border-radius: {tokens.radius.sm}px; }}"
            )
            item_row = QHBoxLayout(item)
            item_row.setContentsMargins(tokens.spacing.sm, tokens.spacing.sm,
                                        tokens.spacing.sm, tokens.spacing.sm)
            item_row.setSpacing(tokens.spacing.sm)

            # Format timecode
            def _fmt(sec):
                m = int(sec // 60)
                s = sec % 60
                return f"{m:02d}:{s:05.2f}"

            time_label = QLabel(f"{_fmt(start)} → {_fmt(end)}")
            time_label.setFont(self._theme.font("mono"))
            time_label.setStyleSheet(f"color: {colors.accent_cyan}; background: transparent;")
            item_row.addWidget(time_label)

            text_label = QLabel(text)
            text_label.setFont(self._theme.font("body_small"))
            text_label.setStyleSheet(f"color: {colors.text_secondary}; background: transparent;")
            item_row.addWidget(text_label, 1)

            self._caption_list_layout.addWidget(item)

    def _on_generate_subtitles(self) -> None:
        """Generate subtitles from the current video."""
        if self._controller is None:
            return
        try:
            state = self._controller.project_state()
            if state.video_path:
                self._controller.run_phase("subtitles")
            else:
                pass  # No video loaded
        except Exception:
            pass

    def _on_import_subtitles(self) -> None:
        """Import an SRT subtitle file."""
        from PySide6.QtWidgets import QFileDialog
        import shutil
        from pathlib import Path

        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Import Subtitles",
            "",
            "Subtitle Files (*.srt *.vtt *.ass);;All Files (*)"
        )
        if files:
            output_dir = Path("output")
            output_dir.mkdir(exist_ok=True)
            for f in files:
                shutil.copy2(f, output_dir / Path(f).name)
            self._load_subtitle_list()

    def _build_templates_page(self) -> QWidget:
        """Build the Templates workspace page."""
        tokens = self._theme.tokens
        colors = tokens.colors

        page = _styled(QWidget())
        page.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(
            tokens.spacing.md, tokens.spacing.md,
            tokens.spacing.md, tokens.spacing.md
        )
        layout.setSpacing(tokens.spacing.sm)

        layout.addWidget(_caption(self._theme, "Templates", accent=True))

        categories = [
            ("🎬", "Intro", "Opening sequences"),
            ("🎬", "Outro", "Closing sequences"),
            ("📺", "Lower Thirds", "Name tags and titles"),
            ("🎭", "Overlays", "Text and graphic overlays"),
        ]
        for icon, name, desc in categories:
            cat = _styled(QFrame())
            cat.setObjectName("TemplateCat")
            cat.setStyleSheet(
                f"#TemplateCat {{ background: {colors.surface_elevated}; "
                f"border: 1px solid {colors.border}; "
                f"border-radius: {tokens.radius.sm}px; }}"
            )
            cat_row = QHBoxLayout(cat)
            cat_row.setContentsMargins(tokens.spacing.md, tokens.spacing.sm,
                                       tokens.spacing.md, tokens.spacing.sm)
            cat_row.setSpacing(tokens.spacing.md)

            icon_label = QLabel(icon)
            icon_label.setFont(self._theme.font("body"))
            icon_label.setStyleSheet(f"color: {colors.accent_purple}; background: transparent;")
            cat_row.addWidget(icon_label)

            text_col = QVBoxLayout()
            text_col.setSpacing(0)
            name_label = QLabel(name)
            name_label.setFont(self._theme.font("body_small"))
            name_label.setStyleSheet(f"color: {colors.text_primary}; background: transparent;")
            text_col.addWidget(name_label)
            desc_label = QLabel(desc)
            desc_label.setFont(self._theme.font("caption"))
            desc_label.setStyleSheet(f"color: {colors.text_muted}; background: transparent;")
            text_col.addWidget(desc_label)
            cat_row.addLayout(text_col, 1)

            layout.addWidget(cat)

        layout.addStretch(1)
        return page

    def _build_ai_studio_page(self) -> QWidget:
        """Build the AI Studio workspace page with real AIController integration."""
        tokens = self._theme.tokens
        colors = tokens.colors

        page = _styled(QWidget())
        page.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(
            tokens.spacing.sm, tokens.spacing.sm,
            tokens.spacing.sm, tokens.spacing.sm
        )
        layout.setSpacing(tokens.spacing.sm)

        layout.addWidget(_caption(self._theme, "AI Studio", accent=True))

        # AI status
        if self._controller is not None:
            status = QLabel("🟢 AI Engine: Idle")
            status.setFont(self._theme.font("body_small"))
            status.setStyleSheet(f"color: {colors.text_secondary}; background: transparent;")
        else:
            status = QLabel("🔴 AI Engine: Not connected")
            status.setFont(self._theme.font("body_small"))
            status.setStyleSheet(f"color: {colors.text_muted}; background: transparent;")
        layout.addWidget(status)

        # AI tools from existing phases
        tools = [
            ("🧠", "Scene Detection", "Detect scene changes", "analysis", colors.accent_cyan),
            ("🎵", "Audio Analysis", "Analyze audio tracks", "audio", colors.accent_blue),
            ("📝", "Speech-to-Text", "Generate captions", "subtitles", colors.accent_purple),
            ("👤", "Face Detection", "Find faces in video", "ocr", colors.accent_pink),
            ("⭐", "Highlight Detection", "Find best moments", "highlight", colors.warning),
            ("🖼", "Thumbnail Generator", "Create thumbnails", "render", colors.success),
            ("🎭", "Voice Cleanup", "Enhance voice quality", "audio", colors.accent_cyan),
            ("📊", "Video Analyzing", "Analyze resolution/FPS", "analysis", colors.accent_blue),
        ]
        for icon, name, desc, phase_id, color in tools:
            tool = _styled(QFrame())
            tool.setObjectName("AITool")
            tool.setCursor(Qt.CursorShape.PointingHandCursor)
            tool.setStyleSheet(
                f"#AITool {{ background: {colors.surface_elevated}; "
                f"border: 1px solid {colors.border}; "
                f"border-radius: {tokens.radius.sm}px; }} "
                f"#AITool:hover {{ border: 1px solid {colors.accent_cyan}; }}"
            )
            tool_row = QHBoxLayout(tool)
            tool_row.setContentsMargins(tokens.spacing.sm, tokens.spacing.sm,
                                        tokens.spacing.sm, tokens.spacing.sm)
            tool_row.setSpacing(tokens.spacing.sm)

            icon_label = QLabel(icon)
            icon_label.setFont(self._theme.font("body_small"))
            icon_label.setFixedSize(28, 28)
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_label.setStyleSheet(
                f"color: {colors.text_primary}; background: {color}; "
                f"border-radius: 14px;"
            )
            tool_row.addWidget(icon_label)

            text_col = QVBoxLayout()
            text_col.setSpacing(0)
            name_label = QLabel(name)
            name_label.setFont(self._theme.font("body_small"))
            name_label.setStyleSheet(f"color: {colors.text_primary}; background: transparent;")
            text_col.addWidget(name_label)
            desc_label = QLabel(desc)
            desc_label.setFont(self._theme.font("caption"))
            desc_label.setStyleSheet(f"color: {colors.text_muted}; background: transparent;")
            text_col.addWidget(desc_label)
            tool_row.addLayout(text_col, 1)

            # Run button
            run_btn = QLabel("▶")
            run_btn.setFont(self._theme.font("body_small"))
            run_btn.setStyleSheet(
                f"color: {colors.accent_cyan}; background: transparent; padding: 4px;"
            )
            run_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            run_btn.mouseReleaseEvent = lambda _e, p=phase_id: self._run_ai_phase(p)
            tool_row.addWidget(run_btn)

            layout.addWidget(tool)

        # AI logs section
        layout.addWidget(_caption(self._theme, "AI Logs"))
        self._ai_logs_text = QLabel("No logs yet. Run an AI task to see results.")
        self._ai_logs_text.setFont(self._theme.font("caption"))
        self._ai_logs_text.setStyleSheet(f"color: {colors.text_muted}; background: transparent;")
        self._ai_logs_text.setWordWrap(True)
        layout.addWidget(self._ai_logs_text)

        layout.addStretch(1)
        return page

    def _run_ai_phase(self, phase_id: str) -> None:
        """Run an AI phase via the WorkflowController."""
        if self._controller is None:
            return
        try:
            self._controller.run_phase(phase_id)
            if hasattr(self, '_ai_logs_text'):
                self._ai_logs_text.setText(f"Running {phase_id}... Check status bar.")
        except Exception as exc:
            if hasattr(self, '_ai_logs_text'):
                self._ai_logs_text.setText(f"Error: {exc}")

    def _build_export_page(self) -> QWidget:
        """Build the Export workspace page - empty until exports are available."""
        tokens = self._theme.tokens
        colors = tokens.colors

        page = _styled(QWidget())
        page.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(
            tokens.spacing.sm, tokens.spacing.sm,
            tokens.spacing.sm, tokens.spacing.sm
        )
        layout.setSpacing(tokens.spacing.sm)

        layout.addWidget(_caption(self._theme, "Export", accent=True))

        # Export button
        from gui.widgets.neon_button import NeonButton
        export_btn = NeonButton(self._theme, "⬆  Export Video", variant="primary", accent="cyan")
        export_btn.clicked.connect(self._on_export_video)
        layout.addWidget(export_btn)

        # Empty state for presets
        layout.addWidget(_empty_state(
            self._theme, "📤", "No export presets",
            "Select a video and configure export settings to begin",
        ))

        layout.addStretch(1)
        return page

    def _select_export_preset(self, params: dict, name: str) -> None:
        """Select an export preset."""
        self._export_params = params

    def _on_export_video(self) -> None:
        """Export video using the selected preset."""
        if self._controller is None:
            return
        try:
            self._controller.run_phase("render")
        except Exception:
            pass

    def _build_settings_page(self) -> QWidget:
        """Build the Settings workspace page with real config backend."""
        tokens = self._theme.tokens
        colors = tokens.colors

        page = _styled(QWidget())
        page.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(
            tokens.spacing.sm, tokens.spacing.sm,
            tokens.spacing.sm, tokens.spacing.sm
        )
        layout.setSpacing(tokens.spacing.sm)

        layout.addWidget(_caption(self._theme, "Settings", accent=True))

        # General settings from config.py
        sections = [
            ("⚙", "General", "Application preferences"),
            ("🎬", "Playback", "Playback and preview settings"),
            ("🖥", "GPU", "Hardware acceleration"),
            ("🧠", "AI", "AI engine configuration"),
            ("💾", "Cache", "Cache and storage settings"),
            ("⌨", "Shortcuts", "Keyboard shortcuts"),
        ]

        # Read current settings from controller
        current_settings = {}
        if self._controller is not None:
            try:
                state = self._controller.project_state()
                current_settings = dict(state.settings) if state.settings else {}
            except Exception:
                pass

        for icon, name, desc in sections:
            section = _styled(QFrame())
            section.setObjectName("SettingsSection")
            section.setStyleSheet(
                f"#SettingsSection {{ background: {colors.surface_elevated}; "
                f"border: 1px solid {colors.border}; "
                f"border-radius: {tokens.radius.sm}px; }}"
            )
            section_col = QVBoxLayout(section)
            section_col.setContentsMargins(tokens.spacing.sm, tokens.spacing.sm,
                                           tokens.spacing.sm, tokens.spacing.sm)
            section_col.setSpacing(tokens.spacing.xs)

            section_row = QHBoxLayout()
            section_row.setSpacing(tokens.spacing.md)

            icon_label = QLabel(icon)
            icon_label.setFont(self._theme.font("body"))
            icon_label.setStyleSheet(f"color: {colors.accent_cyan}; background: transparent;")
            section_row.addWidget(icon_label)

            text_col = QVBoxLayout()
            text_col.setSpacing(0)
            name_label = QLabel(name)
            name_label.setFont(self._theme.font("body_small"))
            name_label.setStyleSheet(f"color: {colors.text_primary}; background: transparent;")
            text_col.addWidget(name_label)
            desc_label = QLabel(desc)
            desc_label.setFont(self._theme.font("caption"))
            desc_label.setStyleSheet(f"color: {colors.text_muted}; background: transparent;")
            text_col.addWidget(desc_label)
            section_row.addLayout(text_col, 1)

            section_col.addLayout(section_row)

            # Add relevant settings fields
            if name == "General":
                self._add_setting_field(section_col, "Project Directory", "project_dir",
                                       current_settings.get("project_dir", ""), "text")
            elif name == "AI":
                self._add_setting_field(section_col, "AI Provider", "ai_provider",
                                       current_settings.get("ai_provider", ""), "dropdown",
                                       ["openai", "claude", "gemini", "ollama"])
                self._add_setting_field(section_col, "Model", "ai_model",
                                       current_settings.get("ai_model", ""), "text")
            elif name == "Playback":
                self._add_setting_field(section_col, "Default FPS", "default_fps",
                                       str(current_settings.get("default_fps", "")), "text")
                self._add_setting_field(section_col, "Loop Playback", "loop_playback",
                                       current_settings.get("loop_playback", ""), "toggle")

            layout.addWidget(section)

        layout.addStretch(1)
        return page

    def _add_setting_field(self, layout: QVBoxLayout, label: str, key: str,
                           value: str, field_type: str, options: list = None) -> None:
        """Add a settings field to a layout."""
        tokens = self._theme.tokens
        colors = tokens.colors

        field = QHBoxLayout()
        field.setSpacing(tokens.spacing.sm)

        lbl = QLabel(label)
        lbl.setFont(self._theme.font("body_small"))
        lbl.setStyleSheet(f"color: {colors.text_secondary}; background: transparent;")
        lbl.setFixedWidth(100)
        field.addWidget(lbl)

        if field_type == "toggle":
            from gui.widgets.toggle_switch import ToggleSwitch
            toggle = ToggleSwitch(self._theme)
            toggle.set_checked(value.lower() == "true")
            toggle.toggled.connect(lambda checked, k=key: self._save_setting(k, str(checked).lower()))
            field.addWidget(toggle)
        elif field_type == "dropdown":
            from gui.widgets.dropdown import Dropdown
            dropdown = Dropdown(self._theme, items=options or [])
            # Set current value
            if value in (options or []):
                idx = (options or []).index(value)
                dropdown.set_current_index(idx)
            dropdown.changed.connect(lambda idx, opts=options: self._save_setting(key, opts[idx] if idx < len(opts) else ""))
            field.addWidget(dropdown, 1)
        else:
            from gui.widgets.text_field import TextField
            text_field = TextField(self._theme, placeholder="Enter value...")
            text_field.set_text(value)
            text_field.editing_finished.connect(lambda k=key, tf=text_field: self._save_setting(k, tf.text()))
            field.addWidget(text_field, 1)

        layout.addLayout(field)

    def _save_setting(self, key: str, value: str) -> None:
        """Save a setting via the WorkflowController."""
        if self._controller is not None:
            try:
                self._controller.set_setting(key, value)
            except Exception:
                pass

    def _build_generic_page(self, title: str) -> QWidget:
        """Build a generic placeholder workspace page."""
        tokens = self._theme.tokens
        colors = tokens.colors

        page = _styled(QWidget())
        page.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(
            tokens.spacing.md, tokens.spacing.md,
            tokens.spacing.md, tokens.spacing.md
        )
        layout.setSpacing(tokens.spacing.sm)

        layout.addWidget(_caption(self._theme, title, accent=True))

        placeholder = QLabel(f"No content available for {title}")
        placeholder.setFont(self._theme.font("body_small"))
        placeholder.setStyleSheet(f"color: {colors.text_muted}; background: transparent;")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(placeholder)

        layout.addStretch(1)
        return page

    def _build_preview_header(self) -> QWidget:
        """Build the preview header bar matching screenshot exactly."""
        tokens = self._theme.tokens
        colors = tokens.colors

        header = _styled(QFrame())
        header.setObjectName("PreviewHeader")
        header.setFixedHeight(30)
        header.setStyleSheet(
            f"#PreviewHeader {{ background: transparent; border: none; }}"
        )
        row = QHBoxLayout(header)
        row.setContentsMargins(4, 0, 4, 0)
        row.setSpacing(12)

        program = QLabel("Program: No media")
        program.setFont(self._theme.font("body"))
        program.setStyleSheet(f"color: {colors.text_primary}; background: transparent;")
        row.addWidget(program)

        row.addStretch(1)

        # Resolution dropdown chip
        res_chip = _styled(QFrame())
        res_chip.setObjectName("ResChip")
        res_chip.setStyleSheet(
            f"#ResChip {{ background: {colors.surface_overlay}; "
            f"border: 1px solid {colors.border}; border-radius: 4px; }}"
        )
        res_row = QHBoxLayout(res_chip)
        res_row.setContentsMargins(8, 3, 8, 3)
        res_row.setSpacing(4)
        res_label = QLabel("--")
        res_label.setFont(self._theme.font("body_small"))
        res_label.setStyleSheet(f"color: {colors.text_primary}; background: transparent;")
        res_row.addWidget(res_label)
        res_arrow = QLabel("▾")
        res_arrow.setStyleSheet(f"color: {colors.text_muted}; background: transparent;")
        res_row.addWidget(res_arrow)
        row.addWidget(res_chip)

        fps_chip = _styled(QFrame())
        fps_chip.setObjectName("FpsChip")
        fps_chip.setStyleSheet(
            f"#FpsChip {{ background: {colors.surface_overlay}; "
            f"border: 1px solid {colors.border}; border-radius: 4px; }}"
        )
        fps_row = QHBoxLayout(fps_chip)
        fps_row.setContentsMargins(8, 3, 8, 3)
        fps_row.setSpacing(4)
        fps_label = QLabel("-- fps")
        fps_label.setFont(self._theme.font("body_small"))
        fps_label.setStyleSheet(f"color: {colors.text_primary}; background: transparent;")
        fps_row.addWidget(fps_label)
        fps_arrow = QLabel("▾")
        fps_arrow.setStyleSheet(f"color: {colors.text_muted}; background: transparent;")
        fps_row.addWidget(fps_arrow)
        row.addWidget(fps_chip)

        zoom_chip = _styled(QFrame())
        zoom_chip.setObjectName("ZoomChip")
        zoom_chip.setStyleSheet(
            f"#ZoomChip {{ background: {colors.surface_overlay}; "
            f"border: 1px solid {colors.border}; border-radius: 4px; }}"
        )
        zoom_row = QHBoxLayout(zoom_chip)
        zoom_row.setContentsMargins(8, 3, 8, 3)
        zoom_row.setSpacing(4)
        zoom_label = QLabel("--")
        zoom_label.setFont(self._theme.font("body_small"))
        zoom_label.setStyleSheet(f"color: {colors.text_primary}; background: transparent;")
        zoom_row.addWidget(zoom_label)
        zoom_arrow = QLabel("▾")
        zoom_arrow.setStyleSheet(f"color: {colors.text_muted}; background: transparent;")
        zoom_row.addWidget(zoom_arrow)
        row.addWidget(zoom_chip)

        settings = QLabel("⚙")
        settings.setFont(self._theme.font("body_small"))
        settings.setStyleSheet(f"color: {colors.text_muted}; background: transparent;")
        row.addWidget(settings)

        return header

    def _show_workspace_page(self, index: int) -> None:
        """Switch the workspace panel to the specified page.

        Args:
            index: Sidebar nav index (0=Dashboard, 1=Projects, 2=Media, etc.)
        """
        # Map nav index to workspace page index (they match 1:1)
        if hasattr(self, '_workspace_pages'):
            clamped = max(0, min(index, self._workspace_pages.count() - 1))
            self._workspace_pages.setCurrentIndex(clamped)

    def get_preview_stage(self) -> QWidget:
        """Get the preview stage widget."""
        return self._stage

    def get_timeline(self) -> QWidget:
        """Get the timeline widget."""
        return self._timeline

    def get_controller(self):
        """Get the backend controller."""
        return self._controller

    def set_controller(self, controller) -> None:
        """Set the backend controller and update dashboard."""
        self._controller = controller
        if hasattr(self._dashboard, 'set_controller'):
            self._dashboard.set_controller(controller)


def build_studio_screen(theme: ThemeManager, *, media_source=None, controller=None) -> QWidget:
    """Build and return the full studio workspace screen.

    Constructed without running a Qt event loop so it can be asserted
    headlessly in tests. All visual values come from the injected ``theme``.

    Integration Milestone 2: the screen embeds the existing
    :class:`MediaBrowser` and :class:`TransportBar` as hidden children and
    wires media selection to the preview stage (first frame, title,
    timecode). Without a selection, the original static/demo presentation
    renders unchanged.

    Phase 3: Navigation support with Dashboard and Editor pages.

    Args:
        theme: The injected theme manager (sole source of visual values).
        media_source: Optional preview media source (duck-typed like
            :class:`~gui.integration.preview_media.PreviewMediaSource`).
            When omitted, the real source is constructed lazily; tests
            inject a fake.
        controller: Optional WorkflowController for backend integration.

    Returns:
        The fully composed studio screen as a :class:`QWidget`.
    """
    return StudioScreen(theme, media_source=media_source, controller=controller)
