# Phase 8C-4 - Interactive Primitives

Phase 8C-4 adds three generic, reusable **interactive** widgets to the widget
library under `gui/widgets/`: an on/off switch, a labeled checkbox and a
single-line text field. They contain no application, video-editing,
page-layout or dashboard concepts and never import `gui_core` or any backend
module.

They follow every Phase 8B/8C rule: each subclasses `ThemedWidget`, takes an
injected `ThemeManager` as its first argument, resolves all visual values
through that manager, and generates any QSS only via `gui/widgets/styling.py`.
None imports `gui.theme.tokens/palettes/motion/colorutils`. All are High-DPI
aware, focusable with the neon focus ring, and set an accessible name.

## No-QGraphicsEffect policy (frozen)

None of these widgets install any `QGraphicsEffect` -- no opacity effect, no
drop shadow, no nested effect. This guarantees they render correctly inside an
effect-bearing container such as `GlassCard` (whose drop-shadow effect cannot
have another effect in its source subtree). ToggleSwitch's knob motion is a
`QVariantAnimation` driving a plain float knob position plus QSS state; there
is no graphics effect anywhere. Checkbox and TextField have no animation.

## Widgets and frozen public API

### ToggleSwitch (`toggle_switch.py`)
An on/off switch composing an inner `QCheckBox` (native Space toggling) with a
QSS-styled track and a position-animated knob.

* `ToggleSwitch(theme, *, checked=False, accent='cyan', animated=True,
  parent=None)`
* `set_checked(bool)` (no-op when unchanged), `is_checked() -> bool`
* `set_accent(str)` (no-op when unchanged); properties `accent`, `checked`
* Signal: `toggled(bool)`
* Accent vocabulary (frozen): `blue`, `cyan`, `purple`. Invalid accent raises
  `ValueError`.
* Accessibility: an explicit `QWidget.setAccessibleName(...)` always takes
  precedence; otherwise the accessible name is `"On"`/`"Off"` and tracks the
  checked state.
* Motion: knob slide via `QVariantAnimation` (float position) + QSS; when
  `animated=False` the end state is applied instantly (reduce-motion). No
  graphics effect.

### Checkbox (`checkbox.py`)
A labeled checkbox composing an inner `QCheckBox`.

* `Checkbox(theme, text='', *, checked=False, accent='cyan', parent=None)`
* `set_checked(bool)` (no-op when unchanged), `is_checked() -> bool`
* `set_text(str)`, `text() -> str`
* `set_accent(str)` (no-op when unchanged); properties `checked`, `accent`
* Signal: `toggled(bool)`
* Accent vocabulary (frozen): `blue`, `cyan`, `purple`. Invalid accent raises
  `ValueError`.
* Accessibility: an explicit `setAccessibleName(...)` always takes precedence;
  otherwise the accessible name is the label text, or `"checkbox"` when empty.
* No animation, no graphics effect.

### TextField (`text_field.py`)
A single-line text input composing an inner `QLineEdit` (native entry, caret,
selection, clipboard, IME).

* `TextField(theme, *, text='', placeholder='', parent=None)`
* `set_text(str)` (no-op when unchanged), `text() -> str`
* `set_placeholder(str)`, `placeholder() -> str`
* `clear()`
* Signals: `text_changed(str)`, `return_pressed()`, `editing_finished()`
* Accessibility: an explicit `setAccessibleName(...)` always takes precedence;
  otherwise the accessible name is the placeholder, or `"text field"` when
  empty.
* No animation, no graphics effect.

## Frozen public API

After 8C-4, the public API of ToggleSwitch, Checkbox and TextField is
considered stable and should not change unless a bug is found.

## styling.py additions (pure, no imports)

8C-4 adds only additive, side-effect-free builders: `toggle_switch_qss`,
`toggle_focus_qss`, `checkbox_qss`, and `text_field_qss`. Existing builders and
their signatures are unchanged.
