"""Prompt builder for ai_core: task + context + memory -> system prompt.

The caller passes only a short instruction ("Generate cinematic edit"); this
module expands it with the collected :class:`~ai_core.context.AIContext`,
persisted preferences, and a per-task system template — including the exact
output-format contract the :class:`~ai_core.parser.ResponseParser` expects.

No Qt symbol is imported here.
"""
from __future__ import annotations

from typing import Dict

from ai_core.context import AIContext
from ai_core.memory import MemoryEngine
from ai_core.types import TaskKind

_BASE_IDENTITY = (
    "You are the AI brain of INFY EDIT PRO, a professional desktop video "
    "editor for gaming content. Answer precisely and never invent editor "
    "state that is not in the provided context."
)

#: Per-task system templates, including the parser's output contracts.
_TASK_TEMPLATES: Dict[TaskKind, str] = {
    TaskKind.EDIT_PLAN: (
        "Produce a video edit plan. Respond with ONLY a JSON object: "
        '{"segments": [{"start": <s>, "end": <s>, "label": "...", '
        '"reason": "..."}], "style": "...", "notes": "..."}. '
        "Segments must be within the video duration, non-overlapping and "
        "in chronological order."
    ),
    TaskKind.SUBTITLES: (
        "Generate subtitles. Respond with ONLY a JSON object: "
        '{"language": "<code>", "lines": [{"start": <s>, "end": <s>, '
        '"text": "..."}]}. Lines must be chronological.'
    ),
    TaskKind.VISION: (
        "Analyze the provided frame(s). Respond with ONLY a JSON object: "
        '{"description": "...", "labels": ["..."], "confidence": 0.0-1.0}.'
    ),
    TaskKind.OCR: (
        "Extract every piece of visible text. Respond with ONLY a JSON "
        'object: {"text": "<all text>", "regions": ["..."]}.'
    ),
    TaskKind.SCRIPT: (
        "Write a video script. Respond with ONLY a JSON object: "
        '{"script": "...", "scenes": ["..."]}.'
    ),
    TaskKind.TITLE: (
        "Suggest video titles. Respond with ONLY a JSON object: "
        '{"titles": ["..."]}. 5 suggestions, most clickable first.'
    ),
    TaskKind.DESCRIPTION: (
        "Write a video description optimized for search and engagement. "
        "Respond with plain text only."
    ),
    TaskKind.TAGS: (
        "Suggest video tags. Respond with ONLY a JSON object: "
        '{"tags": ["..."]}. 10-20 lowercase tags.'
    ),
    TaskKind.THUMBNAIL: (
        "Write an image-generation brief for a video thumbnail. Respond "
        'with ONLY a JSON object: {"prompt": "...", '
        '"negative_prompt": "...", "style": "..."}.'
    ),
    TaskKind.CODING: (
        "You are assisting with code. Return complete, runnable code in a "
        "single fenced block; explain only what is non-obvious."
    ),
    TaskKind.EFFECTS: (
        "Recommend visual effects for the described clip. Respond with "
        'ONLY a JSON object: {"tags": ["<effect names>"]}.'
    ),
    TaskKind.TRANSITION: (
        "Recommend transitions between the described clips. Respond with "
        'ONLY a JSON object: {"tags": ["<transition names>"]}.'
    ),
}


class PromptBuilder:
    """Builds the final system prompt for a task.

    Args:
        memory: The preference store rendered into every prompt.
    """

    def __init__(self, memory: MemoryEngine) -> None:
        self._memory = memory

    def build_system(self, task: TaskKind, context: AIContext) -> str:
        """Compose identity + task contract + editor context + preferences."""
        sections = [_BASE_IDENTITY]
        template = _TASK_TEMPLATES.get(task)
        if template:
            sections.append(template)
        context_block = self._render_context(context)
        if context_block:
            sections.append("EDITOR CONTEXT:\n" + context_block)
        preferences = self._memory.preference_lines()
        if preferences:
            sections.append("USER PREFERENCES:\n" + preferences)
        return "\n\n".join(sections)

    @staticmethod
    def _render_context(context: AIContext) -> str:
        """Render the context snapshot as compact prompt lines."""
        lines = []
        if context.video_name:
            lines.append(f"- Video: {context.video_name}")
        if context.timeline_duration > 0:
            lines.append(
                f"- Timeline duration: {context.timeline_duration:.1f}s"
            )
        if context.track_names:
            lines.append(f"- Tracks: {', '.join(context.track_names)}")
        if context.clip_summaries:
            shown = context.clip_summaries[:20]
            lines.append(f"- Clips ({len(context.clip_summaries)}):")
            lines.extend(f"    - {clip}" for clip in shown)
            if len(context.clip_summaries) > len(shown):
                lines.append(
                    f"    - ... {len(context.clip_summaries) - len(shown)}"
                    " more"
                )
        if context.selected_clip:
            lines.append(f"- Selected clip: {context.selected_clip}")
        if context.playhead_seconds > 0:
            lines.append(f"- Playhead: {context.playhead_seconds:.2f}s")
        if context.marker_count:
            lines.append(f"- Markers: {context.marker_count}")
        if context.artifacts:
            lines.append(f"- Artifacts: {', '.join(context.artifacts)}")
        if context.runnable_phases:
            lines.append(
                f"- Runnable phases: {', '.join(context.runnable_phases)}"
            )
        if context.settings:
            shown_settings = list(context.settings.items())[:15]
            rendered = ", ".join(f"{k}={v}" for k, v in shown_settings)
            lines.append(f"- Settings: {rendered}")
        return "\n".join(lines)
