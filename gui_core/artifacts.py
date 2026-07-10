"""Read-only artifact contract for the gui_core layer.

The backend producers each write a well-known output file into
``config.paths.output_dir``. This module centralizes those filename
conventions so the rest of ``gui_core`` (gating, state, the GUI) can discover
\"what exists\" without hardcoding filenames anywhere else.

This module is strictly read-only: it never writes, moves, or overwrites any
file. Producers remain the sole writers, and they already implement
never-overwrite semantics.

No Qt symbol is imported here.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


class ArtifactKind(enum.Enum):
    """The distinct output artifacts produced across the pipeline."""

    ANALYSIS = "analysis"
    HIGHLIGHT = "highlight"
    OCR = "ocr"
    AUDIO = "audio"
    ENRICHED_HIGHLIGHT = "enriched_highlight"
    EDIT_PLAN = "edit_plan"
    RENDER = "render"
    SUBTITLES_JSON = "subtitles_json"
    SUBTITLES_SRT = "subtitles_srt"


#: Suffix appended to the source video stem for each artifact kind. These
#: mirror the frozen producer output names exactly and must not diverge.
ARTIFACT_SUFFIXES: Dict[ArtifactKind, str] = {
    ArtifactKind.ANALYSIS: "_analysis.json",
    ArtifactKind.HIGHLIGHT: "_highlight.json",
    ArtifactKind.OCR: "_ocr.json",
    ArtifactKind.AUDIO: "_audio.json",
    ArtifactKind.ENRICHED_HIGHLIGHT: "_enriched_highlight.json",
    ArtifactKind.EDIT_PLAN: "_edit_plan.json",
    ArtifactKind.RENDER: "_reel.mp4",
    ArtifactKind.SUBTITLES_JSON: "_subtitles.json",
    ArtifactKind.SUBTITLES_SRT: ".srt",
}


@dataclass(frozen=True)
class ArtifactInfo:
    """Immutable description of one discovered artifact.

    Attributes:
        kind: Which :class:`ArtifactKind` this file represents.
        path: Absolute path to the (existing) artifact file.
    """

    kind: ArtifactKind
    path: Path


class ArtifactResolver:
    """Resolve and discover producer artifacts for a given video stem.

    The resolver derives the *canonical* expected filename for each artifact
    kind. Producers may add a numeric suffix on collision (never-overwrite),
    so discovery also recognizes those variants when detecting presence.
    """

    def __init__(self, output_dir: Path) -> None:
        """Create a resolver bound to an ``output/`` directory.

        Args:
            output_dir: The directory producers write artifacts into.
        """
        self._output_dir = output_dir

    def expected_path(self, stem: str, kind: ArtifactKind) -> Path:
        """Return the canonical expected path for ``stem`` and ``kind``.

        This is the name a producer writes on first run (before any
        never-overwrite numeric suffix is applied).
        """
        return self._output_dir / f"{stem}{ARTIFACT_SUFFIXES[kind]}"

    def find(self, stem: str, kind: ArtifactKind) -> Optional[Path]:
        """Return the canonical artifact path if it exists, else ``None``.

        Only the canonical (non-suffixed) name is treated as the current
        artifact; numeric-suffixed variants are older, never-overwritten
        copies and are intentionally not reported as the active artifact.
        """
        candidate = self.expected_path(stem, kind)
        return candidate if candidate.is_file() else None

    def exists(self, stem: str, kind: ArtifactKind) -> bool:
        """Return whether the canonical artifact for ``stem``/``kind`` exists."""
        return self.find(stem, kind) is not None

    def discover(self, stem: str) -> List[ArtifactInfo]:
        """Return all canonical artifacts that currently exist for ``stem``."""
        found: List[ArtifactInfo] = []
        for kind in ArtifactKind:
            path = self.find(stem, kind)
            if path is not None:
                found.append(ArtifactInfo(kind=kind, path=path))
        return found
