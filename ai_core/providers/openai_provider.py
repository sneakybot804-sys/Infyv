"""OpenAI-compatible chat provider (also the OmniRoute base implementation).

Implements the OpenAI ``/chat/completions`` wire format used by OpenAI
itself and by OpenAI-compatible gateways. Multimodal attachments are encoded
as data-URL image parts per the OpenAI vision schema.

No Qt symbol is imported here.
"""
from __future__ import annotations

import base64
from typing import List

from ai_core.errors import ResponseFormatError
from ai_core.providers.base import AIProvider
from ai_core.types import AIRequest, AIResponse, AIUsage, Modality, TaskKind

#: Task kinds a plain OpenAI deployment serves (no image/video generation
#: through chat/completions).
_TEXT_TASKS = frozenset(
    {
        TaskKind.CHAT,
        TaskKind.REASONING,
        TaskKind.CODING,
        TaskKind.VISION,
        TaskKind.OCR,
        TaskKind.VIDEO_ANALYSIS,
        TaskKind.AUDIO_ANALYSIS,
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


class OpenAICompatProvider(AIProvider):
    """Chat-completions client for OpenAI and OpenAI-compatible endpoints."""

    def supports(self, task: TaskKind) -> bool:
        """Return whether the task maps onto chat/completions."""
        return task in _TEXT_TASKS

    def complete(self, request: AIRequest) -> AIResponse:
        """Execute a chat completion and map the reply to :class:`AIResponse`."""
        url = f"{self._config.base_url}/chat/completions"
        payload = {
            "model": request.model,
            "messages": self._build_messages(request),
        }
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        headers = {}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        body, latency = self._post_json(url, payload, headers)
        return self._parse_response(body, request, latency)

    # ------------------------------------------------------------------ #
    # Wire mapping
    # ------------------------------------------------------------------ #
    def _build_messages(self, request: AIRequest) -> List[dict]:
        """Map an :class:`AIRequest` onto OpenAI chat messages."""
        messages: List[dict] = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        if request.attachments:
            parts: List[dict] = [{"type": "text", "text": request.prompt}]
            for attachment in request.attachments:
                if attachment.modality is not Modality.IMAGE:
                    continue  # chat/completions carries images only
                encoded = base64.b64encode(attachment.data).decode("ascii")
                parts.append(
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": (
                                f"data:{attachment.mime_type};base64,{encoded}"
                            )
                        },
                    }
                )
            messages.append({"role": "user", "content": parts})
        else:
            messages.append({"role": "user", "content": request.prompt})
        return messages

    def _parse_response(
        self, body: dict, request: AIRequest, latency: float
    ) -> AIResponse:
        """Map an OpenAI-schema reply body onto :class:`AIResponse`."""
        try:
            choice = body["choices"][0]
            text = choice["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise ResponseFormatError(
                f"{self.name}: unexpected chat/completions shape."
            ) from exc
        usage_raw = body.get("usage") or {}
        usage = AIUsage(
            prompt_tokens=int(usage_raw.get("prompt_tokens", 0) or 0),
            completion_tokens=int(usage_raw.get("completion_tokens", 0) or 0),
            total_tokens=int(usage_raw.get("total_tokens", 0) or 0),
            cost_usd=float(usage_raw.get("cost", 0.0) or 0.0),
        )
        return AIResponse(
            text=text,
            modality=Modality.TEXT,
            model=str(body.get("model", request.model)),
            provider=self.name,
            usage=usage,
            latency_seconds=latency,
            raw=body,
        )
