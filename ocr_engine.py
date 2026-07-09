"""Phase 5B: pluggable OCR engines.

The :class:`OcrEngine` Protocol turns a single image (an ROI crop, as a numpy
array) into raw text results. Engines are swappable behind the Protocol; the
reference implementation is Tesseract, but the concrete default is a
benchmarking decision (see ``PHASE5B_DESIGN.md`` section 4).

Engines return **raw** results only: text, confidence and a normalized bbox.
They never assign detection ids or ``scene_index`` and never interpret text
(no game meaning). The extractor owns ids, scene mapping and aggregation.

CPU-first: OCR runs only on small ROI crops, never full frames.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol, runtime_checkable

import numpy as np
from numpy.typing import NDArray

from logger import get_logger
from ocr_config import OcrError

logger = get_logger(__name__)


@dataclass
class OcrResult:
    """A raw OCR result for one recognized text span within an ROI crop.

    ``bbox`` is normalized 0..1 **relative to the full frame** (the extractor
    converts crop-local boxes to frame coordinates). No id, no scene_index.
    """

    text: str
    confidence: float
    bbox: dict[str, float]  # {"x", "y", "w", "h"} normalized 0..1


@runtime_checkable
class OcrEngine(Protocol):
    """Recognize text in a single image (an ROI crop)."""

    name: str

    def recognize(self, image: NDArray[np.uint8], /) -> list[OcrResult]:
        """Return raw text results for ``image`` (crop-local bboxes 0..1)."""
        ...


# --------------------------------------------------------------------- #
# Preprocessing helpers (pure, testable; used by engines/extractor)
# --------------------------------------------------------------------- #
def to_grayscale(image: NDArray[np.uint8]) -> NDArray[np.uint8]:
    """Convert a BGR (or already-gray) image to single-channel grayscale."""
    if image.ndim == 2:
        return image
    # Luminosity weights on BGR channels (OpenCV order), dependency-free.
    b = image[:, :, 0].astype(np.float32)
    g = image[:, :, 1].astype(np.float32)
    r = image[:, :, 2].astype(np.float32)
    gray = 0.114 * b + 0.587 * g + 0.299 * r
    return gray.clip(0, 255).astype(np.uint8)


def binarize(gray: NDArray[np.uint8]) -> NDArray[np.uint8]:
    """Threshold a grayscale image at its mean (deterministic, simple)."""
    if gray.size == 0:
        return gray
    thresh = float(gray.mean())
    return np.where(gray >= thresh, np.uint8(255), np.uint8(0)).astype(np.uint8)


def upscale(image: NDArray[np.uint8], factor: float) -> NDArray[np.uint8]:
    """Nearest-neighbour upscale (dependency-free) to enlarge small crops."""
    if factor == 1.0 or image.size == 0:
        return image
    h, w = image.shape[:2]
    new_h = max(int(round(h * factor)), 1)
    new_w = max(int(round(w * factor)), 1)
    row_idx = (np.arange(new_h) / factor).astype(int).clip(0, h - 1)
    col_idx = (np.arange(new_w) / factor).astype(int).clip(0, w - 1)
    return image[row_idx][:, col_idx]


# --------------------------------------------------------------------- #
# Reference backend: Tesseract
# --------------------------------------------------------------------- #
class TesseractOcrEngine:
    """Reference CPU OCR backend using ``pytesseract``.

    The heavy dependency is imported lazily so unit tests (which inject a fake
    engine) never require Tesseract, and a missing binary fails gracefully
    with a clear error (mirroring the FFmpeg pattern).
    """

    name = "tesseract"

    # Page segmentation mode. PSM 6 ("assume a single uniform block of
    # text") is robust for small ROI crops / single words; the default
    # PSM 3 (automatic page segmentation) often returns nothing on such
    # crops. The configured value is supplied via OcrConfig.psm and wired
    # on by the extractor, mirroring tesseract_cmd.
    DEFAULT_PSM = 6

    def __init__(self, cmd: str | None = None, psm: int = DEFAULT_PSM) -> None:
        self._pytesseract = None
        # Optional absolute path to the Tesseract binary. When set, it is
        # applied to pytesseract on first use so PATH is not required.
        self._cmd = cmd
        self._psm = psm

    def _lazy(self):
        if self._pytesseract is None:
            try:
                import pytesseract  # type: ignore
            except ImportError as exc:  # pragma: no cover - env dependent
                raise OcrError(
                    "pytesseract is not installed. Install pytesseract and the "
                    "Tesseract binary, or select a different OCR engine."
                ) from exc
            if self._cmd:
                pytesseract.pytesseract.tesseract_cmd = self._cmd
            self._pytesseract = pytesseract
        return self._pytesseract

    def recognize(self, image: NDArray[np.uint8], /) -> list[OcrResult]:
        pytesseract = self._lazy()
        h, w = image.shape[:2]
        if h == 0 or w == 0:
            return []
        try:
            data = pytesseract.image_to_data(
                image,
                output_type=pytesseract.Output.DICT,
                config=f"--psm {self._psm}",
            )
        except Exception as exc:  # pragma: no cover - env dependent
            raise OcrError(f"Tesseract recognition failed: {exc}") from exc

        results: list[OcrResult] = []
        n = len(data.get("text", []))
        for i in range(n):
            text = (data["text"][i] or "").strip()
            if not text:
                continue
            conf_raw = float(data.get("conf", ["-1"])[i])
            confidence = max(0.0, min(conf_raw / 100.0, 1.0))
            bx, by = int(data["left"][i]), int(data["top"][i])
            bw, bh = int(data["width"][i]), int(data["height"][i])
            results.append(
                OcrResult(
                    text=text,
                    confidence=round(confidence, 6),
                    bbox={
                        "x": round(bx / w, 6),
                        "y": round(by / h, 6),
                        "w": round(bw / w, 6),
                        "h": round(bh / h, 6),
                    },
                )
            )
        return results


# --------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------- #
EngineFactory = Callable[[], OcrEngine]

_REGISTRY: dict[str, EngineFactory] = {
    TesseractOcrEngine.name: TesseractOcrEngine,
}


def register_engine(name: str, factory: EngineFactory) -> None:
    """Register an OCR engine factory under ``name`` (idempotent overwrite)."""
    _REGISTRY[name] = factory


def create_engine(name: str) -> OcrEngine:
    """Instantiate a registered OCR engine by name."""
    try:
        factory = _REGISTRY[name]
    except KeyError as exc:
        available = ", ".join(sorted(_REGISTRY)) or "(none)"
        raise OcrError(
            f"Unknown OCR engine '{name}'. Available: {available}."
        ) from exc
    return factory()


def available_engines() -> list[str]:
    """Return the sorted list of registered engine names."""
    return sorted(_REGISTRY)
