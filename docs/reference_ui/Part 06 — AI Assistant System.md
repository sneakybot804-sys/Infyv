# AI Gaming Video Editor
# MASTER UI DESIGN SYSTEM

## Part 06 — AI Assistant System

Version: 1.0

Status:
Official AI Workspace Specification

---

# PURPOSE

The AI Assistant is the defining feature of the application.

It is not a chatbot.

It is not a floating widget.

It is not a settings panel.

It is an intelligent editing workspace integrated into the editor.

Every interaction with the AI should feel natural, powerful, and professional.

---

# DESIGN GOALS

The AI Assistant should communicate:

Intelligent

Helpful

Fast

Premium

Reliable

Professional

Creator Focused

The AI Assistant should feel comparable to modern AI-first creative software.

Examples of inspiration:

Cursor

GitHub Copilot Workspace

Adobe Firefly

Runway

Descript

Not ChatGPT clone.

Not Discord chat.

Not Messenger UI.

---

# VISUAL PRIORITY

Preview

★★★★★

Timeline

★★★★☆

AI Assistant

★★★★☆

Inspector

★★★☆☆

Media Browser

★★★☆☆

Toolbar

★★☆☆☆

Status Bar

★☆☆☆☆

The AI Assistant should always feel like a core editing feature.

Never hide it visually.

---

# PANEL SIZE

Preferred Width

340–420 px

Minimum Width

320 px

Never compress below readability.

---

# PANEL STRUCTURE

The AI panel follows this hierarchy:

Header

↓

Current Context

↓

Prompt Area

↓

Quick Actions

↓

Suggested Actions

↓

Conversation

↓

Pipeline

↓

History

↓

Footer

Every section must have clear spacing.

---

# HEADER

Height

48 px

Contains:

AI icon

Title

Model badge

Connection status

Settings button

Never overcrowd.

---

# MODEL BADGE

Examples

GPT-5

Local AI

Qwen

Gemini

Claude

Display as a subtle status pill.

---

# CONNECTION STATUS

States

Connected

Offline

Thinking

Generating

Error

Use small colored status pills.

---

# CURRENT CONTEXT

Always show what AI is working on.

Examples

Current Clip

Current Timeline Selection

Selected Track

Entire Project

No Selection

Users should always know the AI context.

---

# PROMPT AREA

This is the most important component.

Large.

Comfortable.

Desktop optimized.

Minimum Height

120 px

Preferred Height

160–220 px

Rounded.

Glass surface.

Soft border.

Placeholder examples:

Describe your edit...

Generate highlights...

Remove silence...

Create captions...

Improve audio...

---

# SEND BUTTON

Primary Button.

Cyan accent.

Always aligned with prompt.

Keyboard Shortcut

Enter

Multi-line

Shift + Enter

---

# QUICK ACTIONS

Displayed directly below prompt.

Examples

Auto Edit

Auto Captions

Remove Silence

Scene Detection

Highlight Generator

Noise Removal

Auto Zoom

Smart Reframe

One click.

Large click targets.

---

# SUGGESTED ACTIONS

The AI should proactively suggest tasks.

Examples

Detected gameplay moments

Remove dead air

Generate subtitles

Improve audio

Export vertical version

Display as cards.

Dismissable.

---

# CONVERSATION

Chat history displayed as message cards.

User messages

Right aligned.

AI messages

Left aligned.

Maximum line width

75%

Glass cards.

Readable spacing.

---

# AI MESSAGE CARD

Contains

Message

Timestamp

Optional action buttons

Examples

Apply

Preview

Copy

Retry

---

# USER MESSAGE CARD

Simpler appearance.

No glow.

Accent border optional.

---

# PIPELINE

Always visible.

Shows running AI tasks.

Examples

Scene Detection

█████████░

90%

Caption Generation

██████░░░░

60%

Audio Cleanup

Queued

Use progress bars.

---

# HISTORY

Recent completed AI tasks.

Examples

Generated Captions

Yesterday

Removed Silence

5 min ago

Generated Highlights

Today

Compact cards.

---

# RECOMMENDATIONS

The AI may recommend actions based on project analysis.

Examples

Large silence detected

Audio clipping found

Low bitrate source

Scene changes detected

Use informational cards.

Never interrupt workflow.

---

# EMPTY STATE

When no conversation exists

Display

Illustration

↓

Headline

↓

Description

↓

Suggested Prompts

↓

Quick Actions

Never show a blank panel.

---

# LOADING STATE

When AI is processing

Disable prompt.

Show progress.

Display animated status.

Never freeze.

---

# ERROR STATE

Examples

Network Error

Model Offline

Generation Failed

GPU Busy

Display

Icon

↓

Headline

↓

Explanation

↓

Retry

---

# STATUS PILLS

Examples

Thinking

Generating

Ready

Offline

Local

Cloud

GPU

CPU

Queue

Small.

Consistent.

Rounded.

---

# ACTION CARDS

Cards contain:

Icon

↓

Title

↓

Description

↓

Primary Button

↓

Optional Secondary Button

Used for

Recommendations

Suggestions

Automation

Templates

---

# CONTEXT CARDS

Examples

Selected Clip

Selected Track

Timeline Range

Project Duration

Resolution

FPS

Read-only.

---

# AI OUTPUT

Generated content appears as expandable cards.

Examples

Captions

Transcript

Summary

Highlight List

Edit Plan

Expandable.

Searchable.

Copyable.

---

# PROMPT HISTORY

Recent prompts.

Searchable.

Reusable.

Pin favorite prompts.

Never lose context.

---

# ANIMATIONS

Message

Fade In

180 ms

Suggestions

Slide Up

200 ms

Pipeline

Smooth Progress

Prompt Focus

150 ms

Never flashy.

---

# COLOR SYSTEM

Primary

Cyan

AI Accent

Purple

Thinking

Blue

Success

Green

Warning

Orange

Error

Red

Maintain consistency.

---

# ACCESSIBILITY

Prompt must always remain readable.

Keyboard navigation supported.

Visible focus states.

High contrast text.

---

# PERFORMANCE

Never block the UI.

Heavy AI tasks should display progress.

Keep scrolling smooth.

Avoid excessive blur.

---

# DESIGN PRINCIPLES

The AI Assistant is a productivity tool.

It should reduce work.

Not create distractions.

Every element should support the editing workflow.

The AI should feel integrated into the editor, not attached beside it.

---

# IMPLEMENTATION RULES

Do not implement AI logic here.

Do not change backend.

Do not modify APIs.

Do not add business logic.

Preserve object names.

Preserve tests.

Improve visual design only.

Future milestones should continuously evolve the AI Assistant toward a premium AI-first editing experience.

End of Part 06.