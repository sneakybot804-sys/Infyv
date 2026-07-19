"""OmniRoute provider: the primary multi-model gateway (OpenAI-compatible).

OmniRoute exposes many upstream models (Claude / GPT / Gemini / DeepSeek /
Qwen / Llama / Grok / Flux / SDXL / Whisper / ElevenLabs / Veo / ...) behind
one OpenAI-compatible chat/completions API, addressed by namespaced model ids
(e.g. ``anthropic/claude-sonnet-4-5``). Because the wire format is the
OpenAI schema, this class simply reuses :class:`OpenAICompatProvider` with
support for EVERY task kind — the gateway, not this client, decides which
upstream serves a given model id.

No Qt symbol is imported here.
"""
from __future__ import annotations

from ai_core.providers.openai_provider import OpenAICompatProvider
from ai_core.types import TaskKind


class OmniRouteProvider(OpenAICompatProvider):
    """OpenAI-compatible client for the OmniRoute gateway (all task kinds)."""

    def supports(self, task: TaskKind) -> bool:
        """OmniRoute routes every task kind to some upstream model."""
        return True
