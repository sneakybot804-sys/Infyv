# Phase 8C-5 - Advanced Interactive Controls

Phase 8C-5 adds three generic, reusable **advanced interactive** widgets to
the widget library under `gui/widgets/`: a single-select dropdown, a
continuous numeric slider and a single-choice segmented control. They contain
no application, video-editing, page-layout or dashboard concepts and never
import `gui_core` or any backend module.

They follow every Phase 8B/8C rule: each subclasses `ThemedWidget`, takes an
injected `ThemeManager` as its first argument, resolves all visual values
through that manager, and generates any QSS only via `gui/widgets/styling.py`.
None imports `gui.theme.tokens/palettes/motion/colorutils`. All are High-DPI
aware, focusable with the neon focus ring, and set an accessible name.

## Animation & no-QGraphicsEffect policy (frozen)

No animation in 8C-5. None of these widgets install any `QGraphicsEffect` --
no opacity effect, drop shadow, glow, or nested effect; all visual state is
QSS. This guarantees GlassCard-safety. The Dropdown popup is Qt's native
top-level popup window, outside any effect subtree.

## Widgets and frozen public API

### Dropdown (`dropdown.py`)
Single-select control composing an inner `QComboBox`.

* `Dropdown(theme, *, items=(), current=0, accent='cyan', parent=None)`
* `set_items(items)`, `items() -> list[str]`
* `set_current_index(int)` (no-op when unchanged), `current_index() -> int`
* `current_text() -> str`
* `set_accent(str)` (no-op when unchanged); property `accent`
* Signal: `changed(int)` (new current index)
* Accent (frozen): `blue`, `cyan`, `purple`; invalid -> `ValueError`.
  Out-of-range index -> `ValueError`. Empty items -> index `-1`, text `''`.
* Accessibility: explicit `setAccessibleName(...)` wins; otherwise
  `current_text()` or `"dropdown"`.

### Slider (`slider.py`)
Continuous float-range control composing an inner horizontal `QSlider`.

* `Slider(theme, *, minimum=0.0, maximum=1.0, value=0.0, accent='cyan',
  parent=None)`
* `set_value(float)` (clamped), `value() -> float`
* `set_range(minimum, maximum)`, `minimum() -> float`, `maximum() -> float`
* `set_accent(str)` (no-op when unchanged); property `accent`
* Signal: `value_changed(float)`
* Accent (frozen): `blue`, `cyan`, `purple`; invalid -> `ValueError`.
  `minimum >= maximum` -> `ValueError`. Value out of range is clamped.
* Accessibility: explicit `setAccessibleName(...)` wins; otherwise
  `"Slider <current value>"` (e.g. `"Slider 0.5"`, `"Slider 75"`).
* Continuous only (no `step` in the public API).

### SegmentedControl (`segmented_control.py`)
Single-choice inline selector composing an exclusive `QButtonGroup` of
checkable `QPushButton` segments.

* `SegmentedControl(theme, options, *, current=0, accent='cyan', parent=None)`
* `set_options(options)`, `options() -> list[str]`
* `set_current_index(int)` (no-op when unchanged), `current_index() -> int`
* `current_text() -> str`
* `set_accent(str)` (no-op when unchanged); property `accent`
* Signal: `changed(int)` (new current index)
* Accent (frozen): `blue`, `cyan`, `purple`; invalid -> `ValueError`.
  Requires at least 2 options -> `ValueError`. Out-of-range -> `ValueError`.
* Accessibility: explicit `setAccessibleName(...)` wins; otherwise
  `current_text()` or `"segmented control"`; each segment carries its label.

## Frozen public API

After 8C-5, the public API of Dropdown, Slider and SegmentedControl is
considered stable and should not change unless a bug is found.

## styling.py additions (pure, no imports)

8C-5 adds only additive, side-effect-free builders: `dropdown_qss`,
`slider_qss`, and `segmented_control_qss`. Existing builders and their
signatures are unchanged.
