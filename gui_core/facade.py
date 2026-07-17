"""ApplicationFacade: the single public entry point to gui_core.

The facade is intentionally **thin**. It owns and wires the core services
(event bus, logger, plugin registry, pipeline, artifact resolver, state store,
phase runner) and exposes only high-level, orchestration-level methods. It
contains no business logic: every method delegates to a dedicated service.

All front ends (the PySide6 GUI, a future AI assistant, a REST API, a plugin
host, the CLI) talk to this class and nothing else in the package.

No Qt symbol is imported here.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, List, Optional

from gui_core.artifacts import ArtifactInfo, ArtifactResolver
from gui_core.commands import Command, PhaseResult
from gui_core.errors import PhaseGatedError, ProjectNotLoadedError, UnknownPhaseError
from gui_core.events import Event, EventBus, EventHandler, EventPriority
from gui_core.logs import CoreLogger, LogLevel, LogRecord, filter_records
from gui_core.pipeline import Pipeline
from gui_core.producers import DefaultProducerFactories
from gui_core.registry import PhasePlugin, PluginRegistry, register_builtins
from gui_core.runner import PhaseRunner
from gui_core.state import ProjectState, StateStore
from gui_core.timeline import Timeline


class ApplicationFacade:
    """Thin orchestration layer over the gui_core services."""

    def __init__(
        self,
        app_config: Any,
        *,
        producers: Optional[Any] = None,
        registry: Optional[PluginRegistry] = None,
        frame_service: Optional[Any] = None,
    ) -> None:
        """Build and wire the core services by composition.

        Args:
            app_config: The shared application config (paths, ollama, etc.).
            producers: Optional producer factory bundle. Defaults to the real
                backend producers; tests inject a fake bundle.
            registry: Optional pre-populated registry. When omitted, a fresh
                registry is created and the built-in phases self-register.
        """
        self._config = app_config
        self._bus = EventBus()
        self._logger = CoreLogger("facade", self._bus)
        # Decoding/metadata service. Reuses the existing FFmpegService; built
        # lazily on first use so importing gui_core never imports ffmpeg/numpy
        # and tests can inject a fake via `frame_service`.
        self._frame_service = frame_service

        self._registry = registry or PluginRegistry()
        if registry is None:
            register_builtins(self._registry)

        output_dir = app_config.paths.output_dir
        self._artifacts = ArtifactResolver(output_dir)
        self._pipeline = Pipeline(self._registry)
        self._store = StateStore(self._bus, self._artifacts)
        self._producers = producers or DefaultProducerFactories(app_config)
        self._runner = PhaseRunner(
            bus=self._bus,
            logger=self._logger,
            artifacts=self._artifacts,
            producers=self._producers,
            output_dir=output_dir,
        )

    # ------------------------------------------------------------------ #
    # Project / selection (delegates to StateStore)
    # ------------------------------------------------------------------ #
    def open_project(self, path: str | Path) -> ProjectState:
        """Open a project/workspace rooted at ``path``."""
        return self._store.load_project(Path(path))

    def select_video(self, path: str | Path) -> ProjectState:
        """Select the active source video and refresh discovered artifacts."""
        return self._store.select_video(Path(path))

    def project_state(self) -> ProjectState:
        """Return the current immutable :class:`ProjectState` snapshot."""
        return self._store.state

    def timeline(self) -> Optional[Timeline]:
        """Return the current immutable timeline, or ``None`` if unset."""
        return self._store.state.timeline

    def update_timeline(self, timeline: Timeline) -> ProjectState:
        """Replace the timeline and publish ``TimelineChanged``."""
        return self._store.update_timeline(timeline)

    # ------------------------------------------------------------------ #
    # Decoding / preview frames (reuses the existing FFmpegService)
    # ------------------------------------------------------------------ #
    def frame_service(self) -> Any:
        """Return the decode/metadata service, building it lazily.

        Reuses the existing :class:`FFmpegService` (ffmpeg-python/numpy;
        Qt-free). Imported lazily so importing ``gui_core`` never imports
        ffmpeg/numpy. Tests may inject a fake via the constructor.
        """
        if self._frame_service is None:
            from ffmpeg_service import FFmpegService

            self._frame_service = FFmpegService(self._config)
        return self._frame_service

    def media_metadata(self, path: str | Path) -> Any:
        """Return media metadata via the existing FFmpegService."""
        return self.frame_service().read_metadata(path)

    def decode_frame(self, path: str | Path, seconds: float) -> Any:
        """Decode a single frame at ``seconds`` via the existing FFmpegService.

        Returns the ``(H, W, 3)`` uint8 BGR ndarray produced by
        :meth:`FFmpegService.extract_frame_at`. The UI converts it to a Qt
        image; ``gui_core`` performs no Qt work.
        """
        return self.frame_service().extract_frame_at(path, seconds)

    def extract_audio(self, path: str | Path) -> Any:
        """Extract a playable audio track via the existing FFmpegService.

        Delegates to :meth:`FFmpegService.extract_audio` (writes an MP3 into
        the configured output dir) and returns its path. Used by the UI audio
        player for playback synchronization.
        """
        return self.frame_service().extract_audio(path)

    # ------------------------------------------------------------------ #
    # Phases (delegates to Pipeline / registry / runner)
    # ------------------------------------------------------------------ #
    def available_phases(self) -> List[PhasePlugin]:
        """Return the phases currently runnable for the selected video.

        Returns an empty list when no video is selected.
        """
        state = self._store.state
        if state.video_stem is None:
            return []
        return self._pipeline.runnable_phases(state.video_stem, self._artifacts)

    def run_phase(self, phase_id: str) -> PhaseResult:
        """Run the phase ``phase_id`` for the selected video.

        Raises:
            ProjectNotLoadedError: If no video is selected.
            UnknownPhaseError: If the phase id is not registered.
            PhaseGatedError: If the phase's dependencies are not satisfied.
        """
        state = self._store.state
        if state.video_path is None or state.video_stem is None:
            raise ProjectNotLoadedError("Select a video before running a phase.")

        plugin = self._registry.get(phase_id)
        if plugin is None:
            raise UnknownPhaseError(f"Unknown phase id: '{phase_id}'.")

        if not self._pipeline.dependencies_satisfied(
            plugin, state.video_stem, self._artifacts
        ):
            raise PhaseGatedError(
                f"Phase '{phase_id}' is blocked: dependencies not satisfied."
            )

        command: Command = plugin.build_command()  # fresh, stateless
        result = self._runner.run(command, state.video_path)
        self._store.refresh_artifacts()
        return result

    def cancel_phase(self, phase_id: str) -> None:
        """Request cancellation of a running phase (reserved for the future).

        Cancellation is not implemented in Phase 8A. This method exists so the
        public API is stable; it currently performs no action.
        """
        self._logger.debug(
            f"cancel_phase('{phase_id}') requested; cancellation is not yet "
            "implemented",
            phase=phase_id,
        )

    # ------------------------------------------------------------------ #
    # Artifacts / settings / logs (thin delegates)
    # ------------------------------------------------------------------ #
    def artifacts(self) -> List[ArtifactInfo]:
        """Return the artifacts discovered for the selected video."""
        return list(self._store.state.artifacts)

    def settings(self) -> dict[str, object]:
        """Return a copy of the current settings mapping."""
        return dict(self._store.state.settings)

    def update_settings(self, key: str, value: object) -> ProjectState:
        """Update one setting and publish ``SettingsChanged``."""
        return self._store.update_setting(key, value)

    def logs(
        self,
        *,
        level: Optional[LogLevel] = None,
        module: Optional[str] = None,
        phase: Optional[str] = None,
        category: Optional[str] = None,
        artifact: Optional[str] = None,
    ) -> List[LogRecord]:
        """Return retained log records filtered by field (no string parsing)."""
        return filter_records(
            self._logger.history(),
            level=level,
            module=module,
            phase=phase,
            category=category,
            artifact=artifact,
        )

    # ------------------------------------------------------------------ #
    # Events (thin delegate to the bus)
    # ------------------------------------------------------------------ #
    def subscribe(
        self,
        event: Event,
        handler: EventHandler,
        priority: EventPriority = EventPriority.NORMAL,
        replay: bool = False,
    ) -> Callable[[], None]:
        """Subscribe ``handler`` to ``event``; return an unsubscribe callable.

        Set ``replay=True`` to immediately synchronize with the latest cached
        persistent-state event (ProjectLoaded / VideoSelected /
        SettingsChanged).
        """
        return self._bus.subscribe(event, handler, priority=priority, replay=replay)
