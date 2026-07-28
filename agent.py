"""AI agent that generates video edit plans via the provider system.

Delegates all LLM calls to a :class:`AiProviderClient` built from the
session's AI settings. No longer hardcodes Ollama.
"""
from __future__ import annotations

from ai_provider_factory import AiProviderClient, ProviderFactoryError, build_ai_client
from logger import get_logger
from prompts.edit_plan import SYSTEM_PROMPT, build_edit_plan_prompt
from session import session

logger = get_logger(__name__)


class OllamaConnectionError(RuntimeError):
    """Raised when the agent cannot reach or get a valid response from the AI provider."""


class GamingEditorAgent:
    """Connects to the configured AI provider to generate video edit plans."""

    def __init__(self, client: AiProviderClient | None = None) -> None:
        self._client = client
        logger.info(
            "Initialized agent (provider=%s, model=%s)",
            self._resolve_provider_name(),
            self._resolve_model(),
        )

    def _resolve_client(self) -> AiProviderClient:
        if self._client is not None:
            return self._client
        return build_ai_client(session.ai_settings)

    def _resolve_provider_name(self) -> str:
        if self._client is not None:
            return self._client.provider_name
        return session.ai_provider

    def _resolve_model(self) -> str:
        if self._client is not None:
            return self._client.model
        return session.ai_model

    def generate_edit_plan(self, video_description: str) -> str:
        """Send the gameplay description to the AI provider and return the edit plan."""
        if not video_description or not video_description.strip():
            raise ValueError("video_description must not be empty.")

        prompt = build_edit_plan_prompt(video_description)
        logger.info("Generating edit plan (%d chars input)", len(video_description))

        try:
            raw_response = self._resolve_client().generate(SYSTEM_PROMPT, prompt)
        except ProviderFactoryError as exc:
            raise OllamaConnectionError(str(exc)) from exc
        except Exception as exc:
            logger.error("Provider error: %s", exc)
            raise OllamaConnectionError(
                f"AI provider request failed: {exc}"
            ) from exc

        plan = raw_response.strip()

        logger.info("Edit plan generated (%d chars output)", len(plan))
        return plan
