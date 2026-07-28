"""Provider registry for ai_core.

One construction point maps provider names to classes. Adding a provider =
adding one class + one registry entry; AIManager and the router never change
(Open/Closed).

No Qt symbol is imported here.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional, Type

from ai_core.config import AIConfig
from ai_core.errors import AIConfigError
from ai_core.providers.base import AIProvider
from ai_core.providers.claude_provider import ClaudeProvider
from ai_core.providers.gemini_provider import GeminiProvider
from ai_core.providers.ollama_provider import OllamaProvider
from ai_core.providers.omniroute_provider import OmniRouteProvider
from ai_core.providers.openai_provider import OpenAICompatProvider

#: Name -> provider class. Extend here to add a provider.
PROVIDER_CLASSES: Dict[str, Type[AIProvider]] = {
    "omniroute": OmniRouteProvider,
    "openai": OpenAICompatProvider,
    "claude": ClaudeProvider,
    "gemini": GeminiProvider,
    "ollama": OllamaProvider,
}


def build_providers(
    config: AIConfig, *, base_dir: Optional[Path] = None
) -> Dict[str, AIProvider]:
    """Construct every enabled, known provider from ``config``.

    Unknown names are skipped (a config may list future providers before the
    code ships). Raises :class:`AIConfigError` when no provider could be
    built at all.
    """
    providers: Dict[str, AIProvider] = {}
    for name, provider_config in config.providers.items():
        if not provider_config.enabled:
            continue
        cls = PROVIDER_CLASSES.get(name)
        if cls is None:
            continue
        providers[name] = cls(
            provider_config,
            api_key=provider_config.resolve_api_key(base_dir),
            timeout_seconds=config.timeout_seconds,
        )
    if not providers:
        raise AIConfigError("No enabled AI provider could be constructed.")
    return providers
