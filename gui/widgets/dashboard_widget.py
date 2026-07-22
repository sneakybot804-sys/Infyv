"""Dashboard widget: Project Overview panel matching the target UI.

Displays Quick Overview stats, Recent Projects, and Recent Exports
in a scrollable panel. All data sourced from backend when available,
with realistic demo data as fallback.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from gui.theme.manager import ThemeManager

__all__ = ["DashboardWidget"]


class DashboardWidget(QWidget):
    """Project Overview panel matching the target UI screenshot.

    Shows Quick Overview stats, Recent Projects list, and Recent Exports list.
    """

    recent_project_activated = Signal(str)
    recent_export_activated = Signal(str)

    def __init__(
        self,
        theme: ThemeManager,
        *,
        controller=None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._theme = theme
        self._controller = controller
        self._setup_ui()
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_data)
        self._refresh_timer.start(5000)
        self._refresh_data()

    def _setup_ui(self) -> None:
        tokens = self._theme.tokens
        colors = tokens.colors

        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"background: {colors.surface};")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        content = QWidget()
        content.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        content.setStyleSheet("background: transparent;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(16, 16, 16, 16)
        content_layout.setSpacing(16)

        # --- Header: "Project Overview" with hamburger icon ---
        header_row = QHBoxLayout()
        header_row.setSpacing(8)
        hamburger = QLabel("☰")
        hamburger.setFont(self._theme.font("body"))
        hamburger.setStyleSheet(f"color: {colors.text_secondary}; background: transparent;")
        header_row.addWidget(hamburger)
        header_title = QLabel("Project Overview")
        header_title.setFont(self._theme.font("h2"))
        header_title.setStyleSheet(f"color: {colors.text_primary}; background: transparent;")
        header_row.addWidget(header_title)
        header_row.addStretch(1)
        content_layout.addLayout(header_row)

        # --- Quick Overview section ---
        qo_label = QLabel("QUICK OVERVIEW")
        qo_label.setFont(self._theme.font("caption"))
        qo_label.setStyleSheet(
            f"color: {colors.text_muted}; background: transparent; letter-spacing: 1px;"
        )
        content_layout.addWidget(qo_label)

        # 2x2 grid of stat boxes
        stats_grid = QGridLayout()
        stats_grid.setSpacing(8)

        self._stat_projects = self._create_stat_box("0", "Projects")
        self._stat_media = self._create_stat_box("0", "Media Files")
        self._stat_ai = self._create_stat_box("0", "AI Tasks")
        self._stat_exports = self._create_stat_box("0", "Exports")

        stats_grid.addWidget(self._stat_projects, 0, 0)
        stats_grid.addWidget(self._stat_media, 0, 1)
        stats_grid.addWidget(self._stat_ai, 1, 0)
        stats_grid.addWidget(self._stat_exports, 1, 1)
        content_layout.addLayout(stats_grid)

        # --- Recent Projects section ---
        rp_header = QHBoxLayout()
        rp_title = QLabel("RECENT PROJECTS")
        rp_title.setFont(self._theme.font("caption"))
        rp_title.setStyleSheet(
            f"color: {colors.text_muted}; background: transparent; letter-spacing: 1px;"
        )
        rp_header.addWidget(rp_title)
        rp_header.addStretch(1)
        view_all = QLabel("View All")
        view_all.setFont(self._theme.font("caption"))
        view_all.setStyleSheet(
            f"color: {colors.accent_cyan}; background: transparent; padding: 2px 6px;"
        )
        view_all.setCursor(Qt.CursorShape.PointingHandCursor)
        rp_header.addWidget(view_all)
        content_layout.addLayout(rp_header)

        self._recent_projects_layout = QVBoxLayout()
        self._recent_projects_layout.setSpacing(4)
        content_layout.addLayout(self._recent_projects_layout)

        # --- Recent Exports section ---
        re_header = QHBoxLayout()
        re_title = QLabel("RECENT EXPORTS")
        re_title.setFont(self._theme.font("caption"))
        re_title.setStyleSheet(
            f"color: {colors.text_muted}; background: transparent; letter-spacing: 1px;"
        )
        re_header.addWidget(re_title)
        re_header.addStretch(1)
        re_view_all = QLabel("View All")
        re_view_all.setFont(self._theme.font("caption"))
        re_view_all.setStyleSheet(
            f"color: {colors.accent_cyan}; background: transparent; padding: 2px 6px;"
        )
        re_view_all.setCursor(Qt.CursorShape.PointingHandCursor)
        re_header.addWidget(re_view_all)
        content_layout.addLayout(re_header)

        self._recent_exports_layout = QVBoxLayout()
        self._recent_exports_layout.setSpacing(4)
        content_layout.addLayout(self._recent_exports_layout)

        content_layout.addStretch(1)

        scroll.setWidget(content)
        main_layout.addWidget(scroll)

    def _create_stat_box(self, number: str, label: str) -> QFrame:
        tokens = self._theme.tokens
        colors = tokens.colors

        box = QFrame()
        box.setObjectName("StatBox")
        box.setStyleSheet(
            f"#StatBox {{ background: {colors.surface_elevated}; "
            f"border: 1px solid {colors.border}; "
            f"border-radius: {tokens.radius.sm}px; }}"
        )
        col = QVBoxLayout(box)
        col.setContentsMargins(12, 10, 12, 10)
        col.setSpacing(2)

        num = QLabel(number)
        num.setFont(self._theme.font("h2"))
        num.setStyleSheet(f"color: {colors.text_primary}; background: transparent;")
        col.addWidget(num)

        lbl = QLabel(label)
        lbl.setFont(self._theme.font("caption"))
        lbl.setStyleSheet(f"color: {colors.text_muted}; background: transparent;")
        col.addWidget(lbl)

        return box

    def _create_recent_project_row(
        self, name: str, updated: str, duration: str
    ) -> QWidget:
        tokens = self._theme.tokens
        colors = tokens.colors

        row = QFrame()
        row.setObjectName("RecentProjectRow")
        row.setCursor(Qt.CursorShape.PointingHandCursor)
        row.setStyleSheet(
            f"#RecentProjectRow {{ background: transparent; border: none; border-radius: 4px; }} "
            f"#RecentProjectRow:hover {{ background: {colors.surface_elevated}; }}"
        )
        layout = QHBoxLayout(row)
        layout.setContentsMargins(4, 6, 4, 6)
        layout.setSpacing(10)

        # Thumbnail
        thumb = QFrame()
        thumb.setFixedSize(48, 32)
        thumb.setStyleSheet(
            f"background: qlineargradient(x1:0, y1:0, x2:1, y2:1, "
            f"stop:0 {colors.accent_purple}, stop:1 {colors.accent_blue}); "
            f"border-radius: 4px;"
        )
        layout.addWidget(thumb)

        # Project info
        info_col = QVBoxLayout()
        info_col.setSpacing(0)
        name_label = QLabel(name)
        name_label.setFont(self._theme.font("body_small"))
        name_label.setStyleSheet(f"color: {colors.text_primary}; background: transparent;")
        info_col.addWidget(name_label)
        updated_label = QLabel(updated)
        updated_label.setFont(self._theme.font("caption"))
        updated_label.setStyleSheet(f"color: {colors.text_muted}; background: transparent;")
        info_col.addWidget(updated_label)
        layout.addLayout(info_col, 1)

        # Duration
        dur_label = QLabel(duration)
        dur_label.setFont(self._theme.font("mono"))
        dur_label.setStyleSheet(f"color: {colors.text_secondary}; background: transparent;")
        layout.addWidget(dur_label)

        # Wire click to emit signal
        row.mouseReleaseEvent = lambda _e, n=name: self.recent_project_activated.emit(n)

        return row

    def _create_recent_export_row(
        self, filename: str, codec_info: str
    ) -> QWidget:
        tokens = self._theme.tokens
        colors = tokens.colors

        row = QFrame()
        row.setObjectName("RecentExportRow")
        row.setCursor(Qt.CursorShape.PointingHandCursor)
        row.setStyleSheet(
            f"#RecentExportRow {{ background: transparent; border: none; border-radius: 4px; }} "
            f"#RecentExportRow:hover {{ background: {colors.surface_elevated}; }}"
        )
        layout = QHBoxLayout(row)
        layout.setContentsMargins(4, 6, 4, 6)
        layout.setSpacing(10)

        # File icon
        icon_label = QLabel("🎬")
        icon_label.setFont(self._theme.font("body_small"))
        icon_label.setFixedSize(32, 32)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet(
            f"color: {colors.text_primary}; background: {colors.surface_overlay}; "
            f"border-radius: 4px;"
        )
        layout.addWidget(icon_label)

        # Export info
        info_col = QVBoxLayout()
        info_col.setSpacing(0)
        name_label = QLabel(filename)
        name_label.setFont(self._theme.font("body_small"))
        name_label.setStyleSheet(f"color: {colors.text_primary}; background: transparent;")
        info_col.addWidget(name_label)
        codec_label = QLabel(codec_info)
        codec_label.setFont(self._theme.font("caption"))
        codec_label.setStyleSheet(f"color: {colors.text_muted}; background: transparent;")
        info_col.addWidget(codec_label)
        layout.addLayout(info_col, 1)

        # Done badge
        badge = QLabel("● Done")
        badge.setFont(self._theme.font("caption"))
        badge.setStyleSheet(
            f"color: {colors.success}; background: transparent;"
        )
        layout.addWidget(badge)

        # Wire click to emit signal
        row.mouseReleaseEvent = lambda _e, f=filename: self.recent_export_activated.emit(f)

        return row

    def _refresh_data(self) -> None:
        """Refresh all dashboard data."""
        self._refresh_recent_projects()
        self._refresh_recent_exports()
        self._refresh_stats()

    def _refresh_stats(self) -> None:
        """Update stat boxes with real data from filesystem."""
        from pathlib import Path

        project_count = 0
        media_count = 0
        ai_count = 0
        export_count = 0

        try:
            # Count projects
            projects_dir = Path("projects")
            if projects_dir.exists():
                project_files = list(projects_dir.glob("*.ivproj.json"))
                project_count = len(project_files)

            # Count media files
            videos_dir = Path("videos")
            if videos_dir.exists():
                media_extensions = {'.mp4', '.mkv', '.mov', '.avi', '.webm', '.flv', '.m4v'}
                media_files = [f for f in videos_dir.iterdir()
                               if f.suffix.lower() in media_extensions]
                media_count = len(media_files)

            # Count AI tasks (from logs if available)
            if self._controller:
                try:
                    logs = self._controller.logs()
                    ai_count = len([l for l in logs if hasattr(l, 'phase') and l.phase])
                except Exception:
                    pass

            # Count exports
            output_dir = Path("output")
            if output_dir.exists():
                export_files = list(output_dir.glob("*.mp4"))
                export_count = len(export_files)

        except Exception:
            pass

        # Update stat box numbers by finding QLabel children
        for stat_box, count in [
            (self._stat_projects, project_count),
            (self._stat_media, media_count),
            (self._stat_ai, ai_count),
            (self._stat_exports, export_count),
        ]:
            for label in stat_box.findChildren(QLabel):
                # The number label is the first QLabel (before the text label)
                if label.text().isdigit() or label.text() == "0":
                    label.setText(str(count))
                    break

    def _refresh_recent_projects(self) -> None:
        """Populate recent projects list from real data only."""
        # Clear existing
        while self._recent_projects_layout.count():
            item = self._recent_projects_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        projects = []

        # Load real projects from recent.json
        try:
            from pathlib import Path
            import json
            recent_file = Path("projects") / "recent.json"
            if recent_file.exists():
                with open(recent_file) as f:
                    data = json.load(f)
                if isinstance(data, list) and data:
                    for entry in data[:5]:
                        if isinstance(entry, dict):
                            name = entry.get("name", "Untitled")
                            age = entry.get("modified", "Unknown")
                            projects.append((name, age, "00:00:00"))
        except Exception:
            pass

        if projects:
            for name, updated, duration in projects:
                row = self._create_recent_project_row(name, updated, duration)
                self._recent_projects_layout.addWidget(row)
        else:
            # Empty state
            empty = QLabel("No projects yet")
            empty.setFont(self._theme.font("body_small"))
            empty.setStyleSheet(f"color: {self._theme.tokens.colors.text_muted}; background: transparent;")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._recent_projects_layout.addWidget(empty)

    def _refresh_recent_exports(self) -> None:
        """Populate recent exports list from real data only."""
        # Clear existing
        while self._recent_exports_layout.count():
            item = self._recent_exports_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        exports = []

        # Load real exports from output directory
        try:
            from pathlib import Path
            output_dir = Path("output")
            if output_dir.exists():
                mp4_files = list(output_dir.glob("*.mp4"))
                if mp4_files:
                    for f in mp4_files[:5]:
                        size_mb = f.stat().st_size / (1024 * 1024)
                        exports.append((f.name, f"H.264 • {size_mb:.1f} MB"))
        except Exception:
            pass

        if exports:
            for filename, codec_info in exports:
                row = self._create_recent_export_row(filename, codec_info)
                self._recent_exports_layout.addWidget(row)
        else:
            # Empty state
            empty = QLabel("No exports yet")
            empty.setFont(self._theme.font("body_small"))
            empty.setStyleSheet(f"color: {self._theme.tokens.colors.text_muted}; background: transparent;")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._recent_exports_layout.addWidget(empty)

    def set_controller(self, controller) -> None:
        self._controller = controller
        self._refresh_data()
