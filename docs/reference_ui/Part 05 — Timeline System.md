# AI Gaming Video Editor
# MASTER UI DESIGN SYSTEM

## Part 05 — Timeline System

Version: 1.0

Status:
Official Timeline Specification

---

# PURPOSE

The Timeline is the second most important region of the application.

The Timeline is where creators spend most of their time.

The Timeline must feel like a professional Non-Linear Editor (NLE).

Never allow the Timeline to resemble a list of colored rectangles.

The Timeline should immediately communicate:

Professional

Powerful

Accurate

Fast

Premium

Creator Focused

AI Assisted

---

# DESIGN GOALS

The Timeline should feel comparable to:

Adobe Premiere Pro

DaVinci Resolve

Final Cut Pro

Blackmagic Fusion

Professional Broadcast Software

Never resemble:

Simple Track List

Spreadsheet

Qt Demo

Web Dashboard

---

# VISUAL PRIORITY

Preview

★★★★★

Timeline

★★★★☆

Everything else

★★☆☆☆

---

# TIMELINE HEIGHT

Minimum Height

320 px

Preferred Height

34–40% of the workspace

Timeline should expand before shrinking Preview.

Never compress tracks unnecessarily.

---

# TIMELINE SURFACE

Timeline consists of multiple layers.

Workspace Background

↓

Timeline Container

↓

Toolbar

↓

Time Ruler

↓

Track Headers

↓

Track Area

↓

Playhead

↓

Selection Overlay

↓

Floating Indicators

Each layer must be visually distinguishable.

---

# TIMELINE TOOLBAR

Height

48 px

Contains

Zoom

Magnet

Snap

Ripple

Link

Markers

Undo

Redo

Playback Speed

Search

Icons grouped.

Groups separated by spacing.

Never use heavy borders.

---

# TIME RULER

Height

36 px

Purpose

Display time divisions.

Major divisions

Bold

Minor divisions

Thin

Current frame indicator

Accent Color

Readable at every zoom level.

---

# PLAYHEAD

The playhead is the most important object inside the Timeline.

Width

2 px

Accent Color

Cyan

Soft glow

Always visible.

Always rendered above clips.

Top triangle indicator required.

---

# TRACKS

Track spacing

8 px

Track height

72–96 px

Video tracks

Larger

Audio tracks

Slightly shorter

Tracks must breathe.

Never appear compressed.

---

# TRACK HEADERS

Width

220 px

Contains

Track Number

Track Name

Track Color

Visibility

Mute

Solo

Lock

Collapse

Resize Handle

Icons aligned.

Large click targets.

Hover state required.

---

# TRACK COLORS

Every track receives a subtle accent.

Examples

Video

Blue

Audio

Green

Effects

Purple

Titles

Orange

AI

Cyan

Never use random colors.

---

# CLIPS

Rounded Corners

10 px

Soft gradient

Soft shadow

Thin border

Hover elevation

Never flat rectangles.

---

# CLIP STATES

Normal

Soft gradient

Hover

Slight elevation

Selection

Cyan outline

Glow

Focused

Additional shadow

Disabled

Lower opacity

---

# VIDEO CLIPS

Display

Thumbnail Strip

Clip Name

Duration

Effects Badge

Proxy Badge

Color Label

Thumbnails should scale with zoom.

---

# AUDIO CLIPS

Display

Waveform

Clip Name

Duration

Volume Badge

Mute Badge

Never appear empty.

---

# AI CLIPS

Special appearance.

Purple accent.

AI badge.

Glow slightly.

Examples

Auto Captions

Scene Detection

Highlight Detection

Silence Removal

Object Tracking

AI clips should immediately stand out.

---

# TRANSITIONS

Displayed between clips.

Small.

Centered.

Readable.

Hover tooltip.

---

# EFFECTS

Display small indicators.

FX badge

Color badge

Adjustment layer

Speed change

Nested clip

Keep minimal.

---

# MARKERS

Displayed above ruler.

Small flags.

Different colors.

Chapter

Scene

AI

Export

Review

Hover reveals details.

---

# SELECTION

Selected clips must be immediately obvious.

Use

Glow

Outline

Shadow

Never rely on color alone.

---

# MULTI-SELECTION

Selected group receives

Shared highlight

Bounding outline

Collective movement indicator

---

# DRAGGING

Dragging clip

Raise elevation.

Increase shadow.

Show insertion indicator.

Smooth movement.

---

# RESIZING

Edges glow.

Resize handles appear.

Cursor changes.

Real-time preview.

---

# MAGNET

Snap indicator

Thin cyan line.

Visible before snapping.

---

# ZOOM

Smooth.

Mouse wheel supported.

Slider optional.

Current zoom displayed.

Never jump abruptly.

---

# SCROLLING

Horizontal

Smooth

Vertical

Smooth

Overlay scrollbars.

Never thick scrollbars.

---

# EMPTY TIMELINE

Display

Illustration

↓

Headline

↓

Description

↓

Import Button

↓

Quick Start

Never show an empty gray box.

---

# WAVEFORMS

High contrast.

Readable.

Adaptive.

Scale with zoom.

---

# THUMBNAILS

Frame previews.

Even spacing.

Adaptive density.

Higher zoom

↓

More thumbnails.

---

# GRID

Optional.

Very subtle.

Never dominate.

---

# SAFE AREAS

Optional guides.

Low opacity.

---

# FLOATING INFO

During editing show

Clip Length

Trim Amount

Current Frame

Timecode

Small floating cards.

---

# TOOLTIPS

Every icon

Tooltip required.

Delay

400 ms

---

# CONTEXT MENU

Modern glass menu.

Icons

Shortcuts

Rounded corners

Soft shadow

---

# KEYBOARD FOCUS

Visible.

Professional.

Never default Qt focus rectangle.

---

# ANIMATIONS

Hover

120 ms

Selection

180 ms

Drag

Real-time

Expand

200 ms

Collapse

200 ms

Never flashy.

Always smooth.

---

# SHADOWS

Clips

Soft

Selected Clips

Medium

Dragging

Largest

Playhead

Subtle glow

---

# PERFORMANCE

Visual effects must remain lightweight.

Avoid excessive blur.

Avoid expensive rendering.

Maintain smooth scrolling.

---

# DESIGN PRINCIPLES

Timeline must feel like premium editing software.

The Timeline should immediately communicate precision.

Every pixel should help editing.

Nothing decorative without purpose.

Professionalism over effects.

---

# IMPLEMENTATION RULES

Do not change editing logic.

Do not change APIs.

Do not change signals.

Do not change tests.

Do not change backend.

Improve visuals only.

Preserve architecture.

The Timeline should always move closer to a commercial desktop NLE.

End of Part 05.