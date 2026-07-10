# Phase 8C — Reusable Widget Library

The widget library lives under `gui/widgets/`. It is built in verified
sub-steps (8C-1 infrastructure, 8C-2 primitives, ...). This document records
the conventions every widget follows and the public API of each widget so
future widgets stay consistent.

## Widget-layer rules

* Widgets receive a `ThemeManager` by **dependency injection** (first
  constructor argument); there is no global manager.
* Widgets obtain every resolved Qt value (`QColor`, `QFont`, `QEasingCurve`,
  durations) from the manager: `theme.color(...)`, `theme.font(...)`,
  `theme.easing(...)`, `theme.duration(...)`.
* Widgets must NOT import `gui.theme.tokens`, `gui.theme.palettes`,
  `gui.theme.motion`, `gui.theme.colorutils`, or `gui_core`. Allowed:
  `gui.theme.manager`, `gui.theme.dpi`, Qt, stdlib, and the widget-layer
  helpers (`styling`, `animation`, `effects`, `base`).
* Per-widget QSS is generated only in `gui/widgets/styling.py` (pure
  token-value -> QSS; no side effects).
* Optional motion goes through `gui/widgets/animation.py`; visual effects
  through `gui/widgets/effects.py`. Animations are reduce-motion aware
  (`animated=False` applies the final state instantly).
* Interactive widgets keep a SINGLE persistent graphics effect and reuse
  animation objects (no per-event allocation); rapid state changes stop and
  re-target the existing animation for clean interruption.
* High-DPI: sizes/radii pass through `ThemedWidget.scaled(...)`.
* Accessibility: interactive widgets are focusable with a visible focus ring
  and expose an accessible name; icon-only controls require one.

## Infrastructure (8C-1)

* `ThemedWidget` (base): stores the injected manager, restyles on theme
  change (`apply_theme` override hook), `scaled()`, `icon()`, cleanup.
* `styling.py`: token-value -> QSS builders.
* `animation.py`: `fade`, `fade_effect`, `tween_value` (Qt-only; caller passes
  resolved duration/easing).
* `effects.py`: `apply_shadow`, `apply_glow`, `apply_blur`, `clear_effect`.

## Primitives (8C-2)

### GlassCard
Rounded translucent container with a single persistent shadow/glow effect.

* `GlassCard(theme, *, radius='lg', glow=None, elevation='medium',
  animated=True, parent=None)`
* `set_content(widget)`, `content() -> QWidget | None`
* `set_glow(role | None)`, `set_elevation(level)`
* `glow_active() -> bool`
* Properties: `glow_role`, `elevation_level`
* Hover fades the glow in/out (blur + alpha) on the single effect; optional
  fade-in on first show. Not focusable (non-interactive container).

### NeonButton
Action button composing an inner `QPushButton`.

* `NeonButton(theme, text='', *, variant='primary', accent='cyan',
  icon_name=None, animated=True, parent=None)`
* `set_text(str)`, `text() -> str`, `set_icon(name | None)`
* `set_variant('primary'|'secondary'|'ghost')`, `set_accent(role)`
* `set_loading(bool)`
* Properties: `variant`, `accent`, `loading`
* Signal: `clicked()`
* Single persistent opacity effect + one reused animation for smooth,
  interruptible hover/press/release; focus ring; disabled state.

### IconButton
Icon-only button composing an inner `QToolButton`.

* `IconButton(theme, icon_name, *, accent='cyan', checkable=False,
  tooltip='', accessible_name='', animated=True, parent=None)`
* `set_icon(name)`, `set_accent(role)`, `set_checked(bool)`,
  `is_checked() -> bool`, `set_tooltip(str)`
* `set_context_menu(menu | None)`, `has_context_menu() -> bool`
* Properties: `accent`, `checkable`, `checked`
* Signals: `clicked()`, `toggled(bool)`
* Requires an accessible name (from `accessible_name`/`tooltip`/icon name).

### SectionHeader
Title + optional subtitle + optional badge + optional trailing action +
optional divider.

* `SectionHeader(theme, title, *, subtitle='', parent=None)`
* `set_title(str)`, `set_subtitle(str)`, `set_action(widget | None)`
* `set_badge(text | None, *, accent='cyan')`, `set_divider(bool)`
* `title() -> str`, `subtitle() -> str`,
  `badge_visible() -> bool`, `divider_visible() -> bool`
* Not interactive itself; the action slot may hold an interactive widget.

## Gallery

`gui/app_theme_preview.py` is a dev-only component gallery built exclusively
from these primitives with dummy content (token-driven margins/spacing,
aligned rows, consistent sizing, plus hover/disabled/loading examples). It is
not part of the application and wires no backend.

## Extension guidelines (authoring a new widget)

Follow these steps so future widgets match the established architecture:

1. **Subclass `ThemedWidget`** and take `theme: ThemeManager` as the first
   constructor argument. Call `super().__init__(theme, parent)`.
2. **Compose, don't deep-inherit.** Build the widget from Qt primitives or
   other themed widgets held as members. Re-expose only the signals you need.
3. **Resolve visuals through the manager**: `theme.color/font/easing/
   duration`. Never import `gui.theme.tokens/palettes/motion/colorutils` or
   `gui_core`.
4. **Put QSS in `styling.py`** as a pure `colors + scalars -> str` function;
   scale sizes/radii with `self.scaled(...)`.
5. **Override `apply_theme()`** to (re)build QSS/effects from `self.tokens`.
   Guard setters so they only call `apply_theme()` when state actually
   changes (avoid needless repaints).
6. **Create graphics effects and animations once** (in `__init__`) and reuse
   them. On interaction, `stop()` and re-target the existing animation from
   the current animated value; never allocate per event.
7. **Make motion optional and reduce-motion aware** (`animated` flag; when
   False, apply the end state instantly).
8. **Accessibility**: set an accessible name; make interactive widgets
   focusable with the neon focus ring; support Enter/Space activation.
9. **Public API**: expose intent-revealing methods/properties and small state
   accessors (e.g. `..._visible()`), not internal widgets. Add full type
   hints and docstrings.
10. **Tests**: prefer the public API; use white-box access only where Qt
    event delivery to a composed child is unavoidable, and don't expand it.

## Frozen public API

After 8C-2, the public API of GlassCard, NeonButton, IconButton and
SectionHeader is considered stable and should not change unless a bug is
found.

## Temporary implementation detail: NeonButton hover animation

A `QGraphicsEffect` cannot be nested inside another effect's source tree:
when a `NeonButton` carrying a `QGraphicsOpacityEffect` sits inside a
`GlassCard` (which uses a `QGraphicsDropShadowEffect`), Qt fails to render the
card to its offscreen pixmap and prints 'Painter not active' warnings, leaving
the card blank.

As a **temporary** measure, NeonButton's animated opacity effect was removed;
hover/pressed/disabled feedback now comes from QSS state rules only. This
keeps the public API unchanged and the gallery rendering correctly with no
QPainter warnings.

**Planned restoration:** reintroduce richer hover/press animation using a
rendering-safe approach that does not nest graphics effects -- for example an
animated custom `Q_PROPERTY` driving a dynamic stylesheet, or a color/geometry
tween on the inner button. Because the public API is stable, this change will
be internal only.
