"""Phase 5D: configuration for the Signal Fusion Engine.

The fusion engine is a pure *consumer* of the frozen Phase 5 artifacts
(``highlight.json`` 5a.1, ``ocr.json`` 5b.1, ``audio.json`` 5c.1). It fuses
them at **scene level** into ``enriched_highlight.json`` (5d.1). Every
tunable lives here so no weight, reference or threshold is hardcoded in the
logic (Open/Closed Principle), mirroring ``HighlightScoringConfig``,
``OcrConfig`` and ``AudioConfig``.

Design constraints (Phase 5D):
- Scene-level fusion only; time-window refinement is deferred.
- Missing OCR/Audio artifacts must never fail fusion (their signals
  contribute 0). A missing highlight artifact is fatal (nothing to enrich).
- No new third-party dependencies; no interpretation of text/audio meaning.
"""
from __future__ import annotations

from dataclasses import dataclass


class FusionError(RuntimeError):
    """Raised when fusion configuration or fusion itself fails.

    Mirrors the ``HighlightScorerError`` / ``AudioAnalyzerError`` / ``OcrError``
    pattern: fail loud, normalized, and logged before raising.
    """


@dataclass(frozen=True)
class FusionConfig:
    """Fully configurable weights, references and thresholds for fusion.

    Each signal is normalized to a 0..1 sub-score, multiplied by its weight,
    and the weighted sum is normalized by the total active weight so the
    fused score is itself 0..1 internally. The public artifact exposes the
    score on the same **0..100** scale as Phase 5A for consistency.

    Priority intent (fusion is highlight-anchored): the base Phase 5A score
    is the backbone; OCR and audio act as corroborating boosts.
    """

    # --- Per-signal weights (applied to 0..1 sub-scores) ---
    base_highlight_weight: float = 1.0
    ocr_weight: float = 0.5
    audio_energy_weight: float = 0.6
    voice_excitement_weight: float = 0.7

    # --- Normalization references (define what "1.0" means per signal) ---
    # Phase 5A scores are already 0..100; this maps them onto 0..1.
    base_score_reference: float = 100.0
    # OCR detection confidence is already 0..1; reference kept explicit so a
    # deployment can down-weight noisy engines without code changes.
    ocr_confidence_reference: float = 1.0
    # Audio event energy sub-score reference (RawEvent.energy is ~0..1 from
    # the numpy backend; a reference > 0 keeps this tunable).
    audio_energy_reference: float = 1.0
    # Excitement peak score reference (peak.score is ~0..1).
    excitement_reference: float = 1.0

    # --- Output score scale (public artifact) ---
    output_score_scale: float = 100.0

    # --- Selection ---
    # None => keep all scenes; a positive int keeps the top-N by fused score.
    top_n: int | None = None

    # --- Classification thresholds on the final 0..100 fused score ---
    # Independent from Phase 5A thresholds so the fusion layer is decoupled.
    excellent_threshold: float = 70.0
    good_threshold: float = 45.0
    average_threshold: float = 20.0

    def validate(self) -> None:
        """Validate weights, references, thresholds and selection."""
        for name, value in (
            ("base_highlight_weight", self.base_highlight_weight),
            ("ocr_weight", self.ocr_weight),
            ("audio_energy_weight", self.audio_energy_weight),
            ("voice_excitement_weight", self.voice_excitement_weight),
        ):
            if value < 0.0:
                raise FusionError(f"{name} must be >= 0.")

        total_weight = (
            self.base_highlight_weight
            + self.ocr_weight
            + self.audio_energy_weight
            + self.voice_excitement_weight
        )
        if total_weight <= 0.0:
            raise FusionError("At least one signal weight must be positive.")

        for name, value in (
            ("base_score_reference", self.base_score_reference),
            ("ocr_confidence_reference", self.ocr_confidence_reference),
            ("audio_energy_reference", self.audio_energy_reference),
            ("excitement_reference", self.excitement_reference),
            ("output_score_scale", self.output_score_scale),
        ):
            if value <= 0.0:
                raise FusionError(f"{name} must be positive.")

        if self.top_n is not None and self.top_n <= 0:
            raise FusionError("top_n must be a positive integer or None.")

        if not (
            self.excellent_threshold
            > self.good_threshold
            > self.average_threshold
            >= 0.0
        ):
            raise FusionError(
                "Classification thresholds must be strictly descending and "
                ">= 0 (excellent > good > average >= 0)."
            )
