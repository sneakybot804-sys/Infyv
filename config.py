"""Application configuration."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class OllamaConfig:
    """Settings for the local Ollama connection."""

    host: str = "http://localhost:11434"
    model: str = "qwen3:8b"
    request_timeout: int = 120  # seconds
    temperature: float = 0.7


@dataclass(frozen=True)
class PathConfig:
    """Filesystem layout for the project."""

    base_dir: Path = field(default_factory=lambda: Path(__file__).resolve().parent)

    @property
    def videos_dir(self) -> Path:
        return self.base_dir / "videos"

    @property
    def output_dir(self) -> Path:
        return self.base_dir / "output"

    @property
    def assets_dir(self) -> Path:
        return self.base_dir / "assets"

    @property
    def prompts_dir(self) -> Path:
        return self.base_dir / "prompts"

    @property
    def logs_dir(self) -> Path:
        return self.base_dir / "logs"


@dataclass
class AiSettings:
    """Mutable AI provider settings persisted in the session.

    These settings control which AI provider is active and how it is
    configured. They are intentionally mutable (not frozen) so the CLI
    can update them at runtime.
    """

    provider: str = "ollama"

    # Ollama settings
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "qwen3:8b"

    # OpenAI settings
    openai_api_key: str = ""
    openai_model: str = "gpt-5"

    # Common
    temperature: float = 0.7
    request_timeout: int = 120

    @property
    def available_providers(self) -> tuple[str, ...]:
        return ("ollama", "openai")

    @property
    def openai_models(self) -> tuple[str, ...]:
        return ("gpt-5.5", "gpt-5", "gpt-4.1")

    def validate(self) -> None:
        if self.provider not in self.available_providers:
            raise ValueError(
                f"Unknown provider '{self.provider}'. "
                f"Available: {', '.join(self.available_providers)}"
            )


@dataclass(frozen=True)
class AppConfig:
    """Top-level application configuration."""

    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    paths: PathConfig = field(default_factory=PathConfig)
    log_level: str = "INFO"

    def ensure_directories(self) -> None:
        """Create all required directories if they do not exist."""
        for directory in (
            self.paths.videos_dir,
            self.paths.output_dir,
            self.paths.assets_dir,
            self.paths.logs_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)


# Single shared instance imported across the app.
config = AppConfig()
