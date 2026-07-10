# Phase 8B — Theme Foundation

Phase 8B adds the theme layer under `gui/`. Qt begins here; `gui_core` (Phase
8A, frozen) stays completely Qt-free. This phase is **theme foundation only**:
no widgets, pages, dashboard, main window, animations, business logic, or
backend wiring.

## Layering

```
DesignTokens (pure data, no Qt)
        |
   builder modules (colorutils, qss, palette_builder, fonts, motion)
        |
   ThemeManager  <-- the ONLY public theme entry point
        |
   QApplication (stylesheet + palette + fonts)
```

Future widgets must request colors, spacing, typography and motion through
`ThemeManager` (via `ThemeManager.tokens`), never by importing token modules
directly.

## Modules

* **`gui/theme/tokens.py`** — pure-data frozen dataclasses, no Qt import
  (no `QColor`/`QPalette`/`QFont`/`QEasingCurve`): colors (layered dark
  backgrounds, glass fill/border/highlight, blue/cyan/purple neon accents each
  with a glow, semantic text and status), typography (family stack + modular
  scale), spacing, radius, shadows, blur, motion (durations + easing names),
  elevation. `DesignTokens` aggregates them with `name`/`is_dark` so the same
  shape supports future themes.
* **`gui/theme/palettes.py`** — `DARK_TOKENS`, the only registered theme and
  the single place color/scale literals are written (every color is an
  explicit readable value). No light palette or placeholder colors.
* **`gui/theme/colorutils.py`** — the sole conversion point between token
  strings and `QColor` / QSS strings.
* **`gui/theme/qss.py`** — `build_stylesheet(tokens)`; the only place tokens
  are emitted into stylesheet text (QSS has no variables). No color literals
  outside tokens.
* **`gui/theme/palette_builder.py`** — maps tokens onto `QPalette` roles.
* **`gui/theme/fonts.py`** — registers bundled fonts; builds the base `QFont`.
* **`gui/theme/motion.py`** — maps easing names to `QEasingCurve`.
* **`gui/theme/dpi.py`** — high-DPI rounding policy + token-aware `scale()`.
* **`gui/theme/icons.py`** — SVG loader that recolors `currentColor` to a
  token color, renders at size/DPR, and caches.
* **`gui/theme/manager.py`** — `ThemeManager`, the single authority. Registers
  only dark; `set_theme("light")` raises `NotImplementedError`. `apply(app)`
  installs stylesheet + palette + fonts. Change notification is a plain
  callback (no Qt signal) so it is headless-testable.
* **`gui/app_theme_preview.py`** — minimal dev-only smoke test: QApplication +
  `ThemeManager.apply` + empty window + exit.

## Constraints honoured

* No hardcoded colors anywhere except the token definitions in `palettes.py`.
* Token layer is fully Qt-free; Qt conversion lives only in the builders.
* Qt-free token tests import no PySide6; Qt tests use `importorskip` and run
  under the `offscreen` platform, so the Phase 8A suite is unaffected.
* PySide6 pinned `>=6.7,<6.8`, used only by `gui/`.

## Testing

* `tests/test_gui_theme_tokens.py` — Qt-free token integrity + a source-text
  guard that `gui/theme/tokens.py` references no Qt symbol.
* `tests/test_gui_theme_qt.py` — offscreen Qt tests for colorutils, qss,
  palette, icons and the manager; skipped entirely without PySide6.
