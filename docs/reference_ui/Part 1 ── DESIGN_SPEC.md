# MASTER UI DESIGN SPEC
Version: 1.0

Project:
AI Gaming Video Editor

Status:
Official Visual Design Reference

This document is the single source of truth for every UI implementation.

Every future UI change must move the application closer to this design.

The reference image represents the target visual quality.

Never redesign using personal preference.

Always follow this specification.

----------------------------------------------------------
1. DESIGN GOAL
----------------------------------------------------------

The application must feel like a premium desktop creative software.

Target quality:

★★★★★ AAA Desktop Software

Inspiration:

Adobe Premiere Pro

DaVinci Resolve

Cursor IDE

Linear

Figma Desktop

Blackmagic Fusion

OBS Studio

CapCut Desktop

Not a website.

Not a mobile app.

Desktop-first.

Professional creators.

Gaming creators.

AI-first workflow.

----------------------------------------------------------
2. DESIGN LANGUAGE
----------------------------------------------------------

Overall feeling:

Dark

Minimal

Futuristic

Premium

Elegant

Professional

AI Powered

Cyber Inspired

Luxury Software

Never feel:

Flat

Cheap

Bootstrap

Windows Forms

Electron Demo

Material Design

Web Dashboard

----------------------------------------------------------
3. VISUAL HIERARCHY
----------------------------------------------------------

Visual importance order:

Level 1

Video Preview

Timeline

Level 2

Left Navigation

Properties

AI Assistant

Level 3

Toolbars

Status Bars

Information Panels

Level 4

Labels

Badges

Captions

Preview must immediately attract the user's eyes.

Timeline must become the second strongest visual element.

----------------------------------------------------------
4. WINDOW STRUCTURE
----------------------------------------------------------

Top Menu Bar

↓

Top Toolbar

↓

Main Workspace

├── Left Navigation
├── Preview
├── Right Sidebar

↓

Timeline

↓

Bottom Status Bar

Nothing should overlap.

Everything aligned.

Use clean spacing.

----------------------------------------------------------
5. SPACING SYSTEM
----------------------------------------------------------

Use only:

4 px

8 px

12 px

16 px

24 px

32 px

48 px

Never random spacing.

Every component aligned to the spacing grid.

----------------------------------------------------------
6. BORDER RADIUS
----------------------------------------------------------

Tiny controls

6 px

Buttons

8 px

Panels

12 px

Cards

14 px

Preview

16 px

Never use sharp rectangles.

----------------------------------------------------------
7. COLOR SYSTEM
----------------------------------------------------------

Background

#07090E

Workspace

#0B1020

Primary Panel

#111827

Secondary Panel

#151C2E

Floating Card

#1A2238

Accent

Cyan

AI Accent

Purple

Success

Green

Warning

Orange

Danger

Red

Never use rainbow colors.

Never mix more than four accent colors.

----------------------------------------------------------
8. GLASSMORPHISM
----------------------------------------------------------

Panels use:

Very subtle transparency.

Soft blur.

Soft highlights.

Thin border.

No heavy glow.

Only hero elements glow.

----------------------------------------------------------
9. SHADOW SYSTEM
----------------------------------------------------------

Panels

Soft shadow

Preview

Medium shadow

Floating elements

Large soft shadow

Never hard black shadows.

----------------------------------------------------------
10. TYPOGRAPHY
----------------------------------------------------------

Window Title

22

Main Section

18

Panel Title

16

Subsection

14

Body

13

Caption

12

Status

11

Tiny

10

Weight hierarchy:

700

600

500

400

Never same size everywhere.

----------------------------------------------------------
11. ICON SYSTEM
----------------------------------------------------------

One icon pack only.

Outline icons.

Rounded corners.

Consistent stroke width.

No emoji.

No mixed icon styles.

----------------------------------------------------------
12. LEFT SIDEBAR
----------------------------------------------------------

Width

220 px

Contains:

Logo

Navigation

Projects

Storage

System Status

Selected item:

Bright cyan glow.

Rounded.

Animated.

Hover:

Subtle elevation.

Icons left.

Text center aligned vertically.

----------------------------------------------------------
13. TOP TOOLBAR
----------------------------------------------------------

Contains:

Project Selector

Search

Notifications

Profile

Export

Toolbar Actions

Every action:

Icon

↓

Label

Spacing 16 px

Toolbar height

72 px

----------------------------------------------------------
14. VIDEO PREVIEW
----------------------------------------------------------

Largest component.

Always centered.

16:9.

Rounded.

Subtle glow.

Thin border.

Never plain black.

Empty state must contain:

Illustration

Drop media message

Import button

Quick Start

Recent Projects

----------------------------------------------------------
15. PLAYBACK CONTROLS
----------------------------------------------------------

Centered.

Professional.

Icons only.

Primary:

Play

Pause

Secondary:

Frame Forward

Frame Back

Loop

Fullscreen

Zoom

Timeline scrubber:

Thin

Cyan

Animated

----------------------------------------------------------
16. TIMELINE
----------------------------------------------------------

Minimum height

300 px

Track headers

Large

Colored

Icons

Lock

Mute

Solo

Eye

Waveforms visible.

Video thumbnails visible.

Selection glow.

Current frame line cyan.

Professional NLE feeling.

----------------------------------------------------------
17. AI ASSISTANT
----------------------------------------------------------

Hero feature.

Large prompt area.

Suggested actions.

Recent AI jobs.

Pipeline.

One-click automation.

Must never feel like a small widget.

----------------------------------------------------------
18. PROPERTIES PANEL
----------------------------------------------------------

Grouped sections.

Transform

Audio

Effects

Color

Motion

Export

Sliders:

Long

Thin

Modern

Grouped properly.

----------------------------------------------------------
19. STATUS BADGES
----------------------------------------------------------

Use pills.

Examples:

GPU

Proxy

Ready

Rendering

AI

HDR

Consistent height.

Rounded.

Never random colors.

----------------------------------------------------------
20. SCROLLBARS
----------------------------------------------------------

Very thin.

Overlay.

Transparent.

Appear only when scrolling.

Never thick purple bars.

----------------------------------------------------------
21. ANIMATIONS
----------------------------------------------------------

Hover

150 ms

Selection

200 ms

Panel

250 ms

Never flashy.

Smooth.

----------------------------------------------------------
22. IMPLEMENTATION RULES
----------------------------------------------------------

Every milestone must move closer to this specification.

Never redesign randomly.

Never introduce new design systems.

Maintain consistency.

Preserve:

Object names

Signals

Public API

Tests

Architecture

Only improve visuals.

The reference image is the target quality standard.