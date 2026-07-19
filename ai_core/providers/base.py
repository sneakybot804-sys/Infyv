"""Provider interface and shared HTTP plumbing for ai_core (Qt-free).

Every provider implements :class:`AIProvider`. The shared HTTP helper lives
here once (stdlib ``urllib``, mirroring the existing ``agent.py`` transport
convention — no new third-party dependency), so concrete providers contain
only payload mapping, never transport code.

No Qt symbol is imported here.
"""
from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from typing import Dict, Optional, Tuple

from ai_core.config import AIProviderConfig
from ai_core.errors import (
    AuthenticationError,
    ModelNotFoundError,
    ProviderError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    RateLimitError,
    ResponseFormatError,
)
from ai_core.types import AIRequest, AIResponse, TaskKind


class AIProvider(ABC):
    """Abstract provider: one ``complete`` call, capability introspection.

    Args:
        config: The provider's connection settings.
        api_key: Resolved secret (may be empty for keyless local providers).
        timeout_seconds: HTTP timeout per request.
    """

    def __init__(
        self,
        config: AIProviderConfig,
        *,
        api_key: str = "",
        timeout_seconds: float = 120.0,
    ) -> None:
        self._config = config
        self._api_key = api_key
        self._timeout = float(timeout_seconds)

    @property
    def name(self) -> str:
        """Return the provider's stable name."""
        return self._config.name

    @abstractmethod
    def supports(self, task: TaskKind) -> bool:
        """Return whether this provider can serve ``task``."""

    @abstractmethod
    def complete(self, request: AIRequest) -> AIResponse:
        """Execute ``request`` synchronously and return a typed response.

        Raises:
            ProviderError subclasses on transport/provider failures;
            ResponseFormatError when the payload cannot be decoded.
        """

    # ------------------------------------------------------------------ #
    # Shared HTTP plumbing (single implementation for all providers)
    # ------------------------------------------------------------------ #
    def _post_json(
        self,
        url: str,
        payload: dict,
        headers: Optional[Dict[str, str]] = None,
    ) -> Tuple[dict, float]:
        """POST ``payload`` as JSON; return ``(decoded_body, latency_s)``.

        Translates every transport failure into the typed error hierarchy so
        no raw urllib/socket exception crosses the provider boundary.
        """
        data = json.dumps(payload).encode("utf-8")
        merged = {"Content-Type": "application/json"}
        if headers:
            merged.update(headers)
        request = urllib.request.Request(
            url, data=data, headers=merged, method="POST"
        )
        started = time.monotonic()
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as reply:
                body = reply.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            self._raise_http_error(exc)
        except socket.timeout as exc:
            raise ProviderTimeoutError(
                f"{self.name}: request timed out after {self._timeout:.0f}s.",
                provider=self.name,
            ) from exc
        except urllib.error.URLError as exc:
            reason = getattr(exc, "reason", exc)
            if isinstance(reason, socket.timeout):
                raise ProviderTimeoutError(
                    f"{self.name}: request timed out after {self._timeout:.0f}s.",
                    provider=self.name,
                ) from exc
            raise ProviderUnavailableError(
                f"{self.name}: endpoint unreachable ({reason}).",
                provider=self.name,
            ) from exc
        latency = time.monotonic() - started
        try:
            return json.loads(body), latency
        except ValueError as exc:
            raise ResponseFormatError(
                f"{self.name}: response is not valid JSON."
            ) from exc

    def _raise_http_error(self, exc: "urllib.error.HTTPError") -> None:
        """Map an HTTP status to the typed error hierarchy (always raises)."""
        detail = ""
        try:
            detail = exc.read().decode("utf-8")[:500]
        except Exception:
            pass
        message = f"{self.name}: HTTP {exc.code}. {detail}".strip()
        if exc.code in (401, 403):
            raise AuthenticationError(message, provider=self.name) from exc
        if exc.code == 404:
            raise ModelNotFoundError(message, provider=self.name) from exc
        if exc.code == 429:
            raise RateLimitError(message, provider=self.name) from exc
        if exc.code >= 500:
            raise ProviderUnavailableError(message, provider=self.name) from exc
        raise ProviderError(message, provider=self.name) from exc
