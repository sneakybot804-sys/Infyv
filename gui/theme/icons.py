"""SVG icon infrastructure: load, recolor to a token color, cache.

Icons are stored as monochrome SVGs under ``gui/assets/icons``. The loader
rewrites the SVG's fill to a theme token color so icons follow the neon
palette, renders them crisply at a requested size and device pixel ratio, and
caches the result. Icon colors therefore also come only from tokens.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple

from PySide6.QtCore import QByteArray, QRectF, QSize, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

#: Directory holding SVG icon sources.
ICONS_DIR = Path(__file__).resolve().parent.parent / "assets" / "icons"

_CacheKey = Tuple[str, str, int, int, float]


class IconLoader:
    """Load and recolor SVG icons, caching rendered pixmaps/icons."""

    def __init__(self, icons_dir: Path = ICONS_DIR) -> None:
        """Create a loader bound to ``icons_dir``."""
        self._icons_dir = icons_dir
        self._pixmaps: Dict[_CacheKey, QPixmap] = {}

    def _read_svg(self, name: str) -> str:
        """Return the raw SVG text for icon ``name`` (without extension)."""
        path = self._icons_dir / f"{name}.svg"
        if not path.is_file():
            raise FileNotFoundError(f"Icon not found: {path}")
        return path.read_text(encoding="utf-8")

    @staticmethod
    def _recolor(svg: str, color: str) -> str:
        """Return ``svg`` with its fill color replaced by ``color``.

        Icons use the literal placeholder ``currentColor`` for their fill; this
        swaps in the concrete theme color at render time.
        """
        return svg.replace("currentColor", color)

    def pixmap(
        self,
        name: str,
        color: str,
        size: int,
        dpr: float = 1.0,
    ) -> QPixmap:
        """Render icon ``name`` in ``color`` at ``size`` px (cached).

        Args:
            name: Icon file stem under the icons directory.
            color: A theme color token string (hex or rgba).
            size: Target square size in logical pixels.
            dpr: Device pixel ratio for crisp rendering.
        """
        key: _CacheKey = (name, color, size, size, dpr)
        cached = self._pixmaps.get(key)
        if cached is not None:
            return cached

        svg = self._recolor(self._read_svg(name), color)
        renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))

        pixel_size = max(1, int(round(size * dpr)))
        pixmap = QPixmap(QSize(pixel_size, pixel_size))
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        try:
            renderer.render(painter, QRectF(0, 0, pixel_size, pixel_size))
        finally:
            painter.end()
        pixmap.setDevicePixelRatio(dpr)

        self._pixmaps[key] = pixmap
        return pixmap

    def icon(self, name: str, color: str, size: int, dpr: float = 1.0) -> QIcon:
        """Return a :class:`QIcon` for icon ``name`` in ``color``."""
        return QIcon(self.pixmap(name, color, size, dpr))
