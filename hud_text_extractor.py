"""Phase 5B: HUD Text Extractor -- independent producer of ``ocr.json``.

Orchestrates per-scene frame sampling, **ROI-only** OCR via a pluggable
:class:`OcrEngine`, deterministic detection-id assignment, optional scene
mapping from a Phase 4A ``analysis.json``, and never-overwrite output of
``ocr.json`` (schema ``5b.1``).

Hard boundaries (``PHASE5B_DESIGN.md``):
- **Fully decoupled.** No import of ``highlight_scorer``, ``video_analyzer``,
  ``audio_analyzer``, ``scene_detector`` or OCR game-adapters. Produces
  ``ocr.json`` only.
- **Game-agnostic.** Raw text/region/confidence only; no interpretation.
- **ROI-only.** OCR runs on configured static ROI crops of sampled frames,
  never full frames.
- **No magic numbers.** All tunables live in :class:`OcrConfig`.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from config import AppConfig, config
from logger import get_logger
from ocr_config import OcrConfig, OcrError, Roi
from ocr_engine import (
    OcrEngine,
    OcrResult,
    TesseractOcrEngine,
    binarize,
    create_engine,
    to_grayscale,
    upscale,
)

logger = get_logger(__name__)

SCHEMA_VERSION = "5b.1"
INPUT_SCHEMA_VERSION = "4a.1"


class HudTextExtractor:
    """Extract HUD text from a video into a standalone ``ocr.json``."""

    def __init__(
        self,
        app_config: AppConfig | None = None,
        ocr_config: OcrConfig | None = None,
        ffmpeg_service: Any | None = None,
    ) -> None:
        """Create an extractor.

        Args:
            app_config: Shared application config (paths).
            ocr_config: Tunables; static ROIs, sampling, preprocessing.
            ffmpeg_service: Object exposing ``extract_frame_at``. Injectable
                for tests. Imported lazily so unit tests never require FFmpeg.
        """
        self._config = app_config or config
        self._ocr = ocr_config or OcrConfig()
        self._ocr.validate()
        self._ffmpeg = ffmpeg_service or self._default_ffmpeg()
        logger.info("Initialized HudTextExtractor (engine=%s)", self._ocr.engine)

    @staticmethod
    def _default_ffmpeg() -> Any:
        """Lazily construct the real FFmpegService (kept out of unit tests)."""
        from ffmpeg_service import FFmpegService

        return FFmpegService()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def extract(
        self,
        video: str | Path,
        analysis_path: str | Path | None = None,
    ) -> dict[str, Any]:
        """Extract HUD text and return the ``ocr.json`` document (dict)."""
        video = str(video)
        scenes = self._load_scenes(analysis_path, video)
        samples = self._sample_points(scenes)

        engine: OcrEngine = create_engine(self._ocr.engine)
        # Wire the optional config-driven Tesseract options onto the engine:
        # the binary path (so it need not be on PATH) and the page
        # segmentation mode. Applied only to the reference Tesseract backend;
        # other engines are unaffected.
        if isinstance(engine, TesseractOcrEngine):
            if self._ocr.tesseract_cmd:
                engine._cmd = self._ocr.tesseract_cmd
            engine._psm = self._ocr.psm
        raw_detections: list[dict[str, Any]] = []

        # In the open-ended fallback walk (no scenes) a decode failure means
        # end-of-video: stop sampling. With a bounded scene-based schedule a
        # single bad frame is tolerated (continue) so it never aborts a known
        # set of samples.
        stop_on_missing_frame = scenes is None

        for timestamp in samples:
            try:
                frame = self._ffmpeg.extract_frame_at(video, timestamp)
            except Exception as exc:  # bad/absent frame
                logger.warning("Frame at %.3fs failed, skipped: %s", timestamp, exc)
                if stop_on_missing_frame:
                    break
                continue
            for roi in self._ocr.rois:
                for result in self._ocr_roi(engine, frame, roi):
                    raw_detections.append(
                        self._to_detection(result, roi, timestamp, scenes)
                    )

        detections = self._assign_ids(raw_detections)
        return {
            "schema_version": SCHEMA_VERSION,
            "video": video,
            "engine": self._ocr.engine,
            "detections": detections,
        }

    def extract_to_file(
        self,
        video: str | Path,
        analysis_path: str | Path | None = None,
        output_name: str | None = None,
    ) -> Path:
        """Extract and write ``<video>_ocr.json`` (never overwritten)."""
        document = self.extract(video, analysis_path)
        out_dir = self._config.paths.output_dir
        out_dir.mkdir(parents=True, exist_ok=True)

        stem = Path(str(video)).stem
        base_name = output_name or f"{stem}_ocr.json"
        output = self._unique_path(out_dir, base_name)
        output.write_text(json.dumps(document, indent=2), encoding="utf-8")
        logger.info("Wrote OCR JSON -> %s", output)
        return output

    # ------------------------------------------------------------------ #
    # ROI OCR (ROI-only; never full-frame)
    # ------------------------------------------------------------------ #
    def _ocr_roi(
        self, engine: OcrEngine, frame: NDArray[np.uint8], roi: Roi
    ) -> list[OcrResult]:
        """Crop a single ROI, preprocess, and OCR only that crop."""
        crop = self._crop(frame, roi)
        if crop.size == 0:
            return []
        crop = self._preprocess(crop)
        results = engine.recognize(crop)

        kept: list[OcrResult] = []
        for res in results:
            if (
                res.confidence >= self._ocr.min_confidence
                and len(res.text) >= self._ocr.min_text_length
            ):
                kept.append(res)
        return kept

    @staticmethod
    def _crop(frame: NDArray[np.uint8], roi: Roi) -> NDArray[np.uint8]:
        """Return the ROI sub-image from a frame using normalized coords."""
        h, w = frame.shape[:2]
        x0 = int(round(roi.x * w))
        y0 = int(round(roi.y * h))
        x1 = min(int(round((roi.x + roi.w) * w)), w)
        y1 = min(int(round((roi.y + roi.h) * h)), h)
        if x1 <= x0 or y1 <= y0:
            return np.empty((0, 0), dtype=np.uint8)
        return frame[y0:y1, x0:x1]

    def _preprocess(self, crop: NDArray[np.uint8]) -> NDArray[np.uint8]:
        """Apply configured preprocessing to an ROI crop."""
        out = crop
        if self._ocr.grayscale:
            out = to_grayscale(out)
        if self._ocr.threshold:
            gray = out if out.ndim == 2 else to_grayscale(out)
            out = binarize(gray)
        if self._ocr.upscale != 1.0:
            out = upscale(out, self._ocr.upscale)
        return out

    def _to_detection(
        self,
        result: OcrResult,
        roi: Roi,
        timestamp: float,
        scenes: list[dict[str, float]] | None,
    ) -> dict[str, Any]:
        """Build a detection dict (id assigned later) with a frame-space bbox.

        The engine returns a bbox relative to the ROI crop; convert it to
        full-frame normalized coordinates using the ROI offset/size.
        """
        bbox = {
            "x": round(roi.x + result.bbox["x"] * roi.w, 6),
            "y": round(roi.y + result.bbox["y"] * roi.h, 6),
            "w": round(result.bbox["w"] * roi.w, 6),
            "h": round(result.bbox["h"] * roi.h, 6),
        }
        return {
            "id": None,  # assigned deterministically after ordering
            "scene_index": self._scene_index_for(timestamp, scenes),
            "timestamp": round(float(timestamp), 3),
            "region": roi.name,
            "text": result.text,
            "confidence": round(float(result.confidence), 6),
            "bbox": bbox,
        }

    # ------------------------------------------------------------------ #
    # Deterministic detection ids (section 3.3)
    # ------------------------------------------------------------------ #
    @staticmethod
    def _assign_ids(detections: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Order deterministically and assign ``<region>-<seq>`` ids.

        Order: ascending timestamp, then region, then reading order
        (bbox y, then x) for full determinism. Sequence is per-region.
        """
        ordered = sorted(
            detections,
            key=lambda d: (
                d["timestamp"],
                d["region"],
                d["bbox"]["y"],
                d["bbox"]["x"],
            ),
        )
        counters: dict[str, int] = {}
        for det in ordered:
            region = det["region"]
            counters[region] = counters.get(region, 0) + 1
            det["id"] = f"{region}-{counters[region]:04d}"
        return ordered

    # ------------------------------------------------------------------ #
    # Sampling
    # ------------------------------------------------------------------ #
    def _sample_points(self, scenes: list[dict[str, float]] | None) -> list[float]:
        """Return the sorted, de-duplicated timestamps to OCR.

        Per-scene when scenes are available (``frames_per_scene`` evenly
        spaced inside each scene), otherwise a fixed fallback interval.
        """
        points: list[float] = []
        if scenes:
            for scene in scenes:
                start, end = scene["start"], scene["end"]
                span = max(end - start, 0.0)
                n = self._ocr.frames_per_scene
                for k in range(n):
                    # Evenly spaced sample fractions inside the scene.
                    frac = (k + 1) / (n + 1)
                    points.append(round(start + frac * span, 3))
        else:
            # No scenes: sample the whole video at a fixed interval. Duration
            # is unknown here without decoding; sample a bounded set and let
            # frame extraction stop failing past the end (skipped gracefully).
            # Walk from the start of the video (t=0.0) at a fixed interval.
            # The extract loop stops this open-ended walk at the first frame
            # that fails to decode (end of video).
            step = self._ocr.fallback_interval_seconds
            points = [round(step * i, 3) for i in range(0, 1000)]
        return sorted(set(points))

    # ------------------------------------------------------------------ #
    # Scene mapping (identical to Phase 5C)
    # ------------------------------------------------------------------ #
    def _load_scenes(
        self, analysis_path: str | Path | None, video: str
    ) -> list[dict[str, float]] | None:
        """Load scene bounds from an optional analysis.json.

        Returns None (=> all scene_index null, fallback sampling) when the
        file is absent, unreadable, or its ``video`` key does not match.
        """
        if analysis_path is None:
            return None
        path = Path(analysis_path).expanduser()
        if not path.is_file():
            logger.warning("analysis.json not found at %s; scene_index=null", path)
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not read analysis.json (%s); scene_index=null", exc)
            return None

        recorded = str(data.get("video", ""))
        if recorded and Path(recorded).name != Path(video).name:
            logger.warning(
                "analysis.json video '%s' does not match '%s'; scene_index=null",
                recorded,
                video,
            )
            return None

        scenes = data.get("scenes", [])
        if not isinstance(scenes, list) or not scenes:
            return None
        parsed: list[dict[str, float]] = []
        black_idle = self._black_idle_spans(data) if self._ocr.skip_black_idle else []
        for position, s in enumerate(scenes):
            start = float(s.get("start", 0.0))
            end = float(s.get("end", 0.0))
            if self._ocr.skip_black_idle and self._fully_covered(start, end, black_idle):
                continue
            # Preserve the ORIGINAL Phase 4A scene index (from the analysis
            # 'index' field, else the pre-skip position) so scene_index stays
            # consistent with analysis.json/audio.json for fusion, even when
            # black/idle scenes are skipped here.
            original_index = int(s.get("index", position))
            parsed.append({"start": start, "end": end, "index": original_index})
        return parsed or None

    @staticmethod
    def _black_idle_spans(data: dict[str, Any]) -> list[tuple[float, float]]:
        spans: list[tuple[float, float]] = []
        for key in ("black_screens", "idle_sections"):
            for span in data.get(key, []) or []:
                spans.append((float(span.get("start", 0.0)), float(span.get("end", 0.0))))
        return spans

    @staticmethod
    def _fully_covered(
        start: float, end: float, spans: list[tuple[float, float]]
    ) -> bool:
        """True if [start, end) is entirely inside one black/idle span."""
        for s, e in spans:
            if s <= start and end <= e:
                return True
        return False

    @staticmethod
    def _scene_index_for(
        timestamp: float, scenes: list[dict[str, float]] | None
    ) -> int | None:
        """Map a timestamp to a scene using a half-open interval (5C rule).

        Rule: ``scene.start <= timestamp < scene.end``. Outside all scenes,
        or when no scenes are available, map to ``None`` (never 0).
        """
        if not scenes:
            return None
        for position, scene in enumerate(scenes):
            if scene["start"] <= timestamp < scene["end"]:
                # Prefer the preserved original 4A index when present.
                return int(scene.get("index", position))
        return None

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _unique_path(directory: Path, base_name: str) -> Path:
        """Return a path in ``directory`` that does not already exist."""
        candidate = directory / base_name
        if not candidate.exists():
            return candidate
        stem = Path(base_name).stem
        suffix = Path(base_name).suffix
        counter = 1
        while True:
            candidate = directory / f"{stem}_{counter}{suffix}"
            if not candidate.exists():
                return candidate
            counter += 1
