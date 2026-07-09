"""Phase 5E: AI Decision Pipeline -- producer of ``edit_plan.json``.

A pure **consumer** that reads a Phase 5D ``enriched_highlight.json`` (schema
``5d.1``) and produces a lightweight ``edit_plan.json`` (schema ``5e.1``) for
the future Phase 6 renderer.

Hard boundaries (Phase 5E design):
- **Independent of ``agent.py``.** This module never imports the existing
  ``GamingEditorAgent`` or its error type. It defines its own error
  (``DecisionError``) and its own thin Ollama client behind a small
  :class:`LlmClient` Protocol so tests inject a fake (no network).
- **Pure consumer.** Reads the enriched artifact (and optional analysis for
  metadata) and writes ``edit_plan.json`` only. No producer import, no
  producer mutation.
- **LLM is best-effort.** The response is validated against ``5e.1``; any
  failure (unreachable, invalid JSON, schema violation) falls back to a
  deterministic, configurable selection. Plan generation never hard-fails on
  an LLM problem.
- **No magic numbers.** All selection/shaping tunables live in
  :class:`DecisionConfig`.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from config import AppConfig, config
from decision_config import DecisionConfig, DecisionError, FallbackStrategy
from logger import get_logger
from prompts.decision_plan import SYSTEM_PROMPT, build_decision_prompt

logger = get_logger(__name__)

SCHEMA_VERSION = "5e.1"
INPUT_SCHEMA_VERSION = "5d.1"

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


# --------------------------------------------------------------------- #
# LLM client abstraction (decision-specific; not coupled to agent.py)
# --------------------------------------------------------------------- #
@runtime_checkable
class LlmClient(Protocol):
    """Minimal text-in/text-out client the decision agent depends on."""

    def generate(self, system: str, prompt: str) -> str:
        """Return the model's raw text response for ``system`` + ``prompt``."""
        ...


class OllamaDecisionClient:
    """Thin, decision-specific Ollama client (own implementation).

    Mirrors the local ``/api/generate`` call pattern but is intentionally
    separate from ``agent.py`` so the decision pipeline carries no dependency
    on the existing agent. Failures raise :class:`DecisionError`, which the
    agent catches to trigger the deterministic fallback.
    """

    def __init__(
        self, app_config: AppConfig | None = None, temperature: float | None = None
    ) -> None:
        self._ollama = (app_config or config).ollama
        self._temperature = (
            temperature if temperature is not None else self._ollama.temperature
        )

    def generate(self, system: str, prompt: str) -> str:
        url = f"{self._ollama.host}/api/generate"
        payload: dict[str, Any] = {
            "model": self._ollama.model,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "options": {"temperature": self._temperature},
        }
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(
                request, timeout=self._ollama.request_timeout
            ) as response:
                body = response.read().decode("utf-8")
        except (urllib.error.URLError, TimeoutError) as exc:
            raise DecisionError(
                f"Could not reach Ollama at {self._ollama.host}: {exc}"
            ) from exc
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError as exc:
            raise DecisionError("Received invalid JSON envelope from Ollama.") from exc
        text = str(parsed.get("response", ""))
        if not text:
            raise DecisionError("Ollama returned an empty response.")
        return text


# --------------------------------------------------------------------- #
# Output dataclasses (schema 5e.1)
# --------------------------------------------------------------------- #
@dataclass
class EditSegment:
    """One clip in the edit plan."""

    id: str
    source_scene_index: int
    start: float
    end: float
    score: float
    reason: str


@dataclass
class EditPlan:
    """Complete edit plan, serializable to ``edit_plan.json`` (5e.1)."""

    source_video: str
    decision_source: str  # "llm" | "fallback"
    segments: list[EditSegment] = field(default_factory=list)
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "source_video": self.source_video,
            "decision_source": self.decision_source,
            "segments": [asdict(s) for s in self.segments],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


class DecisionAgent:
    """Turn an enriched highlight report into an ``edit_plan.json`` (5e.1)."""

    def __init__(
        self,
        app_config: AppConfig | None = None,
        decision_config: DecisionConfig | None = None,
        llm_client: LlmClient | None = None,
    ) -> None:
        """Create the agent.

        Args:
            app_config: Shared application config (paths, ollama).
            decision_config: Selection/shaping tunables and LLM controls.
            llm_client: Injectable text client. When None and ``use_llm`` is
                True, a thin :class:`OllamaDecisionClient` is built lazily.
                Injecting a fake keeps unit tests network-free.
        """
        self._config = app_config or config
        self._decision = decision_config or DecisionConfig()
        self._decision.validate()
        self._llm_client = llm_client
        logger.info(
            "Initialized DecisionAgent (use_llm=%s, fallback=%s)",
            self._decision.use_llm,
            self._decision.fallback_strategy.value,
        )

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def decide(
        self,
        enriched: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> EditPlan:
        """Produce an edit plan from an in-memory enriched report dict."""
        if not isinstance(enriched, dict) or "scenes" not in enriched:
            raise DecisionError(
                "enriched artifact is required and must contain 'scenes'."
            )

        video = str(enriched.get("video", ""))
        scenes = enriched.get("scenes", []) or []
        candidates = self._select_candidates(scenes)

        segments: list[EditSegment] | None = None
        decision_source = "fallback"

        if self._decision.use_llm:
            try:
                segments = self._llm_segments(candidates, video)
                decision_source = "llm"
            except (DecisionError, Exception) as exc:
                # Any LLM problem (unreachable client, invalid JSON, schema
                # violation, or an unexpected client error) is non-fatal:
                # fall back to the deterministic selection.
                logger.warning("LLM decision failed (%s); using fallback.", exc)
                segments = None

        if segments is None:
            segments = self._fallback_segments(candidates)
            decision_source = "fallback"

        segments = self._shape_segments(segments)
        plan = EditPlan(
            source_video=video,
            decision_source=decision_source,
            segments=segments,
        )
        self._validate_plan(plan, candidates)
        logger.info(
            "Decision plan: %d segment(s) via %s",
            len(plan.segments),
            plan.decision_source,
        )
        return plan

    def decide_files(
        self,
        video: str | Path | None = None,
        *,
        enriched_path: str | Path | None = None,
        analysis_path: str | Path | None = None,
    ) -> EditPlan:
        """Load the enriched artifact (auto-discovered or explicit) and decide."""
        e_path, a_path = self._resolve_paths(video, enriched_path, analysis_path)
        enriched = self._read_json(e_path, required=True, kind="enriched_highlight")
        analysis = self._read_json(a_path, required=False, kind="analysis")
        metadata = (analysis or {}).get("metadata") if analysis else None
        return self.decide(enriched, metadata)

    def decide_to_file(
        self,
        video: str | Path | None = None,
        *,
        enriched_path: str | Path | None = None,
        analysis_path: str | Path | None = None,
        output_name: str | None = None,
    ) -> Path:
        """Decide and write ``<stem>_edit_plan.json`` (never overwritten)."""
        plan = self.decide_files(
            video, enriched_path=enriched_path, analysis_path=analysis_path
        )
        out_dir = self._config.paths.output_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        stem = self._stem_for_output(video, plan.source_video)
        base_name = output_name or f"{stem}_edit_plan.json"
        output = self._unique_path(out_dir, base_name)
        output.write_text(json.dumps(plan.to_dict(), indent=2), encoding="utf-8")
        logger.info("Wrote edit plan -> %s", output)
        return output

    # ------------------------------------------------------------------ #
    # Candidate selection (config-driven; deterministic)
    # ------------------------------------------------------------------ #
    def _select_candidates(self, scenes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Filter+order scenes per the configured fallback strategy.

        The same candidate set is offered to the LLM and used by the
        deterministic fallback, so both operate on identical, reproducible
        inputs.
        """
        cfg = self._decision
        # Deterministic base order: score desc, then scene index asc.
        ordered = sorted(
            scenes,
            key=lambda s: (-float(s.get("score", 0.0)), int(s.get("index", 0))),
        )
        strategy = cfg.fallback_strategy
        if strategy == FallbackStrategy.TOP_N:
            selected = ordered[: cfg.top_n]
        elif strategy == FallbackStrategy.THRESHOLD:
            selected = [s for s in ordered if float(s.get("score", 0.0)) >= cfg.min_score]
        else:  # HYBRID
            thresholded = [
                s for s in ordered if float(s.get("score", 0.0)) >= cfg.min_score
            ]
            selected = thresholded[: cfg.top_n]
        return selected[: cfg.max_segments]

    @staticmethod
    def _candidate_payload(scenes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Compact, LLM-facing view of the candidate scenes."""
        payload: list[dict[str, Any]] = []
        for s in scenes:
            payload.append(
                {
                    "index": int(s.get("index", 0)),
                    "start": float(s.get("start", 0.0)),
                    "end": float(s.get("end", 0.0)),
                    "score": float(s.get("score", 0.0)),
                    "classification": s.get("classification", ""),
                    "ocr": list(s.get("ocr", []) or []),
                    "signals": s.get("signals", {}),
                }
            )
        return payload

    # ------------------------------------------------------------------ #
    # LLM path (validated; best-effort)
    # ------------------------------------------------------------------ #
    def _llm_segments(
        self, candidates: list[dict[str, Any]], video: str
    ) -> list[EditSegment]:
        """Query the LLM and parse+validate its response into segments."""
        client = self._resolve_client()
        prompt = build_decision_prompt(
            self._candidate_payload(candidates), self._decision.max_segments
        )
        raw = client.generate(SYSTEM_PROMPT, prompt)
        cleaned = _THINK_RE.sub("", raw).strip()
        obj = self._parse_json_object(cleaned)
        raw_segments = obj.get("segments")
        if not isinstance(raw_segments, list):
            raise DecisionError("LLM response has no 'segments' array.")

        valid_indices = {int(c["index"]) for c in self._candidate_payload(candidates)}
        by_index = {int(c["index"]): c for c in self._candidate_payload(candidates)}
        segments: list[EditSegment] = []
        for i, seg in enumerate(raw_segments, start=1):
            if not isinstance(seg, dict):
                raise DecisionError("LLM segment is not an object.")
            try:
                scene_index = int(seg["source_scene_index"])
                start = float(seg["start"])
                end = float(seg["end"])
            except (KeyError, TypeError, ValueError) as exc:
                raise DecisionError(f"LLM segment missing/invalid fields: {exc}") from exc
            if scene_index not in valid_indices:
                raise DecisionError(
                    f"LLM referenced unknown scene index {scene_index}."
                )
            if not end > start:
                raise DecisionError("LLM segment must have end > start.")
            reason = str(seg.get("reason", "")).strip() or "selected by model"
            segments.append(
                EditSegment(
                    id=f"segment-{i:04d}",
                    source_scene_index=scene_index,
                    start=round(start, 3),
                    end=round(end, 3),
                    score=float(by_index[scene_index].get("score", 0.0)),
                    reason=reason,
                )
            )
        return segments

    @staticmethod
    def _parse_json_object(text: str) -> dict[str, Any]:
        """Parse a JSON object from model text, tolerating surrounding prose."""
        try:
            obj = json.loads(text)
        except json.JSONDecodeError:
            # Best-effort: extract the first {...} block.
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if not match:
                raise DecisionError("LLM response contained no JSON object.")
            try:
                obj = json.loads(match.group(0))
            except json.JSONDecodeError as exc:
                raise DecisionError(f"LLM response is not valid JSON: {exc}") from exc
        if not isinstance(obj, dict):
            raise DecisionError("LLM response JSON is not an object.")
        return obj

    def _resolve_client(self) -> LlmClient:
        """Return the injected client or build the default Ollama client."""
        if self._llm_client is not None:
            return self._llm_client
        return OllamaDecisionClient(
            self._config, temperature=self._decision.temperature_override
        )

    # ------------------------------------------------------------------ #
    # Deterministic fallback
    # ------------------------------------------------------------------ #
    def _fallback_segments(
        self, candidates: list[dict[str, Any]]
    ) -> list[EditSegment]:
        """Build segments directly from the selected candidate scenes."""
        segments: list[EditSegment] = []
        for i, s in enumerate(candidates, start=1):
            start = float(s.get("start", 0.0))
            end = float(s.get("end", 0.0))
            if not end > start:
                continue
            score = float(s.get("score", 0.0))
            classification = str(s.get("classification", "")).strip()
            reason = (
                f"score {round(score, 1)}"
                + (f", {classification}" if classification else "")
            )
            segments.append(
                EditSegment(
                    id=f"segment-{i:04d}",
                    source_scene_index=int(s.get("index", 0)),
                    start=round(start, 3),
                    end=round(end, 3),
                    score=score,
                    reason=reason,
                )
            )
        return segments

    # ------------------------------------------------------------------ #
    # Segment shaping (padding + adjacency merge; config-driven)
    # ------------------------------------------------------------------ #
    def _shape_segments(self, segments: list[EditSegment]) -> list[EditSegment]:
        """Apply padding, optional adjacency merge, cap, and re-id.

        Ordering for shaping is chronological (by start) so adjacency is
        well defined; ids are reassigned after shaping for determinism.
        """
        cfg = self._decision
        if not segments:
            return []

        padded = []
        for seg in segments:
            start = max(seg.start - cfg.pre_roll_seconds, 0.0)
            end = seg.end + cfg.post_roll_seconds
            padded.append((start, end, seg))
        padded.sort(key=lambda t: (t[0], t[1]))

        merged: list[EditSegment] = []
        cur_start, cur_end, cur_seg = padded[0]
        for start, end, seg in padded[1:]:
            if cfg.merge_adjacent and start - cur_end <= cfg.merge_gap_seconds:
                # Merge: keep the higher-scored segment's provenance.
                cur_end = max(cur_end, end)
                if seg.score > cur_seg.score:
                    cur_seg = seg
            else:
                merged.append(self._segment_span(cur_seg, cur_start, cur_end))
                cur_start, cur_end, cur_seg = start, end, seg
        merged.append(self._segment_span(cur_seg, cur_start, cur_end))

        # Chronological order was only needed to detect adjacency for the
        # merge. Restore the selection order (score desc, tie-break by scene
        # index) so TOP_N / HYBRID output preserves descending score/rank.
        merged.sort(key=lambda s: (-s.score, s.source_scene_index))

        merged = merged[: cfg.max_segments]
        for i, seg in enumerate(merged, start=1):
            seg.id = f"segment-{i:04d}"
        return merged

    @staticmethod
    def _segment_span(seg: EditSegment, start: float, end: float) -> EditSegment:
        """Return a copy of ``seg`` with adjusted (rounded) bounds."""
        return EditSegment(
            id=seg.id,
            source_scene_index=seg.source_scene_index,
            start=round(start, 3),
            end=round(end, 3),
            score=seg.score,
            reason=seg.reason,
        )

    # ------------------------------------------------------------------ #
    # Validation before writing
    # ------------------------------------------------------------------ #
    def _validate_plan(
        self, plan: EditPlan, candidates: list[dict[str, Any]]
    ) -> None:
        """Validate the plan shape before it is returned/written."""
        if plan.schema_version != SCHEMA_VERSION:
            raise DecisionError("edit plan schema_version mismatch.")
        if plan.decision_source not in ("llm", "fallback"):
            raise DecisionError("decision_source must be 'llm' or 'fallback'.")
        valid_indices = {int(c.get("index", 0)) for c in candidates}
        seen_ids: set[str] = set()
        for seg in plan.segments:
            if seg.id in seen_ids:
                raise DecisionError(f"duplicate segment id '{seg.id}'.")
            seen_ids.add(seg.id)
            if not seg.end > seg.start:
                raise DecisionError("segment end must be > start.")
            if seg.source_scene_index not in valid_indices:
                raise DecisionError(
                    f"segment references unknown scene {seg.source_scene_index}."
                )
        if len(plan.segments) > self._decision.max_segments:
            raise DecisionError("plan exceeds max_segments.")

    # ------------------------------------------------------------------ #
    # Path resolution / IO helpers
    # ------------------------------------------------------------------ #
    def _resolve_paths(
        self,
        video: str | Path | None,
        enriched_path: str | Path | None,
        analysis_path: str | Path | None,
    ) -> tuple[Path, Path | None]:
        """Resolve artifact paths from explicit args or naming convention."""
        out_dir = self._config.paths.output_dir
        stem = Path(str(video)).stem if video is not None else None

        def discover(explicit: str | Path | None, suffix: str) -> Path | None:
            if explicit is not None:
                return Path(explicit).expanduser()
            if stem is None:
                return None
            return out_dir / f"{stem}_{suffix}.json"

        enriched = discover(enriched_path, "enriched_highlight")
        if enriched is None:
            raise DecisionError(
                "An enriched highlight artifact is required: provide "
                "'enriched_path' or a 'video' for auto-discovery."
            )
        analysis = discover(analysis_path, "analysis")
        return enriched, analysis

    def _read_json(
        self, path: Path | None, *, required: bool, kind: str
    ) -> dict[str, Any] | None:
        """Read a JSON artifact; required-missing is fatal, optional is None."""
        if path is None:
            if required:
                raise DecisionError(f"Required {kind} artifact path is missing.")
            return None
        if not path.is_file():
            if required:
                raise DecisionError(f"Required {kind} artifact not found: {path}")
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            if required:
                raise DecisionError(
                    f"Could not read {kind} artifact '{path}': {exc}"
                ) from exc
            return None
        if not isinstance(data, dict):
            if required:
                raise DecisionError(f"{kind} artifact '{path}' is not a JSON object.")
            return None
        return data

    @staticmethod
    def _stem_for_output(video: str | Path | None, source_video: str) -> str:
        """Choose an output stem from the video arg or the enriched video."""
        if video is not None:
            return Path(str(video)).stem
        if source_video:
            return Path(source_video).stem
        return "plan"

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
