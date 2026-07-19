"""Anthropic Claude provider (direct, non-gateway access).

Implements the Anthropic ``/messages`` wire format. Enabled only when a
deployment configures direct Anthropic access; by default all Claude models
are reached through the OmniRoute gateway instead.

No Qt symbol is imported here.
"""
from __future__ import annotations

import base64
from typing import List

from ai_core.errors import ResponseFormatError
from ai_core.providers.base import AIProvider
from ai_core.types import AIRequest, AIResponse, AIUsage, Modality, TaskKind

#: Claude serves text + vision tasks (no image/audio/video generation).
_SUPPORTED = frozenset(
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


class ClaudeProvider(AIProvider):
    """Anthropic Messages API client."""

    def supports(self, task: TaskKind) -> bool:
        """Return whether Claude serves ``task``."""
        return task in _SUPPORTED

    def complete(self, request: AIRequest) -> AIResponse:
        """Execute a messages call and map the reply to :class:`AIResponse`."""
        url = f"{self._config.base_url}/messages"
        payload: dict = {
            "model": request.model,
            "max_tokens": request.max_tokens or 4096,
            "messages": [
                {"role": "user", "content": self._build_content(request)}
            ],
        }
        if request.system:
            payload["system"] = request.system
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
        }
        body, latency = self._post_json(url, payload, headers)
        return self._parse_response(body, request, latency)

    def _build_content(self, request: AIRequest):
        """Map the request prompt + image attachments to Anthropic content."""
        if not request.attachments:
            return request.prompt
        parts: List[dict] = []
        for attachment in request.attachments:
            if attachment.modality is not Modality.IMAGE:
                continue
            parts.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": attachment.mime_type,
                        "data": base64.b64encode(attachment.data).decode(
                            "ascii"
                        ),
                    },
                }
            )
        parts.append({"type": "text", "text": request.prompt})
        return parts

    def _parse_response(
        self, body: dict, request: AIRequest, latency: float
    ) -> AIResponse:
        """Map an Anthropic reply body onto :class:`AIResponse`."""
        try:
            blocks = body["content"]
            text = "".join(
                block.get("text", "")
                for block in blocks
                if block.get("type") == "text"
            )
        except (KeyError, TypeError) as exc:
            raise ResponseFormatError(
                f"{self.name}: unexpected messages response shape."
            ) from exc
        usage_raw = body.get("usage") or {}
        prompt_tokens = int(usage_raw.get("input_tokens", 0) or 0)
        completion_tokens = int(usage_raw.get("output_tokens", 0) or 0)
        usage = AIUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
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
