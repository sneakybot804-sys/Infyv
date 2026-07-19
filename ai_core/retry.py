"""Retry manager for ai_core: bounded retries + model fallbacks (Qt-free).

Wraps provider calls with the configured retry policy: transient failures
(timeout / unavailable / rate limit) retry with exponential backoff; on
exhaustion the router-provided fallback models are tried in order. Permanent
failures (auth, unknown model, malformed request) skip straight to the next
model. Every attempt is reported to an optional observer for logging.

The sleep function is injectable so tests run instantly.

No Qt symbol is imported here.
"""
from __future__ import annotations

import time
from dataclasses import replace
from typing import Callable, Optional, Sequence

from ai_core.config import AIRetryConfig
from ai_core.errors import (
    ProviderError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    RateLimitError,
    ResponseFormatError,
    RetryExhaustedError,
)
from ai_core.providers.base import AIProvider
from ai_core.types import AIRequest, AIResponse

#: Errors worth retrying on the SAME model.
_TRANSIENT = (
    ProviderTimeoutError,
    ProviderUnavailableError,
    RateLimitError,
)

#: Attempt observer: (model, attempt, error_or_none) -> None.
AttemptObserver = Callable[[str, int, Optional[Exception]], None]


class RetryManager:
    """Executes requests through a provider with retries and fallbacks.

    Args:
        config: The retry policy.
        sleep: Injectable sleep (tests pass a no-op).
    """

    def __init__(
        self,
        config: AIRetryConfig,
        *,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._config = config
        self._sleep = sleep

    def execute(
        self,
        provider: AIProvider,
        request: AIRequest,
        *,
        fallback_models: Sequence[str] = (),
        observer: Optional[AttemptObserver] = None,
    ) -> AIResponse:
        """Run ``request``; retry transient failures, then try fallbacks.

        Returns the first successful response. Raises
        :class:`RetryExhaustedError` when every model in the chain failed.
        """
        models = [request.model]
        if self._config.use_fallbacks:
            for model in fallback_models:
                if model and model not in models:
                    models.append(model)

        attempts = 0
        last_error: Exception = RuntimeError("no attempt made")
        for model in models:
            model_request = (
                request
                if model == request.model
                else replace(request, model=model)
            )
            for attempt in range(1, self._config.max_attempts + 1):
                attempts += 1
                try:
                    response = provider.complete(model_request)
                except _TRANSIENT as exc:
                    last_error = exc
                    if observer:
                        observer(model, attempts, exc)
                    if attempt < self._config.max_attempts:
                        self._sleep(self._backoff(attempt))
                    continue
                except (ProviderError, ResponseFormatError) as exc:
                    # Permanent for this model: skip to the next model.
                    last_error = exc
                    if observer:
                        observer(model, attempts, exc)
                    break
                if observer:
                    observer(model, attempts, None)
                return response
        raise RetryExhaustedError(
            f"AI request failed after {attempts} attempt(s) across "
            f"{len(models)} model(s): {last_error}",
            attempts=attempts,
            last_error=last_error,
        )

    def _backoff(self, attempt: int) -> float:
        """Return the wait before retry ``attempt + 1`` (capped)."""
        delay = self._config.backoff_seconds * (2 ** (attempt - 1))
        return min(delay, self._config.backoff_cap_seconds)
