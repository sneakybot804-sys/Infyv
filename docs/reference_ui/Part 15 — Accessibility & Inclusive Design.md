# AI Gaming Video Editor
# MASTER UI DESIGN SYSTEM

## Part 15 — Accessibility & Inclusive Design

Version: 1.0

Status:
Official Accessibility Specification

---

# PURPOSE

Accessibility is a core quality requirement.

It is not an optional feature.

The application must remain usable by the widest possible range of users.

Accessibility improves:

Speed

Comfort

Readability

Professionalism

Keyboard Productivity

Long Editing Sessions

Future Maintainability

---

# DESIGN GOALS

The application should be usable:

Without a mouse

Without perfect eyesight

On different monitor sizes

At different DPI scales

With different color perception

For long editing sessions

Accessibility should never reduce visual quality.

---

# KEYBOARD FIRST

Every important workflow should be usable using only the keyboard.

Examples

Media Browser

Timeline

Preview

Inspector

AI Assistant

Toolbar

Menus

Dialogs

Every major panel should receive keyboard focus.

---

# TAB ORDER

Tab navigation must follow a logical flow.

Recommended order

Top Toolbar

↓

Media Browser

↓

Preview

↓

Timeline

↓

Inspector

↓

AI Assistant

↓

Status Bar

Never jump randomly between panels.

---

# FOCUS INDICATOR

Every focused control must display:

Accent Border

↓

Soft Glow

↓

Visible Contrast

Never rely on the default Qt focus rectangle.

---

# FOCUS VISIBILITY

Focus should remain visible even on dark surfaces.

Minimum contrast

3:1

Preferred

4.5:1

---

# KEYBOARD SHORTCUTS

Common shortcuts should always exist.

Examples

Ctrl + O

Import

Ctrl + S

Save

Ctrl + Shift + S

Save As

Ctrl + Z

Undo

Ctrl + Shift + Z

Redo

Space

Play

Delete

Delete Clip

Ctrl + A

Select All

Ctrl + F

Search

Ctrl + E

Export

F11

Fullscreen

Never hide shortcuts.

Display them in menus and tooltips.

---

# SCREEN READER SUPPORT

Every interactive control should expose:

Accessible Name

Accessible Description

Accessible Role

Decorative widgets should not be announced.

---

# BUTTONS

Buttons must always include:

Readable Label

Tooltip

Accessible Name

Icons alone are not sufficient.

---

# ICONS

Icons should never be the only way to communicate information.

Always pair important icons with:

Text

Tooltip

or

Accessible description.

---

# COLOR INDEPENDENCE

Never rely only on color.

Examples

Good

Green Badge

+

Check Icon

+

Text

Bad

Green Badge only

---

# CONTRAST

Text contrast

Minimum

4.5 : 1

Large Text

3 : 1

Critical Information

7 : 1 preferred

Never sacrifice readability.

---

# FONT SIZE

Minimum body size

11 px

Preferred

13 px

Status text

11 px

Tiny labels

10 px

Never display readable information below 10 px.

---

# CLICK TARGETS

Minimum clickable area

32 × 32 px

Preferred

36 × 36 px

Toolbar buttons

40 × 40 px

Never create tiny click targets.

---

# DRAG TARGETS

Timeline clips

Track headers

Drop zones

must remain easy to grab.

---

# SCROLLING

Mouse Wheel

Supported

Trackpad

Supported

Keyboard

Supported

Page Up / Page Down

Supported

Home / End

Supported

---

# SEARCH

Search should always receive:

Keyboard Focus

Placeholder

Clear Button

Escape to Clear

---

# EMPTY STATES

Must always explain:

What happened

↓

What the user can do next

Never display only

"No data"

---

# ERROR STATES

Every error must include:

Problem

↓

Reason

↓

Solution

↓

Retry Action

Never show cryptic errors.

---

# LOADING STATES

Never freeze the interface.

Display

Progress

↓

Status

↓

Cancelable when appropriate

---

# AI ACCESSIBILITY

Prompt box

Large

Readable

Keyboard friendly

Send

Enter

New Line

Shift + Enter

Generated content

Copyable

Selectable

Searchable

---

# TIMELINE ACCESSIBILITY

Selected clip clearly visible.

Playhead visible.

Focused clip visible.

Keyboard movement supported.

Zoom readable.

---

# PREVIEW ACCESSIBILITY

Playback controls reachable.

Fullscreen reachable.

Timecode readable.

Status readable.

---

# INSPECTOR ACCESSIBILITY

Labels aligned.

Editors keyboard accessible.

Reset buttons reachable.

Collapse sections keyboard friendly.

---

# STATUS BAR

Readable.

Low emphasis.

Never hide important status.

---

# DIALOGS

Focus trapped inside dialog.

Escape closes dialog.

Enter confirms when appropriate.

Restore previous focus on close.

---

# TOOLTIPS

Appear after

400 ms

Remain readable.

Maximum

2 lines

Do not obstruct important controls.

---

# DPI SCALING

Support

100%

125%

150%

175%

200%

UI should remain crisp.

No clipping.

No overlapping text.

---

# MULTI MONITOR

Window should scale correctly.

Support different DPI monitors.

No layout corruption.

---

# REDUCED MOTION

If reduced motion is enabled in future:

Reduce animations.

Keep feedback.

Avoid sudden movement.

---

# ACCESSIBILITY TESTING

Verify

Keyboard Only

↓

High DPI

↓

Dark Theme

↓

Long Text

↓

Color Blindness

↓

Focus Navigation

↓

Screen Reader

---

# DESIGN PRINCIPLES

Accessibility is invisible quality.

A user should never notice accessibility.

They should simply feel that the application is easier to use.

Good accessibility is good UX.

---

# IMPLEMENTATION RULES

Never remove keyboard navigation.

Never hide focus.

Never rely only on color.

Never make important controls inaccessible.

Preserve accessibility while improving visuals.

Accessibility improvements must never break architecture or tests.

---

# FINAL PRINCIPLE

A premium desktop application is accessible by default.

Accessibility is not an extra feature.

It is a core design requirement.

End of Part 15.