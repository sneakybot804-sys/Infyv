"""Stateless command objects for phase execution.

Each command wraps exactly one frozen backend producer call. Commands are
**stateless**: they store no mutable execution state and are never shared
singletons. Everything a command needs is provided at execution time through
an immutable :class:`CommandContext`. This keeps future queueing, retries,
batch jobs and distributed execution simple, and leaves room for cancellation
without an architectural change.

Producer construction is injected via the context's ``producers`` factory set
so unit tests supply fakes and never require FFmpeg, Ollama or Tesseract.

No Qt symbol is imported here.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol

from gui_core.artifacts import ArtifactKind, ArtifactResolver
from gui_core.events import Event, EventBus
from gui_core.logs import CoreLogger


class CancellationToken:
    """A minimal, cooperative cancellation seam.

    Cancellation is **not implemented** in Phase 8A; this token always reports
    that cancellation has not been requested. It exists so commands and the
    runner can be written to check ``is_cancelled`` now, and a real
    implementation can be dropped in later with no signature change.
    """

    @property
    def is_cancelled(self) -> bool:
        """Return whether cancellation was requested (always ``False`` today)."""
        return False


class ProducerFactories(Protocol):
    """Factory bundle that builds the backend producers a command needs.

    The default implementation constructs the real producers bound to the
    shared app config. Tests provide a fake bundle so no heavy dependency is
    imported.
    """

    def analysis(self) -> Any: ...
    def highlight(self) -> Any: ...
    def ocr(self) -> Any: ...
    def audio(self) -> Any: ...
    def fusion(self) -> Any: ...
    def decision(self) -> Any: ...
    def render(self) -> Any: ...
    def subtitles(self) -> Any: ...


@dataclass(frozen=True)
class CommandContext:
    """Immutable execution context passed to every command.

    Attributes:
        video_path: The selected source video (may be ``None`` for commands
            that operate on a prior artifact, e.g. highlight scoring).
        output_dir: Directory where producers write artifacts.
        producers: Factory bundle used to construct backend producers.
        artifacts: Resolver used to locate produced/derived artifacts.
        bus: Event bus for publishing progress/artifact events.
        logger: Structured logger for this execution.
        cancellation: Cooperative cancellation token (reserved for future use).
        clock: Injectable time source for deterministic duration measurement.
    """

    video_path: Optional[Path]
    output_dir: Path
    producers: ProducerFactories
    artifacts: ArtifactResolver
    bus: EventBus
    logger: CoreLogger
    cancellation: CancellationToken = field(default_factory=CancellationToken)
    clock: Callable[[], float] = time.time


@dataclass(frozen=True)
class PhaseResult:
    """Immutable outcome of running a command.

    Attributes:
        phase_id: The phase that ran.
        success: Whether the producer completed without error.
        outputs: Paths of artifacts produced (possibly empty).
        message: Human-readable summary or error message.
        duration_seconds: Wall-clock execution time.
    """

    phase_id: str
    success: bool
    outputs: List[Path] = field(default_factory=list)
    message: str = ""
    duration_seconds: float = 0.0


class Command(Protocol):
    """Protocol every phase command implements.

    Implementations must be stateless: ``execute`` derives everything from the
    provided :class:`CommandContext` and returns a :class:`PhaseResult`.
    """

    #: The phase id this command runs.
    phase_id: str
    #: Human-readable command name (useful for future history/macros).
    name: str

    def execute(self, context: CommandContext) -> PhaseResult:
        """Run the wrapped producer and return a structured result."""
        ...


def _require_video(context: CommandContext) -> Path:
    """Return the context video path or raise a clear error if unset."""
    if context.video_path is None:
        raise ValueError("This phase requires a selected video.")
    return context.video_path


class _BaseCommand:
    """Shared execution scaffold: timing, events, and error normalization.

    Subclasses implement :meth:`_run` to invoke exactly one producer method
    and return the produced output paths. This base publishes PhaseStarted /
    PhaseCompleted (and ArtifactCreated per output), measures duration, and
    converts any producer error into a failed :class:`PhaseResult` so backend
    error types never cross the facade boundary.
    """

    phase_id: str = ""
    name: str = ""

    def _run(self, context: CommandContext) -> List[Path]:
        raise NotImplementedError

    def execute(self, context: CommandContext) -> PhaseResult:
        """Execute the command, emitting events and normalizing errors."""
        start = context.clock()
        context.bus.publish(Event.PhaseStarted, {"phase_id": self.phase_id})
        context.logger.info(f"Phase '{self.phase_id}' started", phase=self.phase_id)
        try:
            outputs = self._run(context)
        except Exception as exc:  # normalize any producer error type
            duration = context.clock() - start
            context.logger.error(
                f"Phase '{self.phase_id}' failed: {exc}", phase=self.phase_id
            )
            result = PhaseResult(
                phase_id=self.phase_id,
                success=False,
                outputs=[],
                message=str(exc),
                duration_seconds=duration,
            )
            context.bus.publish(
                Event.PhaseCompleted,
                {"phase_id": self.phase_id, "success": False, "message": str(exc)},
            )
            return result

        duration = context.clock() - start
        for output in outputs:
            context.bus.publish(
                Event.ArtifactCreated,
                {"phase_id": self.phase_id, "path": str(output)},
            )
        context.logger.info(
            f"Phase '{self.phase_id}' completed",
            phase=self.phase_id,
            artifact=str(outputs[0]) if outputs else None,
        )
        context.bus.publish(
            Event.PhaseCompleted, {"phase_id": self.phase_id, "success": True}
        )
        return PhaseResult(
            phase_id=self.phase_id,
            success=True,
            outputs=list(outputs),
            message="ok",
            duration_seconds=duration,
        )


class RunAnalysisCommand(_BaseCommand):
    """Run Phase 4A video analysis on the selected video."""

    phase_id = "analysis"
    name = "Run Analysis"

    def _run(self, context: CommandContext) -> List[Path]:
        video = _require_video(context)
        output = context.producers.analysis().analyze_to_file(video)
        return [Path(output)]


class RunHighlightCommand(_BaseCommand):
    """Run Phase 5A highlight scoring on the video's analysis.json."""

    phase_id = "highlight"
    name = "Run Highlight Scoring"

    def _run(self, context: CommandContext) -> List[Path]:
        video = _require_video(context)
        analysis = context.artifacts.expected_path(video.stem, ArtifactKind.ANALYSIS)
        output = context.producers.highlight().score_to_file(analysis)
        return [Path(output)]


class RunOCRCommand(_BaseCommand):
    """Run Phase 5B HUD text extraction (OCR) on the selected video."""

    phase_id = "ocr"
    name = "Run OCR"

    def _run(self, context: CommandContext) -> List[Path]:
        video = _require_video(context)
        analysis = context.artifacts.find(video.stem, ArtifactKind.ANALYSIS)
        output = context.producers.ocr().extract_to_file(video, analysis_path=analysis)
        return [Path(output)]


class RunAudioCommand(_BaseCommand):
    """Run Phase 5C audio analysis on the selected video."""

    phase_id = "audio"
    name = "Run Audio Analysis"

    def _run(self, context: CommandContext) -> List[Path]:
        video = _require_video(context)
        analysis = context.artifacts.find(video.stem, ArtifactKind.ANALYSIS)
        output = context.producers.audio().analyze_to_file(
            video, analysis_path=analysis
        )
        return [Path(output)]


class RunFusionCommand(_BaseCommand):
    """Run Phase 5D signal fusion on the selected video's artifacts."""

    phase_id = "fusion"
    name = "Run Signal Fusion"

    def _run(self, context: CommandContext) -> List[Path]:
        video = _require_video(context)
        output = context.producers.fusion().fuse_to_file(video)
        return [Path(output)]


class RunDecisionCommand(_BaseCommand):
    """Run Phase 5E AI decision on the selected video's enriched artifact."""

    phase_id = "decision"
    name = "Run AI Decision"

    def _run(self, context: CommandContext) -> List[Path]:
        video = _require_video(context)
        output = context.producers.decision().decide_to_file(video)
        return [Path(output)]


class RunRenderCommand(_BaseCommand):
    """Run Phase 6 rendering of the selected video's edit plan."""

    phase_id = "render"
    name = "Run Render"

    def _run(self, context: CommandContext) -> List[Path]:
        video = _require_video(context)
        output = context.producers.render().render_files(video)
        outputs = [Path(output)]
        # A render is also announced via RenderFinished for future consumers.
        context.bus.publish(
            Event.RenderFinished,
            {"phase_id": self.phase_id, "path": str(outputs[0])},
        )
        return outputs


class RunSubtitleCommand(_BaseCommand):
    """Run Phase 7 subtitle generation on the selected video."""

    phase_id = "subtitles"
    name = "Run Subtitles"

    def _run(self, context: CommandContext) -> List[Path]:
        video = _require_video(context)
        outputs = context.producers.subtitles().transcribe_to_file(video)
        # transcribe_to_file returns an iterable of paths (json and/or srt).
        return [Path(p) for p in outputs]
