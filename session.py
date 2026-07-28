"""Centralized session state for the CLI application.

Provides a singleton ``Session`` that stores the user-selected video path
and AI provider settings. Every phase function reads from this single
source of truth.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from config import AiSettings
from logger import get_logger

logger = get_logger(__name__)

SUPPORTED_EXTENSIONS: tuple[str, ...] = (
    ".mp4",
    ".mkv",
    ".mov",
    ".avi",
    ".webm",
    ".flv",
    ".m4v",
)


class SessionError(RuntimeError):
    """Raised when no video has been selected but one is required."""


class Session:
    """Holds session state (video path, AI settings) for the CLI."""

    def __init__(self) -> None:
        self._current_video: Optional[Path] = None
        self._ai_settings: AiSettings = AiSettings()

    # ------------------------------------------------------------------ #
    # Public API -- Video
    # ------------------------------------------------------------------ #
    @property
    def current_video(self) -> Optional[Path]:
        """The currently selected video path, or ``None``."""
        return self._current_video

    @current_video.setter
    def current_video(self, value: Optional[Path]) -> None:
        self._current_video = value

    def has_video(self) -> bool:
        """Return ``True`` when a video has been selected."""
        return self._current_video is not None

    def get_video(self) -> Path:
        """Return the current video path.

        Raises:
            SessionError: When no video has been selected yet.
        """
        if self._current_video is None:
            raise SessionError(
                "No video selected. Use option 2-9 to pick a video, "
                "or option 10 to change the current video."
            )
        return self._current_video

    def set_video(self, raw: str) -> Path:
        """Validate *raw* path and store it as the current video.

        Validation checks:
          - Path resolves to an existing file
          - File is readable
          - Extension is a known video format

        Returns the resolved ``Path`` on success.

        Raises:
            ValueError: When the path fails any validation check.
        """
        path = Path(raw).expanduser().resolve()

        if not path.exists():
            raise ValueError(f"File does not exist: {path}")
        if not path.is_file():
            raise ValueError(f"Path is not a file: {path}")
        if not path.suffix.lower() in SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported format '{path.suffix}'. "
                f"Supported: {', '.join(SUPPORTED_EXTENSIONS)}"
            )

        try:
            with path.open("rb"):
                pass
        except OSError as exc:
            raise ValueError(f"File is not readable: {exc}") from exc

        self._current_video = path
        logger.info("Current video set to: %s", path)
        return path

    def clear_video(self) -> None:
        """Remove the current video selection."""
        self._current_video = None
        logger.debug("Current video cleared")

    # ------------------------------------------------------------------ #
    # Public API -- AI Settings
    # ------------------------------------------------------------------ #
    @property
    def ai_settings(self) -> AiSettings:
        """The active AI provider settings."""
        return self._ai_settings

    @ai_settings.setter
    def ai_settings(self, value: AiSettings) -> None:
        self._ai_settings = value

    @property
    def ai_provider(self) -> str:
        """Shortcut for the current provider name."""
        return self._ai_settings.provider

    @property
    def ai_model(self) -> str:
        """Shortcut for the current model name."""
        if self._ai_settings.provider == "ollama":
            return self._ai_settings.ollama_model
        return self._ai_settings.openai_model

    @property
    def ai_host(self) -> str:
        """Shortcut for the current provider host/endpoint."""
        return self._ai_settings.ollama_host

    # ------------------------------------------------------------------ #
    # CLI display helpers
    # ------------------------------------------------------------------ #
    def display_status(self) -> str:
        """Return a human-readable status line for the current video."""
        if self._current_video is None:
            return "None"
        return str(self._current_video)


# Single shared instance across the CLI application.
session = Session()
