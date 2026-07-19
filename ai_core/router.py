"""Model router for ai_core: task kind -> model id + fallbacks (Qt-free).

The router owns the "which model" decision. In auto mode it consults, in
order: explicit config overrides, then the built-in routing table. In manual
mode every text task uses the configured manual model. Fallback chains give
the RetryManager alternatives when a model repeatedly fails.

Model ids use gateway namespacing (``vendor/model``) because OmniRoute is
the primary provider; direct providers receive the bare id (the provider
strips the namespace itself if needed).

No Qt symbol is imported here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

from ai_core.config import AIConfig
from ai_core.types import TaskKind

#: Built-in auto-mode routing table: task -> (primary, *fallbacks).
_DEFAULT_ROUTES: Dict[TaskKind, Tuple[str, ...]] = {
    # Coding + large reasoning -> Claude.
    TaskKind.CODING: (
        "anthropic/claude-sonnet-4-5",
        "openai/gpt-4o",
        "deepseek/deepseek-coder-v2",
    ),
    TaskKind.REASONING: (
        "anthropic/claude-sonnet-4-5",
        "openai/gpt-4o",
        "google/gemini-2.0-pro",
    ),
    TaskKind.EDIT_PLAN: (
        "anthropic/claude-sonnet-4-5",
        "openai/gpt-4o",
    ),
    TaskKind.EFFECTS: ("anthropic/claude-sonnet-4-5", "openai/gpt-4o"),
    TaskKind.TRANSITION: ("anthropic/claude-sonnet-4-5", "openai/gpt-4o"),
    # General chat -> GPT.
    TaskKind.CHAT: (
        "openai/gpt-4o",
        "anthropic/claude-sonnet-4-5",
        "meta/llama-3.3-70b",
    ),
    TaskKind.SCRIPT: ("openai/gpt-4o", "anthropic/claude-sonnet-4-5"),
    TaskKind.TITLE: ("openai/gpt-4o-mini", "openai/gpt-4o"),
    TaskKind.DESCRIPTION: ("openai/gpt-4o-mini", "openai/gpt-4o"),
    TaskKind.TAGS: ("openai/gpt-4o-mini", "openai/gpt-4o"),
    # Vision / OCR -> Gemini.
    TaskKind.VISION: (
        "google/gemini-2.0-flash",
        "openai/gpt-4o",
        "anthropic/claude-sonnet-4-5",
    ),
    TaskKind.OCR: ("google/gemini-2.0-flash", "openai/gpt-4o"),
    TaskKind.VIDEO_ANALYSIS: (
        "google/gemini-2.0-pro",
        "google/gemini-2.0-flash",
    ),
    TaskKind.AUDIO_ANALYSIS: ("google/gemini-2.0-flash", "openai/gpt-4o"),
    TaskKind.SUBTITLES: ("openai/whisper-large-v3", "google/gemini-2.0-flash"),
    # Generation models.
    TaskKind.THUMBNAIL: ("bfl/flux-1.1-pro", "stability/sdxl"),
    TaskKind.IMAGE_GENERATION: ("bfl/flux-1.1-pro", "stability/sdxl"),
    TaskKind.VIDEO_GENERATION: ("google/veo-2", "kling/kling-1.5"),
    TaskKind.SPEECH_TO_TEXT: ("openai/whisper-large-v3",),
    TaskKind.TEXT_TO_SPEECH: ("elevenlabs/eleven-multilingual-v2",),
}

#: Task kinds that stay auto-routed even in manual mode (a manual chat model
#: cannot generate images/speech).
_ALWAYS_AUTO = frozenset(
    {
        TaskKind.THUMBNAIL,
        TaskKind.IMAGE_GENERATION,
        TaskKind.VIDEO_GENERATION,
        TaskKind.SPEECH_TO_TEXT,
        TaskKind.TEXT_TO_SPEECH,
    }
)


@dataclass(frozen=True)
class Route:
    """A routing decision: primary model + ordered fallbacks."""

    model: str
    fallbacks: Tuple[str, ...] = ()

    def chain(self) -> Tuple[str, ...]:
        """Return the full ordered model chain (primary first)."""
        return (self.model,) + self.fallbacks


class ModelRouter:
    """Resolves a :class:`TaskKind` to a :class:`Route`.

    Args:
        config: The AI configuration (overrides, auto/manual mode).
    """

    def __init__(self, config: AIConfig) -> None:
        self._config = config

    def route(self, task: TaskKind) -> Route:
        """Return the model route for ``task``.

        Order of precedence: config override -> manual mode (text tasks
        only) -> built-in table -> the chat route as the final default.
        """
        override = self._config.model_overrides.get(task.value)
        table = _DEFAULT_ROUTES.get(task) or _DEFAULT_ROUTES[TaskKind.CHAT]
        if override:
            return Route(model=override, fallbacks=table)
        if not self._config.auto_mode and task not in _ALWAYS_AUTO:
            return Route(model=self._config.manual_model, fallbacks=table)
        return Route(model=table[0], fallbacks=table[1:])
