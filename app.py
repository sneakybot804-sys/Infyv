"""Entry point for the Local AI Gaming Video Editor.

Phase 1 added the interactive edit-plan generator. Phase 4A adds a generic
video-analysis flow. The two are exposed through a small top-level menu; the
original edit-plan behaviour is unchanged.
"""
from __future__ import annotations

import sys

from agent import GamingEditorAgent, OllamaConnectionError
from config import config
from highlight_scorer import HighlightScorer, HighlightScorerError
from logger import get_logger
from video_analyzer import VideoAnalyzer, VideoAnalyzerError
from video_picker import VideoPicker, VideoPickerError

logger = get_logger(__name__)


def prompt_for_description() -> str:
    """Ask the user for a gameplay description."""
    print("=" * 60)
    print("  Local AI Gaming Video Editor - Edit Plan Generator")
    print("=" * 60)
    print("Describe your gameplay footage (e.g. clutch rounds, funny")
    print("moments, boss fight). Press Enter when done.\n")

    description = input("Gameplay description > ").strip()
    return description


def run_edit_plan() -> int:
    """Run the interactive edit-plan generation flow."""
    try:
        description = prompt_for_description()
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled.")
        return 130

    if not description:
        print("No description provided. Exiting.")
        return 1

    agent = GamingEditorAgent(config)

    try:
        plan = agent.generate_edit_plan(description)
    except ValueError as exc:
        logger.error("Invalid input: %s", exc)
        print(f"Input error: {exc}")
        return 1
    except OllamaConnectionError as exc:
        logger.error("Ollama error: %s", exc)
        print(f"\nFailed to generate edit plan: {exc}")
        return 2

    print("\n" + "=" * 60)
    print("  GENERATED EDIT PLAN")
    print("=" * 60 + "\n")
    print(plan)
    print()
    return 0


def run_analysis() -> int:
    """Run the Phase 4A generic video-analysis flow."""
    print("=" * 60)
    print("  Local AI Gaming Video Editor - Generic Video Analysis")
    print("=" * 60)

    try:
        video_path = VideoPicker(config).pick()
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled.")
        return 130
    except VideoPickerError as exc:
        print(f"No video selected: {exc}")
        return 1

    try:
        output = VideoAnalyzer(config).analyze_to_file(video_path)
    except VideoAnalyzerError as exc:
        logger.error("Analysis error: %s", exc)
        print(f"\nAnalysis failed: {exc}")
        return 2

    print(f"\nAnalysis written to: {output}")
    return 0


def run_scoring() -> int:
    """Run the Phase 5A highlight-scoring flow over an analysis.json."""
    print("=" * 60)
    print("  Local AI Gaming Video Editor - Highlight Scoring (Phase 5A)")
    print("=" * 60)

    try:
        analysis_path = input(
            "Path to an analysis.json (blank to cancel) > "
        ).strip()
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled.")
        return 130

    if not analysis_path:
        print("No analysis file provided.")
        return 1

    try:
        output = HighlightScorer(config).score_to_file(analysis_path)
    except HighlightScorerError as exc:
        logger.error("Scoring error: %s", exc)
        print(f"\nScoring failed: {exc}")
        return 2

    print(f"\nHighlights written to: {output}")
    return 0


def choose_action() -> str:
    """Prompt the user to pick a top-level action."""
    print("=" * 60)
    print("  Local AI Gaming Video Editor")
    print("=" * 60)
    print("  1. Generate edit plan (Ollama)")
    print("  2. Analyze video (Phase 4A, generic)")
    print("  3. Score highlights (Phase 5A)")
    print("  q. Quit")
    return input("Choose an option > ").strip().lower()


def run() -> int:
    """Show the top-level menu and dispatch to the chosen flow."""
    config.ensure_directories()

    try:
        choice = choose_action()
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled.")
        return 130

    if choice in {"1", "plan"}:
        return run_edit_plan()
    if choice in {"2", "analyze", "analysis"}:
        return run_analysis()
    if choice in {"3", "score", "highlights"}:
        return run_scoring()
    if choice in {"q", "quit", "exit"}:
        return 0

    print("Unknown option.")
    return 1


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()
