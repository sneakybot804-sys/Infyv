"""Prompt templates for the Phase 5E AI decision pipeline.

The prompt is deliberately split into three separated sections so each can
evolve independently and be inspected/tested in isolation:

1. SYSTEM_PROMPT  -- the model's role and the strict output contract.
2. RULES          -- explicit, enumerated constraints on the decision.
3. Data payload   -- the candidate scenes serialized as JSON.

The model is asked to return **strict JSON only** matching the ``5e.1``
segment shape. The agent still validates the response and falls back
deterministically if the model deviates, so prompt compliance is a
best-effort optimization, never a correctness dependency.
"""
from __future__ import annotations

import json
from typing import Any

SYSTEM_PROMPT: str = (
    "You are a professional gaming video editor. You are given a list of "
    "candidate scenes already scored and ranked by an upstream pipeline. "
    "Your job is to choose which scenes become clips in a highlight reel and "
    "explain why, in one short reason each. "
    "Respond with STRICT JSON ONLY: a single object with a 'segments' array. "
    "Each segment must have exactly: 'source_scene_index' (int), 'start' "
    "(number, seconds), 'end' (number, seconds), 'reason' (string). "
    "Do not include markdown, code fences, commentary, or <think> tags."
)

RULES: tuple[str, ...] = (
    "Only select from the provided candidate scenes; never invent scenes.",
    "Use each scene's 'start' and 'end' as the clip bounds.",
    "'source_scene_index' must equal the candidate scene's 'index'.",
    "Prefer higher-scored scenes; keep the reel tight.",
    "Select at most the requested maximum number of segments.",
    "Keep each 'reason' to one short sentence grounded in the scene data "
    "(score, classification, OCR text or signals).",
    "Return an empty 'segments' array if no scene is worth keeping.",
)


def build_decision_prompt(
    candidates: list[dict[str, Any]],
    max_segments: int,
    metadata: dict[str, Any] | None = None,
) -> str:
    """Assemble the user prompt from the rules and the candidate payload.

    Args:
        candidates: Candidate scenes (already filtered/ranked) to offer the
            model. Each is a compact dict (index, start, end, score,
            classification, ocr, signals).
        max_segments: The maximum number of segments the model may return.
        metadata: Optional video metadata (duration/resolution) for context.

    Returns:
        The fully assembled user prompt string.
    """
    rules_block = "\n".join(f"{i}. {rule}" for i, rule in enumerate(RULES, start=1))
    payload = {
        "max_segments": max_segments,
        "metadata": metadata or {},
        "candidate_scenes": candidates,
    }
    data_block = json.dumps(payload, indent=2)
    return (
        "RULES:\n"
        f"{rules_block}\n\n"
        "DATA (candidate scenes and constraints):\n"
        f"{data_block}\n\n"
        "Return STRICT JSON only, matching the schema described in the "
        "system prompt."
    )
