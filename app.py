"""Entry point for the Local AI Gaming Video Editor.

Phase 1 added the interactive edit-plan generator. Phase 4A adds a generic
video-analysis flow, Phase 5A highlight scoring, and Phase 5C audio analysis.
All are exposed through a small top-level menu; the original edit-plan
behaviour is unchanged.
"""
from __future__ import annotations

import sys
from pathlib import Path

from agent import GamingEditorAgent, OllamaConnectionError
from audio_analyzer import AudioAnalyzer
from audio_config import AudioAnalyzerError
from config import config
from highlight_scorer import HighlightScorer, HighlightScorerError
from hud_text_extractor import HudTextExtractor
from logger import get_logger
from ocr_config import OcrError
from decision_agent import DecisionAgent
from decision_config import DecisionError
from editor_config import EditorError
from signal_fusion import SignalFusionEngine
from signal_fusion_config import FusionError
from video_analyzer import VideoAnalyzer, VideoAnalyzerError
from video_editor import VideoEditor
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


def run_audio_analysis() -> int:
    """Run the Phase 5C audio-analysis flow over a selected video.

    Picks a video with the existing picker, automatically uses the matching
    ``output/<video>_analysis.json`` when it exists (the analyzer treats it
    as an optional scene prior), and writes ``output/<video>_audio.json``.
    """
    print("=" * 60)
    print("  Local AI Gaming Video Editor - Audio Analysis (Phase 5C)")
    print("=" * 60)

    try:
        video_path = VideoPicker(config).pick()
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled.")
        return 130
    except VideoPickerError as exc:
        print(f"No video selected: {exc}")
        return 1

    # Auto-detect the matching Phase 4A analysis.json, if present.
    analysis_candidate = (
        config.paths.output_dir / f"{Path(video_path).stem}_analysis.json"
    )
    analysis_path = analysis_candidate if analysis_candidate.is_file() else None
    if analysis_path is not None:
        print(f"Using analysis for scene mapping: {analysis_path}")
    else:
        print("No matching analysis.json found; scene_index will be null.")

    try:
        output = AudioAnalyzer(config).analyze_to_file(
            video_path, analysis_path=analysis_path
        )
    except AudioAnalyzerError as exc:
        logger.error("Audio analysis error: %s", exc)
        print(f"\nAudio analysis failed: {exc}")
        return 2

    print(f"\nAudio analysis written to: {output}")
    return 0


def run_ocr() -> int:
    """Run the Phase 5B HUD text extraction (OCR) flow over a video.

    Picks a video, automatically uses the matching
    ``output/<video>_analysis.json`` when it exists (optional scene prior),
    and writes ``output/<video>_ocr.json``. OCR runs only on configured
    static ROIs of sampled frames.
    """
    print("=" * 60)
    print("  Local AI Gaming Video Editor - HUD Text Extraction (Phase 5B)")
    print("=" * 60)

    try:
        video_path = VideoPicker(config).pick()
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled.")
        return 130
    except VideoPickerError as exc:
        print(f"No video selected: {exc}")
        return 1

    analysis_candidate = (
        config.paths.output_dir / f"{Path(video_path).stem}_analysis.json"
    )
    analysis_path = analysis_candidate if analysis_candidate.is_file() else None
    if analysis_path is not None:
        print(f"Using analysis for scene mapping: {analysis_path}")
    else:
        print("No matching analysis.json found; scene_index will be null.")

    try:
        output = HudTextExtractor(config).extract_to_file(
            video_path, analysis_path=analysis_path
        )
    except OcrError as exc:
        logger.error("OCR error: %s", exc)
        print(f"\nOCR failed: {exc}")
        return 2

    print(f"\nOCR written to: {output}")
    return 0


def run_fusion() -> int:
    """Run the Phase 5D signal-fusion flow over a video's artifacts.

    Picks a video, auto-discovers the matching
    ``output/<video>_highlight.json`` (required) plus optional
    ``_ocr.json`` / ``_audio.json``, and writes
    ``output/<video>_enriched_highlight.json``. Missing OCR/audio artifacts
    never fail fusion; a missing highlight artifact does.
    """
    print("=" * 60)
    print("  Local AI Gaming Video Editor - Signal Fusion (Phase 5D)")
    print("=" * 60)

    try:
        video_path = VideoPicker(config).pick()
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled.")
        return 130
    except VideoPickerError as exc:
        print(f"No video selected: {exc}")
        return 1

    stem = Path(video_path).stem
    out_dir = config.paths.output_dir
    for kind in ("ocr", "audio"):
        candidate = out_dir / f"{stem}_{kind}.json"
        if candidate.is_file():
            print(f"Using {kind} artifact: {candidate}")
        else:
            print(f"No matching {kind}.json found; that signal contributes 0.")

    try:
        output = SignalFusionEngine(config).fuse_to_file(video_path)
    except FusionError as exc:
        logger.error("Fusion error: %s", exc)
        print(f"\nFusion failed: {exc}")
        return 2

    print(f"\nEnriched highlights written to: {output}")
    return 0


def run_decision() -> int:
    """Run the Phase 5E AI decision flow over a video's enriched artifact.

    Picks a video, auto-discovers the matching
    ``output/<video>_enriched_highlight.json`` (required) plus optional
    ``_analysis.json`` (for metadata), and writes
    ``output/<video>_edit_plan.json``. When the LLM is unavailable or returns
    an invalid plan, a deterministic fallback selection is used instead.
    """
    print("=" * 60)
    print("  Local AI Gaming Video Editor - AI Decision (Phase 5E)")
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
        output = DecisionAgent(config).decide_to_file(video_path)
    except DecisionError as exc:
        logger.error("Decision error: %s", exc)
        print(f"\nDecision failed: {exc}")
        return 2

    print(f"\nEdit plan written to: {output}")
    return 0


def run_render() -> int:
    """Run the Phase 6 render flow over a video's edit plan.

    Picks a video, auto-discovers the matching
    ``output/<video>_edit_plan.json``, trims the planned segments and
    concatenates them into ``output/<video>_reel.mp4``.
    """
    print("=" * 60)
    print("  Local AI Gaming Video Editor - Render Highlights (Phase 6)")
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
        output = VideoEditor(config).render_files(video_path)
    except EditorError as exc:
        logger.error("Render error: %s", exc)
        print(f"\nRender failed: {exc}")
        return 2

    print(f"\nHighlight reel written to: {output}")
    return 0


def choose_action() -> str:
    """Prompt the user to pick a top-level action."""
    print("=" * 60)
    print("  Local AI Gaming Video Editor")
    print("=" * 60)
    print("  1. Generate edit plan (Ollama)")
    print("  2. Analyze video (Phase 4A, generic)")
    print("  3. Score highlights (Phase 5A)")
    print("  4. Analyze audio (Phase 5C)")
    print("  5. Extract HUD text / OCR (Phase 5B)")
    print("  6. Fuse signals (Phase 5D)")
    print("  7. Generate edit plan from highlights (Phase 5E)")
    print("  8. Render highlight reel (Phase 6)")
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
    if choice in {"4", "audio"}:
        return run_audio_analysis()
    if choice in {"5", "ocr", "text"}:
        return run_ocr()
    if choice in {"6", "fuse", "fusion"}:
        return run_fusion()
    if choice in {"7", "decide", "plan", "decision"}:
        return run_decision()
    if choice in {"8", "render", "reel", "edit"}:
        return run_render()
    if choice in {"q", "quit", "exit"}:
        return 0

    print("Unknown option.")
    return 1


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()
