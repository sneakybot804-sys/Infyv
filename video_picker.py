"""Phase 4A: video selection.

Provides a small, isolated way to pick a video file. A native Tkinter file
dialog is used when a display is available (Windows 11 target); otherwise a
CLI fallback lists videos in the configured ``videos`` directory.

This module is intentionally decoupled from the analyzer so the Phase 8 GUI
can replace the selection strategy without touching analysis code (SOLID:
separation of concerns / dependency inversion at the call site).
"""
from __future__ import annotations

from pathlib import Path
from typing import Sequence

from config import AppConfig, config
from logger import get_logger

logger = get_logger(__name__)

# Common container formats we accept for analysis.
VIDEO_EXTENSIONS: tuple[str, ...] = (
    ".mp4",
    ".mkv",
    ".mov",
    ".avi",
    ".webm",
    ".flv",
    ".m4v",
)


class VideoPickerError(RuntimeError):
    """Raised when no video could be selected."""


class VideoPicker:
    """Selects a video file via a GUI dialog or a CLI fallback."""

    def __init__(self, app_config: AppConfig | None = None) -> None:
        """Create a picker bound to the shared application config."""
        self._config = app_config or config
        logger.info("Initialized VideoPicker")

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def pick(self) -> Path:
        """Return a selected video path, trying the GUI dialog first.

        Raises:
            VideoPickerError: If no valid video was selected.
        """
        selected = self._pick_via_dialog()
        if selected is None:
            selected = self._pick_via_cli()

        if selected is None:
            raise VideoPickerError("No video file was selected.")

        path = Path(selected).expanduser().resolve()
        if not path.is_file():
            raise VideoPickerError(f"Selected path is not a file: {path}")
        logger.info("Selected video: %s", path)
        return path

    def list_videos(self) -> list[Path]:
        """Return video files found in the configured ``videos`` directory."""
        videos_dir = self._config.paths.videos_dir
        if not videos_dir.exists():
            return []
        return self.filter_videos(sorted(videos_dir.iterdir()))

    @staticmethod
    def filter_videos(paths: Sequence[Path]) -> list[Path]:
        """Return only the paths whose suffix is a known video extension."""
        return [
            p
            for p in paths
            if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS
        ]

    # ------------------------------------------------------------------ #
    # Selection strategies
    # ------------------------------------------------------------------ #
    def _pick_via_dialog(self) -> str | None:
        """Try to open a native Tkinter file dialog; return None on failure."""
        try:
            import tkinter as tk
            from tkinter import filedialog
        except Exception as exc:  # noqa: BLE001 - headless/no Tk is expected
            logger.debug("Tkinter unavailable, using CLI fallback: %s", exc)
            return None

        try:
            root = tk.Tk()
            root.withdraw()
            patterns = " ".join(f"*{ext}" for ext in VIDEO_EXTENSIONS)
            selected = filedialog.askopenfilename(
                title="Select a gameplay video",
                initialdir=str(self._config.paths.videos_dir),
                filetypes=[("Video files", patterns), ("All files", "*.*")],
            )
            root.destroy()
        except Exception as exc:  # noqa: BLE001 - no display, etc.
            logger.debug("File dialog failed, using CLI fallback: %s", exc)
            return None

        return selected or None

    def _pick_via_cli(self) -> str | None:
        """Fallback: list videos in the videos dir and prompt for a choice."""
        videos = self.list_videos()
        if not videos:
            print(
                "No videos found in "
                f"'{self._config.paths.videos_dir}'. "
                "Add a video there or provide a full path."
            )
            entered = input("Enter full path to a video (blank to cancel) > ").strip()
            return entered or None

        print("Select a video to analyze:")
        for i, path in enumerate(videos, start=1):
            print(f"  {i}. {path.name}")

        choice = input("Number (or full path, blank to cancel) > ").strip()
        if not choice:
            return None

        if choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(videos):
                return str(videos[idx - 1])
            print("Invalid selection.")
            return None

        return choice
