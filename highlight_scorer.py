"""Phase 5A: generic Highlight Scoring Engine.

Consumes a Phase 4A ``analysis.json`` (schema ``4a.1``) and produces a
ranked ``highlight.json`` (schema ``5a.1``). It scores each detected scene
using **only** signals already available from Phase 4A:

    motion, brightness, static score, scene duration, and overlap with the
    idle / black-screen sections.

Hard boundaries for this module:
- **Generic and game-agnostic.** No kill/HUD/OCR/audio logic (Phases 5B+).
- **No Ollama, no FFmpeg, no video editing.** It only reads JSON and writes
  JSON.
- **No magic numbers.** Every weight and threshold lives in
  ``HighlightScoringConfig`` so scoring is fully tunable without code edits
  (Open/Closed Principle).

Scoring rationale (why each factor matters) is documented inline on the
relevant methods and in ``SCORING.md``.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from config import AppConfig, config
from logger import get_logger

logger = get_logger(__name__)

SCHEMA_VERSION = "5a.1"
INPUT_SCHEMA_VERSION = "4a.1"


class HighlightScorerError(RuntimeError):
    """Raised when scoring fails or the input analysis is invalid."""


@dataclass(frozen=True)
class HighlightScoringConfig:
    """Fully configurable weights and thresholds for highlight scoring.

    Nothing in the scoring logic is hardcoded; tuning happens here. All
    weights are applied to component sub-scores that are each normalized to
    the 0..1 range before weighting, so the weights are directly comparable.

    Priority (per project decision, motion-dominant):
        1. motion (highest positive weight)
        2. idle penalty
        3. black-screen penalty
        4. static penalty
        5. duration (small positive influence)
        6. brightness (lowest positive influence)
    """

    # --- Positive contribution weights (applied to 0..1 sub-scores) ---
    motion_weight: float = 1.0
    brightness_weight: float = 0.1
    duration_weight: float = 0.2

    # --- Penalty weights (subtracted, applied to 0..1 penalty ratios) ---
    idle_penalty_weight: float = 0.7
    black_penalty_weight: float = 0.9
    static_penalty_weight: float = 0.4

    # --- Normalization references (define what "1.0" means per signal) ---
    # Motion is a mean absolute frame difference (0..255). Real gameplay
    # rarely approaches 255; this reference maps "a lot of motion" -> 1.0.
    motion_reference: float = 40.0
    # Brightness is 0..255; mapped linearly to 0..1.
    brightness_reference: float = 255.0
    # A scene at/above this many seconds gets full duration credit.
    duration_reference_seconds: float = 8.0

    # --- Classification thresholds on the final 0..100 score ---
    excellent_threshold: float = 70.0
    good_threshold: float = 45.0
    average_threshold: float = 20.0
    # Scenes dominated by black frames are forced to "Ignore" regardless of
    # other signals (nothing watchable to keep).
    force_ignore_black_ratio: float = 0.6

    def validate(self) -> None:
        """Validate threshold ordering and reference sanity."""
        if not (
            self.excellent_threshold
            > self.good_threshold
            > self.average_threshold
            >= 0.0
        ):
            raise HighlightScorerError(
                "Classification thresholds must be strictly descending and "
                ">= 0 (excellent > good > average >= 0)."
            )
        for name, value in (
            ("motion_reference", self.motion_reference),
            ("brightness_reference", self.brightness_reference),
            ("duration_reference_seconds", self.duration_reference_seconds),
        ):
            if value <= 0:
                raise HighlightScorerError(f"{name} must be positive.")


@dataclass
class ScoreComponents:
    """Per-scene breakdown of how the final score was produced.

    Kept in the output for transparency and so Phase 5B/5C can see how much
    the generic signals contributed before new signals are added.
    """

    motion: float
    brightness: float
    duration: float
    idle_penalty: float
    black_penalty: float
    static_penalty: float


@dataclass
class SceneScore:
    """Scored, classified and rankable representation of one scene."""

    index: int
    start: float
    end: float
    duration: float
    score: float  # normalized 0..100
    classification: str
    rank: int = 0
    components: ScoreComponents | None = None


@dataclass
class HighlightReport:
    """Complete ranked highlight report, serializable to ``highlight.json``."""

    video: str
    scenes: list[SceneScore] = field(default_factory=list)
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        """Return a plain-dict representation ready for JSON serialization."""
        return {
            "schema_version": self.schema_version,
            "video": self.video,
            "scenes": [asdict(s) for s in self.scenes],
        }

    def to_json(self, indent: int = 2) -> str:
        """Return the report serialized as a JSON string."""
        return json.dumps(self.to_dict(), indent=indent)


class HighlightScorer:
    """Scores and ranks Phase 4A scenes into a highlight report."""

    def __init__(
        self,
        app_config: AppConfig | None = None,
        scoring_config: HighlightScoringConfig | None = None,
    ) -> None:
        """Create a scorer.

        Args:
            app_config: Shared application config (paths, etc.).
            scoring_config: Weights/thresholds. Defaults are motion-dominant.
        """
        self._config = app_config or config
        self._scoring = scoring_config or HighlightScoringConfig()
        self._scoring.validate()
        logger.info("Initialized HighlightScorer")

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def score_analysis(self, analysis: dict[str, Any]) -> HighlightReport:
        """Score an in-memory Phase 4A analysis dict and return a report."""
        self._validate_analysis(analysis)

        video = str(analysis.get("video", ""))
        scenes_in = analysis.get("scenes", [])
        idle_sections = analysis.get("idle_sections", [])
        black_screens = analysis.get("black_screens", [])

        scored = [
            self._score_scene(scene, idle_sections, black_screens)
            for scene in scenes_in
        ]
        ranked = self._rank(scored)

        report = HighlightReport(video=video, scenes=ranked)
        logger.info(
            "Scored %d scenes (excellent=%d, good=%d, average=%d, ignore=%d)",
            len(ranked),
            *self._class_counts(ranked),
        )
        return report

    def score_file(self, analysis_path: str | Path) -> HighlightReport:
        """Load an ``analysis.json`` file and return a highlight report."""
        path = self._validate_input_path(analysis_path)
        try:
            analysis = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.error("Failed to read analysis JSON %s: %s", path, exc)
            raise HighlightScorerError(
                f"Could not read analysis JSON '{path}': {exc}"
            ) from exc
        return self.score_analysis(analysis)

    def score_to_file(
        self, analysis_path: str | Path, output_name: str | None = None
    ) -> Path:
        """Score an ``analysis.json`` and write ``<video>_highlight.json``.

        Existing highlight files are never overwritten; a numeric suffix is
        added on collision (consistent with Phase 4A behaviour).
        """
        report = self.score_file(analysis_path)
        out_dir = self._config.paths.output_dir
        out_dir.mkdir(parents=True, exist_ok=True)

        stem = self._highlight_stem(analysis_path, report.video)
        base_name = output_name or f"{stem}_highlight.json"
        output = self._unique_path(out_dir, base_name)

        output.write_text(report.to_json(), encoding="utf-8")
        logger.info("Wrote highlight JSON -> %s", output)
        return output

    # ------------------------------------------------------------------ #
    # Scoring (component math is static and testable)
    # ------------------------------------------------------------------ #
    def _score_scene(
        self,
        scene: dict[str, Any],
        idle_sections: list[dict[str, Any]],
        black_screens: list[dict[str, Any]],
    ) -> SceneScore:
        """Score a single scene into a classified ``SceneScore``."""
        cfg = self._scoring
        start = float(scene.get("start", 0.0))
        end = float(scene.get("end", 0.0))
        duration = float(scene.get("duration", max(end - start, 0.0)))
        avg_motion = float(scene.get("avg_motion", 0.0))
        avg_brightness = float(scene.get("avg_brightness", 0.0))
        avg_static = float(scene.get("avg_static", 0.0))

        idle_ratio = self.overlap_ratio(start, end, idle_sections)
        black_ratio = self.overlap_ratio(start, end, black_screens)

        components = ScoreComponents(
            # Motion is the primary indicator of "something is happening":
            # gunfights, movement, action. Highest weight by design.
            motion=round(
                self.normalize(avg_motion, cfg.motion_reference)
                * cfg.motion_weight,
                4,
            ),
            # Brightness is a weak positive: very dark scenes are usually
            # menus/loading; well-lit scenes are marginally more watchable.
            brightness=round(
                self.normalize(avg_brightness, cfg.brightness_reference)
                * cfg.brightness_weight,
                4,
            ),
            # Longer scenes carry slightly more "content", but only up to a
            # reference length so long idle shots are not rewarded.
            duration=round(
                self.normalize(duration, cfg.duration_reference_seconds)
                * cfg.duration_weight,
                4,
            ),
            # Idle overlap means the player/camera was inactive: strong
            # negative signal for a highlight.
            idle_penalty=round(idle_ratio * cfg.idle_penalty_weight, 4),
            # Black screens are unwatchable (transitions/loading): strongest
            # penalty.
            black_penalty=round(black_ratio * cfg.black_penalty_weight, 4),
            # High static score = little changed frame-to-frame; correlates
            # with low action. Moderate penalty, complementary to motion.
            static_penalty=round(avg_static * cfg.static_penalty_weight, 4),
        )

        raw = (
            components.motion
            + components.brightness
            + components.duration
            - components.idle_penalty
            - components.black_penalty
            - components.static_penalty
        )
        score = self._to_0_100(raw)
        classification = self._classify(score, black_ratio)

        return SceneScore(
            index=int(scene.get("index", 0)),
            start=round(start, 3),
            end=round(end, 3),
            duration=round(duration, 3),
            score=round(score, 2),
            classification=classification,
            components=components,
        )

    @staticmethod
    def normalize(value: float, reference: float) -> float:
        """Map ``value`` onto 0..1 relative to ``reference`` (clamped)."""
        if reference <= 0:
            return 0.0
        return max(0.0, min(value / reference, 1.0))

    @staticmethod
    def overlap_ratio(
        start: float, end: float, spans: list[dict[str, Any]]
    ) -> float:
        """Return the fraction (0..1) of [start, end) covered by ``spans``.

        Used for both idle and black-screen overlap. Spans are the Phase 4A
        ``{start, end, duration}`` objects.
        """
        length = end - start
        if length <= 0:
            return 0.0

        covered = 0.0
        for span in spans:
            s = float(span.get("start", 0.0))
            e = float(span.get("end", 0.0))
            covered += max(0.0, min(end, e) - max(start, s))
        return max(0.0, min(covered / length, 1.0))

    def _to_0_100(self, raw: float) -> float:
        """Scale a raw weighted score into the 0..100 range.

        The theoretical maximum raw score is the sum of positive weights
        (all sub-scores at 1.0, no penalties). Dividing by that keeps the
        scale stable and configurable: change the weights and the 0..100
        mapping adjusts automatically, with no magic constants.
        """
        cfg = self._scoring
        max_positive = (
            cfg.motion_weight + cfg.brightness_weight + cfg.duration_weight
        )
        if max_positive <= 0:
            return 0.0
        normalized = raw / max_positive
        return max(0.0, min(normalized, 1.0)) * 100.0

    def _classify(self, score: float, black_ratio: float) -> str:
        """Classify a 0..100 score into a highlight bucket."""
        cfg = self._scoring
        if black_ratio >= cfg.force_ignore_black_ratio:
            return "Ignore"
        if score >= cfg.excellent_threshold:
            return "Excellent"
        if score >= cfg.good_threshold:
            return "Good"
        if score >= cfg.average_threshold:
            return "Average"
        return "Ignore"

    # ------------------------------------------------------------------ #
    # Ranking
    # ------------------------------------------------------------------ #
    @staticmethod
    def _rank(scenes: list[SceneScore]) -> list[SceneScore]:
        """Return scenes sorted by score desc, assigning 1-based ranks.

        Ties break by earlier start time for deterministic output.
        """
        ordered = sorted(scenes, key=lambda s: (-s.score, s.start))
        for position, scene in enumerate(ordered, start=1):
            scene.rank = position
        return ordered

    @staticmethod
    def _class_counts(scenes: list[SceneScore]) -> tuple[int, int, int, int]:
        """Return (excellent, good, average, ignore) counts."""
        counts = {"Excellent": 0, "Good": 0, "Average": 0, "Ignore": 0}
        for scene in scenes:
            counts[scene.classification] = counts.get(scene.classification, 0) + 1
        return (
            counts["Excellent"],
            counts["Good"],
            counts["Average"],
            counts["Ignore"],
        )

    # ------------------------------------------------------------------ #
    # Validation & helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _validate_analysis(analysis: dict[str, Any]) -> None:
        """Validate the minimal shape required from a Phase 4A analysis."""
        if not isinstance(analysis, dict):
            raise HighlightScorerError("Analysis must be a JSON object.")
        if "scenes" not in analysis or not isinstance(analysis["scenes"], list):
            raise HighlightScorerError(
                "Analysis is missing a 'scenes' list (expected schema "
                f"{INPUT_SCHEMA_VERSION})."
            )

    @staticmethod
    def _validate_input_path(analysis_path: str | Path) -> Path:
        """Validate that the analysis path exists and is a file."""
        path = Path(analysis_path).expanduser().resolve()
        if not path.exists():
            raise HighlightScorerError(f"Analysis file does not exist: {path}")
        if not path.is_file():
            raise HighlightScorerError(f"Analysis path is not a file: {path}")
        return path

    @staticmethod
    def _highlight_stem(analysis_path: str | Path, video: str) -> str:
        """Derive the output stem from the video name, falling back to file.

        Prefers the original video stem so the output is
        ``<video_name>_highlight.json``; if the analysis has no video path,
        derive from the analysis filename (stripping a trailing '_analysis').
        """
        if video:
            return Path(video).stem
        stem = Path(analysis_path).stem
        if stem.endswith("_analysis"):
            stem = stem[: -len("_analysis")]
        return stem

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
