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
    # Layered near-black surfaces with a violet cast and a wide luminance
    # step between each layer, so the application background, workspace,
    # secondary panels, primary panels and floating controls read as clearly
    # distinct depths (this is the main driver of the redesigned hierarchy):
    #   background_deep  -> the app void behind everything (deepest)
    #   background_base  -> the application background
    #   surface          -> secondary panels
    #   surface_elevated -> primary panels / cards
    #   surface_overlay  -> floating controls / hover / popups (lightest)
    background_deep="#07060b",
    background_base="#0a0810",
    surface="#120e1c",
    surface_elevated="#161022",
    surface_overlay="#221a36",
    # Glass: violet-tinted translucent fill with a subtle light edge and
    # sheen (tinted toward the panel color rather than a white haze).
    glass_fill="rgba(22, 16, 34, 0.62)",
    glass_border="rgba(168, 130, 240, 0.18)",
    glass_highlight="rgba(216, 180, 255, 0.20)",
    # Neon accents (base) + softer translucent glow used for outer glow/shadow.
    # NEXUS purple primary, magenta neon secondary, fuchsia tertiary. The
    # token names keep their historical "blue"/"cyan" spellings so every
    # widget retints without renames.
    accent_blue="#a855f7",
    accent_blue_glow="rgba(168, 85, 247, 0.55)",
    accent_cyan="#e879f9",
    accent_cyan_glow="rgba(232, 121, 249, 0.55)",
    accent_purple="#d946ef",
    accent_purple_glow="rgba(217, 70, 239, 0.55)",
    # Text shades with more contrast between levels.
    text_primary="#f4f1fa",
    text_secondary="#c3b8dd",
    text_muted="#83779f",
    text_disabled="#4c4363",
    text_on_accent="#0a0810",
    # Status.
    success="#34d399",
    success_glow="rgba(52, 211, 153, 0.50)",
    warning="#f5b93d",
    warning_glow="rgba(245, 185, 61, 0.50)",
    error="#f87171",
    error_glow="rgba(248, 113, 113, 0.50)",
    # Lines / focus: solid violet-slate hairlines so panel edges read crisply
    # against the deep background.
    border="#2b2140",
    divider="rgba(43, 33, 64, 0.60)",
    focus_ring="rgba(217, 70, 239, 0.75)",
    # Extended accents (overlay clips / decorative category colors).
    accent_pink="#ec4899",
    accent_pink_glow="rgba(236, 72, 153, 0.55)",
    # Timeline track category colors (match the reference lanes: video =
    # violet thumbnails, music = green wave, sfx = purple wave, voice =
    # blue wave, text/subtitles = fuchsia chips).
    track_video="#8b5cf6",
    track_overlay="#ec4899",
    track_text="#c084fc",
    track_fx="#f5b93d",
    track_audio="#34d399",
    track_voice="#38bdf8",
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

# Tighter, denser pro-editor corner scale (still ascending; pill largest).
_DARK_RADIUS = RadiusTokens(sm=6, md=10, lg=14, xl=20, pill=999)

# Deeper, richer elevation so cards and floating panels genuinely pop off the
# workspace; stronger neon glows for the accent halo.
_DARK_SHADOWS = ShadowTokens(
    low=ShadowToken(blur=18, x=0, y=4, color="rgba(0, 0, 0, 0.50)"),
    medium=ShadowToken(blur=36, x=0, y=12, color="rgba(0, 0, 0, 0.62)"),
    high=ShadowToken(blur=64, x=0, y=24, color="rgba(0, 0, 0, 0.72)"),
    glow_blue=ShadowToken(blur=34, x=0, y=0, color="rgba(168, 85, 247, 0.55)"),
    glow_cyan=ShadowToken(blur=34, x=0, y=0, color="rgba(232, 121, 249, 0.55)"),
    glow_purple=ShadowToken(blur=34, x=0, y=0, color="rgba(217, 70, 239, 0.55)"),
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
