# AI Gaming Video Editor
## MASTER UI DESIGN SYSTEM

# Part 02 — Layout System

Version: 1.0

Status:
Official Layout Specification

---

# PURPOSE

This document defines the physical layout of the application.

It specifies:

- panel proportions
- workspace organization
- alignment
- spacing rhythm
- desktop composition
- responsive desktop behavior

This document never changes functionality.

It only defines visual structure.

---

# DESIGN PHILOSOPHY

The workspace should feel like a premium creative suite.

Users should instantly understand where to look.

Everything must have a clear visual purpose.

Avoid empty unused areas.

Avoid randomly sized panels.

Every panel should feel intentional.

---

# DESKTOP GRID

The application uses a three-column workspace.

------------------------------------------------

LEFT SIDEBAR

CENTER WORKSPACE

RIGHT SIDEBAR

------------------------------------------------

Below the center workspace sits the Timeline.

The Timeline spans the available width.

The Status Bar remains fixed at the bottom.

---

# WINDOW STRUCTURE

Top Menu Bar

↓

Top Toolbar

↓

Main Workspace

├── Left Sidebar
├── Preview Area
├── Right Sidebar

↓

Timeline

↓

Status Bar

Nothing overlaps.

Everything aligns to the desktop grid.

---

# PANEL PROPORTIONS

Default desktop proportions

Left Sidebar

18%–22%

Center Workspace

56%–62%

Right Sidebar

20%–24%

These ratios may adjust slightly depending on resolution but should remain visually balanced.

---

# PREVIEW AREA

The Preview Viewer is the hero component.

Minimum width:

900 px

Preferred ratio:

16:9

Preview should always dominate the workspace.

No other panel should visually compete with it.

---

# TIMELINE

Timeline is the second most important region.

Minimum height:

300 px

Preferred height:

34–38% of workspace

Timeline must feel spacious.

Tracks should never feel compressed.

---

# LEFT SIDEBAR

Preferred width:

240–280 px

Contains:

Navigation

Media Browser

Projects

Collections

Recent

Storage

Status

Use vertical rhythm.

Do not overcrowd.

---

# RIGHT SIDEBAR

Preferred width:

340–380 px

Contains:

Inspector

AI Assistant

Details

Properties

Cards

Tabs are acceptable.

Cards are preferred.

---

# TOP MENU BAR

Height:

32 px

Purpose:

Application menus only.

Do not place editing controls here.

---

# TOP TOOLBAR

Height:

64–72 px

Contains grouped editing actions.

Actions should be visually grouped.

Groups separated by spacing, not heavy borders.

Example groups:

Project

↓

Import

Save

Open

Editing

↓

Cut

Split

Ripple

Trim

Playback

↓

Play

Stop

Loop

Export

↓

Render

Queue

Export

AI

↓

Auto Edit

Captions

Highlights

Voice

---

# STATUS BAR

Height:

28–32 px

Contains:

GPU

Memory

Render Status

Proxy

FPS

Background Tasks

Keep minimal.

Never clutter.

---

# SPLITTERS

Splitters must feel lightweight.

Handles:

Thin

Low contrast

Easy to drag

Never dominate the interface.

---

# PANEL ALIGNMENT

Every panel aligns to the same grid.

Edges line up.

Corners align.

Padding remains consistent.

No panel should appear randomly shifted.

---

# INTERNAL PANEL LAYOUT

Every panel follows the same hierarchy.

Header

↓

Toolbar (optional)

↓

Primary Content

↓

Footer (optional)

Never mix these orders.

---

# PANEL HEADERS

Height:

40–48 px

Contains:

Title

Optional subtitle

Actions

Search

Never overcrowd.

---

# CARD LAYOUT

Cards should stack vertically.

Gap between cards:

16 px

Cards must never touch each other directly.

---

# SECTION SPACING

Major sections

32 px

Panel groups

24 px

Control groups

16 px

Related controls

8 px

Micro spacing

4 px

---

# SCROLLABLE AREAS

Scrolling should only occur inside content areas.

Headers remain visible.

Footers remain fixed when appropriate.

Avoid nested scrolling where possible.

---

# EMPTY SPACE

Whitespace is intentional.

Do not fill every area.

Allow breathing room.

Whitespace improves readability.

---

# BALANCE

The interface should feel visually balanced.

Avoid making one side heavy unless it is the Preview.

Preview is always the dominant visual element.

---

# RESPONSIVE DESKTOP BEHAVIOR

Large Monitors

Expand Preview first.

Then Timeline.

Then AI.

Small Monitors

Reduce sidebars before reducing Preview.

Never shrink Timeline below its minimum height.

---

# DESIGN RULES

Never add new panels unless required.

Improve existing layout before introducing new regions.

Respect proportions.

Respect hierarchy.

Respect spacing.

Every layout decision should improve clarity.

---

End of Part 02.