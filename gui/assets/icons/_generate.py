"""One-shot generator for the bundled Lucide-style icon set.

Writes monochrome stroke SVGs (viewBox 0 0 24 24, ``stroke="currentColor"``)
into this directory so :class:`gui.theme.icons.IconLoader` can recolor them to
any theme token. Icon geometry follows the Lucide (ISC-licensed) visual style;
paths are hand-authored equivalents, not copied verbatim. Run once:

    python gui/assets/icons/_generate.py

Existing ``play.svg`` / ``spark.svg`` are left untouched.
"""
from __future__ import annotations

from pathlib import Path

_HEADER = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
    'width="24" height="24" fill="none" stroke="currentColor" '
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
)

# name -> inner SVG body (paths/shapes). currentColor is used for stroke.
ICONS: dict[str, str] = {
    # --- Window controls ---
    "minus": '<path d="M5 12h14"/>',
    "square": '<rect x="5" y="5" width="14" height="14" rx="1.5"/>',
    "restore": '<rect x="8" y="8" width="11" height="11" rx="1.5"/>'
               '<path d="M5 16V6a1.5 1.5 0 0 1 1.5-1.5H16"/>',
    "x": '<path d="M18 6 6 18M6 6l12 12"/>',
    # --- Header ---
    "search": '<circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/>',
    "bell": '<path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"/>'
            '<path d="M13.7 21a2 2 0 0 1-3.4 0"/>',
    "help-circle": '<circle cx="12" cy="12" r="9"/>'
                   '<path d="M9.1 9a3 3 0 0 1 5.8 1c0 2-3 3-3 3"/>'
                   '<path d="M12 17h.01"/>',
    "chevron-down": '<path d="M6 9l6 6 6-6"/>',
    # --- Toolbar ---
    "file-plus": '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/>'
                 '<path d="M14 3v5h5"/><path d="M12 12v6M9 15h6"/>',
    "folder-open": '<path d="M3 8V6a2 2 0 0 1 2-2h4l2 2h6a2 2 0 0 1 2 2v1"/>'
                   '<path d="M3 8h17l-2 9a2 2 0 0 1-2 1.6H5A2 2 0 0 1 3 17z"/>',
    "save": '<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/>'
            '<path d="M17 21v-8H7v8"/><path d="M7 3v5h8"/>',
    "download": '<path d="M12 3v12"/><path d="M7 11l5 4 5-4"/>'
                '<path d="M5 21h14"/>',
    "upload": '<path d="M12 21V9"/><path d="M7 13l5-4 5 4"/>'
              '<path d="M5 3h14"/>',
    "disc": '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="3"/>',
    "sparkles": '<path d="M12 3l1.8 4.9L18.5 10l-4.7 2.1L12 17l-1.8-4.9L5.5 10l4.7-2.1z"/>'
                '<path d="M19 15l.7 2 .3.3.7.7-2 .7-.7 2-.7-2-2-.7 2-.7z"/>',
    "scissors": '<circle cx="6" cy="6" r="3"/><circle cx="6" cy="18" r="3"/>'
                '<path d="M8.1 8.1 20 20"/><path d="M8.1 15.9 20 4"/>'
                '<path d="M14.5 9.5 20 4"/>',
    "activity": '<path d="M3 12h4l3 8 4-16 3 8h4"/>',
    "wand": '<path d="M15 4V2M15 10V8M12.5 5.5H10.5M19.5 5.5h-2"/>'
            '<path d="M15 5.5 4 16.5 6 18.5 17 7.5z"/>',
    "clapperboard": '<path d="M4 8h16v11a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1z"/>'
                    '<path d="M4 8 5.5 3.5 9 4.5 7.5 9M9 4.5 12.5 5.5 11 10"/>',
    # --- Nav ---
    "layout-dashboard": '<rect x="3" y="3" width="7" height="9" rx="1"/>'
                        '<rect x="14" y="3" width="7" height="5" rx="1"/>'
                        '<rect x="14" y="12" width="7" height="9" rx="1"/>'
                        '<rect x="3" y="16" width="7" height="5" rx="1"/>',
    "folder": '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    "image": '<rect x="3" y="3" width="18" height="18" rx="2"/>'
             '<circle cx="9" cy="9" r="1.6"/>'
             '<path d="M21 15l-5-5L5 21"/>',
    "package": '<path d="M12 2 21 7v10l-9 5-9-5V7z"/>'
               '<path d="M3 7l9 5 9-5M12 12v10"/>',
    "bot": '<rect x="4" y="8" width="16" height="12" rx="2"/>'
           '<path d="M12 8V4M9 2h6"/>'
           '<circle cx="9" cy="14" r="1"/><circle cx="15" cy="14" r="1"/>',
    "layout-template": '<rect x="3" y="3" width="18" height="7" rx="1"/>'
                       '<rect x="3" y="14" width="9" height="7" rx="1"/>'
                       '<rect x="16" y="14" width="5" height="7" rx="1"/>',
    "zap": '<path d="M13 2 4 14h7l-2 8 9-12h-7z"/>',
    "audio-lines": '<path d="M2 12h1M6 8v8M10 5v14M14 8v8M18 10v4M22 12h-1"/>',
    "settings": '<circle cx="12" cy="12" r="3"/>'
                '<path d="M12 2v3M12 19v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1'
                'M2 12h3M19 12h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1"/>',
    # --- Transport ---
    "play": '<path d="M7 4v16l13-8z"/>',
    "pause": '<path d="M9 4v16M15 4v16"/>',
    "stop": '<rect x="6" y="6" width="12" height="12" rx="1.5"/>',
    "skip-back": '<path d="M18 5v14L8 12z"/><path d="M6 5v14"/>',
    "skip-forward": '<path d="M6 5v14l10-7z"/><path d="M18 5v14"/>',
    "rewind": '<path d="M11 6 4 12l7 6z"/><path d="M20 6l-7 6 7 6z"/>',
    "fast-forward": '<path d="M13 6l7 6-7 6z"/><path d="M4 6l7 6-7 6z"/>',
    "repeat": '<path d="M17 2l4 4-4 4"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/>'
              '<path d="M7 22l-4-4 4-4"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/>',
    "camera": '<path d="M4 8a2 2 0 0 1 2-2h1.5l1.2-2h6.6l1.2 2H20a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2z"/>'
              '<circle cx="12" cy="12.5" r="3.2"/>',
    "mic": '<rect x="9" y="3" width="6" height="11" rx="3"/>'
           '<path d="M5 11a7 7 0 0 0 14 0M12 18v3"/>',
    "webcam": '<circle cx="12" cy="10" r="7"/><circle cx="12" cy="10" r="2.5"/>'
              '<path d="M7 21h10M12 17v4"/>',
    "volume-2": '<path d="M4 9v6h4l5 4V5L8 9z"/>'
                '<path d="M16 8.5a4 4 0 0 1 0 7M18.5 6a7 7 0 0 1 0 12"/>',
    # --- Edit toolbar ---
    "undo-2": '<path d="M9 7 4 12l5 5"/>'
              '<path d="M4 12h11a5 5 0 0 1 0 10h-3"/>',
    "redo-2": '<path d="M15 7l5 5-5 5"/>'
              '<path d="M20 12H9a5 5 0 0 0 0 10h3"/>',
    "trash-2": '<path d="M4 7h16M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>'
               '<path d="M6 7l1 13a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1l1-13"/>'
               '<path d="M10 11v6M14 11v6"/>',
    "zoom-in": '<circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/>'
               '<path d="M11 8v6M8 11h6"/>',
    "zoom-out": '<circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/>'
                '<path d="M8 11h6"/>',
    "split": '<path d="M16 3h5v5M21 3l-7 7M8 21H3v-5M3 21l7-7"/>',
    "type": '<path d="M4 7V5h16v2M9 5v14M9 19h6"/>',
    # --- Timeline track headers ---
    "eye": '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z"/>'
           '<circle cx="12" cy="12" r="3"/>',
    "eye-off": '<path d="M9.9 5.2A9 9 0 0 1 12 5c6.5 0 10 7 10 7a13 13 0 0 1-2.4 3.1"/>'
               '<path d="M6.3 6.3A13 13 0 0 0 2 12s3.5 7 10 7a9 9 0 0 0 4-.9"/>'
               '<path d="M9.9 9.9a3 3 0 0 0 4.2 4.2M2 2l20 20"/>',
    "lock": '<rect x="5" y="11" width="14" height="9" rx="2"/>'
            '<path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
    "unlock": '<rect x="5" y="11" width="14" height="9" rx="2"/>'
              '<path d="M8 11V8a4 4 0 0 1 7.5-2"/>',
    "link-2": '<path d="M9 12h6"/>'
              '<path d="M8 7H6a5 5 0 0 0 0 10h2M16 7h2a5 5 0 0 1 0 10h-2"/>',
    # --- Sidebar system ---
    "cpu": '<rect x="6" y="6" width="12" height="12" rx="2"/>'
           '<rect x="9.5" y="9.5" width="5" height="5" rx="1"/>'
           '<path d="M9 2v2M15 2v2M9 20v2M15 20v2M2 9h2M2 15h2M20 9h2M20 15h2"/>',
    "memory-stick": '<path d="M4 8h16v7l-2 3H6l-2-3z"/>'
                    '<path d="M8 8V5M12 8V5M16 8V5M8 18v2M16 18v2"/>',
    "monitor": '<rect x="3" y="4" width="18" height="12" rx="2"/>'
               '<path d="M8 20h8M12 16v4"/>',
    "gauge": '<path d="M3 15a9 9 0 1 1 18 0"/>'
             '<path d="M12 15l4-4"/><circle cx="12" cy="15" r="1.4"/>',
}


def main() -> None:
    out = Path(__file__).resolve().parent
    for name, body in ICONS.items():
        svg = f"{_HEADER}{body}</svg>\n"
        (out / f"{name}.svg").write_text(svg, encoding="utf-8")
    print(f"wrote {len(ICONS)} icons to {out}")


if __name__ == "__main__":
    main()
