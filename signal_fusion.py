"""Phase 5D: Signal Fusion Engine -- producer of ``enriched_highlight.json``.

A pure **consumer** that reads the frozen Phase 5 artifacts and fuses them at
**scene level** into a ranked ``enriched_highlight.json`` (schema ``5d.1``):

    highlight.json (5a.1)  -- the scoring backbone (required)
    ocr.json       (5b.1)  -- HUD text detections (optional)
    audio.json     (5c.1)  -- acoustic events + commentary excitement (optional)

Hard boundaries (Phase 5D design):
- **Fully decoupled.** No import of ``highlight_scorer``, ``video_analyzer``,
  ``audio_analyzer``, ``hud_text_extractor``, ``ocr_engine`` or
  ``scene_detector``. This module reads JSON and writes JSON only.
- **Read-only on producers.** Producer artifacts are never modified; a new
  artifact is written and never overwritten.
- **Scene-level only.** Alignment is by scene index (``highlight.index`` ==
  ``ocr``/``audio`` ``scene_index``). Detections/events with a null
  ``scene_index`` contribute to no scene; time-window fusion is deferred.
- **Missing signals never fail fusion** (they contribute 0); only a missing
  highlight backbone is fatal.
- **No magic numbers.** All weights/references/thresholds live in
  :class:`FusionConfig`.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from config import AppConfig, config
from logger import get_logger
from signal_fusion_config import FusionConfig, FusionError

logger = get_logger(__name__)

SCHEMA_VERSION = "5d.1"
# Input schema versions this engine is written against (informational; the
# engine tolerates additive fields and missing optional artifacts).
INPUT_SCHEMA_VERSIONS = {
    "highlight": "5a.1",
    "ocr": "5b.1",
    "audio": "5c.1",
}


@dataclass
class SceneSignals:
    """Per-scene normalized (0..1) contribution of each fused signal."""

    base_highlight: float
    ocr: float
    audio_energy: float
    voice_excitement: float


@dataclass
class EnrichedScene:
    """A fused, rankable scene for ``enriched_highlight.json``."""

    index: int
    start: float
    end: float
    duration: float
    score: float  # fused score on the public 0..100 scale (5A parity)
    classification: str
    rank: int
    signals: SceneSignals
    ocr: list[str] = field(default_factory=list)


@dataclass
class EnrichedHighlightReport:
    """Complete fused report, serializable to ``enriched_highlight.json``."""

    video: str
    sources: dict[str, dict[str, Any]]
    scenes: list[EnrichedScene] = field(default_factory=list)
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        """Return a plain-dict representation ready for JSON serialization."""
        return {
            "schema_version": self.schema_version,
            "video": self.video,
            "sources": self.sources,
            "scenes": [
                {
                    "index": s.index,
                    "start": s.start,
                    "end": s.end,
                    "duration": s.duration,
                    "score": s.score,
                    "classification": s.classification,
                    "rank": s.rank,
                    "signals": asdict(s.signals),
                    "ocr": list(s.ocr),
                }
                for s in self.scenes
            ],
        }

    def to_json(self, indent: int = 2) -> str:
        """Return the report serialized as a JSON string."""
        return json.dumps(self.to_dict(), indent=indent)


class SignalFusionEngine:
    """Fuse Phase 5 artifacts into a ranked ``enriched_highlight.json``."""

    def __init__(
        self,
        app_config: AppConfig | None = None,
        fusion_config: FusionConfig | None = None,
    ) -> None:
        """Create an engine.

        Args:
            app_config: Shared application config (paths).
            fusion_config: Weights/references/thresholds. Defaults are
                highlight-anchored with OCR/audio as corroborating boosts.
        """
        self._config = app_config or config
        self._fusion = fusion_config or FusionConfig()
        self._fusion.validate()
        logger.info("Initialized SignalFusionEngine")

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def fuse(
        self,
        highlight: dict[str, Any],
        ocr: dict[str, Any] | None = None,
        audio: dict[str, Any] | None = None,
    ) -> EnrichedHighlightReport:
        """Fuse in-memory artifact dicts into an enriched report.

        ``highlight`` is required; ``ocr`` and ``audio`` are optional and,
        when absent, contribute nothing (never fatal).
        """
        if not isinstance(highlight, dict) or "scenes" not in highlight:
            raise FusionError(
                "highlight artifact is required and must contain 'scenes'."
            )

        video = str(highlight.get("video", ""))
        base_scenes = highlight.get("scenes", []) or []

        # Per-scene aggregates from the optional artifacts (keyed by index).
        ocr_by_scene = self._aggregate_ocr(ocr)
        audio_by_scene = self._aggregate_audio(audio)

        # Availability is per source artifact (present vs absent), decided
        # once. An absent artifact drops its weight from normalization; a
        # present artifact keeps its weight even when a scene's value is a
        # genuine 0. The base highlight signal is always present (required).
        ocr_available = ocr is not None
        audio_available = audio is not None

        fused: list[EnrichedScene] = []
        for scene in base_scenes:
            index = int(scene.get("index", 0))
            signals = self._scene_signals(scene, ocr_by_scene.get(index), audio_by_scene.get(index))
            score_100 = self._fuse_score(signals, ocr_available, audio_available)
            fused.append(
                EnrichedScene(
                    index=index,
                    start=float(scene.get("start", 0.0)),
                    end=float(scene.get("end", 0.0)),
                    duration=float(scene.get("duration", 0.0)),
                    score=round(score_100, 4),
                    classification=self._classify(score_100),
                    rank=0,
                    signals=signals,
                    ocr=self._scene_ocr_text(ocr_by_scene.get(index)),
                )
            )

        ranked = self._rank_and_select(fused)
        report = EnrichedHighlightReport(
            video=video,
            sources=self._sources_block(highlight, ocr, audio),
            scenes=ranked,
        )
        logger.info("Fused %d scenes into enriched report", len(ranked))
        return report

    def fuse_files(
        self,
        video: str | Path | None = None,
        *,
        highlight_path: str | Path | None = None,
        ocr_path: str | Path | None = None,
        audio_path: str | Path | None = None,
    ) -> EnrichedHighlightReport:
        """Load artifacts (auto-discovered or explicit) and fuse them.

        Auto-discovery uses the existing naming convention in the output
        directory: ``<stem>_highlight.json`` / ``_ocr.json`` / ``_audio.json``.
        Explicit paths override discovery per artifact.
        """
        h_path, o_path, a_path = self._resolve_paths(
            video, highlight_path, ocr_path, audio_path
        )

        highlight = self._read_json(h_path, required=True, kind="highlight")
        ocr = self._read_json(o_path, required=False, kind="ocr")
        audio = self._read_json(a_path, required=False, kind="audio")
        return self.fuse(highlight, ocr, audio)

    def fuse_to_file(
        self,
        video: str | Path | None = None,
        *,
        highlight_path: str | Path | None = None,
        ocr_path: str | Path | None = None,
        audio_path: str | Path | None = None,
        output_name: str | None = None,
    ) -> Path:
        """Fuse and write ``<stem>_enriched_highlight.json`` (never overwritten)."""
        report = self.fuse_files(
            video,
            highlight_path=highlight_path,
            ocr_path=ocr_path,
            audio_path=audio_path,
        )
        out_dir = self._config.paths.output_dir
        out_dir.mkdir(parents=True, exist_ok=True)

        stem = self._stem_for_output(video, report.video)
        base_name = output_name or f"{stem}_enriched_highlight.json"
        output = self._unique_path(out_dir, base_name)
        output.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
        logger.info("Wrote enriched highlight JSON -> %s", output)
        return output

    # ------------------------------------------------------------------ #
    # Signal aggregation (scene-level; null scene_index ignored)
    # ------------------------------------------------------------------ #
    @staticmethod
    def _aggregate_ocr(ocr: dict[str, Any] | None) -> dict[int, dict[str, Any]]:
        """Group OCR detections by scene index.

        Returns ``{scene_index: {"max_confidence": float, "texts": [str]}}``.
        Detections with a null/absent ``scene_index`` are skipped.
        """
        by_scene: dict[int, dict[str, Any]] = {}
        if not ocr:
            return by_scene
        for det in ocr.get("detections", []) or []:
            scene_index = det.get("scene_index")
            if scene_index is None:
                continue
            idx = int(scene_index)
            bucket = by_scene.setdefault(idx, {"max_confidence": 0.0, "texts": []})
            conf = float(det.get("confidence", 0.0))
            if conf > bucket["max_confidence"]:
                bucket["max_confidence"] = conf
            text = str(det.get("text", "")).strip()
            if text:
                bucket["texts"].append(text)
        return by_scene

    @staticmethod
    def _aggregate_audio(audio: dict[str, Any] | None) -> dict[int, dict[str, Any]]:
        """Group audio signals by scene index across all tracks.

        Returns ``{scene_index: {"max_energy": float, "max_excitement": float}}``.
        Events / peaks with a null ``scene_index`` are skipped.
        """
        by_scene: dict[int, dict[str, Any]] = {}
        if not audio:
            return by_scene

        def _bucket(idx: int) -> dict[str, Any]:
            return by_scene.setdefault(idx, {"max_energy": 0.0, "max_excitement": 0.0})

        for track in audio.get("tracks", []) or []:
            for event in track.get("events", []) or []:
                scene_index = event.get("scene_index")
                if scene_index is None:
                    continue
                b = _bucket(int(scene_index))
                energy = float(event.get("energy", 0.0))
                if energy > b["max_energy"]:
                    b["max_energy"] = energy
            excitement = track.get("excitement")
            if isinstance(excitement, dict):
                for peak in excitement.get("peaks", []) or []:
                    scene_index = peak.get("scene_index")
                    if scene_index is None:
                        continue
                    b = _bucket(int(scene_index))
                    score = float(peak.get("score", 0.0))
                    if score > b["max_excitement"]:
                        b["max_excitement"] = score
        return by_scene

    @staticmethod
    def _scene_ocr_text(ocr_bucket: dict[str, Any] | None) -> list[str]:
        """Return the OCR text captured for a scene (empty when none)."""
        if not ocr_bucket:
            return []
        return list(ocr_bucket.get("texts", []))

    # ------------------------------------------------------------------ #
    # Fusion math (normalize -> weight -> 0..1 -> public 0..100)
    # ------------------------------------------------------------------ #
    def _scene_signals(
        self,
        base_scene: dict[str, Any],
        ocr_bucket: dict[str, Any] | None,
        audio_bucket: dict[str, Any] | None,
    ) -> SceneSignals:
        """Compute the 0..1 sub-score of each signal for one scene."""
        cfg = self._fusion
        base = self._clamp01(
            float(base_scene.get("score", 0.0)) / cfg.base_score_reference
        )
        ocr_conf = (ocr_bucket or {}).get("max_confidence", 0.0)
        ocr = self._clamp01(float(ocr_conf) / cfg.ocr_confidence_reference)
        energy = (audio_bucket or {}).get("max_energy", 0.0)
        audio_energy = self._clamp01(float(energy) / cfg.audio_energy_reference)
        excitement = (audio_bucket or {}).get("max_excitement", 0.0)
        voice = self._clamp01(float(excitement) / cfg.excitement_reference)
        return SceneSignals(
            base_highlight=round(base, 6),
            ocr=round(ocr, 6),
            audio_energy=round(audio_energy, 6),
            voice_excitement=round(voice, 6),
        )

    def _fuse_score(
        self,
        signals: SceneSignals,
        ocr_available: bool,
        audio_available: bool,
    ) -> float:
        """Weighted mean of the 0..1 sub-scores over the AVAILABLE signals.

        Only signals whose source artifact is present participate in the
        normalization: an absent OCR/audio artifact contributes neither value
        nor weight, so a missing signal never penalizes the fused score. The
        base highlight signal is always present. ``audio_available`` governs
        both audio_energy and voice_excitement (both derive from audio.json).
        """
        cfg = self._fusion
        # (sub_score, weight, available) per signal.
        contributions = [
            (signals.base_highlight, cfg.base_highlight_weight, True),
            (signals.ocr, cfg.ocr_weight, ocr_available),
            (signals.audio_energy, cfg.audio_energy_weight, audio_available),
            (signals.voice_excitement, cfg.voice_excitement_weight, audio_available),
        ]
        weighted = sum(
            weight * value for value, weight, available in contributions if available
        )
        total_weight = sum(
            weight for _value, weight, available in contributions if available
        )
        if total_weight <= 0.0:
            # No available signal carries positive weight; nothing to fuse.
            return 0.0
        fused01 = self._clamp01(weighted / total_weight)
        return fused01 * cfg.output_score_scale

    def _classify(self, score_100: float) -> str:
        """Bucket a fused 0..100 score using the configured thresholds."""
        cfg = self._fusion
        if score_100 >= cfg.excellent_threshold:
            return "Excellent"
        if score_100 >= cfg.good_threshold:
            return "Good"
        if score_100 >= cfg.average_threshold:
            return "Average"
        return "Ignore"

    # ------------------------------------------------------------------ #
    # Deterministic ranking + selection
    # ------------------------------------------------------------------ #
    def _rank_and_select(self, scenes: list[EnrichedScene]) -> list[EnrichedScene]:
        """Rank by fused score (desc), tie-break by scene index (asc).

        Ranking is deterministic. ``top_n`` (when set) keeps the highest-
        ranked N scenes; ``None`` keeps all.
        """
        ordered = sorted(scenes, key=lambda s: (-s.score, s.index))
        for position, scene in enumerate(ordered, start=1):
            scene.rank = position
        top_n = self._fusion.top_n
        if top_n is not None:
            ordered = ordered[:top_n]
        return ordered

    # ------------------------------------------------------------------ #
    # Sources metadata
    # ------------------------------------------------------------------ #
    @staticmethod
    def _sources_block(
        highlight: dict[str, Any],
        ocr: dict[str, Any] | None,
        audio: dict[str, Any] | None,
    ) -> dict[str, dict[str, Any]]:
        """Report which artifacts were present and their schema versions."""
        def entry(art: dict[str, Any] | None) -> dict[str, Any]:
            if not art:
                return {"available": False, "schema_version": None}
            return {
                "available": True,
                "schema_version": art.get("schema_version"),
            }

        return {
            "highlight": entry(highlight),
            "ocr": entry(ocr),
            "audio": entry(audio),
        }

    # ------------------------------------------------------------------ #
    # Path resolution / IO helpers
    # ------------------------------------------------------------------ #
    def _resolve_paths(
        self,
        video: str | Path | None,
        highlight_path: str | Path | None,
        ocr_path: str | Path | None,
        audio_path: str | Path | None,
    ) -> tuple[Path, Path | None, Path | None]:
        """Resolve artifact paths from explicit args or naming convention."""
        out_dir = self._config.paths.output_dir
        stem = Path(str(video)).stem if video is not None else None

        def discover(explicit: str | Path | None, suffix: str) -> Path | None:
            if explicit is not None:
                return Path(explicit).expanduser()
            if stem is None:
                return None
            return out_dir / f"{stem}_{suffix}.json"

        h = discover(highlight_path, "highlight")
        if h is None:
            raise FusionError(
                "A highlight artifact is required: provide 'highlight_path' "
                "or a 'video' for auto-discovery."
            )
        o = discover(ocr_path, "ocr")
        a = discover(audio_path, "audio")
        return h, o, a

    def _read_json(
        self, path: Path | None, *, required: bool, kind: str
    ) -> dict[str, Any] | None:
        """Read a JSON artifact.

        A missing/unreadable **required** artifact raises FusionError; a
        missing optional artifact returns None (fusion proceeds without it).
        """
        if path is None:
            if required:
                raise FusionError(f"Required {kind} artifact path is missing.")
            return None
        if not path.is_file():
            if required:
                raise FusionError(f"Required {kind} artifact not found: {path}")
            logger.info("Optional %s artifact absent (%s); skipping.", kind, path)
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            if required:
                raise FusionError(
                    f"Could not read {kind} artifact '{path}': {exc}"
                ) from exc
            logger.warning(
                "Optional %s artifact unreadable (%s); skipping.", kind, exc
            )
            return None
        if not isinstance(data, dict):
            if required:
                raise FusionError(f"{kind} artifact '{path}' is not a JSON object.")
            return None
        return data

    @staticmethod
    def _stem_for_output(video: str | Path | None, report_video: str) -> str:
        """Choose an output stem from the video arg or the highlight's video."""
        if video is not None:
            return Path(str(video)).stem
        if report_video:
            return Path(report_video).stem
        return "fused"

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

    @staticmethod
    def _clamp01(value: float) -> float:
        """Clamp a value into the 0..1 range."""
        if value < 0.0:
            return 0.0
        if value > 1.0:
            return 1.0
        return value
