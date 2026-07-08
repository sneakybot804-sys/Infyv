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
