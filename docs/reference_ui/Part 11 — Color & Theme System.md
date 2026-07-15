# AI Gaming Video Editor
# MASTER UI DESIGN SYSTEM

## Part 11 — Color & Theme System

Version: 1.0

Status:
Official Color & Theme Specification

---

# PURPOSE

This document defines the complete visual color language of the application.

Every future UI implementation must use this specification.

Never invent new colors.

Never hardcode colors.

Always use the Theme Token System.

This document controls:

Backgrounds

Panels

Cards

Buttons

Icons

Typography

States

Glass Effects

Shadows

Borders

Overlays

Selection

Focus

Hover

Everything visual.

---

# DESIGN PHILOSOPHY

The application should feel:

Professional

Premium

Elegant

Dark

Minimal

Luxury Desktop Software

AI Powered

Creator Focused

The color system should support long editing sessions.

Eye fatigue must remain minimal.

Nothing should feel overly saturated.

---

# THEME MODES

Current

Dark Theme

Future

Light Theme

All components should support theme switching through tokens.

Never hardcode light or dark values directly into widgets.

---

# APPLICATION BACKGROUND

Purpose

Behind the entire application.

Appearance

Very dark.

Almost black.

No gradients.

No visible texture.

This color should visually disappear.

---

# WORKSPACE SURFACE

Purpose

Behind all panels.

Slightly lighter than the application background.

Allows floating panels to become distinguishable.

---

# PRIMARY PANEL

Used for

Preview

Timeline

Media Browser

Inspector

Should appear elevated above the workspace.

Never brighter than floating cards.

---

# SECONDARY PANEL

Used for

Details

Metadata

History

Logs

Information Panels

Slightly darker than primary panels.

Lower visual priority.

---

# FLOATING CARD

Used for

Dialogs

Context Menus

Dropdowns

Floating Toolbars

Notifications

AI Suggestions

Highest surface level.

Always appear above panels.

---

# SURFACE LEVELS

Level 0

Application Background

↓

Level 1

Workspace

↓

Level 2

Primary Panels

↓

Level 3

Secondary Panels

↓

Level 4

Floating Cards

↓

Level 5

Dialogs

Every level should be visually distinguishable.

Never merge surfaces together.

---

# ACCENT COLORS

Primary Accent

Cyan

Purpose

Selection

Focus

Primary Buttons

Playhead

Preview Highlights

Never use Cyan for decorative elements.

---

AI Accent

Purple

Purpose

AI

Smart Suggestions

AI Pipeline

Prompt Area

Never use Purple outside AI features.

---

SUCCESS

Green

Purpose

Completed

Online

Connected

Export Finished

Validation Success

Never use Green for primary actions.

---

WARNING

Orange

Purpose

Missing Media

GPU Warning

Low Storage

Performance Warning

Use sparingly.

---

ERROR

Red

Purpose

Delete

Failure

Render Error

Disconnected

Never use Red for decorative UI.

---

INFO

Blue

Purpose

Neutral Information

Updates

Hints

Documentation

Not for selection.

---

# TEXT COLORS

Primary Text

Highest contrast.

Titles.

Important values.

---

Secondary Text

Descriptions.

Metadata.

Supporting information.

---

Muted Text

Disabled controls.

Inactive labels.

Footnotes.

---

Placeholder Text

Search fields.

Prompt areas.

Input hints.

Lowest emphasis.

---

# ICON COLORS

Default

Secondary Text

Hover

Primary Text

Active

Accent

Disabled

Muted

Never mix icon colors randomly.

---

# BUTTON COLORS

PRIMARY

Filled Accent

White text

SECONDARY

Dark surface

Thin border

White text

GHOST

Transparent

Hover surface only

DANGER

Red

White text

SUCCESS

Green

White text

---

# INPUT COLORS

Background

Secondary Surface

Border

Very subtle

Focus

Accent Border

Soft Glow

Placeholder

Muted Text

---

# DROPDOWNS

Background

Panel Surface

Hover

Slightly Brighter

Selected

Accent

Arrow

Secondary Text

---

# TOGGLES

Off

Muted Surface

On

Accent

Thumb

White

---

# CHECKBOXES

Unchecked

Border only

Checked

Accent Fill

Hover

Slight highlight

---

# SCROLLBARS

Track

Transparent

Thumb

Low Contrast

Hover

Accent

Never dominate the interface.

---

# TIMELINE COLORS

Video Track

Blue Accent

Audio Track

Green Accent

Effects

Purple

Titles

Orange

Markers

Yellow

Playhead

Cyan

Selection

Bright Cyan

Keep tracks readable.

Never create rainbow timelines.

---

# PREVIEW COLORS

Viewer Background

Near Black

HUD

Glass Surface

Safe Area

Low Contrast

Grid

Very Low Opacity

Selection

Accent

---

# AI COLORS

Primary

Purple

Prompt

Purple Border

Pipeline

Purple Progress

Thinking

Blue

Generating

Purple

Completed

Green

Error

Red

---

# INSPECTOR COLORS

Headers

Primary Text

Section Titles

Secondary Text

Property Labels

Muted

Property Values

Primary Text

Reset Buttons

Ghost

---

# STATUS PILLS

GPU

Blue

AI

Purple

Proxy

Orange

Ready

Green

Offline

Gray

Rendering

Cyan

Never create unnecessary badge colors.

---

# GLASS EFFECT

Transparency

Very subtle

Blur

Medium

Inner Highlight

Low Opacity

Outer Shadow

Soft

Border

Thin

Never use strong frosted glass.

---

# SHADOW COLORS

Panels

Low Opacity Black

Floating Cards

Medium Opacity Black

Dialogs

Largest Shadow

Preview

Soft Hero Shadow

Never harsh.

---

# BORDER COLORS

Always subtle.

Never bright.

Accent borders only appear on:

Focus

Selection

Primary Actions

---

# HOVER COLORS

Hover should never dramatically change color.

Only:

Brightness

Elevation

Border

Glow

may change.

---

# FOCUS COLORS

Always Accent.

Visible.

Accessible.

Never rely only on border thickness.

---

# DISABLED COLORS

Lower opacity.

Readable.

Never disappear completely.

---

# LOADING COLORS

Progress

Accent

Skeleton

Surface Variation

Spinner

Accent

---

# ERROR COLORS

Background

Subtle Red Tint

Border

Red

Text

White

Icon

Red

---

# SUCCESS COLORS

Background

Subtle Green Tint

Border

Green

Icon

Green

Text

White

---

# TOKEN RULES

Never hardcode colors.

Always reference Theme Tokens.

Every component must resolve colors through the theme system.

Support future themes automatically.

---

# IMPLEMENTATION RULES

Do not bypass ThemeManager.

Do not introduce inline colors.

Do not duplicate token values.

If a new color is required,

extend the token system instead of hardcoding.

Every UI element must derive its appearance from this document.

---

# FINAL PRINCIPLE

Color should communicate hierarchy,

not decoration.

Every color used in the application must have a clear purpose.

If a color does not communicate meaning,

remove it.

End of Part 11.