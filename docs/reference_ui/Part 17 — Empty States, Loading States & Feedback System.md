# AI Gaming Video Editor
# MASTER UI DESIGN SYSTEM

## Part 17 — Empty States, Loading States & Feedback System

Version: 1.0

Status:
Official Feedback & State Design Specification

---

# PURPOSE

This document defines how the application communicates with users when content is unavailable, loading, processing, completed, or fails.

A professional application should never leave users wondering:

What happened?

What is happening?

What should I do next?

Every system state must provide clear feedback.

---

# DESIGN GOALS

The application should always feel:

Responsive

Helpful

Professional

Predictable

Trustworthy

Every state should reduce uncertainty.

---

# STATE CATEGORIES

The application supports the following UI states:

Empty

Loading

Processing

Success

Warning

Error

Offline

Disabled

Busy

Queued

Completed

Every state must have its own visual language.

---

# EMPTY STATE

Purpose

Explain why nothing is shown.

Never leave blank areas.

Every empty state contains:

Illustration

↓

Headline

↓

Description

↓

Primary Action

↓

Optional Secondary Action

---

# EMPTY STATE HEADLINE

Examples

Drop Media Here

Import Your First Clip

No Projects Yet

No AI History

No Search Results

Never use generic text.

Example to avoid

"No Data"

---

# EMPTY STATE DESCRIPTION

Maximum

2–3 lines

Explain:

Why the area is empty

↓

What the user should do next

Readable.

Centered.

---

# EMPTY STATE ACTIONS

Primary Action

High emphasis

Secondary Action

Ghost button

Examples

Import Media

Create Project

Browse Files

Generate AI Edit

---

# EMPTY STATE ILLUSTRATION

Minimal

Monochrome

Accent Highlights

Low Detail

Never cartoon.

Never colorful.

Never distracting.

---

# SEARCH EMPTY STATE

When no results exist

Display

Search Icon

↓

Headline

↓

Suggestion

Example

No results found.

Try different keywords or clear filters.

---

# LOADING STATE

Loading should always communicate progress.

Never freeze the interface.

Never display blank content.

---

# LOADING TYPES

Instant

No loader

Short

Spinner

Medium

Skeleton

Long

Progress Bar

Very Long

Progress + ETA

---

# SPINNER

Small.

Centered.

Accent color.

Never oversized.

Never spin too fast.

---

# PROGRESS BAR

Rounded.

Thin.

Animated.

Always display percentage when meaningful.

---

# SKELETON LOADING

Preferred for:

Media Browser

Inspector

AI History

Project List

Cards

Avoid flashing placeholders.

---

# PROGRESS INFORMATION

Whenever possible display:

Current Task

↓

Progress

↓

Remaining Steps

↓

Estimated Time

Users should always know what is happening.

---

# AI PROCESSING

Display:

Animated Status

↓

Pipeline Progress

↓

Current Operation

↓

Cancelable if possible

Examples

Analyzing Timeline

Generating Captions

Removing Silence

Detecting Highlights

---

# RENDERING

Render state displays

Progress

↓

Frame Count

↓

Time Remaining

↓

Encoding Speed

↓

Current File

Never display only a spinner.

---

# SUCCESS STATE

Successful operations should provide subtle confirmation.

Examples

Export Complete

Project Saved

AI Generation Finished

Media Imported

---

# SUCCESS FEEDBACK

Show

Success Icon

↓

Headline

↓

Optional Action

↓

Auto dismiss

No unnecessary dialogs.

---

# WARNING STATE

Warnings should inform,

not alarm.

Examples

Low Disk Space

Proxy Disabled

GPU Memory High

Missing Fonts

Use Orange Accent.

---

# ERROR STATE

Errors must help users recover.

Every error contains:

Error Icon

↓

Headline

↓

Explanation

↓

Solution

↓

Retry Button

Never display technical stack traces.

---

# ERROR MESSAGES

Good

Media could not be imported.

Unsupported codec.

Try converting the file or choosing another clip.

Bad

Error 0xA84F

---

# OFFLINE STATE

Display

Connection Status

↓

Explanation

↓

Retry

↓

Offline Mode

Applicable for future cloud features.

---

# DISABLED STATE

Disabled controls remain:

Visible

Readable

Clearly inactive

Never disappear.

Explain why when appropriate.

---

# BUSY STATE

When a feature is unavailable because another task is running

Display

Busy Indicator

↓

Reason

↓

Estimated Completion

---

# QUEUE STATE

Background tasks should appear inside a queue.

Display

Task Name

↓

Progress

↓

Queue Position

↓

Cancel

---

# BACKGROUND TASKS

Examples

Generating Proxy

Rendering

Transcoding

AI Analysis

Background tasks should never interrupt editing.

---

# NOTIFICATIONS

Use toast notifications.

Position

Bottom Right

Auto Dismiss

4–6 seconds

Never block workflow.

---

# NOTIFICATION TYPES

Information

Blue

Success

Green

Warning

Orange

Error

Red

AI

Purple

---

# CONFIRMATIONS

Confirmation dialogs only for destructive actions.

Examples

Delete Project

Delete Clip

Reset Settings

Avoid confirmation overload.

---

# RETRY

Every recoverable failure should provide Retry.

Never force users to repeat the entire workflow.

---

# CANCEL

Long-running operations should expose Cancel whenever possible.

Users should remain in control.

---

# TIMEOUT

When operations take unusually long

Display

Still Working...

↓

Current Step

↓

Retry Option

Never appear frozen.

---

# NETWORK STATES

Future cloud features should communicate:

Connecting

Connected

Offline

Syncing

Conflict

Clear status.

---

# FILE STATES

Examples

Missing

Relink Required

Read Only

Modified

Unsaved

Use badges.

Never surprise users.

---

# AUTO SAVE

Future implementation should show

Saving...

↓

Saved

↓

Failed

Without interrupting editing.

---

# STATUS BAR FEEDBACK

Background tasks appear here.

Examples

Rendering

Analyzing

Importing

Exporting

Keep compact.

---

# ACCESSIBILITY

Feedback must not rely only on color.

Always include:

Text

↓

Icon

↓

Status

Screen readers should announce important changes.

---

# MOTION

Feedback animations should be subtle.

Fade

Slide

Progress

Avoid shaking.

Avoid flashing.

---

# PERFORMANCE

Feedback should appear immediately.

Never delay visual response.

Avoid excessive animation.

---

# DESIGN PRINCIPLES

Every application state should answer three questions:

What happened?

What is happening?

What should I do next?

If users cannot answer those questions,

the UI has failed.

---

# IMPLEMENTATION RULES

Never leave blank panels.

Never leave users without feedback.

Never hide errors.

Never interrupt workflow unnecessarily.

Preserve architecture.

Do not change backend.

Do not change APIs.

Do not modify tests.

Improve visual communication only.

---

# FINAL PRINCIPLE

Professional software constantly communicates with users.

Silence creates uncertainty.

Good feedback builds confidence.

Every state should make the application feel reliable and trustworthy.

End of Part 17.