"""AI error hierarchy for ai_core (Qt-free).

Mirrors the ``gui_core.errors`` convention: a small, typed hierarchy so
callers can catch precisely. Provider implementations translate raw
transport errors into these types; nothing above the provider layer ever
sees an ``urllib`` / socket exception.

No Qt symbol is imported here.
"""
from __future__ import annotations


class AIError(RuntimeError):
    """Base class for every ai_core error."""


class AIConfigError(AIError):
    """Raised when the AI configuration is invalid or incomplete."""


class ProviderError(AIError):
    """Base class for provider-side failures.

    Attributes:
        provider: Provider name (e.g. ``"omniroute"``).
        model: Model id the request targeted, when known.
    """

    def __init__(
        self, message: str, *, provider: str = "", model: str = ""
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.model = model


class ProviderUnavailableError(ProviderError):
    """The provider endpoint could not be reached (network / DNS / refused)."""


class ProviderTimeoutError(ProviderError):
    """The provider did not answer within the configured timeout."""


class RateLimitError(ProviderError):
    """The provider rejected the request due to rate limiting (HTTP 429)."""


class AuthenticationError(ProviderError):
    """The provider rejected the configured API key (HTTP 401/403)."""


class ModelNotFoundError(ProviderError):
    """The requested model is unknown to the provider (HTTP 404)."""


class ResponseFormatError(AIError):
    """The provider answered, but the payload could not be parsed."""


class RetryExhaustedError(AIError):
    """Every attempt (including fallbacks) failed.

    Attributes:
        attempts: Number of attempts made.
        last_error: The final underlying error.
    """

    def __init__(self, message: str, *, attempts: int, last_error: Exception) -> None:
        super().__init__(message)
        self.attempts = attempts
        self.last_error = last_error
