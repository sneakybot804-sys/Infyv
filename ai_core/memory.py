"""Memory engine for ai_core: persistent user preferences (Qt-free).

Stores durable user preferences (style, language, export defaults, ...)
separately from any conversation. Backed by a small JSON file under the
existing output directory; every operation is failure-tolerant so a broken
file can never crash a caller.

No Qt symbol is imported here.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional

#: Preference keys with editor-level meaning (free-form keys are allowed).
KNOWN_PREFERENCES = (
    "style",              # e.g. "anime", "cyberpunk"
    "game",               # e.g. "valorant"
    "subtitle_style",
    "transition",
    "thumbnail_style",
    "export_resolution",
    "language",
)


class MemoryEngine:
    """Persistent key/value preference store with an in-memory cache.

    Args:
        path: JSON file location; ``None`` keeps memory purely in-process
            (tests, headless).
    """

    def __init__(self, path: Optional[Path] = None) -> None:
        self._path = Path(path) if path is not None else None
        self._cache: Dict[str, str] = {}
        self._loaded = False

    # ------------------------------------------------------------------ #
    # Load / save (lazy, failure-tolerant)
    # ------------------------------------------------------------------ #
    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        if self._path is None:
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                self._cache = {
                    str(k): str(v) for k, v in data.items()
                }
        except (OSError, ValueError):
            self._cache = {}

    def _save(self) -> None:
        if self._path is None:
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(self._cache, indent=2, sort_keys=True),
                encoding="utf-8",
            )
        except OSError:
            pass

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def remember(self, key: str, value: str) -> None:
        """Store a preference and persist it."""
        self._ensure_loaded()
        self._cache[str(key)] = str(value)
        self._save()

    def recall(self, key: str, default: str = "") -> str:
        """Return a stored preference (or ``default``)."""
        self._ensure_loaded()
        return self._cache.get(key, default)

    def forget(self, key: str) -> None:
        """Remove a preference (idempotent) and persist."""
        self._ensure_loaded()
        if key in self._cache:
            del self._cache[key]
            self._save()

    def all(self) -> Dict[str, str]:
        """Return a copy of every stored preference."""
        self._ensure_loaded()
        return dict(self._cache)

    def preference_lines(self) -> str:
        """Render the preferences as prompt-ready bullet lines."""
        self._ensure_loaded()
        if not self._cache:
            return ""
        return "\n".join(
            f"- {key}: {value}"
            for key, value in sorted(self._cache.items())
        )
