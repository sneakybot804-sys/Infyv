"""MediaBrowser: a themed, UI-only media list panel (Phase 8H, Milestone 2).

A left-panel media browser composed from the frozen widget library. It shows a
static import affordance (a NeonButton placeholder -- no file dialog, no
filesystem, no backend) and a vertically scrolling list of media items. Each
item is rendered as a ``NeonButton(variant="ghost")`` row (object name
``MediaItem``); there is no custom item widget in Milestone 2.

Selection is UI-only state: the browser tracks the current index and emits
:attr:`selection_changed` when it changes. No real media is opened and
:mod:`gui_core` is never touched.

Stable object names for later integration and tests:

* ``MediaBrowser`` -- the root widget
* ``MediaBrowserImport`` -- the import-area button
* ``MediaBrowserList`` -- the scroll area holding the item rows
* ``MediaItem`` -- each item row button
"""
from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from gui.theme.manager import ThemeManager
from gui.widgets.base import ThemedWidget
from gui.widgets.meta_label import MetaLabel
from gui.widgets.neon_button import NeonButton
from gui.widgets.section_header import SectionHeader
from gui.widgets.segmented_control import SegmentedControl
from gui.widgets.status_badge import StatusBadge
from gui.widgets.text_field import TextField


class MediaBrowser(ThemedWidget):
    """A themed, UI-only media list with an import affordance.

    Args:
        theme: Injected theme manager (sole source of visual values).
        items: Optional initial media labels (static/demo). Default empty.
        parent: Optional Qt parent.

    Signals:
        selection_changed(int): Emitted with the new current index when the
            selection changes (``-1`` when cleared). UI-only; no backend.
        import_requested(): Emitted when the import affordance is activated.
            A placeholder hook for a future milestone; wires no file dialog.
    """

    selection_changed = Signal(int)
    import_requested = Signal()

    def __init__(
        self,
        theme: ThemeManager,
        *,
        items: Optional[List[str]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(theme, parent)
        self.setObjectName("MediaBrowser")

        self._items: List[str] = []
        self._buttons: List[NeonButton] = []
        self._current = -1

        tokens = self.tokens

        self._column = QVBoxLayout(self)
        self._column.setContentsMargins(
            tokens.spacing.md, tokens.spacing.md, tokens.spacing.md, tokens.spacing.md
        )
        self._column.setSpacing(tokens.spacing.md)

        header = SectionHeader(self._theme, "Media", subtitle="Imported clips")
        header.set_divider(True)
        self._column.addWidget(header)

        # --- Phase 10E: professional asset-panel chrome (decorative) --- #
        # A meta row: an asset-count label and a grid/list view toggle. Both
        # are placeholders (the toggle switches nothing).
        self._meta_row = QWidget(self)
        self._meta_row.setObjectName("MediaBrowserMetaRow")
        meta_layout = QHBoxLayout(self._meta_row)
        meta_layout.setContentsMargins(0, 0, 0, 0)
        meta_layout.setSpacing(tokens.spacing.sm)
        self._count_label = MetaLabel(
            self._theme, "0 assets", role="muted", style="caption"
        )
        self._count_label.setObjectName("MediaBrowserCount")
        meta_layout.addWidget(self._count_label, 1)
        self._view_toggle = SegmentedControl(
            self._theme, ["Grid", "List"], current=1, accent="cyan"
        )
        self._view_toggle.setObjectName("MediaBrowserViewToggle")
        meta_layout.addWidget(self._view_toggle, 0)
        self._column.addWidget(self._meta_row)

        # A search field placeholder (no real search / filtering).
        self._search = TextField(
            self._theme, placeholder="Search assets\u2026"
        )
        self._search.setObjectName("MediaBrowserSearch")
        self._column.addWidget(self._search)

        # A decorative filter-chip row (All / Video / Audio / Image).
        self._filters = QWidget(self)
        self._filters.setObjectName("MediaBrowserFilters")
        filters_layout = QHBoxLayout(self._filters)
        filters_layout.setContentsMargins(0, 0, 0, 0)
        filters_layout.setSpacing(tokens.spacing.xs)
        for text, status in (
            ("All", "info"),
            ("Video", "neutral"),
            ("Audio", "neutral"),
            ("Image", "neutral"),
        ):
            chip = StatusBadge(self._theme, text, status=status)
            chip.setObjectName("MediaBrowserFilterChip")
            filters_layout.addWidget(chip)
        filters_layout.addStretch(1)
        self._column.addWidget(self._filters)

        # A placeholder sidebar section block (Folders / Collections /
        # Favorites / Recent Imports). Static labels wired to nothing.
        self._sidebar = QWidget(self)
        self._sidebar.setObjectName("MediaBrowserSidebar")
        sidebar_layout = QVBoxLayout(self._sidebar)
        sidebar_layout.setContentsMargins(
            tokens.spacing.sm, tokens.spacing.sm,
            tokens.spacing.sm, tokens.spacing.sm,
        )
        sidebar_layout.setSpacing(tokens.spacing.xxs)
        for text in (
            "\U0001f4c1 Folders",
            "\u2b50 Favorites",
            "\U0001f5c2 Collections",
            "\U0001f552 Recent Imports",
        ):
            entry = MetaLabel(
                self._theme, text, role="muted", style="body_small"
            )
            entry.setObjectName("MediaBrowserSidebarItem")
            sidebar_layout.addWidget(entry)
        self._column.addWidget(self._sidebar)

        # Import affordance: placeholder only -- emits import_requested, opens
        # no dialog and touches no filesystem in this milestone.
        self._import_button = NeonButton(
            self._theme, "Import Media", variant="secondary", accent="cyan"
        )
        self._import_button.setObjectName("MediaBrowserImport")
        self._import_button.clicked.connect(self.import_requested.emit)
        self._column.addWidget(self._import_button)

        # A premium empty-state label (shown only while there are no items).
        self._empty_label = MetaLabel(
            self._theme,
            "No media imported yet.\nImport clips to get started.",
            role="muted",
            style="body_small",
        )
        self._empty_label.setObjectName("MediaBrowserEmpty")
        self._column.addWidget(self._empty_label)

        # Scrollable list region for the item rows.
        self._list_area = QScrollArea(self)
        self._list_area.setObjectName("MediaBrowserList")
        self._list_area.setWidgetResizable(True)
        self._list_container = QWidget()
        self._list_container.setObjectName("MediaBrowserListContainer")
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(tokens.spacing.sm)
        self._list_layout.addStretch(1)
        self._list_area.setWidget(self._list_container)
        self._column.addWidget(self._list_area, 1)

        # Asset-metadata placeholder footer (filename / duration / resolution
        # / fps captions). Static; represents the selected-asset detail strip.
        self._meta_footer = QWidget(self)
        self._meta_footer.setObjectName("MediaBrowserMeta")
        footer_layout = QVBoxLayout(self._meta_footer)
        footer_layout.setContentsMargins(
            tokens.spacing.sm, tokens.spacing.sm,
            tokens.spacing.sm, tokens.spacing.sm,
        )
        footer_layout.setSpacing(tokens.spacing.xxs)
        for text in (
            "filename.mp4",
            "Duration  00:00:00",
            "Resolution  1920x1080",
            "FPS  60",
        ):
            detail = MetaLabel(
                self._theme, text, role="muted", style="caption"
            )
            detail.setObjectName("MediaBrowserMetaItem")
            footer_layout.addWidget(detail)
        self._column.addWidget(self._meta_footer)

        if items:
            self.set_items(items)

        self._update_chrome()
        self.setAccessibleName("media browser")
        self.apply_theme()

    def _update_chrome(self) -> None:
        """Refresh decorative chrome from the current item count (UI-only).

        Updates the asset-count label and shows the empty-state label only
        while the list is empty. Touches no selection, signal, item widget or
        public API; safe to call after any set_items rebuild.
        """
        count = len(self._items)
        label = "1 asset" if count == 1 else f"{count} assets"
        self._count_label.set_text(label)
        self._empty_label.setVisible(count == 0)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def set_items(self, items: List[str]) -> None:
        """Replace the media list with ``items`` (clears the selection).

        Rebuilds the item rows as ``NeonButton(variant="ghost")`` controls.
        The current selection is reset to ``-1`` and :attr:`selection_changed`
        is emitted once to reflect the cleared state.
        """
        # Remove existing rows (keep the trailing stretch at the end).
        for button in self._buttons:
            self._list_layout.removeWidget(button)
            button.setParent(None)
        self._buttons.clear()

        self._items = list(items)
        for index, label in enumerate(self._items):
            button = NeonButton(self._theme, label, variant="ghost", accent="cyan")
            button.setObjectName("MediaItem")
            button.clicked.connect(lambda _=False, i=index: self.select(i))
            # Insert before the trailing stretch (last layout item).
            self._list_layout.insertWidget(self._list_layout.count() - 1, button)
            self._buttons.append(button)

        self._current = -1
        self._update_chrome()
        self.selection_changed.emit(self._current)

    def items(self) -> List[str]:
        """Return a copy of the current media labels."""
        return list(self._items)

    def count(self) -> int:
        """Return the number of media items."""
        return len(self._items)

    def select(self, index: int) -> None:
        """Select the item at ``index``; no-op when already selected.

        Emits :attr:`selection_changed` when the current index changes. A
        value of ``-1`` clears the selection. Out-of-range indices raise.
        """
        if index != -1 and not (0 <= index < len(self._items)):
            raise ValueError(f"selection index out of range: {index}")
        if index == self._current:
            return
        self._current = index
        self.selection_changed.emit(self._current)

    def current_index(self) -> int:
        """Return the current selection index (``-1`` when none)."""
        return self._current

    def current_item(self) -> Optional[str]:
        """Return the current item's label, or ``None`` when none selected."""
        if 0 <= self._current < len(self._items):
            return self._items[self._current]
        return None

    # ------------------------------------------------------------------ #
    # Theming
    # ------------------------------------------------------------------ #
    def apply_theme(self) -> None:
        """Apply the premium panel styling to the browser surfaces.

        Styling-only (Phase 9F): object-name-scoped, token-derived QSS that
        makes the browser read as a docked, glassy asset panel (rounded panel
        root, borderless inset scroll list, slim neon scrollbar, deep list
        surface). The composed child widgets (SectionHeader, NeonButtons) keep
        their own self-theming; no logic, signal, object name or API changes.
        """
        colors = self.tokens.colors
        radius = self.tokens.radius.md
        radius_lg = self.tokens.radius.lg

        # Panel root: a layered surface so the browser looks like a first-class
        # docked panel rather than a bare column.
        self.setStyleSheet(
            f"#MediaBrowser {{ background: {colors.surface}; "
            f"border: 1px solid {colors.border}; "
            f"border-radius: {radius_lg}px; }}"
        )

        # Scroll area + its viewport: transparent, borderless and rounded so
        # the list blends into the panel; a slim, rounded scrollbar with an
        # accent-cyan hover handle matches the app's premium scrollbar style.
        self._list_area.setStyleSheet(
            f"#MediaBrowserList {{ background: transparent; border: none; }} "
            f"#MediaBrowserList > QWidget > QWidget {{ background: transparent; }} "
            f"QScrollBar:vertical {{ background: transparent; "
            f"width: {self.tokens.spacing.sm}px; margin: 0px; }} "
            f"QScrollBar::handle:vertical {{ background: {colors.surface_overlay}; "
            f"border-radius: {self.tokens.radius.sm}px; min-height: {self.tokens.spacing.xl}px; }} "
            f"QScrollBar::handle:vertical:hover {{ background: {colors.accent_cyan}; }} "
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ "
            f"height: 0px; }} "
            f"QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ "
            f"background: transparent; }}"
        )

        # List container: a deep inset surface for the item rows.
        self._list_container.setStyleSheet(
            f"#MediaBrowserListContainer {{ background: {colors.background_deep}; "
            f"border-radius: {radius}px; }}"
        )

        # --- Phase 10E: professional chrome styling (decorative) --- #
        # Search field: a glassy inset input.
        self._search.setStyleSheet(
            f"#MediaBrowserSearch {{ background: {colors.background_deep}; "
            f"border: 1px solid {colors.border}; "
            f"border-radius: {radius}px; }}"
        )
        # Filter chips: rounded, subtly bordered pills.
        self._filters.setStyleSheet(
            f"#MediaBrowserFilters {{ background: transparent; }} "
            f'#MediaBrowserFilterChip {{ border-radius: {self.tokens.radius.pill}px; }}'
        )
        # Sidebar section block: a deep inset rail with muted rows.
        self._sidebar.setStyleSheet(
            f"#MediaBrowserSidebar {{ background: {colors.background_deep}; "
            f"border: 1px solid {colors.border}; "
            f"border-radius: {radius}px; }} "
            f"#MediaBrowserSidebarItem {{ background: transparent; }}"
        )
        # Empty state: a calm, muted, softly-padded placeholder.
        self._empty_label.setStyleSheet(
            f"#MediaBrowserEmpty {{ color: {colors.text_muted}; "
            f"background: {colors.background_deep}; "
            f"border: 1px solid {colors.border}; "
            f"border-radius: {radius}px; "
            f"padding: {self.tokens.spacing.md}px; }}"
        )
        # Metadata footer: a subtle glass detail strip.
        self._meta_footer.setStyleSheet(
            f"#MediaBrowserMeta {{ background: {colors.surface}; "
            f"border: 1px solid {colors.border}; "
            f"border-radius: {radius}px; }} "
            f"#MediaBrowserMetaItem {{ background: transparent; }}"
        )
