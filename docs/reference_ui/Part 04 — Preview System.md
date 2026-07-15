# AI Gaming Video Editor
# MASTER UI DESIGN SYSTEM

## Part 04 — Preview System

Version: 1.0

Status:
Official Preview Specification

---

# PURPOSE

The Preview Viewer is the heart of the application.

Every visual decision inside the workspace should naturally direct the user's attention toward the Preview before any other panel.

The Preview should never feel like a plain black rectangle.

It should always feel like a premium professional video viewer.

---

# DESIGN GOALS

The Preview should communicate:

Professional

Modern

Premium

Immersive

AI Powered

Responsive

Minimal

Elegant

The Preview must become the visual centerpiece of the application.

---

# VISUAL PRIORITY

Priority Level:

★★★★★

Nothing should visually compete with the Preview.

Timeline is always second.

Everything else is secondary.

---

# PREVIEW SIZE

Preferred Ratio

16:9

Minimum Width

900 px

Preferred Width

Expand whenever additional workspace is available.

Never shrink the Preview before reducing side panels.

---

# SURFACE

The Preview is not a flat rectangle.

It consists of layered surfaces.

Application Background

↓

Workspace Surface

↓

Preview Container

↓

Glass Frame

↓

Video Surface

↓

HUD Overlay

↓

Floating Controls

Every layer must be visually distinguishable.

---

# PREVIEW CONTAINER

Rounded Corners

16 px

Glass Surface

Soft Blur

Subtle Inner Highlight

Soft Outer Shadow

Very Thin Border

Maximum Border Thickness

1 px

Never use heavy outlines.

---

# VIDEO SURFACE

Aspect Ratio

16:9

Background

Near Black

No visible gradients.

No noisy textures.

Never use pure black (#000000).

---

# EMPTY STATE

When no media is loaded, the viewer should display:

Centered Illustration

↓

Headline

↓

Description

↓

Primary Action

↓

Secondary Action

Examples

Import Media

Open Recent Project

Create New Project

---

# EMPTY STATE HEADLINE

Examples

Drop Media Here

Ready to Create

Import Your First Clip

Never display only

"No clip selected"

---

# EMPTY STATE DESCRIPTION

Explain briefly:

Drag & Drop files

or

Click Import

Maximum:

2 lines

Readable

Centered

---

# EMPTY STATE ACTIONS

Primary

Import Media

Secondary

Open Recent

Buttons centered.

Consistent spacing.

---

# VIEWER TOOLBAR

Position

Top

Floating

Glass Surface

Contains

Zoom

Fit

100%

Safe Area

Grid

Screenshot

Fullscreen

Controls grouped.

Never appear crowded.

---

# VIEWER HUD

Position

Top Left

Displays

Timecode

FPS

Resolution

Playback Status

Proxy

GPU

Small.

Minimal.

Readable.

---

# PLAYBACK CONTROLS

Position

Bottom Center

Large

Professional

Icons Only

Contains

Play

Pause

Previous Frame

Next Frame

Loop

Playback Rate

Volume

Fullscreen

Most important control:

Play

---

# PLAYHEAD

Thin

Accent Color

Highly Visible

Always above video.

---

# TIMECODE

Use monospace font.

Always aligned.

Readable.

Examples

00:00:12:18

---

# OVERLAYS

Optional overlays

Safe Area

Rule of Thirds

Center Cross

Grid

Action Safe

Title Safe

Overlays should never dominate the viewer.

Low opacity.

---

# ZOOM

Display current zoom level.

Examples

50%

100%

Fit

200%

Never use unclear labels.

---

# FULLSCREEN

Clearly separated from playback controls.

Top Right preferred.

---

# SCREENSHOT

Small icon.

Tooltip required.

No text necessary.

---

# VIEWER STATUS

Examples

Ready

Playing

Paused

Rendering

Analyzing

AI Processing

Display subtly.

Never use bright colors.

---

# LOADING STATE

When media is loading

Show

Spinner

↓

Progress

↓

Status Text

↓

Background Blur

Never show frozen black viewer.

---

# ERROR STATE

Examples

Unsupported Codec

Missing Media

Decode Failed

Display

Icon

↓

Headline

↓

Description

↓

Retry

↓

Locate Media

---

# AI OVERLAYS

When AI is active

Display subtle overlay cards.

Examples

Scene Detection

Face Tracking

Auto Captions

Highlight Detection

Audio Analysis

Cards appear in corners.

Never block the video.

---

# DRAG & DROP

Dragging media over Preview

Background slightly brightens.

Border glows.

Drop indicator appears.

Drop animation

150 ms

---

# ANIMATIONS

Fade In

180 ms

Toolbar Reveal

150 ms

Overlay Fade

180 ms

Button Hover

150 ms

Fullscreen

250 ms

All animations smooth.

Never flashy.

---

# SHADOWS

Viewer

Largest shadow in the application.

Floating Controls

Medium shadow.

Overlay Cards

Soft shadow.

Never hard shadows.

---

# RESPONSIVENESS

Large Monitor

Expand Preview first.

Medium Monitor

Reduce sidebars first.

Small Monitor

Never reduce below 16:9 minimum.

---

# DESIGN RULES

The Preview is always the hero.

Every visual decision should strengthen its importance.

Never allow side panels to compete visually with the Preview.

If the interface feels balanced but the Preview is not immediately dominant,

the design has failed.

---

# IMPLEMENTATION RULES

Do not change playback logic.

Do not change APIs.

Do not change signals.

Do not change backend.

Do not change tests.

Improve visuals only.

Preserve architecture.

End of Part 04.