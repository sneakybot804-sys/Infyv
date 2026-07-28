"""Ollama provider implementing the ai_core provider interface.

Maps Ollama's ``/api/generate`` endpoint onto the ``AIProvider`` ABC so
the CLI can use Ollama through the same interface as OpenAI, Claude, etc.
"""
from __future__ import annotations

import json
import re
from typing import Any

from ai_core.errors import ResponseFormatError
from ai_core.providers.base import AIProvider
from ai_core.types import AIRequest, AIResponse, AIUsage, Modality, TaskKind

_TEXT_TASKS = frozenset(
    {
        TaskKind.CHAT,
        TaskKind.REASONING,
        TaskKind.CODING,
        TaskKind.EDIT_PLAN,
        TaskKind.EFFECTS,
        TaskKind.TRANSITION,
        TaskKind.SUBTITLES,
        TaskKind.SCRIPT,
        TaskKind.TITLE,
        TaskKind.DESCRIPTION,
        TaskKind.TAGS,
        TaskKind.THUMBNAIL,
    }
)

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


class OllamaProvider(AIProvider):
    """Local Ollama provider using the ``/api/generate`` endpoint."""

    def _endpoint(self) -> str:
        base = self._config.base_url.rstrip("/")
        return f"{base}/api/generate"

    def supports(self, task: TaskKind) -> bool:
        return task in _TEXT_TASKS

    def complete(self, request: AIRequest) -> AIResponse:
        url = self._endpoint()
        payload: dict[str, Any] = {
            "model": request.model,
            "prompt": request.prompt,
            "system": request.system or "",
            "stream": False,
        }
        if request.temperature is not None:
            payload.setdefault("options", {})
            payload["options"]["temperature"] = request.temperature

        body, latency = self._post_json(url, payload)
        return self._parse_response(body, request, latency)

    def _parse_response(
        self, body: dict, request: AIRequest, latency: float
    ) -> AIResponse:
        try:
            raw = body.get("response", "")
            if not raw:
                raise KeyError("response")
        except (KeyError, TypeError) as exc:
            raise ResponseFormatError(
                f"{self.name}: unexpected Ollama response shape."
            ) from exc

        cleaned = _THINK_RE.sub("", raw).strip()

        return AIResponse(
            text=cleaned,
            modality=Modality.TEXT,
            model=str(body.get("model", request.model)),
            provider=self.name,
            usage=AIUsage(),
            latency_seconds=latency,
            raw=body,
        )

    # ------------------------------------------------------------------ #
    # Health check / connectivity test
    # ------------------------------------------------------------------ #
    def health_check(self) -> bool:
        """Return ``True`` if the Ollama server is reachable."""
        url = f"{self._config.base_url.rstrip('/')}/api/tags"
        try:
            self._post_json(url, {})
            return True
        except Exception:
            return False
