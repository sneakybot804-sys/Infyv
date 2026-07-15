"""Concrete theme token instances.

Only the **Dark** theme is defined in Phase 8B. This is the single place
actual color/scale values are written down; every widget in later phases must
obtain values from :class:`~gui.theme.manager.ThemeManager` (which serves
these tokens), never by hardcoding.

The Light theme is intentionally absent: no placeholder colors and no fake
palette. The theme-switching architecture exists in the manager, which raises
a clear error for any theme that is not registered.
"""
from __future__ import annotations

from gui.theme.tokens import (
    BlurTokens,
    ColorTokens,
    DesignTokens,
    ElevationTokens,
    MotionTokens,
    RadiusTokens,
    ShadowToken,
    ShadowTokens,
    SpacingTokens,
    TypeStyle,
    TypographyTokens,
)

#: Name of the dark theme, referenced by the manager registration.
DARK_THEME_NAME = "dark"


_DARK_COLORS = ColorTokens(
    # Layered navy-slate surfaces with a wide luminance step between each
    # layer, so the application background, workspace, secondary panels,
    # primary panels and floating controls read as clearly distinct depths
    # (this is the main driver of the redesigned hierarchy):
    #   background_deep  -> the app void behind everything (deepest)
    #   background_base  -> the application background
    #   surface          -> secondary panels
    #   surface_elevated -> primary panels / cards
    #   surface_overlay  -> floating controls / hover / popups (lightest)
    background_deep="#04060c",
    background_base="#0b0f1a",
    surface="#141a2b",
    surface_elevated="#1e2740",
    surface_overlay="#2a3557",
    # Glass: richer cool translucent fill with a clearer light edge and sheen.
    glass_fill="rgba(255, 255, 255, 0.06)",
    glass_border="rgba(255, 255, 255, 0.14)",
    glass_highlight="rgba(255, 255, 255, 0.22)",
    # Neon accents (base) + softer translucent glow used for outer glow/shadow.
    # Slightly punchier premium accents (not gaming-RGB).
    accent_blue="#4f8dff",
    accent_blue_glow="rgba(79, 141, 255, 0.60)",
    accent_cyan="#2ee6ff",
    accent_cyan_glow="rgba(46, 230, 255, 0.60)",
    accent_purple="#b569ff",
    accent_purple_glow="rgba(181, 105, 255, 0.60)",
    # Text shades with more contrast between levels.
    text_primary="#f4f7ff",
    text_secondary="#c2cbe6",
    text_muted="#828db0",
    text_disabled="#4d5570",
    text_on_accent="#04060c",
    # Status.
    success="#34d399",
    success_glow="rgba(52, 211, 153, 0.50)",
    warning="#fbbf24",
    warning_glow="rgba(251, 191, 36, 0.50)",
    error="#f87171",
    error_glow="rgba(248, 113, 113, 0.50)",
    # Lines / focus: slightly stronger so hierarchy reads without heavy
    # outlines everywhere.
    border="rgba(255, 255, 255, 0.10)",
    divider="rgba(255, 255, 255, 0.07)",
    focus_ring="rgba(46, 230, 255, 0.75)",
)


_DARK_TYPOGRAPHY = TypographyTokens(
    family_primary="Inter",
    family_mono="JetBrains Mono",
    fallback_families=("Segoe UI", "Roboto", "Arial", "sans-serif"),
    # A wider modular scale so each level reads as a distinct rank instead of
    # near-identical sizes: big tight-tracked headings down to a small,
    # wide-tracked caption.
    display=TypeStyle(size_px=40, weight=800, line_height=1.15, letter_spacing=-0.6),
    h1=TypeStyle(size_px=30, weight=700, line_height=1.2, letter_spacing=-0.4),
    h2=TypeStyle(size_px=22, weight=700, line_height=1.28, letter_spacing=-0.2),
    h3=TypeStyle(size_px=17, weight=600, line_height=1.35),
    body=TypeStyle(size_px=14, weight=400, line_height=1.55),
    body_small=TypeStyle(size_px=12, weight=400, line_height=1.5),
    caption=TypeStyle(size_px=11, weight=600, line_height=1.35, letter_spacing=0.4),
    mono=TypeStyle(size_px=13, weight=500, line_height=1.5),
)


_DARK_SPACING = SpacingTokens(xxs=2, xs=4, sm=8, md=12, lg=16, xl=24, xxl=32)

# Softer, more modern corner scale (still ascending; pill largest).
_DARK_RADIUS = RadiusTokens(sm=8, md=12, lg=18, xl=26, pill=999)

# Deeper, richer elevation so cards and floating panels genuinely pop off the
# workspace; stronger neon glows for the accent halo.
_DARK_SHADOWS = ShadowTokens(
    low=ShadowToken(blur=18, x=0, y=4, color="rgba(0, 0, 0, 0.50)"),
    medium=ShadowToken(blur=36, x=0, y=12, color="rgba(0, 0, 0, 0.62)"),
    high=ShadowToken(blur=64, x=0, y=24, color="rgba(0, 0, 0, 0.72)"),
    glow_blue=ShadowToken(blur=34, x=0, y=0, color="rgba(79, 141, 255, 0.60)"),
    glow_cyan=ShadowToken(blur=34, x=0, y=0, color="rgba(46, 230, 255, 0.60)"),
    glow_purple=ShadowToken(blur=34, x=0, y=0, color="rgba(181, 105, 255, 0.60)"),
)

_DARK_BLUR = BlurTokens(panel=18, backdrop=32, heavy=48)

_DARK_MOTION = MotionTokens(
    duration_instant_ms=90,
    duration_fast_ms=150,
    duration_normal_ms=240,
    duration_slow_ms=380,
    easing_standard="in_out_cubic",
    easing_decelerate="out_cubic",
    easing_accelerate="in_cubic",
    easing_emphasized="in_out_quart",
)

_DARK_ELEVATION = ElevationTokens(base=0, raised=10, overlay=20, modal=30, toast=40)


#: The fully-populated dark theme -- the only registered theme in Phase 8B.
DARK_TOKENS = DesignTokens(
    name=DARK_THEME_NAME,
    is_dark=True,
    colors=_DARK_COLORS,
    typography=_DARK_TYPOGRAPHY,
    spacing=_DARK_SPACING,
    radius=_DARK_RADIUS,
    shadows=_DARK_SHADOWS,
    blur=_DARK_BLUR,
    motion=_DARK_MOTION,
    elevation=_DARK_ELEVATION,
    metadata={"description": "Dark futuristic neon theme"},
)
