# AI Gaming Video Editor
# MASTER UI DESIGN SYSTEM

## Part 08 — Motion System & Micro Interactions

Version: 1.0

Status:
Official Motion Specification

---

# PURPOSE

Motion exists to communicate.

Motion is not decoration.

Every animation must improve clarity.

Users should immediately understand:

What changed

What was selected

Where focus moved

What is loading

What completed

Motion should never exist just because it looks cool.

---

# DESIGN GOALS

The application should feel:

Fluid

Responsive

Predictable

Professional

Modern

Elegant

Never flashy.

Never distracting.

Never game-like.

---

# MOTION PHILOSOPHY

Every animation must answer one question:

Why does this animation exist?

If there is no purpose,

remove it.

---

# ANIMATION PRINCIPLES

Animations should be:

Fast

Subtle

Meaningful

Consistent

Interruptible

Never block user interaction.

---

# DURATION SYSTEM

Micro Hover

100–120 ms

Hover Exit

100 ms

Focus

120–150 ms

Button Press

80 ms

Selection

150–180 ms

Expand

180–220 ms

Collapse

180–220 ms

Fade

180 ms

Dialog

220–260 ms

Panel

250 ms

Fullscreen

300 ms

Never exceed

400 ms

for standard UI interactions.

---

# EASING

Preferred easing

Ease Out

Ease In Out

Never linear.

Never elastic.

Never bounce.

Professional desktop software should feel smooth.

---

# HOVER EFFECTS

Every interactive component responds to hover.

Examples

Buttons

Cards

Timeline Clips

Track Headers

Toolbar Icons

Tabs

Menus

Hover may include

Slight brightness increase

Soft elevation

Border highlight

Cursor change

Never dramatic scaling.

---

# BUTTON INTERACTIONS

Hover

Increase elevation slightly.

Background brightens.

Pressed

Slight downward movement.

Reduced shadow.

Release

Return smoothly.

Primary buttons may have a soft glow.

---

# CARD INTERACTIONS

Hover

Increase shadow.

Border brightens slightly.

Optional subtle lift

1–2 px

Never more.

---

# PANEL INTERACTIONS

Panels never animate continuously.

Only animate

Opening

Closing

Docking

Resizing

Never pulse.

Never breathe.

---

# SIDEBAR

Expand

Slide

220 ms

Collapse

Slide

220 ms

Content fades slightly.

---

# TIMELINE

Clip Hover

Soft highlight

Clip Selection

Glow

Outline

Drag

Elevation

Shadow

Insertion Indicator

Resize

Live preview

Playhead movement must remain smooth.

---

# PLAYHEAD

Always smooth.

Never jump.

Scrolling should remain synchronized.

Current frame indicator should stay stable.

---

# PREVIEW

Toolbar

Fade

150 ms

HUD

Fade

150 ms

Overlay

Fade

180 ms

Fullscreen

300 ms

Loading

Smooth transition

Never flash.

---

# AI ASSISTANT

New Message

Fade + Slide

Pipeline Progress

Smooth width animation

Suggestion Cards

Slide Up

Prompt Focus

Glow

Processing

Animated status indicator

Never spinner overload.

---

# INSPECTOR

Expand Sections

200 ms

Collapse Sections

200 ms

Property Highlight

Fade

Search Filter

Crossfade

Never instant pop.

---

# DROPDOWNS

Open

Fade + Scale

Close

Fade

No bouncing.

---

# MENUS

Fade

150 ms

Hover

Immediate

Selection

Fade

---

# TABS

Switch

Crossfade

150 ms

Underline animation

Optional

Never slide entire layout.

---

# CHECKBOXES

Check

120 ms

Switch

180 ms

Smooth thumb movement.

---

# TOGGLES

Thumb slides smoothly.

Track color transitions.

No abrupt changes.

---

# SLIDERS

Thumb movement

Smooth

Track fill updates instantly.

Value animation

Optional.

---

# SCROLLING

Smooth scrolling.

Momentum optional.

Overlay scrollbars fade.

Never thick flashing scrollbars.

---

# TOOLTIPS

Fade In

120 ms

Fade Out

120 ms

No scaling.

---

# DIALOGS

Fade + Scale

220 ms

Background blur appears gradually.

Closing reverses animation.

---

# MODALS

Focus transition

220 ms

Background interaction disabled.

---

# EMPTY STATES

Illustration fades in.

Buttons appear after text.

Never animate continuously.

---

# LOADING

Skeleton shimmer.

Progress bars animate smoothly.

Status updates fade.

Never freeze.

---

# ERROR STATES

Appear gently.

Avoid shaking animations.

Highlight solution instead of error.

---

# SUCCESS STATES

Small confirmation.

Subtle accent flash.

No confetti.

No fireworks.

---

# NOTIFICATIONS

Slide from corner.

Fade.

Auto dismiss.

Remain readable.

---

# STATUS PILLS

Color transition only.

No movement.

---

# GLOW

Glow is reserved for

Playhead

Primary Buttons

Focused Input

Selected Clip

AI Processing

Never glow everything.

Glow should be rare.

---

# BLUR

Use only on

Dialogs

Floating Panels

Menus

Glass Cards

Avoid excessive blur.

---

# SHADOW ANIMATION

Shadow changes gradually.

Never pop.

---

# RESIZING

Panels resize smoothly.

Avoid layout jumps.

Maintain alignment.

---

# WINDOW OPEN

Fade

220 ms

Restore previous layout.

---

# WINDOW CLOSE

Quick fade.

No dramatic animation.

---

# DRAG & DROP

Drop target highlights.

Border glows.

Drop indicator fades.

Success confirmation subtle.

---

# PERFORMANCE

Animations must never reduce responsiveness.

Prioritize smooth interaction over visual effects.

Avoid unnecessary repaints.

Avoid expensive blur.

Keep CPU and GPU usage reasonable.

---

# ACCESSIBILITY

Animations should respect reduced-motion preferences if implemented.

Focus states must remain visible.

Motion should never hide information.

---

# DESIGN PRINCIPLES

Motion should make the interface feel alive,

not busy.

Users should notice the result of the interaction,

not the animation itself.

The best animation is one that feels natural enough to disappear.

---

# IMPLEMENTATION RULES

Do not introduce animation frameworks unnecessarily.

Reuse existing Qt animation systems.

Keep APIs unchanged.

Do not modify business logic.

Do not change tests.

Do not alter backend behavior.

Improve visual polish only.

Future milestones should maintain a consistent motion language across the entire application.

End of Part 08.