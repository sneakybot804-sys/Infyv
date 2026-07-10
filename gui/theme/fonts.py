"""Font registration and base-font construction from typography tokens.

Bundled fonts (if any) under ``gui/assets/fonts`` are registered with the
:class:`QFontDatabase` so the configured family is available regardless of the
host system. When a bundled/system family is missing, Qt's own substitution
plus the token fallback stack keep typography working.
"""
from __future__ import annotations

from pathlib import Path
from typing import List

from PySide6.QtGui import QFont, QFontDatabase

from gui.theme.tokens import DesignTokens, TypeStyle

#: Directory holding optional bundled font files (``.ttf`` / ``.otf``).
FONTS_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"


def register_bundled_fonts(fonts_dir: Path = FONTS_DIR) -> List[str]:
    """Register every font file found in ``fonts_dir`` with Qt.

    Args:
        fonts_dir: Directory to scan for ``.ttf``/``.otf`` files.

    Returns:
        The list of font family names successfully registered (possibly
        empty when no fonts are bundled yet).
    """
    if not fonts_dir.is_dir():
        return []
    families: List[str] = []
    for path in sorted(fonts_dir.iterdir()):
        if path.suffix.lower() not in (".ttf", ".otf"):
            continue
        font_id = QFontDatabase.addApplicationFont(str(path))
        if font_id != -1:
            families.extend(QFontDatabase.applicationFontFamilies(font_id))
    return families


def make_qfont(tokens: DesignTokens, style: TypeStyle | None = None) -> QFont:
    """Build a :class:`QFont` for ``style`` (defaults to the body style).

    The primary family is requested; Qt falls back through its substitution
    table (seeded by the token fallback families) if it is unavailable.
    """
    typography = tokens.typography
    chosen = style or typography.body
    font = QFont(typography.family_primary)
    font.setPixelSize(chosen.size_px)
    font.setWeight(QFont.Weight(chosen.weight))
    if chosen.letter_spacing:
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, chosen.letter_spacing)
    # Seed Qt's fallback resolution with the token fallback families.
    font.setFamilies([typography.family_primary, *typography.fallback_families])
    return font
