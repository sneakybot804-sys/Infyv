"""Entry point for the Local AI Gaming Video Editor.

Provides a CLI menu for all pipeline phases plus AI provider management.
The active AI provider is selected via option 12 (AI Settings).
"""
from __future__ import annotations

import sys
from pathlib import Path

from agent import GamingEditorAgent, OllamaConnectionError
from ai_provider_factory import AiProviderClient, ProviderFactoryError, build_ai_client
from audio_analyzer import AudioAnalyzer
from audio_config import AudioAnalyzerError
from config import AiSettings, config
from highlight_scorer import HighlightScorer, HighlightScorerError
from hud_text_extractor import HudTextExtractor
from logger import get_logger
from ocr_config import OcrError
from decision_agent import DecisionAgent
from decision_config import DecisionError
from editor_config import EditorError
from subtitle_config import SubtitleError
from subtitle_engine import SubtitleEngine
from signal_fusion import SignalFusionEngine
from signal_fusion_config import FusionError
from video_analyzer import VideoAnalyzer, VideoAnalyzerError
from video_editor import VideoEditor
from video_picker import VideoPicker, VideoPickerError

logger = get_logger(__name__)

_ai_client: AiProviderClient | None = None
_ai_settings: AiSettings = AiSettings()


def _get_client() -> AiProviderClient:
    global _ai_client
    if _ai_client is None:
        _ai_client = build_ai_client(_ai_settings)
    return _ai_client


def _invalidate_client() -> None:
    global _ai_client
    _ai_client = None


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

    try:
        client = _get_client()
    except ProviderFactoryError as exc:
        print(f"Provider error: {exc}")
        return 2

    agent = GamingEditorAgent(client)

    try:
        plan = agent.generate_edit_plan(description)
    except ValueError as exc:
        logger.error("Invalid input: %s", exc)
        print(f"Input error: {exc}")
        return 1
    except OllamaConnectionError as exc:
        logger.error("Provider error: %s", exc)
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
    """Run the Phase 5C audio-analysis flow over a selected video."""
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
    """Run the Phase 5B HUD text extraction (OCR) flow over a video."""
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
    """Run the Phase 5D signal-fusion flow over a video's artifacts."""
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
    """Run the Phase 5E AI decision flow over a video's enriched artifact."""
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
        output = DecisionAgent().decide_to_file(video_path)
    except DecisionError as exc:
        logger.error("Decision error: %s", exc)
        print(f"\nDecision failed: {exc}")
        return 2

    print(f"\nEdit plan written to: {output}")
    return 0


def run_render() -> int:
    """Run the Phase 6 render flow over a video's edit plan."""
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


def run_subtitles() -> int:
    """Run the Phase 7 subtitle flow over the original source video."""
    print("=" * 60)
    print("  Local AI Gaming Video Editor - Subtitles (Phase 7)")
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
        outputs = SubtitleEngine(config).transcribe_to_file(video_path)
    except SubtitleError as exc:
        logger.error("Subtitle error: %s", exc)
        print(f"\nSubtitle generation failed: {exc}")
        return 2

    for path in outputs:
        print(f"Subtitle artifact written to: {path}")
    return 0


# ------------------------------------------------------------------ #
# AI Settings management
# ------------------------------------------------------------------ #
def run_ai_settings() -> int:
    """Interactive AI settings menu."""
    global _ai_settings

    while True:
        print("=" * 60)
        print("  AI Settings")
        print("=" * 60)
        print(f"  Current Provider: {_ai_settings.provider}")
        print(f"  Model: {_get_model()}")
        print("=" * 60)
        print("  1. Switch Provider")
        print("  2. Configure Ollama")
        print("  3. Configure OpenAI")
        print("  4. Health Check")
        print("  5. Show Current Settings")
        print("  b. Back")

        try:
            choice = input("Choose an option > ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print("\nCancelled.")
            return 130

        if choice in {"b", "back"}:
            return 0
        if choice == "1":
            _switch_provider()
        elif choice == "2":
            _configure_ollama()
        elif choice == "3":
            _configure_openai()
        elif choice == "4":
            _run_health_check()
        elif choice == "5":
            _show_settings()
        else:
            print("Unknown option.")


def _get_model() -> str:
    if _ai_settings.provider == "ollama":
        return _ai_settings.ollama_model
    return _ai_settings.openai_model


def _switch_provider() -> None:
    global _ai_settings
    print("\nAvailable Providers:")
    for i, p in enumerate(_ai_settings.available_providers, start=1):
        marker = " (current)" if p == _ai_settings.provider else ""
        print(f"  {i}. {p}{marker}")

    try:
        choice = input("Select provider > ").strip()
    except (KeyboardInterrupt, EOFError):
        return

    providers = _ai_settings.available_providers
    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(providers):
            new_provider = providers[idx]
        else:
            print("Invalid selection.")
            return
    elif choice.lower() in providers:
        new_provider = choice.lower()
    else:
        print(f"Unknown provider: {choice}")
        return

    if new_provider != _ai_settings.provider:
        _ai_settings.provider = new_provider
        _invalidate_client()
        print(f"Provider changed to: {_ai_settings.provider}")


def _configure_ollama() -> None:
    global _ai_settings
    print("\nOllama Settings")
    print(f"  Host: {_ai_settings.ollama_host}")
    print(f"  Model: {_ai_settings.ollama_model}")
    print()

    try:
        host = input(
            f"Host [{_ai_settings.ollama_host}] > "
        ).strip()
    except (KeyboardInterrupt, EOFError):
        return
    if host:
        _ai_settings.ollama_host = host
        _invalidate_client()

    try:
        model = input(
            f"Model [{_ai_settings.ollama_model}] > "
        ).strip()
    except (KeyboardInterrupt, EOFError):
        return
    if model:
        _ai_settings.ollama_model = model
        _invalidate_client()

    print("Ollama settings updated.")


def _configure_openai() -> None:
    global _ai_settings
    print("\nOpenAI Settings")
    masked = "********" if _ai_settings.openai_api_key else "(not set)"
    print(f"  API Key: {masked}")
    print(f"  Model: {_ai_settings.openai_model}")
    print(f"  Available models: {', '.join(_ai_settings.openai_models)}")
    print()

    try:
        api_key = input(
            "API Key (blank to keep current) > "
        ).strip()
    except (KeyboardInterrupt, EOFError):
        return
    if api_key:
        _ai_settings.openai_api_key = api_key
        _invalidate_client()

    try:
        model = input(
            f"Model [{_ai_settings.openai_model}] > "
        ).strip()
    except (KeyboardInterrupt, EOFError):
        return
    if model:
        _ai_settings.openai_model = model
        _invalidate_client()

    print("OpenAI settings updated.")


def _run_health_check() -> None:
    print(f"\nChecking {_ai_settings.provider} connectivity...")
    try:
        client = build_ai_client(_ai_settings)
        if client.health_check():
            print(f"[OK] {_ai_settings.provider} is reachable.")
        else:
            print(f"[FAIL] {_ai_settings.provider} health check failed.")
    except ProviderFactoryError as exc:
        print(f"[FAIL] {exc}")
    except Exception as exc:
        print(f"[FAIL] Connection error: {exc}")


def _show_settings() -> None:
    print("\nCurrent AI Settings:")
    print(f"  Provider: {_ai_settings.provider}")
    if _ai_settings.provider == "ollama":
        print(f"  Host: {_ai_settings.ollama_host}")
        print(f"  Model: {_ai_settings.ollama_model}")
    else:
        masked = "********" if _ai_settings.openai_api_key else "(not set)"
        print(f"  API Key: {masked}")
        print(f"  Model: {_ai_settings.openai_model}")
    print(f"  Temperature: {_ai_settings.temperature}")
    print(f"  Timeout: {_ai_settings.request_timeout}s")
    print()


# ------------------------------------------------------------------ #
# Main menu
# ------------------------------------------------------------------ #
def choose_action() -> str:
    """Prompt the user to pick a top-level action."""
    print("=" * 60)
    print("  Local AI Gaming Video Editor")
    print("=" * 60)
    print(f"  AI Provider: {_ai_settings.provider}")
    print("=" * 60)
    print("  1. Generate edit plan (AI)")
    print("  2. Analyze video (Phase 4A, generic)")
    print("  3. Score highlights (Phase 5A)")
    print("  4. Analyze audio (Phase 5C)")
    print("  5. Extract HUD text / OCR (Phase 5B)")
    print("  6. Fuse signals (Phase 5D)")
    print("  7. Generate edit plan from highlights (Phase 5E)")
    print("  8. Render highlight reel (Phase 6)")
    print("  9. Generate subtitles (Phase 7)")
    print(" 12. AI Settings")
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
    if choice in {"7", "decide", "decision"}:
        return run_decision()
    if choice in {"8", "render", "reel", "edit"}:
        return run_render()
    if choice in {"9", "subtitles", "subs", "captions"}:
        return run_subtitles()
    if choice in {"12", "ai", "settings"}:
        return run_ai_settings()
    if choice in {"q", "quit", "exit"}:
        return 0

    print("Unknown option.")
    return 1


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()
