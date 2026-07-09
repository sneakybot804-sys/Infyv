"""Phase 5E: configuration for the AI Decision Pipeline.

The decision pipeline is a pure *consumer* of ``enriched_highlight.json``
(schema ``5d.1``) that produces a lightweight ``edit_plan.json`` (schema
``5e.1``) for the future Phase 6 renderer. Every tunable lives here so no
weight, threshold or size is hardcoded in the logic (Open/Closed Principle),
mirroring ``FusionConfig``, ``OcrConfig`` and ``AudioConfig``.

This module is deliberately independent of ``agent.py``: it defines its own
error type and never couples to the existing ``GamingEditorAgent``.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class DecisionError(RuntimeError):
    """Raised when decision configuration or plan generation fails.

    Mirrors the ``FusionError`` / ``OcrError`` / ``AudioAnalyzerError``
    pattern: fail loud, normalized, and logged before raising. Deliberately
    distinct from any agent error so the pipeline stays decoupled.
    """


class FallbackStrategy(str, Enum):
    """How the deterministic fallback selects candidate scenes.

    - ``TOP_N``: keep the highest-ranked ``top_n`` scenes.
    - ``THRESHOLD``: keep every scene with ``score >= min_score``.
    - ``HYBRID``: keep scenes with ``score >= min_score``, then cap to the
      highest-ranked ``top_n`` of those.
    """

    TOP_N = "top_n"
    THRESHOLD = "threshold"
    HYBRID = "hybrid"


@dataclass(frozen=True)
class DecisionConfig:
    """Fully configurable settings for the AI decision pipeline."""

    # --- LLM control ---
    # When False, the pipeline always uses the deterministic fallback (a
    # useful offline mode and the default for unit tests).
    use_llm: bool = True
    # Optional override for the model temperature; None uses OllamaConfig.
    temperature_override: float | None = None

    # --- Candidate selection (deterministic fallback + LLM candidate set) ---
    fallback_strategy: FallbackStrategy = FallbackStrategy.HYBRID
    # Keep at most this many segments in the final plan.
    max_segments: int = 10
    # TOP_N / HYBRID: number of highest-ranked scenes to keep.
    top_n: int = 5
    # THRESHOLD / HYBRID: minimum fused score (0..100) to keep a scene.
    min_score: float = 20.0

    # --- Segment shaping ---
    # Padding added before/after each scene's bounds (seconds, clamped >= 0).
    pre_roll_seconds: float = 0.0
    post_roll_seconds: float = 0.0
    # Merge segments whose gap is <= this many seconds into one.
    merge_adjacent: bool = True
    merge_gap_seconds: float = 0.5

    def validate(self) -> None:
        """Validate ranges and selection sizes."""
        if self.max_segments <= 0:
            raise DecisionError("max_segments must be positive.")
        if self.top_n <= 0:
            raise DecisionError("top_n must be positive.")
        if not 0.0 <= self.min_score <= 100.0:
            raise DecisionError("min_score must be within 0..100.")
        if self.pre_roll_seconds < 0.0 or self.post_roll_seconds < 0.0:
            raise DecisionError("pre/post roll seconds must be >= 0.")
        if self.merge_gap_seconds < 0.0:
            raise DecisionError("merge_gap_seconds must be >= 0.")
        if self.temperature_override is not None and self.temperature_override < 0.0:
            raise DecisionError("temperature_override must be >= 0 when set.")
        if not isinstance(self.fallback_strategy, FallbackStrategy):
            raise DecisionError("fallback_strategy must be a FallbackStrategy.")
