"""Prompt templates for edit-plan generation."""
from __future__ import annotations

SYSTEM_PROMPT: str = (
    "You are a professional gaming video editor assistant. "
    "Given a description of gameplay footage, produce a clear, structured "
    "editing plan. Include suggested cuts, highlight moments, pacing, "
    "transitions, text overlays, and audio/music cues. "
    "Respond with a concise, well-organized plan. Do not include any "
    "internal reasoning or <think> tags in your answer."
)


def build_edit_plan_prompt(video_description: str) -> str:
    """Build the user prompt for a given gameplay description."""
    return (
        "Create a detailed editing plan for the following gameplay footage.\n\n"
        f"Gameplay description:\n{video_description.strip()}\n\n"
        "Structure the plan into clear sections."
    )
