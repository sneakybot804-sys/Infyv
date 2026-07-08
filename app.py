"""Entry point for the Local AI Gaming Video Editor (Phase 1)."""
from __future__ import annotations

import sys

from agent import GamingEditorAgent, OllamaConnectionError
from config import config
from logger import get_logger

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


def run() -> int:
    """Run the interactive edit-plan generation flow."""
    config.ensure_directories()

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


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()
