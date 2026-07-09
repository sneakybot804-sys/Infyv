"""Phase 7: pluggable transcription backends.

The :class:`TranscriptBackend` Protocol turns an extracted audio file into a
raw transcript (segments and optional word timings). Backends are swappable
behind the Protocol and resolved via a small registry, exactly like the OCR
engines (``ocr_engine.py``) and audio backends (``audio_backend.py``).

Backends return **raw** results only: language, segments, words. They never
assign cue ids, wrap lines, or format SRT -- the engine owns all of that.

The default :class:`PlaceholderTranscriptBackend` returns an **empty**
transcript. It exists solely to satisfy the Protocol and keep the project
dependency-free (no Whisper, no ASR library). A real backend can be added in
a future phase and registered under a new name without changing this API.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol, runtime_checkable

from logger import get_logger
from subtitle_config import SubtitleError

logger = get_logger(__name__)


# --------------------------------------------------------------------- #
# Raw transcript data (no cue ids, no formatting)
# --------------------------------------------------------------------- #
@dataclass
class Word:
    """A single recognized word with its timing (seconds) and confidence."""

    text: str
    start: float
    end: float
    confidence: float = 1.0


@dataclass
class TranscriptSegment:
    """A contiguous transcribed span with optional per-word timings."""

    text: str
    start: float
    end: float
    words: list[Word] = field(default_factory=list)


@dataclass
class TranscriptResult:
    """A full transcript: detected language and ordered segments."""

    language: str | None = None
    segments: list[TranscriptSegment] = field(default_factory=list)


# --------------------------------------------------------------------- #
# Backend Protocol
# --------------------------------------------------------------------- #
@runtime_checkable
class TranscriptBackend(Protocol):
    """Transcribe an audio file into a raw transcript."""

    name: str

    def transcribe(
        self,
        audio_path: str | Path,
        /,
        *,
        language: str | None,
        word_timestamps: bool,
    ) -> TranscriptResult:
        """Return a raw transcript for ``audio_path``."""
        ...


# --------------------------------------------------------------------- #
# Default dependency-free backend (empty transcript)
# --------------------------------------------------------------------- #
class PlaceholderTranscriptBackend:
    """Default backend that produces **no** transcript.

    Returns an empty :class:`TranscriptResult` so production never emits
    fabricated subtitles and the project carries no transcription dependency.
    It exists only to satisfy the Protocol and keep the pipeline runnable end
    to end. Replace by registering a real ASR backend under another name.
    """

    name = "placeholder"

    def transcribe(
        self,
        audio_path: str | Path,
        /,
        *,
        language: str | None,
        word_timestamps: bool,
    ) -> TranscriptResult:
        logger.info(
            "PlaceholderTranscriptBackend: returning empty transcript for %s "
            "(no ASR backend installed).",
            audio_path,
        )
        return TranscriptResult(language=language, segments=[])


# --------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------- #
BackendFactory = Callable[[], TranscriptBackend]

_REGISTRY: dict[str, BackendFactory] = {
    PlaceholderTranscriptBackend.name: PlaceholderTranscriptBackend,
}


def register_backend(name: str, factory: BackendFactory) -> None:
    """Register a transcript backend factory under ``name`` (idempotent)."""
    _REGISTRY[name] = factory


def create_backend(name: str) -> TranscriptBackend:
    """Instantiate a registered transcript backend by name."""
    try:
        factory = _REGISTRY[name]
    except KeyError as exc:
        available = ", ".join(sorted(_REGISTRY)) or "(none)"
        raise SubtitleError(
            f"Unknown transcript backend '{name}'. Available: {available}."
        ) from exc
    return factory()


def available_backends() -> list[str]:
    """Return the sorted list of registered backend names."""
    return sorted(_REGISTRY)
