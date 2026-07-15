# AI Gaming Video Editor
# MASTER UI DESIGN SYSTEM

## Part 03 — Component Library

Version: 1.0

Status:
Official Component Specification

---

# PURPOSE

This document defines every reusable UI component used throughout the application.

Every widget must follow these specifications.

Never invent new component styles unless absolutely necessary.

Always reuse existing components before creating new ones.

Consistency is more important than variety.

---

# COMPONENT PHILOSOPHY

Every component must be:

Minimal

Professional

Readable

Accessible

Consistent

Desktop First

No component should feel experimental.

No component should resemble a web dashboard.

---

# BUTTON SYSTEM

Buttons belong to four categories.

------------------------------------------------

PRIMARY

------------------------------------------------

Purpose

Main action.

Examples

Export

Generate

Import

Render

AI Edit

Appearance

Filled

Cyan accent

Soft shadow

8 px radius

Hover glow

Height

40 px

Minimum width

110 px

------------------------------------------------

SECONDARY

------------------------------------------------

Purpose

Normal actions.

Appearance

Dark surface

Subtle border

Hover elevation

No glow

Height

40 px

------------------------------------------------

GHOST

------------------------------------------------

Purpose

Toolbar actions.

Context menu.

Timeline tools.

Transparent background.

Hover only.

No border.

------------------------------------------------

DANGER

------------------------------------------------

Purpose

Delete

Reset

Remove

Stop Render

Red accent.

Never used for normal actions.

---

# ICON BUTTONS

Square.

36 × 36 px

Rounded.

Hover elevation.

No text.

Tooltip required.

---

# TOGGLE BUTTONS

Used for

Mute

Solo

Lock

Visibility

Snap

Magnet

Loop

Consistent size.

Selected state:

Accent color.

---

# INPUT FIELDS

Height

40 px

Padding

12 px

Placeholder

Low opacity.

Focused

Accent border.

Soft glow.

Never thick borders.

---

# SEARCH BOX

Always contains:

Search icon

Placeholder

Clear button

Rounded.

Large enough for desktop.

Never tiny.

---

# DROPDOWNS

Height

40 px

Rounded.

Thin border.

Hover highlight.

Arrow aligned right.

Never use native operating system styling.

---

# SLIDERS

Thin track.

Rounded thumb.

Accent color.

Value shown beside slider.

Reset icon optional.

Never oversized.

---

# CHECKBOXES

Rounded.

16 × 16 px

Accent fill when checked.

Label aligned vertically.

---

# RADIO BUTTONS

Minimal.

Circular.

Thin outline.

Accent fill.

---

# SWITCHES

Modern desktop switch.

Rounded.

Animated.

Consistent width.

Never use default Qt switches.

---

# CARDS

Cards represent grouped information.

Examples

AI

Details

Properties

History

Export Queue

Cards use

Subtle elevation

Rounded corners

Glass surface

Soft shadow

Internal padding

16 px

Gap between cards

16 px

---

# GLASS CARDS

Hero cards.

Preview.

AI.

Floating tools.

Properties.

Glass cards use

Transparency

Blur

Inner highlight

Outer shadow

Soft border

Never heavy opacity.

---

# PANEL HEADERS

Height

44 px

Contains

Title

Subtitle

Actions

Search

Badges

Everything aligned.

---

# SECTION HEADERS

Simple.

Smaller than panel headers.

May collapse.

Chevron left.

Title.

Optional badge.

Divider optional.

---

# STATUS PILLS

Examples

GPU

HDR

Proxy

AI

Rendering

Ready

Exporting

Small.

Rounded.

Equal height.

Consistent typography.

---

# TAGS

Used for

Codec

Resolution

FPS

Track Type

Duration

Small.

Low emphasis.

Never brighter than buttons.

---

# BADGES

Information only.

No interaction.

Use:

Neutral

Success

Warning

Danger

Info

Only one accent per badge.

---

# TABS

Rounded.

Modern.

Animated.

Active tab

Accent underline

or

Glass fill.

Never use default Qt tabs.

---

# TOOLBARS

Toolbar buttons

36–40 px

Icon

↓

Label

↓

Tooltip

Groups separated by spacing.

Not borders.

---

# CONTEXT MENUS

Glass surface.

Rounded.

Soft shadow.

Hover row highlight.

Icons aligned.

Keyboard shortcuts aligned right.

---

# MENUS

Desktop style.

Comfortable spacing.

Readable.

Consistent width.

No cramped rows.

---

# DIALOGS

Centered.

Glass panel.

Rounded.

Soft shadow.

Primary action right aligned.

Cancel left.

---

# MODALS

Blur background.

Focus on content.

Prevent visual clutter.

---

# TOOLTIPS

Small.

Dark.

Rounded.

Readable.

Never oversized.

---

# SCROLLBARS

Overlay.

Thin.

Appear on hover.

Rounded thumb.

Transparent track.

Never thick.

---

# DIVIDERS

Very subtle.

1 px.

Low opacity.

Spacing preferred over lines.

---

# TABLES

Alternating rows.

Hover highlight.

Selected row glow.

Readable spacing.

---

# LISTS

Comfortable height.

Hover state.

Selection state.

Consistent padding.

---

# TREE VIEWS

Used for

Folders

Projects

Assets

Indentation

16 px

Chevron animation.

---

# EMPTY STATES

Every empty state contains

Illustration

Title

Description

Primary Action

Optional secondary action.

Never display plain text only.

---

# LOADING STATES

Skeletons.

Progress indicators.

Animated shimmer.

Never frozen blank screens.

---

# HOVER STATES

Every interactive element responds.

Hover

↓

Elevation

↓

Highlight

↓

Cursor

Never remain static.

---

# FOCUS STATES

Keyboard accessible.

Visible focus ring.

Accent color.

Soft glow.

---

# SELECTION STATES

Always obvious.

Use

Accent border

Glow

Background

Never rely on color only.

---

# DISABLED STATES

Reduced opacity.

No glow.

Readable.

Not completely hidden.

---

# MICRO INTERACTIONS

Hover

150 ms

Focus

150 ms

Expand

220 ms

Collapse

220 ms

Fade

180 ms

Never flashy.

---

# COMPONENT RULES

Never create duplicate components.

Reuse existing widgets.

Keep APIs stable.

Keep object names stable.

Keep signals stable.

Improve appearance only.

Every component should feel like part of one unified desktop application.

---

End of Part 03.