"""Centralized design tokens (pure data, no Qt import).

Every visual property in the application derives from the tokens defined here:
colors, typography, spacing, radius, shadows, blur and motion. This module
must never import Qt (no QColor/QPalette/QFont/QEasingCurve); all Qt
conversion happens in the builder modules. Keeping tokens Qt-free makes them
trivially testable and reusable by non-Qt consumers.

The single aggregate :class:`DesignTokens` bundles all token groups and is the
unit a theme is expressed in. Concrete instances live in
:mod:`gui.theme.palettes`; the active one is served by
:class:`~gui.theme.manager.ThemeManager`.

Color format: all colors are stored as CSS-style strings, either ``#RRGGBB``
or ``rgba(r, g, b, a)`` where ``a`` is 0..1. This is directly consumable by
Qt Style Sheets and easy to convert to a Qt color inside the builders.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Tuple


@dataclass(frozen=True)
class ColorTokens:
    """The full color palette for a theme.

    Attributes are grouped as: layered backgrounds (for depth), glass
    surfaces, neon accents (each with a matching ``*_glow`` used for shadows/
    outer glow), semantic text shades, and status colors.
    """

    # --- Layered backgrounds (dark -> elevated), for depth ---
    background_base: str
    background_deep: str
    surface: str
    surface_elevated: str
    surface_overlay: str

    # --- Glassmorphism ---
    glass_fill: str  # semi-transparent fill for glass panels
    glass_border: str  # subtle light border for glass edges
    glass_highlight: str  # top edge sheen

    # --- Neon accents (base + glow) ---
    accent_blue: str
    accent_blue_glow: str
    accent_cyan: str
    accent_cyan_glow: str
    accent_purple: str
    accent_purple_glow: str

    # --- Text ---
    text_primary: str
    text_secondary: str
    text_muted: str
    text_disabled: str
    text_on_accent: str

    # --- Status ---
    success: str
    success_glow: str
    warning: str
    warning_glow: str
    error: str
    error_glow: str

    # --- Lines / dividers / focus ---
    border: str
    divider: str
    focus_ring: str

    # --- Extended accents (additive; timeline/overlay category colors) ---
    accent_pink: str
    accent_pink_glow: str

    # --- Timeline track category colors (video/overlay/text/fx/audio) ---
    track_video: str
    track_overlay: str
    track_text: str
    track_fx: str
    track_audio: str
    track_voice: str


@dataclass(frozen=True)
class TypeStyle:
    """One typographic style: size, weight and spacing metrics.

    Attributes:
        size_px: Font size in logical pixels (pre-DPI scaling).
        weight: Numeric font weight (100..900).
        line_height: Multiplier applied to ``size_px`` for line spacing.
        letter_spacing: Tracking in pixels (may be negative).
    """

    size_px: int
    weight: int
    line_height: float = 1.4
    letter_spacing: float = 0.0


@dataclass(frozen=True)
class TypographyTokens:
    """Font family stack and the modular type scale."""

    family_primary: str
    family_mono: str
    fallback_families: Tuple[str, ...]

    display: TypeStyle
    h1: TypeStyle
    h2: TypeStyle
    h3: TypeStyle
    body: TypeStyle
    body_small: TypeStyle
    caption: TypeStyle
    mono: TypeStyle

    def family_stack(self) -> str:
        """Return a CSS/QSS ``font-family`` stack including fallbacks."""
        families = (self.family_primary, *self.fallback_families)
        return ", ".join(f'"{name}"' for name in families)


@dataclass(frozen=True)
class SpacingTokens:
    """Spacing scale built on a consistent base unit (logical pixels)."""

    xxs: int
    xs: int
    sm: int
    md: int
    lg: int
    xl: int
    xxl: int


@dataclass(frozen=True)
class RadiusTokens:
    """Border-radius scale (logical pixels); ``pill`` is fully rounded."""

    sm: int
    md: int
    lg: int
    xl: int
    pill: int


@dataclass(frozen=True)
class ShadowToken:
    """A single elevation shadow definition.

    Attributes:
        blur: Blur radius in pixels.
        x: Horizontal offset in pixels.
        y: Vertical offset in pixels.
        color: Shadow color (rgba string).
    """

    blur: int
    x: int
    y: int
    color: str


@dataclass(frozen=True)
class ShadowTokens:
    """Named elevation shadows for floating-panel depth and neon glow."""

    low: ShadowToken
    medium: ShadowToken
    high: ShadowToken
    glow_blue: ShadowToken
    glow_cyan: ShadowToken
    glow_purple: ShadowToken


@dataclass(frozen=True)
class BlurTokens:
    """Blur radii (pixels) for glassmorphism effects.

    These are numeric tokens only; they are applied by paint/effect code in a
    later phase (e.g. via a blur effect), not in the theme layer.
    """

    panel: int
    backdrop: int
    heavy: int


@dataclass(frozen=True)
class MotionTokens:
    """Animation timing tokens: durations (ms) and named easing curves.

    ``easing_*`` values are curve *names* (strings) kept Qt-free here; the
    mapping to a Qt easing curve is done in the Qt-facing builder layer so this
    module imports no Qt symbol.
    """

    duration_instant_ms: int
    duration_fast_ms: int
    duration_normal_ms: int
    duration_slow_ms: int

    easing_standard: str
    easing_decelerate: str
    easing_accelerate: str
    easing_emphasized: str


@dataclass(frozen=True)
class ElevationTokens:
    """Logical stacking order for layered/floating surfaces."""

    base: int
    raised: int
    overlay: int
    modal: int
    toast: int


@dataclass(frozen=True)
class DesignTokens:
    """Aggregate of every token group that defines one theme.

    Attributes:
        name: Unique theme name (e.g. ``"dark"``).
        is_dark: Whether this is a dark theme (future light theme sets False).
        colors, typography, spacing, radius, shadows, blur, motion, elevation:
            The individual token groups.
    """

    name: str
    is_dark: bool
    colors: ColorTokens
    typography: TypographyTokens
    spacing: SpacingTokens
    radius: RadiusTokens
    shadows: ShadowTokens
    blur: BlurTokens
    motion: MotionTokens
    elevation: ElevationTokens
    metadata: Dict[str, str] = field(default_factory=dict)
