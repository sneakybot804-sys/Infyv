"""Synchronous phase runner.

The runner builds a fresh :class:`~gui_core.commands.CommandContext` for a
single execution, runs the given stateless command, and returns its
:class:`~gui_core.commands.PhaseResult`. It deliberately stays synchronous:
threading is a front-end concern (the GUI runs the runner on a worker thread),
and cancellation is reserved for the future via the context's token.

No Qt symbol is imported here.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from gui_core.artifacts import ArtifactResolver
from gui_core.commands import (
    Command,
    CommandContext,
    PhaseResult,
    ProducerFactories,
)
from gui_core.events import EventBus
from gui_core.logs import CoreLogger


class PhaseRunner:
    """Runs a single stateless command and returns a structured result."""

    def __init__(
        self,
        bus: EventBus,
        logger: CoreLogger,
        artifacts: ArtifactResolver,
        producers: ProducerFactories,
        output_dir: Path,
    ) -> None:
        """Create a runner.

        Args:
            bus: Shared event bus for progress/artifact events.
            logger: Structured logger for run diagnostics.
            artifacts: Resolver used by commands to locate inputs/outputs.
            producers: Factory bundle used to construct backend producers.
            output_dir: Directory where producers write artifacts.
        """
        self._bus = bus
        self._logger = logger
        self._artifacts = artifacts
        self._producers = producers
        self._output_dir = output_dir

    def run(self, command: Command, video_path: Optional[Path]) -> PhaseResult:
        """Execute ``command`` for ``video_path`` and return its result.

        A new :class:`CommandContext` is constructed per call so the command
        remains stateless and safe for future queueing, retries and batch or
        distributed execution.
        """
        context = CommandContext(
            video_path=video_path,
            output_dir=self._output_dir,
            producers=self._producers,
            artifacts=self._artifacts,
            bus=self._bus,
            logger=self._logger,
        )
        return command.execute(context)
