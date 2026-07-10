# Phase 8C-3 - Information & Progress Widgets

Phase 8C-3 adds four generic, reusable **presentation** widgets to the widget
library under `gui/widgets/`. They display status, text, progress and simple
statistics. They contain no application, video-editing, page-layout or
dashboard concepts and never import `gui_core` or any backend module.

They follow every Phase 8B/8C rule: each subclasses `ThemedWidget`, takes an
injected `ThemeManager` as its first argument, resolves all visual values
through that manager, and generates any QSS only via `gui/widgets/styling.py`.
None imports `gui.theme.tokens/palettes/motion/colorutils`. All are High-DPI
aware, set an accessible name, and install **no** `QGraphicsEffect` (which
guards the nested-effect rendering hazard seen in 8C-2).

## Widgets and frozen public API

### StatusBadge (`status_badge.py`)
A non-interactive status pill.

* `StatusBadge(theme, text='', *, status='neutral', parent=None)`
* `set_text(str)`, `text() -> str`
* `set_status(str)` (no-op when unchanged), `status() -> str`
* Status vocabulary (frozen): `neutral`, `info`, `success`, `warning`,
  `error`. An invalid status raises `ValueError` (no silent fallback).
* No animation, no graphics effect.

### MetaLabel (`meta_label.py`)
A typography- and color-role-aware text label.

* `MetaLabel(theme, text='', *, role='secondary', style='body', parent=None)`
* `set_text(str)`, `text() -> str`
* `set_role(str)` (no-op when unchanged), `role() -> str` - roles: `primary`,
  `secondary`, `muted`, `disabled`.
* `set_style(str)` (no-op when unchanged), `style() -> str` - styles are
  exactly those exposed by `ThemeManager.font(...)`: `display`, `h1`, `h2`,
  `h3`, `body`, `body_small`, `caption`, `mono`.
* An invalid role or style raises `ValueError`.

### ProgressBar (`progress_bar.py`)
A determinate/indeterminate linear progress indicator composing an inner
`QProgressBar`.

* `ProgressBar(theme, *, value=0.0, indeterminate=False, accent='cyan',
  animated=True, parent=None)`
* `set_value(float)` (clamped to `0.0..1.0`), `value() -> float`
* `set_indeterminate(bool)` (no-op when unchanged), `is_indeterminate() -> bool`
* `set_accent(str)` (no-op when unchanged), `accent() -> str`
* Accent vocabulary (frozen): `blue`, `cyan`, `purple`. An invalid accent
  raises `ValueError`.
* Paint/QSS based only; no `QGraphicsEffect`. Reduce-motion aware: when
  `animated=False`, the indeterminate busy sweep is not run.

### StatBlock (`stat_block.py`)
A value + label (+ optional subtitle) statistic block that composes
`MetaLabel` members.

* `StatBlock(theme, label='', value='', *, subtitle='', parent=None)`
* `set_label(str)`, `label() -> str`
* `set_value(str)`, `value() -> str`
* `set_subtitle(str)`, `subtitle() -> str`
* When the subtitle is empty the subtitle row is hidden **and** the column
  spacing collapses to zero (no reserved gap).

## Frozen public API

After 8C-3, the public API of StatusBadge, MetaLabel, ProgressBar and
StatBlock is considered stable and should not change unless a bug is found.

## styling.py additions (pure, no imports)

8C-3 adds only additive, side-effect-free builders: `status_badge_qss`,
`progress_track_qss`, and `progress_chunk_qss`. Existing builders and their
signatures are unchanged.
