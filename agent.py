"""AI agent that connects to a local Ollama model."""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any

from config import AppConfig, config
from logger import get_logger
from prompts.edit_plan import SYSTEM_PROMPT, build_edit_plan_prompt

logger = get_logger(__name__)


class OllamaConnectionError(RuntimeError):
    """Raised when the agent cannot reach or get a valid response from Ollama."""


class GamingEditorAgent:
    """Connects to a local Ollama model to generate video edit plans."""

    def __init__(self, app_config: AppConfig | None = None) -> None:
        self._config = app_config or config
        self._ollama = self._config.ollama
        logger.info(
            "Initialized agent (model=%s, host=%s)",
            self._ollama.model,
            self._ollama.host,
        )

    def generate_edit_plan(self, video_description: str) -> str:
        """Send the gameplay description to Ollama and return the edit plan."""
        if not video_description or not video_description.strip():
            raise ValueError("video_description must not be empty.")

        prompt = build_edit_plan_prompt(video_description)
        logger.info("Generating edit plan (%d chars input)", len(video_description))

        raw_response = self._call_ollama(prompt)
        plan = self._clean_response(raw_response)

        logger.info("Edit plan generated (%d chars output)", len(plan))
        return plan

    def _call_ollama(self, prompt: str) -> str:
        """Perform the HTTP request to the Ollama /api/generate endpoint."""
        url = f"{self._ollama.host}/api/generate"
        payload: dict[str, Any] = {
            "model": self._ollama.model,
            "prompt": prompt,
            "system": SYSTEM_PROMPT,
            "stream": False,
            "options": {"temperature": self._ollama.temperature},
        }

        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            logger.debug("POST %s", url)
            with urllib.request.urlopen(
                request, timeout=self._ollama.request_timeout
            ) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            logger.error("Ollama HTTP error %s: %s", exc.code, exc.reason)
            raise OllamaConnectionError(
                f"Ollama returned HTTP {exc.code}: {exc.reason}"
            ) from exc
        except urllib.error.URLError as exc:
            logger.error("Cannot reach Ollama at %s: %s", url, exc.reason)
            raise OllamaConnectionError(
                f"Could not connect to Ollama at {self._ollama.host}. "
                "Is the Ollama service running?"
            ) from exc
        except TimeoutError as exc:
            logger.error("Ollama request timed out after %ss", self._ollama.request_timeout)
            raise OllamaConnectionError("Ollama request timed out.") from exc

        return self._parse_response_body(body)

    @staticmethod
    def _parse_response_body(body: str) -> str:
        """Extract the 'response' field from Ollama's JSON reply."""
        try:
            parsed: dict[str, Any] = json.loads(body)
        except json.JSONDecodeError as exc:
            logger.error("Invalid JSON from Ollama: %s", exc)
            raise OllamaConnectionError("Received invalid JSON from Ollama.") from exc

        response_text = parsed.get("response", "")
        if not response_text:
            raise OllamaConnectionError("Ollama returned an empty response.")
        return str(response_text)

    @staticmethod
    def _clean_response(text: str) -> str:
        """Strip qwen3 <think>...</think> reasoning blocks and whitespace."""
        cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
        return cleaned.strip()
