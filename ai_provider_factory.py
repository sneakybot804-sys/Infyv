"""Lightweight AI provider factory for the CLI.

Builds and returns the correct :class:`AIProvider` from ai_core based on
the session's AI settings. Abstracts away all provider-specific setup
so the rest of the application only sees a simple ``generate()`` API.

Adding a future provider requires:
  1. Create a new provider class in ``ai_core/providers/``
  2. Register it in ``ai_core/providers/__init__.py``
  3. Add its name + settings to :class:`AiSettings`
  4. Add a branch in :func:`_build_provider` below
"""
from __future__ import annotations

import os
from typing import Optional

from ai_core.config import AIProviderConfig
from ai_core.providers.base import AIProvider
from ai_core.providers.ollama_provider import OllamaProvider
from ai_core.providers.openai_provider import OpenAICompatProvider
from ai_core.types import AIRequest, AIResponse, AIUsage, Modality, TaskKind
from logger import get_logger

logger = get_logger(__name__)


class ProviderFactoryError(RuntimeError):
    """Raised when a provider cannot be built or fails a health check."""


class AiProviderClient:
    """Thin wrapper around an AIProvider for CLI consumption.

    Provides a simple ``generate(system, prompt) -> str`` interface
    that is compatible with both the ``LlmClient`` Protocol used by
    ``DecisionAgent`` and the internal ``_call_ollama`` pattern used
    by ``GamingEditorAgent``.
    """

    def __init__(self, provider: AIProvider, model: str) -> None:
        self._provider = provider
        self._model = model

    @property
    def provider_name(self) -> str:
        return self._provider.name

    @property
    def model(self) -> str:
        return self._model

    def generate(self, system: str, prompt: str) -> str:
        """Send system+prompt to the provider and return the raw text response."""
        request = AIRequest(
            task=TaskKind.EDIT_PLAN,
            prompt=prompt,
            system=system,
            model=self._model,
        )
        response = self._provider.complete(request)
        return response.text

    def health_check(self) -> bool:
        """Verify the provider is reachable.

        For Ollama, this calls the tags endpoint.
        For OpenAI, this performs a minimal API test.
        """
        provider = self._provider
        if hasattr(provider, "health_check"):
            return provider.health_check()
        try:
            request = AIRequest(
                task=TaskKind.CHAT,
                prompt="ping",
                system="",
                model=self._model,
                max_tokens=1,
            )
            provider.complete(request)
            return True
        except Exception:
            return False


def build_ai_client(ai_settings) -> AiProviderClient:
    """Build an :class:`AiProviderClient` from the given AI settings.

    Args:
        ai_settings: An :class:`AiSettings` instance from the session.

    Returns:
        A ready-to-use :class:`AiProviderClient`.

    Raises:
        ProviderFactoryError: When settings are invalid or the provider
            cannot be constructed.
    """
    ai_settings.validate()

    if ai_settings.provider == "ollama":
        return _build_ollama(ai_settings)
    if ai_settings.provider == "openai":
        return _build_openai(ai_settings)
    raise ProviderFactoryError(f"Unknown provider: {ai_settings.provider}")


def _build_ollama(ai_settings) -> AiProviderClient:
    config = AIProviderConfig(
        name="ollama",
        base_url=ai_settings.ollama_host,
    )
    provider = OllamaProvider(
        config,
        api_key="",
        timeout_seconds=ai_settings.request_timeout,
    )
    return AiProviderClient(provider, ai_settings.ollama_model)


def _build_openai(ai_settings) -> AiProviderClient:
    api_key = ai_settings.openai_api_key or os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise ProviderFactoryError(
            "OpenAI API key not set. Provide it via AI settings "
            "or the OPENAI_API_KEY environment variable."
        )
    config = AIProviderConfig(
        name="openai",
        base_url="https://api.openai.com/v1",
        api_key=api_key,
    )
    provider = OpenAICompatProvider(
        config,
        api_key=api_key,
        timeout_seconds=ai_settings.request_timeout,
    )
    return AiProviderClient(provider, ai_settings.openai_model)
