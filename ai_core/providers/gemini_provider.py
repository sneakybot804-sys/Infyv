"""Google Gemini provider (direct, non-gateway access).

Implements the Gemini ``generateContent`` wire format. Enabled only when a
deployment configures direct Google access; by default Gemini models are
reached through the OmniRoute gateway.

No Qt symbol is imported here.
"""
from __future__ import annotations

import base64
from typing import List

from ai_core.errors import ResponseFormatError
from ai_core.providers.base import AIProvider
from ai_core.types import AIRequest, AIResponse, AIUsage, Modality, TaskKind

#: Gemini serves text + vision/OCR tasks in this integration.
_SUPPORTED = frozenset(
    {
        TaskKind.CHAT,
        TaskKind.REASONING,
        TaskKind.VISION,
        TaskKind.OCR,
        TaskKind.VIDEO_ANALYSIS,
        TaskKind.AUDIO_ANALYSIS,
        TaskKind.SUBTITLES,
        TaskKind.SCRIPT,
        TaskKind.TITLE,
        TaskKind.DESCRIPTION,
        TaskKind.TAGS,
        TaskKind.THUMBNAIL,
    }
)


class GeminiProvider(AIProvider):
    """Google Generative Language API client (generateContent)."""

    def supports(self, task: TaskKind) -> bool:
        """Return whether Gemini serves ``task``."""
        return task in _SUPPORTED

    def complete(self, request: AIRequest) -> AIResponse:
        """Execute generateContent and map the reply to :class:`AIResponse`."""
        url = (
            f"{self._config.base_url}/models/"
            f"{request.model}:generateContent?key={self._api_key}"
        )
        payload: dict = {
            "contents": [{"role": "user", "parts": self._build_parts(request)}]
        }
        if request.system:
            payload["systemInstruction"] = {
                "parts": [{"text": request.system}]
            }
        generation: dict = {}
        if request.temperature is not None:
            generation["temperature"] = request.temperature
        if request.max_tokens is not None:
            generation["maxOutputTokens"] = request.max_tokens
        if generation:
            payload["generationConfig"] = generation
        body, latency = self._post_json(url, payload)
        return self._parse_response(body, request, latency)

    def _build_parts(self, request: AIRequest) -> List[dict]:
        """Map the prompt + attachments to Gemini content parts."""
        parts: List[dict] = [{"text": request.prompt}]
        for attachment in request.attachments:
            if attachment.modality not in (Modality.IMAGE, Modality.VIDEO):
                continue
            parts.append(
                {
                    "inlineData": {
                        "mimeType": attachment.mime_type,
                        "data": base64.b64encode(attachment.data).decode(
                            "ascii"
                        ),
                    }
                }
            )
        return parts

    def _parse_response(
        self, body: dict, request: AIRequest, latency: float
    ) -> AIResponse:
        """Map a generateContent reply body onto :class:`AIResponse`."""
        try:
            candidate = body["candidates"][0]
            parts = candidate["content"]["parts"]
            text = "".join(part.get("text", "") for part in parts)
        except (KeyError, IndexError, TypeError) as exc:
            raise ResponseFormatError(
                f"{self.name}: unexpected generateContent shape."
            ) from exc
        usage_raw = body.get("usageMetadata") or {}
        usage = AIUsage(
            prompt_tokens=int(usage_raw.get("promptTokenCount", 0) or 0),
            completion_tokens=int(
                usage_raw.get("candidatesTokenCount", 0) or 0
            ),
            total_tokens=int(usage_raw.get("totalTokenCount", 0) or 0),
        )
        return AIResponse(
            text=text,
            modality=Modality.TEXT,
            model=request.model,
            provider=self.name,
            usage=usage,
            latency_seconds=latency,
            raw=body,
        )
