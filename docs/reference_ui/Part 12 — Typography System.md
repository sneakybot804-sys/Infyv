# AI Gaming Video Editor
# MASTER UI DESIGN SYSTEM

## Part 12 — Typography System

Version: 1.0

Status:
Official Typography Specification

---

# PURPOSE

Typography is the primary communication system of the application.

It defines hierarchy.

It improves readability.

It reduces cognitive load.

Typography should never become decoration.

Every text element must communicate its importance through:

Size

Weight

Contrast

Spacing

Alignment

Never through random styling.

---

# DESIGN GOALS

The typography should feel:

Professional

Modern

Minimal

Readable

Elegant

Comfortable during long editing sessions

It should resemble high-end desktop software rather than websites.

---

# FONT FAMILY

Primary Font

Inter

Fallbacks

Segoe UI

Roboto

Helvetica Neue

Arial

sans-serif

Use one primary font family throughout the application.

Never mix multiple sans-serif families.

---

# MONOSPACE FONT

Use for

Timecode

Frame Numbers

FPS

Bitrate

Resolution

Duration

File Size

Progress

Preferred

JetBrains Mono

Fallback

Consolas

Cascadia Code

Courier New

monospace

Never use monospace for paragraphs.

---

# FONT WEIGHTS

Light

300

Regular

400

Medium

500

Semi Bold

600

Bold

700

Avoid Black (900).

Avoid Ultra Light (100).

---

# TYPOGRAPHY SCALE

Display

32 px

Window Title

26 px

Workspace Title

22 px

Panel Title

18 px

Section Title

16 px

Subsection

14 px

Body

13 px

Caption

12 px

Status

11 px

Tiny

10 px

Never invent intermediate sizes.

---

# DISPLAY TEXT

Purpose

Splash Screen

Marketing

Landing

Never use inside editor panels.

Weight

700

---

# WINDOW TITLE

Examples

Project Name

Workspace

Editor

Weight

700

Readable.

Dominant.

---

# PANEL TITLE

Examples

Preview

Timeline

Media Browser

Inspector

AI Assistant

Weight

600

Always left aligned.

---

# SECTION TITLE

Examples

Transform

Motion

Video

Audio

Effects

Metadata

Weight

600

Smaller than panel title.

---

# BODY TEXT

Examples

Property Values

Descriptions

Lists

Metadata

Weight

400

Primary reading font.

---

# CAPTION

Examples

Hints

Descriptions

Helper text

Weight

400

Lower contrast.

---

# STATUS TEXT

Examples

Ready

Offline

Rendering

Proxy

GPU

Queue

Weight

500

Small.

Readable.

---

# BUTTON TEXT

Primary

600

Secondary

500

Ghost

500

Never bold unnecessarily.

---

# INPUT TEXT

Weight

400

Placeholder

Muted

Entered Value

Primary

Cursor always clearly visible.

---

# PROPERTY LABELS

Examples

Scale

Opacity

Rotation

Volume

Weight

500

Always aligned consistently.

---

# PROPERTY VALUES

Weight

400

Readable.

Never stronger than labels.

---

# NUMERIC VALUES

Use monospace when values update frequently.

Examples

FPS

Frame Number

Timecode

Duration

Zoom

Playback Speed

---

# TIMECODE

Always monospace.

Examples

00:01:14:12

Digit width must remain constant.

Never shift while updating.

---

# FPS

Example

60 FPS

Use monospace.

Right aligned where possible.

---

# FILE NAMES

Weight

500

Allow truncation with ellipsis.

Never wrap long filenames.

---

# TRACK NAMES

Weight

500

Readable.

Maximum

One line.

---

# CLIP NAMES

Weight

500

Centered vertically.

Ellipsis when required.

---

# AI CHAT

User Message

400

AI Message

400

Code

Monospace

Headings

600

---

# STATUS PILLS

Weight

600

Uppercase optional.

Keep compact.

---

# TOOLTIPS

Weight

400

Maximum

Two lines

Readable

Never tiny.

---

# MENUS

Weight

400

Shortcut

Monospace

Menu title

600

---

# DIALOGS

Title

700

Body

400

Buttons

600

---

# EMPTY STATES

Headline

600

Description

400

Primary Action

600

Everything centered.

---

# LINE HEIGHT

Display

1.2

Titles

1.25

Body

1.5

Captions

1.4

Maintain comfortable reading.

---

# LETTER SPACING

Display

-1%

Titles

0%

Body

0%

Captions

0.5%

Never overuse tracking.

---

# TEXT ALIGNMENT

Titles

Left

Descriptions

Left

Numbers

Right when appropriate

Timecodes

Center or Right

Buttons

Center

Maintain consistency.

---

# TEXT CONTRAST

Primary

Highest

Secondary

Medium

Muted

Low

Placeholder

Lowest

Never reduce readability.

---

# TRUNCATION

Long text uses ellipsis.

Never overflow panels.

Never wrap important values unexpectedly.

---

# LOCALIZATION

Allow additional space for longer translated strings.

Avoid fixed-width labels when possible.

---

# ACCESSIBILITY

Minimum readable size

11 px

Never rely only on color.

Maintain strong contrast.

Keyboard focus must remain visible.

---

# PERFORMANCE

Typography should remain crisp on:

100%

125%

150%

200%

Windows scaling.

Avoid blurry rendering.

---

# IMPLEMENTATION RULES

Never hardcode font sizes.

Never hardcode font weights.

Always resolve typography through theme tokens or centralized style definitions.

Maintain consistency across all widgets.

---

# FINAL PRINCIPLE

Typography should quietly organize the interface.

Users should never consciously notice the typography.

They should simply understand the interface faster because of it.

End of Part 12.