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
    # Layered near-black navy backgrounds create depth under glass panels.
    background_base="#0a0d16",
    background_deep="#05070d",
    surface="#111524",
    surface_elevated="#171c30",
    surface_overlay="#1d2340",
    # Glass: cool translucent fill with a faint light edge and top sheen.
    glass_fill="rgba(255, 255, 255, 0.05)",
    glass_border="rgba(255, 255, 255, 0.10)",
    glass_highlight="rgba(255, 255, 255, 0.16)",
    # Neon accents (base) + softer translucent glow used for outer glow/shadow.
    accent_blue="#3b82f6",
    accent_blue_glow="rgba(59, 130, 246, 0.55)",
    accent_cyan="#22d3ee",
    accent_cyan_glow="rgba(34, 211, 238, 0.55)",
    accent_purple="#a855f7",
    accent_purple_glow="rgba(168, 85, 247, 0.55)",
    # Text shades.
    text_primary="#eef2ff",
    text_secondary="#b4bcd8",
    text_muted="#7c86a6",
    text_disabled="#4b5268",
    text_on_accent="#05070d",
    # Status.
    success="#34d399",
    success_glow="rgba(52, 211, 153, 0.50)",
    warning="#fbbf24",
    warning_glow="rgba(251, 191, 36, 0.50)",
    error="#f87171",
    error_glow="rgba(248, 113, 113, 0.50)",
    # Lines / focus.
    border="rgba(255, 255, 255, 0.08)",
    divider="rgba(255, 255, 255, 0.06)",
    focus_ring="rgba(34, 211, 238, 0.70)",
)


_DARK_TYPOGRAPHY = TypographyTokens(
    family_primary="Inter",
    family_mono="JetBrains Mono",
    fallback_families=("Segoe UI", "Roboto", "Arial", "sans-serif"),
    display=TypeStyle(size_px=34, weight=700, line_height=1.2, letter_spacing=-0.5),
    h1=TypeStyle(size_px=26, weight=700, line_height=1.25, letter_spacing=-0.3),
    h2=TypeStyle(size_px=20, weight=600, line_height=1.3),
    h3=TypeStyle(size_px=16, weight=600, line_height=1.35),
    body=TypeStyle(size_px=14, weight=400, line_height=1.5),
    body_small=TypeStyle(size_px=13, weight=400, line_height=1.5),
    caption=TypeStyle(size_px=12, weight=500, line_height=1.4, letter_spacing=0.2),
    mono=TypeStyle(size_px=13, weight=400, line_height=1.5),
)


_DARK_SPACING = SpacingTokens(xxs=2, xs=4, sm=8, md=12, lg=16, xl=24, xxl=32)

_DARK_RADIUS = RadiusTokens(sm=6, md=10, lg=16, xl=22, pill=999)

_DARK_SHADOWS = ShadowTokens(
    low=ShadowToken(blur=12, x=0, y=2, color="rgba(0, 0, 0, 0.45)"),
    medium=ShadowToken(blur=24, x=0, y=8, color="rgba(0, 0, 0, 0.55)"),
    high=ShadowToken(blur=48, x=0, y=16, color="rgba(0, 0, 0, 0.65)"),
    glow_blue=ShadowToken(blur=28, x=0, y=0, color="rgba(59, 130, 246, 0.55)"),
    glow_cyan=ShadowToken(blur=28, x=0, y=0, color="rgba(34, 211, 238, 0.55)"),
    glow_purple=ShadowToken(blur=28, x=0, y=0, color="rgba(168, 85, 247, 0.55)"),
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
