# AI Gaming Video Editor
# MASTER UI DESIGN SYSTEM

## Part 14 — Design Token System

Version: 1.0

Status:
Official Design Token Specification

---

# PURPOSE

The Design Token System is the foundation of the entire user interface.

Every visual decision must originate from a design token.

Never hardcode visual values.

Every widget should inherit appearance from centralized tokens.

This guarantees:

Consistency

Maintainability

Scalability

Theme Support

Future Redesign Capability

---

# CORE PRINCIPLE

Never ask

"What color should this widget use?"

Instead ask

"Which token represents this purpose?"

Tokens describe meaning,

not appearance.

---

# TOKEN CATEGORIES

The application uses the following token groups.

Colors

Typography

Spacing

Radius

Borders

Elevation

Shadows

Blur

Opacity

Motion

Animation

Sizing

Icons

Z-Index

Glass

Every visual property belongs to one of these groups.

---

# COLOR TOKENS

Never reference raw colors.

Always use semantic tokens.

Examples

background_base

background_workspace

surface_primary

surface_secondary

surface_overlay

surface_dialog

text_primary

text_secondary

text_muted

text_placeholder

border_default

border_focus

border_selected

accent_primary

accent_ai

accent_success

accent_warning

accent_error

accent_info

---

# SPACING TOKENS

Never use fixed pixel values.

Spacing Scale

4

8

12

16

24

32

48

64

Semantic Names

space_xs

space_sm

space_md

space_lg

space_xl

space_2xl

space_3xl

space_4xl

Spacing should remain predictable.

---

# RADIUS TOKENS

Do not hardcode radius.

Use

radius_small

6 px

radius_medium

8 px

radius_large

12 px

radius_card

14 px

radius_preview

16 px

radius_dialog

18 px

radius_pill

999 px

---

# TYPOGRAPHY TOKENS

font_display

font_window_title

font_panel_title

font_section

font_body

font_caption

font_status

font_monospace

Never specify font sizes directly inside widgets.

---

# ICON TOKENS

icon_small

16 px

icon_medium

18 px

icon_toolbar

20 px

icon_large

24 px

icon_dialog

28 px

---

# BORDER TOKENS

border_none

0 px

border_thin

1 px

border_medium

2 px

border_focus

2 px Accent

Never invent custom border thickness.

---

# SHADOW TOKENS

shadow_none

shadow_soft

shadow_medium

shadow_large

shadow_floating

shadow_dialog

Preview receives Hero Shadow.

Dialogs receive Largest Shadow.

---

# ELEVATION TOKENS

Level 0

Background

Level 1

Workspace

Level 2

Panel

Level 3

Card

Level 4

Floating

Level 5

Dialog

Elevation should communicate hierarchy.

Never decoration.

---

# GLASS TOKENS

glass_blur_light

glass_blur_medium

glass_blur_heavy

glass_opacity_low

glass_opacity_medium

glass_border

glass_highlight

Glass appearance must remain subtle.

---

# OPACITY TOKENS

opacity_disabled

opacity_muted

opacity_secondary

opacity_primary

opacity_overlay

opacity_drag

opacity_hover

Never hardcode opacity.

---

# MOTION TOKENS

motion_hover

120 ms

motion_focus

150 ms

motion_expand

200 ms

motion_panel

250 ms

motion_dialog

250 ms

motion_fullscreen

300 ms

---

# EASING TOKENS

ease_standard

ease_out

ease_in_out

ease_accelerate

Never use arbitrary easing curves.

---

# SIZE TOKENS

toolbar_height

72 px

statusbar_height

32 px

timeline_toolbar

48 px

preview_toolbar

48 px

panel_header

48 px

track_header

220 px

track_height

80 px

button_height

36 px

input_height

36 px

---

# PANEL TOKENS

sidebar_width

220 px

inspector_width

380 px

ai_width

380 px

preview_min_width

900 px

timeline_min_height

320 px

---

# BUTTON TOKENS

button_primary

button_secondary

button_ghost

button_danger

button_success

Each button style resolves through tokens.

---

# INPUT TOKENS

input_background

input_border

input_focus

input_placeholder

input_radius

---

# SCROLLBAR TOKENS

scrollbar_width

6 px

scrollbar_radius

999 px

scrollbar_hover

Accent

scrollbar_track

Transparent

---

# STATUS TOKENS

status_ready

status_processing

status_success

status_warning

status_error

status_offline

status_proxy

status_ai

Never define badge colors individually.

---

# TIMELINE TOKENS

track_video

track_audio

track_ai

track_effect

clip_selected

clip_hover

clip_drag

playhead

marker

waveform

thumbnail

---

# AI TOKENS

ai_prompt

ai_card

ai_pipeline

ai_thinking

ai_generating

ai_complete

ai_error

---

# PREVIEW TOKENS

viewer_background

viewer_overlay

viewer_grid

viewer_safe_area

viewer_hud

viewer_toolbar

---

# INSPECTOR TOKENS

property_label

property_value

property_background

property_hover

property_focus

property_reset

---

# EMPTY STATE TOKENS

empty_title

empty_description

empty_action

empty_icon

empty_background

---

# LOADING TOKENS

loading_spinner

loading_progress

loading_skeleton

loading_overlay

---

# ERROR TOKENS

error_background

error_border

error_icon

error_text

retry_button

---

# SUCCESS TOKENS

success_background

success_border

success_icon

success_text

---

# RESPONSIVE TOKENS

desktop_large

desktop_medium

desktop_small

future_tablet

future_touch

Avoid hardcoded breakpoints.

---

# THEME SWITCHING

Changing the active theme should require changing token values only.

Widgets should never know whether the application is:

Dark

Light

High Contrast

Future themes should work automatically.

---

# TOKEN OWNERSHIP

Only the Theme System owns tokens.

Widgets consume tokens.

Widgets never define tokens.

---

# IMPLEMENTATION RULES

Never duplicate token values.

Never bypass the token system.

Never hardcode visual values.

If a required token does not exist,

extend the token system instead of inventing local values.

---

# FINAL PRINCIPLE

Tokens define intent,

not implementation.

A widget should never ask for

"#111827"

It should ask for

"surface_primary"

The token system is the single source of truth for all visual styling.

End of Part 14.