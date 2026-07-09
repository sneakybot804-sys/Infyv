"""Phase 5B: configuration for HUD text extraction (OCR).

All tunables live here so no threshold, ROI or sampling value is hardcoded in
the logic (Open/Closed Principle), mirroring ``AudioConfig`` and
``HighlightScoringConfig``.

CPU-first for the target hardware (Ryzen 7 5700G, 16 GB). OCR runs only on
configured **static** ROIs of a few sampled frames per scene; full-frame OCR
is out of scope. Automatic HUD detection is deferred to a future phase.

No backend is hardcoded: the concrete default engine is chosen by
implementation-time benchmarking. ``OcrConfig.engine`` names whichever engine
the caller selects; the extractor resolves it via a small registry.
"""
from __future__ import annotations

from dataclasses import dataclass, field


class OcrError(RuntimeError):
    """Raised when OCR configuration or extraction fails.

    Mirrors the ``FFmpegServiceError`` / ``AudioAnalyzerError`` pattern: fail
    loud, normalized, and logged before raising.
    """


@dataclass(frozen=True)
class Roi:
    """A named, normalized (0..1) static region of interest.

    Coordinates are fractions of frame width/height so a profile works across
    resolutions. ``name`` is a generic, config-defined label (e.g.
    ``"top_right"``), never a game concept like "kill feed".
    """

    name: str
    x: float
    y: float
    w: float
    h: float

    def validate(self) -> None:
        """Validate that the rectangle lies within the normalized frame."""
        for label, value in (("x", self.x), ("y", self.y), ("w", self.w), ("h", self.h)):
            if not 0.0 <= value <= 1.0:
                raise OcrError(f"ROI '{self.name}' {label}={value} must be within 0..1.")
        if self.w <= 0.0 or self.h <= 0.0:
            raise OcrError(f"ROI '{self.name}' must have positive width and height.")
        if self.x + self.w > 1.0 or self.y + self.h > 1.0:
            raise OcrError(f"ROI '{self.name}' extends beyond the frame bounds.")


# A sensible default profile: common HUD corners/edges as generic ROIs.
DEFAULT_ROIS: tuple[Roi, ...] = (
    Roi("top_left", 0.00, 0.00, 0.30, 0.15),
    Roi("top_right", 0.70, 0.00, 0.30, 0.15),
    Roi("top_center", 0.30, 0.00, 0.40, 0.12),
    Roi("bottom_left", 0.00, 0.85, 0.30, 0.15),
    Roi("bottom_right", 0.70, 0.85, 0.30, 0.15),
    Roi("bottom_center", 0.30, 0.88, 0.40, 0.12),
)


@dataclass(frozen=True)
class OcrConfig:
    """Fully configurable OCR settings (CPU-first, static ROIs only)."""

    # --- Engine (chosen by benchmarking; not locked by the design) ---
    engine: str = "tesseract"

    # Optional absolute path to the Tesseract binary. When set, it overrides
    # PATH-based discovery (e.g. r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    # on Windows). When None, the engine relies on the system PATH.
    tesseract_cmd: str | None = None

    # Tesseract page segmentation mode. PSM 6 ("assume a single uniform block
    # of text") is robust for small ROI crops / single words; the Tesseract
    # default (PSM 3, automatic page segmentation) often returns nothing on
    # such crops. Config-driven so it is not a hidden magic number.
    psm: int = 6

    # --- Static ROIs (configuration-driven; no automatic HUD detection) ---
    rois: tuple[Roi, ...] = DEFAULT_ROIS

    # --- Per-scene sampling ---
    frames_per_scene: int = 1          # representative frames per scene
    # When no analysis.json is available, sample the whole video at a fixed
    # interval instead of per-scene.
    fallback_interval_seconds: float = 10.0

    # --- Preprocessing (applied to each ROI crop before OCR) ---
    grayscale: bool = True
    threshold: bool = True             # binarize for stylized HUD fonts
    upscale: float = 2.0               # enlarge small crops for accuracy

    # --- Thresholds ---
    min_confidence: float = 0.4        # drop detections below this (0..1)
    min_text_length: int = 1          # drop shorter recognized strings

    # --- Skip rules ---
    skip_black_idle: bool = True       # skip scenes marked black/idle in analysis

    def validate(self) -> None:
        """Validate ranges, ROIs and unique ROI names."""
        if not self.rois:
            raise OcrError("At least one ROI must be configured.")
        names = [roi.name for roi in self.rois]
        if len(names) != len(set(names)):
            raise OcrError("ROI names must be unique.")
        for roi in self.rois:
            roi.validate()

        if self.frames_per_scene <= 0:
            raise OcrError("frames_per_scene must be positive.")
        if self.fallback_interval_seconds <= 0:
            raise OcrError("fallback_interval_seconds must be positive.")
        if self.upscale <= 0:
            raise OcrError("upscale must be positive.")
        if not 0.0 <= self.min_confidence <= 1.0:
            raise OcrError("min_confidence must be within 0..1.")
        if self.min_text_length < 0:
            raise OcrError("min_text_length must be >= 0.")
