"""ClipInspector: a UI-only, read-only clip properties panel (Phase 8H, M4).

Displays the properties of a selected timeline clip: its label, track index,
start time and length. It is a pure presentation widget -- read-only, with an
explicit empty state when nothing is selected. It depends only on the injected
:class:`ThemeManager` and composes the frozen :class:`SectionHeader` and
:class:`MetaLabel` widgets.

Milestone 4 is UI-only: there is NO backend, NO :mod:`gui_core`, NO playback,
NO drag-and-drop, NO trim/split and NO editing. The inspector merely reflects
whatever clip mapping it is given via :meth:`show_clip`; it emits no signals.

Phase 10B (professional property editor, UI-only, additive): beneath the four
frozen property rows the inspector now hosts a scrollable, professional
property-editor body -- collapsible sections (Transform, Motion, Video, Audio,
AI, Effects, Metadata) whose rows compose the existing widget library
(Slider, Dropdown, SegmentedControl, ToggleSwitch, Checkbox, MetaLabel,
NeonButton). These are decorative, placeholder controls wired to nothing; they
are always present and are independent of the empty/populated visibility of
the four legacy fields, so the frozen state machine and its tests are
untouched.

Stable object names for later integration and tests:

* ``ClipInspector`` -- the root widget
* ``ClipInspectorHeader`` -- the section header
* ``ClipInspectorEmpty`` -- the empty-state label (visible when no clip)
* ``ClipInspectorField`` -- each legacy property row (a MetaLabel); exactly 4

Additive Phase 10B object names (placeholder property editor):

* ``ClipInspectorBody`` -- the scrollable property-editor body
* ``ClipInspectorSection`` -- each collapsible section's header
* ``ClipInspectorSectionToggle`` -- the expand/collapse toggle button
* ``ClipInspectorPropertyRow`` -- each labeled control row
* ``ClipInspectorRowLabel`` -- the left-hand row label
* ``ClipInspectorReset`` -- an optional per-row reset affordance
"""
from __future__ import annotations

from typing import Dict, List, Optional

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from gui.theme.manager import ThemeManager
from gui.widgets.base import ThemedWidget
from gui.widgets.checkbox import Checkbox
from gui.widgets.dropdown import Dropdown
from gui.widgets.meta_label import MetaLabel
from gui.widgets.neon_button import NeonButton
from gui.widgets.section_header import SectionHeader
from gui.widgets.segmented_control import SegmentedControl
from gui.widgets.slider import Slider
from gui.widgets.toggle_switch import ToggleSwitch

#: A clip is a plain mapping (as produced by the Timeline widget).
Clip = Dict[str, object]

#: Placeholder shown for a missing field value (kept out of f-string
#: expression braces so no backslash appears inside them).
_DASH = "\u2014"

#: Collapsed / expanded glyphs for the section toggle (text-only; no icon
#: asset dependency).
_CHEVRON_EXPANDED = "\u25be"  # black down-pointing small triangle
_CHEVRON_COLLAPSED = "\u25b8"  # black right-pointing small triangle


class _PropertySection(ThemedWidget):
    """A collapsible professional property section (UI-only placeholder).

    Composes a :class:`SectionHeader` with a text expand/collapse toggle and a
    glassy content frame that holds labeled property rows. The toggle only
    flips the local visibility of the content frame; it is wired to no logic.

    Args:
        theme: Injected theme manager (sole source of visual values).
        title: Section title (e.g. ``"Transform"``).
        subtitle: Optional muted subtitle under the title.
        expanded: Initial expanded state. Default ``True``.
        parent: Optional Qt parent.
    """

    def __init__(
        self,
        theme: ThemeManager,
        title: str,
        *,
        subtitle: str = "",
        expanded: bool = True,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(theme, parent)
        self.setObjectName("ClipInspectorSectionRoot")
        self._title = title
        self._expanded = bool(expanded)
        self._rows: List[QWidget] = []

        tokens = self.tokens

        self._column = QVBoxLayout(self)
        self._column.setContentsMargins(0, 0, 0, 0)
        self._column.setSpacing(tokens.spacing.xs)

        # Header with a trailing expand/collapse toggle.
        self._header = SectionHeader(self._theme, title, subtitle=subtitle)
        self._header.setObjectName("ClipInspectorSection")
        self._toggle = NeonButton(
            self._theme,
            self._chevron(),
            variant="ghost",
            accent="cyan",
        )
        self._toggle.setObjectName("ClipInspectorSectionToggle")
        self._toggle.clicked.connect(self._on_toggle)
        self._header.set_action(self._toggle)
        self._column.addWidget(self._header)

        # Glassy content frame holding the rows.
        self._content = QFrame(self)
        self._content.setObjectName("ClipInspectorSectionContent")
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(
            tokens.spacing.sm,
            tokens.spacing.sm,
            tokens.spacing.sm,
            tokens.spacing.sm,
        )
        self._content_layout.setSpacing(tokens.spacing.xs)
        self._column.addWidget(self._content)
        self._content.setVisible(self._expanded)

        self.apply_theme()

    # ------------------------------------------------------------------ #
    # Row building
    # ------------------------------------------------------------------ #
    def add_row(
        self,
        label: str,
        control: QWidget,
        *,
        resettable: bool = False,
    ) -> QWidget:
        """Append a labeled control row and return it (UI-only placeholder).

        Args:
            label: Left-hand property name (e.g. ``"Opacity"``).
            control: The reused library control shown on the right.
            resettable: When ``True``, add a ghost reset affordance wired to
                nothing.
        """
        tokens = self.tokens
        row = QWidget(self._content)
        row.setObjectName("ClipInspectorPropertyRow")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(
            tokens.spacing.xs,
            tokens.spacing.xxs,
            tokens.spacing.xs,
            tokens.spacing.xxs,
        )
        row_layout.setSpacing(tokens.spacing.sm)

        name = MetaLabel(self._theme, label, role="muted", style="body_small")
        name.setObjectName("ClipInspectorRowLabel")
        row_layout.addWidget(name, 0)

        row_layout.addStretch(1)
        row_layout.addWidget(control, 1)

        if resettable:
            reset = NeonButton(
                self._theme, "Reset", variant="ghost", accent="cyan"
            )
            reset.setObjectName("ClipInspectorReset")
            row_layout.addWidget(reset, 0)

        self._content_layout.addWidget(row)
        self._rows.append(row)
        return row

    def row_count(self) -> int:
        """Return the number of property rows in this section."""
        return len(self._rows)

    def title(self) -> str:
        """Return the section title."""
        return self._title

    def is_expanded(self) -> bool:
        """Return whether the section is currently expanded."""
        return self._expanded

    # ------------------------------------------------------------------ #
    # Collapse behaviour (UI-only)
    # ------------------------------------------------------------------ #
    def _chevron(self) -> str:
        """Return the glyph for the current expanded state."""
        return _CHEVRON_EXPANDED if self._expanded else _CHEVRON_COLLAPSED

    def _on_toggle(self) -> None:
        """Flip the local expanded state (no external effect)."""
        self._expanded = not self._expanded
        self._content.setVisible(self._expanded)
        self._toggle.set_text(self._chevron())

    # ------------------------------------------------------------------ #
    # Theming
    # ------------------------------------------------------------------ #
    def apply_theme(self) -> None:
        """Style the section content frame as a glassy property card."""
        colors = self.tokens.colors
        radius = self.tokens.radius.md
        self._content.setStyleSheet(
            f"#ClipInspectorSectionContent {{ "
            f"background: {colors.surface}; "
            f"border: 1px solid {colors.border}; "
            f"border-radius: {radius}px; }} "
            f"#ClipInspectorPropertyRow {{ background: transparent; }} "
            f"#ClipInspectorPropertyRow:hover {{ "
            f"background: {colors.surface_overlay}; "
            f"border-radius: {self.tokens.radius.sm}px; }}"
        )


class ClipInspector(ThemedWidget):
    """A read-only panel showing the selected clip's properties.

    Args:
        theme: Injected theme manager (sole source of visual values).
        parent: Optional Qt parent.

    The inspector starts in the empty state. Call :meth:`show_clip` with a clip
    mapping to populate it, or with ``None`` to return to the empty state.
    """

    def __init__(
        self,
        theme: ThemeManager,
        *,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(theme, parent)
        self.setObjectName("ClipInspector")
        self._current: Optional[Clip] = None
        self._sections: List[_PropertySection] = []

        tokens = self.tokens
        self._column = QVBoxLayout(self)
        self._column.setContentsMargins(
            tokens.spacing.md, tokens.spacing.md, tokens.spacing.md, tokens.spacing.md
        )
        self._column.setSpacing(tokens.spacing.sm)

        self._header = SectionHeader(
            self._theme, "Clip Inspector", subtitle="Selected clip"
        )
        self._header.setObjectName("ClipInspectorHeader")
        self._header.set_divider(True)
        self._column.addWidget(self._header)

        # Empty-state label (shown when no clip is selected).
        self._empty = MetaLabel(self._theme, "No clip selected")
        self._empty.setObjectName("ClipInspectorEmpty")
        self._column.addWidget(self._empty)

        # Property rows (hidden until a clip is shown).
        self._field_label = MetaLabel(self._theme, "Label: \u2014")
        self._field_track = MetaLabel(self._theme, "Track: \u2014")
        self._field_start = MetaLabel(self._theme, "Start: \u2014")
        self._field_length = MetaLabel(self._theme, "Length: \u2014")
        self._fields: List[MetaLabel] = [
            self._field_label,
            self._field_track,
            self._field_start,
            self._field_length,
        ]
        for field in self._fields:
            field.setObjectName("ClipInspectorField")
            field.setVisible(False)
            self._column.addWidget(field)

        # --- Phase 10B: professional property-editor body (additive) --- #
        # A scrollable body of collapsible property sections. It is always
        # present and independent of the empty/populated field visibility, so
        # it never interferes with the frozen state machine or its tests.
        self._body = QScrollArea(self)
        self._body.setObjectName("ClipInspectorBody")
        self._body.setWidgetResizable(True)
        self._body_container = QWidget()
        self._body_container.setObjectName("ClipInspectorBodyContainer")
        self._body_layout = QVBoxLayout(self._body_container)
        self._body_layout.setContentsMargins(0, 0, 0, 0)
        self._body_layout.setSpacing(tokens.spacing.sm)
        self._build_property_sections()
        self._body_layout.addStretch(1)
        self._body.setWidget(self._body_container)
        self._column.addWidget(self._body, 1)

        self.setAccessibleName("clip inspector")
        self.apply_theme()

    # ------------------------------------------------------------------ #
    # Professional property editor (Phase 10B, UI-only placeholders)
    # ------------------------------------------------------------------ #
    def _build_property_sections(self) -> None:
        """Populate the body with placeholder professional property sections.

        Every control is a reused library widget wired to nothing; the section
        list mirrors a real editor's inspector (Transform / Motion / Video /
        Audio / AI / Effects / Metadata).
        """
        theme = self._theme

        transform = self._add_section("Transform", subtitle="Position & scale")
        transform.add_row(
            "Position",
            SegmentedControl(theme, ["X", "Y"], current=0, accent="cyan"),
            resettable=True,
        )
        transform.add_row(
            "Scale",
            Slider(theme, minimum=0.0, maximum=400.0, value=100.0, accent="cyan"),
            resettable=True,
        )
        transform.add_row(
            "Rotation",
            Slider(theme, minimum=-180.0, maximum=180.0, value=0.0, accent="purple"),
            resettable=True,
        )
        transform.add_row(
            "Opacity",
            Slider(theme, minimum=0.0, maximum=100.0, value=100.0, accent="cyan"),
            resettable=True,
        )

        motion = self._add_section("Motion", subtitle="Speed & interpolation")
        motion.add_row(
            "Speed",
            Slider(theme, minimum=0.0, maximum=400.0, value=100.0, accent="cyan"),
            resettable=True,
        )
        motion.add_row(
            "Direction",
            SegmentedControl(
                theme, ["Forward", "Reverse"], current=0, accent="blue"
            ),
        )
        motion.add_row(
            "Frame Blend",
            ToggleSwitch(theme, checked=False, accent="cyan"),
        )

        video = self._add_section("Video", subtitle="Compositing")
        video.add_row(
            "Blend Mode",
            Dropdown(
                theme,
                items=["Normal", "Add", "Screen", "Multiply", "Overlay"],
                current=0,
                accent="cyan",
            ),
        )
        video.add_row(
            "Resolution",
            MetaLabel(theme, "1920 x 1080", role="secondary", style="mono"),
        )
        video.add_row(
            "Frame Rate",
            MetaLabel(theme, "60 fps", role="secondary", style="mono"),
        )
        video.add_row(
            "Codec",
            MetaLabel(theme, "H.264", role="secondary", style="mono"),
        )

        audio = self._add_section("Audio", subtitle="Levels")
        audio.add_row(
            "Volume",
            Slider(theme, minimum=0.0, maximum=200.0, value=100.0, accent="cyan"),
            resettable=True,
        )
        audio.add_row(
            "Pan",
            Slider(theme, minimum=-100.0, maximum=100.0, value=0.0, accent="blue"),
            resettable=True,
        )
        audio.add_row(
            "Mute",
            ToggleSwitch(theme, checked=False, accent="cyan"),
        )

        ai = self._add_section("AI", subtitle="Automatic enhancement")
        ai.add_row(
            "Auto Highlight",
            ToggleSwitch(theme, checked=True, accent="purple"),
        )
        ai.add_row(
            "Smart Reframe",
            ToggleSwitch(theme, checked=False, accent="cyan"),
        )
        ai.add_row(
            "Scene Confidence",
            MetaLabel(theme, "0.92", role="secondary", style="mono"),
        )

        effects = self._add_section("Effects", subtitle="Applied", expanded=False)
        effects.add_row(
            "Color Grade",
            Checkbox(theme, "Enabled", checked=False, accent="cyan"),
        )
        effects.add_row(
            "Sharpen",
            Checkbox(theme, "Enabled", checked=False, accent="blue"),
        )
        effects.add_row(
            "Glow",
            Checkbox(theme, "Enabled", checked=False, accent="purple"),
        )

        metadata = self._add_section(
            "Metadata", subtitle="Clip info", expanded=False
        )
        metadata.add_row(
            "Track",
            MetaLabel(theme, "V1", role="secondary", style="mono"),
        )
        metadata.add_row(
            "Duration",
            MetaLabel(theme, "00:00:20:00", role="secondary", style="mono"),
        )
        metadata.add_row(
            "Source",
            MetaLabel(theme, "gameplay.mp4", role="secondary", style="mono"),
        )

    def _add_section(
        self, title: str, *, subtitle: str = "", expanded: bool = True
    ) -> _PropertySection:
        """Create, register and mount a new property section; return it."""
        section = _PropertySection(
            self._theme, title, subtitle=subtitle, expanded=expanded
        )
        self._sections.append(section)
        self._body_layout.addWidget(section)
        return section

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def show_clip(self, clip: Optional[Clip]) -> None:
        """Display ``clip``'s properties, or the empty state when falsy.

        Args:
            clip: A clip mapping (keys ``label``/``track``/``start``/``length``)
                or ``None``. An empty mapping is treated as no selection.
        """
        if not clip:
            self.clear()
            return
        self._current = dict(clip)
        self._field_label.set_text(f"Label: {clip.get('label', _DASH)}")
        self._field_track.set_text(f"Track: {clip.get('track', _DASH)}")
        self._field_start.set_text(f"Start: {clip.get('start', _DASH)}")
        self._field_length.set_text(f"Length: {clip.get('length', _DASH)}")
        self._empty.setVisible(False)
        for field in self._fields:
            field.setVisible(True)

    def current(self) -> Optional[Clip]:
        """Return a copy of the currently shown clip, or ``None``."""
        return dict(self._current) if self._current is not None else None

    def clear(self) -> None:
        """Return to the empty state (no clip shown). Idempotent."""
        self._current = None
        for field in self._fields:
            field.setVisible(False)
        self._empty.setVisible(True)

    def is_empty(self) -> bool:
        """Return whether the inspector is currently in the empty state."""
        return self._current is None

    # ------------------------------------------------------------------ #
    # Theming
    # ------------------------------------------------------------------ #
    def apply_theme(self) -> None:
        """Apply premium property-panel styling to the inspector surfaces.

        Styling-only (Phase 10A/10B): object-name-scoped, token-derived QSS
        that renders each legacy property row as a glassy "property card",
        gives the empty state a calm, muted look, and makes the Phase 10B
        property-editor body read as a borderless, inset scroll region with a
        slim neon scrollbar. The composed SectionHeader / MetaLabel / control
        children keep their own self-theming; no logic, field text, visibility
        behavior, object name, signal or API is changed.
        """
        colors = self.tokens.colors
        radius = self.tokens.radius.md
        pad_v = self.tokens.spacing.xs
        pad_h = self.tokens.spacing.md

        # Empty state: muted, softly padded.
        self._empty.setStyleSheet(
            f"#ClipInspectorEmpty {{ color: {colors.text_muted}; "
            f"background: transparent; padding: {pad_v}px {pad_h}px; }}"
        )

        # Property rows rendered as glassy property cards: surface background,
        # rounded corners, a subtle border, comfortable padding and an
        # accent-tinted hover.
        field_qss = (
            f"#ClipInspectorField {{ color: {colors.text_secondary}; "
            f"background: {colors.surface_overlay}; "
            f"border: 1px solid {colors.border}; "
            f"border-radius: {radius}px; "
            f"padding: {pad_v}px {pad_h}px; }} "
            f"#ClipInspectorField:hover {{ "
            f"border: 1px solid {colors.accent_cyan}; "
            f"color: {colors.text_primary}; }}"
        )
        for field in self._fields:
            field.setStyleSheet(field_qss)

        # Property-editor body: borderless, transparent inset scroll region
        # with a slim, rounded, accent-hover scrollbar (matches the app's
        # premium scrollbar language).
        self._body.setStyleSheet(
            f"#ClipInspectorBody {{ background: transparent; border: none; }} "
            f"#ClipInspectorBody > QWidget > QWidget {{ background: transparent; }} "
            f"QScrollBar:vertical {{ background: transparent; "
            f"width: {self.tokens.spacing.sm}px; margin: 0px; }} "
            f"QScrollBar::handle:vertical {{ background: {colors.surface_overlay}; "
            f"border-radius: {self.tokens.radius.sm}px; "
            f"min-height: {self.tokens.spacing.xl}px; }} "
            f"QScrollBar::handle:vertical:hover {{ background: {colors.accent_cyan}; }} "
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ "
            f"height: 0px; }} "
            f"QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ "
            f"background: transparent; }}"
        )
        self._body_container.setStyleSheet(
            f"#ClipInspectorBodyContainer {{ background: transparent; }}"
        )
