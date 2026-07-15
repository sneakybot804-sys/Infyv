# AI Gaming Video Editor
# MASTER UI DESIGN SYSTEM

## Part 07 — Inspector & Properties Panel

Version: 1.0

Status:
Official Inspector Specification

---

# PURPOSE

The Inspector is the control center of the selected object.

It should never feel like a form.

It should never resemble a settings window.

It must feel like a premium professional property editor similar to high-end desktop creative software.

Every editable property should be easy to discover.

Every section should be logically grouped.

The Inspector should encourage experimentation without overwhelming the user.

---

# DESIGN GOALS

The Inspector should communicate:

Professional

Precise

Organized

Powerful

Readable

Modern

Creator Focused

---

# VISUAL PRIORITY

Preview

★★★★★

Timeline

★★★★☆

Inspector

★★★★☆

AI Assistant

★★★★☆

Media Browser

★★★☆☆

Toolbar

★★☆☆☆

---

# PANEL WIDTH

Preferred Width

360–400 px

Minimum Width

340 px

Maximum Width

420 px

Never compress the Inspector below readability.

---

# PANEL STRUCTURE

Header

↓

Current Selection

↓

Quick Properties

↓

Transform

↓

Motion

↓

Video

↓

Audio

↓

Effects

↓

AI Properties

↓

Metadata

↓

Footer

Every section separated by whitespace.

Avoid unnecessary borders.

---

# HEADER

Height

48 px

Contains

Inspector Title

Selected Object Type

Search

Reset

Collapse All

Never overcrowd.

---

# CURRENT SELECTION

Always display

Clip Name

Track

Duration

Resolution

FPS

Selection Icon

Selection should be obvious.

---

# PROPERTY GROUPS

Properties must always be grouped.

Never place unrelated controls together.

Examples

Transform

Motion

Video

Audio

Color

Effects

AI

Metadata

Export

---

# COLLAPSIBLE SECTIONS

Every major group should collapse.

Chevron aligned left.

Title aligned center-left.

Optional badge aligned right.

Collapsed state saves vertical space.

Expand animation

180–220 ms

---

# PROPERTY ROW

Every row contains

Property Label

↓

Editor

↓

Reset Button

↓

Optional Help Icon

Alignment must remain perfectly consistent.

---

# LABELS

Width

120 px

Right aligned or consistently left aligned.

Never jump between rows.

Readable.

---

# VALUE CONTROLS

Supported editors

Slider

Numeric Input

Dropdown

Toggle

Checkbox

Color Picker

File Selector

Segmented Control

Only one editor style per property.

---

# SLIDERS

Thin track.

Rounded thumb.

Value displayed beside slider.

Double-click resets value.

Reset button optional.

Never oversized.

---

# NUMERIC INPUTS

Compact.

Right aligned.

Increment buttons optional.

Support keyboard entry.

Consistent width.

---

# DROPDOWNS

Uniform height.

Rounded.

Glass appearance.

Soft hover.

No native operating-system styling.

---

# TOGGLES

Modern switch.

Animated.

Accent when enabled.

Muted when disabled.

---

# CHECKBOXES

Small.

Rounded.

Readable labels.

Never oversized.

---

# COLOR CONTROLS

Display

Current Color

↓

Hex Value

↓

Opacity

↓

Reset

Compact layout.

---

# RESET BUTTONS

Every editable property may expose reset.

Reset appearance

Ghost button

Small

Low emphasis

Never dominate.

---

# SEARCH

Search filters visible properties.

Placeholder

Search properties...

Real-time filtering preferred.

Search field always visible.

---

# QUICK PROPERTIES

Most common controls appear first.

Examples

Position

Scale

Rotation

Opacity

Volume

Speed

Users should reach them without scrolling.

---

# TRANSFORM SECTION

Properties

Position X

Position Y

Scale

Rotation

Anchor

Opacity

Grouped logically.

---

# MOTION SECTION

Properties

Speed

Reverse

Interpolation

Motion Blur

Frame Blend

Loop

---

# VIDEO SECTION

Properties

Resolution

Aspect Ratio

Crop

Blend Mode

Color Space

Bit Depth

---

# AUDIO SECTION

Properties

Volume

Pan

Balance

Mute

Normalize

Noise Reduction

---

# EFFECTS SECTION

Properties

Applied Effects

Enable

Disable

Reorder

Bypass

Search Effects

FX badges should be subtle.

---

# AI SECTION

Properties

Auto Captions

Smart Crop

Auto Reframe

Face Tracking

Object Tracking

Highlight Detection

Silence Removal

All displayed as AI cards.

Purple accent.

---

# METADATA

Read-only.

Examples

Filename

Codec

Resolution

FPS

Duration

Bitrate

Creation Date

Modification Date

Never editable.

---

# FOOTER

Displays

Selection Count

Memory Usage

Clip Status

Background Task

Compact.

Low emphasis.

---

# EMPTY STATE

When nothing selected

Display

Illustration

↓

Headline

↓

Description

↓

Hint

Example

Select a clip to edit its properties.

Never show a blank panel.

---

# SCROLLING

Only property area scrolls.

Header remains fixed.

Search remains visible.

---

# STATUS BADGES

Examples

AI

HDR

Proxy

Offline

Modified

Linked

Use subtle pills.

Never oversized.

---

# HOVER STATES

Rows highlight softly.

Editors reveal additional actions.

Hover should improve discoverability.

---

# FOCUS STATES

Visible focus ring.

Accent color.

Keyboard accessible.

---

# DISABLED PROPERTIES

Lower opacity.

Remain readable.

Explain why unavailable when appropriate.

---

# TOOLTIPS

Every advanced property

Tooltip required.

Delay

400 ms

Short.

Clear.

Helpful.

---

# ANIMATIONS

Expand

200 ms

Collapse

200 ms

Hover

120 ms

Focus

150 ms

Never flashy.

---

# PERFORMANCE

Inspector updates instantly.

Scrolling remains smooth.

Avoid unnecessary repaints.

Heavy visual effects discouraged.

---

# DESIGN PRINCIPLES

The Inspector is a workspace.

Not a settings dialog.

Not a form.

Everything should feel intentional.

The user should always know:

What is selected.

What can be edited.

What changed.

Without visual clutter.

---

# IMPLEMENTATION RULES

Do not change backend.

Do not change property logic.

Do not change APIs.

Do not change object names.

Do not change signals.

Do not break tests.

Improve visual organization only.

Future milestones should continue evolving the Inspector into a premium desktop property editor.

End of Part 07.