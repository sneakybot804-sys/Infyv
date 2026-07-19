"""Response parser for ai_core: raw AIResponse -> strongly typed results.

The UI never sees raw JSON. Each ``parse_*`` method validates shape and
value ranges and raises :class:`ResponseFormatError` with a clear message
on any violation (fail loud, mirroring gui_core validation conventions).

Model output is defensively extracted: fenced code blocks and leading
prose around a JSON object are tolerated, since even well-prompted models
occasionally wrap JSON in markdown.

No Qt symbol is imported here.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict

from ai_core.errors import ResponseFormatError
from ai_core.types import (
    AIResponse,
    EditPlan,
    EditPlanSegment,
    OCRResult,
    ScriptResult,
    SubtitleLine,
    SubtitleResult,
    TagsResult,
    ThumbnailPrompt,
    TitleResult,
    TranscriptResult,
    VisionResult,
)

_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)
_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


class ResponseParser:
    """Parses raw model text into the typed result objects."""

    # ------------------------------------------------------------------ #
    # JSON extraction
    # ------------------------------------------------------------------ #
    @staticmethod
    def _extract_json(text: str) -> Dict[str, Any]:
        """Extract and decode the first JSON object found in ``text``."""
        candidate = text.strip()
        fenced = _FENCE.search(candidate)
        if fenced:
            candidate = fenced.group(1).strip()
        if not candidate.startswith("{"):
            match = _JSON_BLOCK.search(candidate)
            if match is None:
                raise ResponseFormatError(
                    "Model output contains no JSON object."
                )
            candidate = match.group(0)
        try:
            data = json.loads(candidate)
        except ValueError as exc:
            raise ResponseFormatError(
                f"Model output is not valid JSON: {exc}"
            ) from exc
        if not isinstance(data, dict):
            raise ResponseFormatError("Model output JSON is not an object.")
        return data

    # ------------------------------------------------------------------ #
    # Typed parsers
    # ------------------------------------------------------------------ #
    def parse_edit_plan(self, response: AIResponse) -> EditPlan:
        """Parse and validate an edit plan."""
        data = self._extract_json(response.text)
        raw_segments = data.get("segments")
        if not isinstance(raw_segments, list):
            raise ResponseFormatError("Edit plan is missing 'segments'.")
        segments = []
        for i, raw in enumerate(raw_segments):
            try:
                start = float(raw["start"])
                end = float(raw["end"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ResponseFormatError(
                    f"Edit plan segment {i} has invalid start/end."
                ) from exc
            if start < 0 or end <= start:
                raise ResponseFormatError(
                    f"Edit plan segment {i} range is invalid "
                    f"({start} -> {end})."
                )
            segments.append(
                EditPlanSegment(
                    start=start,
                    end=end,
                    label=str(raw.get("label", "")),
                    reason=str(raw.get("reason", "")),
                )
            )
        return EditPlan(
            segments=tuple(segments),
            style=str(data.get("style", "")),
            notes=str(data.get("notes", "")),
        )

    def parse_subtitles(self, response: AIResponse) -> SubtitleResult:
        """Parse and validate subtitles."""
        data = self._extract_json(response.text)
        raw_lines = data.get("lines")
        if not isinstance(raw_lines, list):
            raise ResponseFormatError("Subtitles are missing 'lines'.")
        lines = []
        for i, raw in enumerate(raw_lines):
            try:
                start = float(raw["start"])
                end = float(raw["end"])
                text = str(raw["text"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ResponseFormatError(
                    f"Subtitle line {i} is malformed."
                ) from exc
            if start < 0 or end < start:
                raise ResponseFormatError(
                    f"Subtitle line {i} range is invalid."
                )
            lines.append(SubtitleLine(start=start, end=end, text=text))
        return SubtitleResult(
            lines=tuple(lines), language=str(data.get("language", ""))
        )

    def parse_vision(self, response: AIResponse) -> VisionResult:
        """Parse and validate a vision analysis."""
        data = self._extract_json(response.text)
        confidence = float(data.get("confidence", 0.0) or 0.0)
        confidence = max(0.0, min(1.0, confidence))
        labels = data.get("labels") or []
        if not isinstance(labels, list):
            raise ResponseFormatError("Vision 'labels' must be a list.")
        return VisionResult(
            description=str(data.get("description", "")),
            labels=tuple(str(label) for label in labels),
            confidence=confidence,
        )

    def parse_ocr(self, response: AIResponse) -> OCRResult:
        """Parse and validate OCR output."""
        data = self._extract_json(response.text)
        regions = data.get("regions") or []
        if not isinstance(regions, list):
            raise ResponseFormatError("OCR 'regions' must be a list.")
        return OCRResult(
            text=str(data.get("text", "")),
            regions=tuple(str(region) for region in regions),
        )

    def parse_script(self, response: AIResponse) -> ScriptResult:
        """Parse and validate a script."""
        data = self._extract_json(response.text)
        scenes = data.get("scenes") or []
        if not isinstance(scenes, list):
            raise ResponseFormatError("Script 'scenes' must be a list.")
        return ScriptResult(
            script=str(data.get("script", "")),
            scenes=tuple(str(scene) for scene in scenes),
        )

    def parse_titles(self, response: AIResponse) -> TitleResult:
        """Parse and validate title suggestions."""
        data = self._extract_json(response.text)
        titles = data.get("titles")
        if not isinstance(titles, list) or not titles:
            raise ResponseFormatError("Titles payload has no 'titles'.")
        return TitleResult(titles=tuple(str(title) for title in titles))

    def parse_tags(self, response: AIResponse) -> TagsResult:
        """Parse and validate tag suggestions."""
        data = self._extract_json(response.text)
        tags = data.get("tags")
        if not isinstance(tags, list) or not tags:
            raise ResponseFormatError("Tags payload has no 'tags'.")
        return TagsResult(tags=tuple(str(tag) for tag in tags))

    def parse_thumbnail_prompt(self, response: AIResponse) -> ThumbnailPrompt:
        """Parse and validate a thumbnail brief."""
        data = self._extract_json(response.text)
        prompt = str(data.get("prompt", ""))
        if not prompt:
            raise ResponseFormatError("Thumbnail brief has no 'prompt'.")
        return ThumbnailPrompt(
            prompt=prompt,
            negative_prompt=str(data.get("negative_prompt", "")),
            style=str(data.get("style", "")),
        )

    def parse_transcript(self, response: AIResponse) -> TranscriptResult:
        """Parse and validate a transcript (subtitle-shaped segments)."""
        subtitles = self.parse_subtitles(response)
        return TranscriptResult(
            text=" ".join(line.text for line in subtitles.lines),
            segments=subtitles.lines,
            language=subtitles.language,
        )
