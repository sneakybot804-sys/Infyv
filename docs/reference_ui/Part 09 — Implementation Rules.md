# AI Gaming Video Editor
# MASTER UI DESIGN SYSTEM

## Part 09 — Implementation Rules

Version: 1.0

Status:
Official Implementation Rules

---

# PURPOSE

This document defines the implementation rules for every future UI milestone.

These rules are mandatory.

If a milestone conflicts with these rules, these rules take priority unless the user explicitly overrides them.

The goal is to continuously improve the application's visual quality while preserving the stability of the production codebase.

---

# GENERAL PRINCIPLES

Every implementation must satisfy all of the following:

Improve visual quality

Improve consistency

Improve hierarchy

Improve usability

Preserve architecture

Preserve maintainability

Preserve production stability

Never sacrifice architecture for appearance.

---

# HIGHEST PRIORITIES

Priority Order

1

Architecture

2

Public APIs

3

Signals

4

Tests

5

Functionality

6

Design System

7

Visual Improvements

If visual changes require breaking the first five priorities,

they must not be implemented.

---

# REQUIRED WORKFLOW

Every UI milestone must begin with:

Read

docs/reference_ui/DESIGN_SPEC.md

Then read every markdown file referenced by DESIGN_SPEC.md.

Treat those documents as the authoritative design specification.

Never skip this step.

---

# BEFORE WRITING CODE

Understand the existing implementation.

Read the current file.

Reuse existing widgets.

Reuse existing tokens.

Reuse existing theme manager.

Reuse existing controls.

Never redesign blindly.

---

# IMPLEMENTATION STRATEGY

Always prefer:

Extend

instead of

Replace.

Prefer

Reuse

instead of

Rewrite.

Prefer

Small safe improvements

instead of

Large risky redesigns.

---

# VISUAL IMPROVEMENTS

Focus on improving:

Hierarchy

Spacing

Typography

Alignment

Glassmorphism

Elevation

Component consistency

Panel proportions

Motion

Hover states

Empty states

Scrollbars

Toolbar organization

Timeline readability

Preview quality

AI workspace

Inspector organization

Avoid cosmetic changes that users cannot notice.

---

# MULTI-FILE CHANGES

You may modify multiple production files if necessary.

Do not artificially limit changes to one file.

However,

every changed file must have a clear purpose.

Do not change unrelated files.

---

# COMPONENT REUSE

Before creating a new widget,

check whether an existing widget already satisfies the requirement.

Reuse whenever possible.

Avoid duplicate components.

---

# DESIGN TOKENS

Never hardcode:

Colors

Spacing

Radius

Typography

Shadows

Animation timings

Always use the design token system.

---

# STYLING

Use ThemeManager.

Use Tokens.

Use global stylesheet where appropriate.

Avoid inline styling unless absolutely necessary.

---

# OBJECT NAMES

Never rename:

Object names

Signals

Slots

Public methods

Classes

Enums

Frozen identifiers

unless explicitly instructed.

---

# PUBLIC API

Do not change:

Method names

Parameters

Return types

Public behavior

unless the user explicitly requests it.

---

# SIGNALS

Never rename signals.

Never remove signals.

Never change signal semantics.

---

# TESTS

Tests are production contracts.

Never modify tests to make visual work pass.

Only update tests when a genuine production bug requires it.

The target is always:

All tests passing.

---

# FUNCTIONALITY

Do not implement:

Backend

AI logic

Rendering

Export

Playback

Business logic

Persistence

Networking

Undo system

unless the milestone explicitly requests those features.

---

# PLACEHOLDERS

Placeholder controls are acceptable when functionality is outside the milestone scope.

Examples

Buttons

Sliders

Dropdowns

Cards

Badges

Prompt areas

Progress indicators

These placeholders must remain visually professional.

---

# FILE ORGANIZATION

Keep changes localized.

Prefer modifying the production file directly responsible for the UI.

Avoid scattering small changes across many unrelated files.

---

# PERFORMANCE

Visual improvements must remain lightweight.

Avoid expensive rendering.

Avoid excessive blur.

Avoid unnecessary repaints.

Maintain responsive desktop performance.

---

# COMMIT STRATEGY

Each milestone should ideally produce:

One logical commit.

Only create additional commits if a genuine correctness issue is discovered.

Avoid commit noise.

---

# SELF REVIEW

Before finishing:

Review imports.

Review object names.

Review signals.

Review public APIs.

Review styling.

Review constructor usage.

Review theme tokens.

Review layout.

Review consistency with DESIGN_SPEC.

Only create another commit if a real correctness problem exists.

---

# REPORTING

After implementation report only:

Commit SHA

Parent SHA

Files Changed

Final HEAD SHA

Expected pytest result

Nothing else.

---

# DESIGN CONSISTENCY

Never introduce a second design language.

Always move closer to the MASTER UI DESIGN SYSTEM.

If an older implementation conflicts visually with the design system,

improve it while preserving functionality.

---

# ARCHITECTURE

Never invent unnecessary services.

Never invent controllers.

Never invent future architecture "just in case."

Keep the code simple.

Keep the implementation production-ready.

---

# VISUAL QUALITY

The application should progressively evolve toward a premium commercial desktop editor.

Every milestone should make the application feel noticeably better.

Avoid changes that users cannot perceive.

Meaningful improvements are preferred over tiny cosmetic tweaks.

---

# FINAL PRINCIPLE

The MASTER UI DESIGN SYSTEM is the single source of truth for visual decisions.

Future milestones must continuously move the application closer to that design while preserving:

Architecture

Public APIs

Signals

Object Names

Functionality

Tests

Maintainability

Production quality.

End of Part 09.