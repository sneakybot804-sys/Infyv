"""AI configuration for ai_core (Qt-free, frozen dataclasses).

Mirrors the repository's ``config.py`` conventions: frozen dataclasses with
sane defaults, one shared composition point. API keys come from environment
variables first and an optional keys file second, so no secret is ever
hardcoded or committed.

No Qt symbol is imported here.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, Tuple

#: Environment variable consulted per provider: AI_<PROVIDER>_API_KEY.
_ENV_TEMPLATE = "AI_{name}_API_KEY"

#: Optional JSON keys file next to the project ({"omniroute": "sk-..."}).
_KEYS_FILENAME = "ai_keys.json"


@dataclass(frozen=True)
class AIProviderConfig:
    """Connection settings for one provider.

    Attributes:
        name: Stable provider name (``"omniroute"``, ``"claude"``, ...).
        base_url: HTTP endpoint base (no trailing slash).
        api_key: Secret key; empty means "resolve from environment/file".
        enabled: Whether the provider may be selected by the router.
    """

    name: str
    base_url: str = ""
    api_key: str = ""
    enabled: bool = True

    def resolve_api_key(self, base_dir: Optional[Path] = None) -> str:
        """Return the API key from config, environment, or the keys file."""
        if self.api_key:
            return self.api_key
        env_key = os.environ.get(_ENV_TEMPLATE.format(name=self.name.upper()))
        if env_key:
            return env_key
        if base_dir is not None:
            keys_path = Path(base_dir) / _KEYS_FILENAME
            try:
                data = json.loads(keys_path.read_text(encoding="utf-8"))
                value = data.get(self.name, "")
                if isinstance(value, str):
                    return value
            except (OSError, ValueError):
                pass
        return ""


@dataclass(frozen=True)
class AIRetryConfig:
    """Retry policy applied by the RetryManager.

    Attributes:
        max_attempts: Total attempts per model (including the first).
        backoff_seconds: Base delay; attempt ``n`` waits ``base * 2**(n-1)``.
        backoff_cap_seconds: Upper bound for a single wait.
        use_fallbacks: Whether router-provided fallback models are tried
            after the primary model's attempts are exhausted.
    """

    max_attempts: int = 3
    backoff_seconds: float = 1.0
    backoff_cap_seconds: float = 15.0
    use_fallbacks: bool = True


@dataclass(frozen=True)
class AIConfig:
    """Top-level AI configuration (single composition point).

    Attributes:
        default_provider: Provider used when a task resolves no override.
        auto_mode: When ``True`` the router picks models per task kind;
            when ``False`` ``manual_model`` is used for every text task.
        manual_model: Model id used in manual mode.
        temperature: Default sampling temperature.
        max_tokens: Default completion budget.
        timeout_seconds: HTTP timeout per request.
        retry: The retry policy.
        providers: Provider connection settings by name.
        model_overrides: Optional task-kind -> model-id routing overrides
            (checked by the router before its built-in table).
        memory_path: Where the MemoryEngine persists preferences (JSON).
    """

    default_provider: str = "omniroute"
    auto_mode: bool = True
    manual_model: str = "anthropic/claude-sonnet-4-5"
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout_seconds: float = 120.0
    retry: AIRetryConfig = field(default_factory=AIRetryConfig)
    providers: Dict[str, AIProviderConfig] = field(default_factory=dict)
    model_overrides: Dict[str, str] = field(default_factory=dict)
    memory_path: Optional[Path] = None

    def provider(self, name: str) -> Optional[AIProviderConfig]:
        """Return the provider config for ``name``, or ``None``."""
        return self.providers.get(name)

    def enabled_providers(self) -> Tuple[str, ...]:
        """Return the names of enabled providers (stable order)."""
        return tuple(
            name for name, cfg in self.providers.items() if cfg.enabled
        )


def default_ai_config(base_dir: Optional[Path] = None) -> AIConfig:
    """Build the default AI configuration.

    OmniRoute is the primary provider (an OpenAI-compatible multi-model
    gateway); the direct providers exist so a deployment can bypass the
    gateway per provider without touching any caller.
    """
    memory = (Path(base_dir) / "output" / "ai_memory.json") if base_dir else None
    return AIConfig(
        providers={
            "omniroute": AIProviderConfig(
                name="omniroute", base_url="https://api.omniroute.ai/v1"
            ),
            "claude": AIProviderConfig(
                name="claude",
                base_url="https://api.anthropic.com/v1",
                enabled=False,
            ),
            "openai": AIProviderConfig(
                name="openai",
                base_url="https://api.openai.com/v1",
                enabled=False,
            ),
            "gemini": AIProviderConfig(
                name="gemini",
                base_url="https://generativelanguage.googleapis.com/v1beta",
                enabled=False,
            ),
        },
        memory_path=memory,
    )
