"""AIManager: the single public entry point of the AI architecture.

Every AI capability of the editor goes through this class — no screen,
widget, dialog or feature may call a provider (or OmniRoute) directly.
Each call flows through the full pipeline:

    AIManager -> ContextEngine -> MemoryEngine -> PromptBuilder
              -> ModelRouter -> RetryManager -> Provider -> model
              -> ResponseParser -> typed result

Synchronous by design (mirrors ``ApplicationFacade``): the GUI layer runs
these calls on a worker thread via :class:`gui.integration.ai_worker.
AIWorker`, exactly like phases run through ``PhaseWorker``. This module
therefore stays Qt-free and headless-testable.

Logging reuses the gui_core CoreLogger conventions: every request logs
provider, model, latency, tokens, cost and status.

No Qt symbol is imported here.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional, Sequence

from ai_core.config import AIConfig, default_ai_config
from ai_core.context import AIContext, ContextEngine
from ai_core.errors import AIConfigError, AIError
from ai_core.memory import MemoryEngine
from ai_core.parser import ResponseParser
from ai_core.prompts import PromptBuilder
from ai_core.providers import build_providers
from ai_core.providers.base import AIProvider
from ai_core.retry import RetryManager
from ai_core.router import ModelRouter
from ai_core.types import (
    AIRequest,
    AIResponse,
    Attachment,
    EditPlan,
    Modality,
    OCRResult,
    ScriptResult,
    SubtitleResult,
    TagsResult,
    ThumbnailPrompt,
    TitleResult,
    TranscriptResult,
    TaskKind,
    VisionResult,
)


class AIManager:
    """Central AI orchestrator (the only public AI entry point).

    Args:
        config: AI configuration; defaults to :func:`default_ai_config`.
        controller: Optional WorkflowController-compatible object for
            context collection (read-only accessors only).
        view_state: Optional callable providing view-only context.
        providers: Injectable provider map (tests inject fakes).
        logger: Optional logger with ``info``/``error`` accepting a message
            plus keyword fields (CoreLogger-compatible). ``None`` disables
            logging.
        sleep: Injectable sleep passed to the RetryManager.
        base_dir: Base directory for key resolution (defaults to the
            repository config's base dir when available).
    """

    def __init__(
        self,
        config: Optional[AIConfig] = None,
        *,
        controller=None,
        view_state=None,
        providers: Optional[Dict[str, AIProvider]] = None,
        logger=None,
        sleep=None,
        base_dir: Optional[Path] = None,
    ) -> None:
        if config is None:
            if base_dir is None:
                try:
                    from config import config as app_config

                    base_dir = app_config.paths.base_dir
                except Exception:
                    base_dir = None
            config = default_ai_config(base_dir)
        self._config = config
        self._context_engine = ContextEngine(controller, view_state)
        self._memory = MemoryEngine(config.memory_path)
        self._prompts = PromptBuilder(self._memory)
        self._router = ModelRouter(config)
        self._parser = ResponseParser()
        retry_kwargs = {} if sleep is None else {"sleep": sleep}
        self._retry = RetryManager(config.retry, **retry_kwargs)
        self._providers = providers or build_providers(
            config, base_dir=base_dir
        )
        self._logger = logger

    # ------------------------------------------------------------------ #
    # Component accessors (read-only; for the GUI settings surface)
    # ------------------------------------------------------------------ #
    @property
    def memory(self) -> MemoryEngine:
        """Return the preference memory engine."""
        return self._memory

    @property
    def config(self) -> AIConfig:
        """Return the active AI configuration."""
        return self._config

    # ------------------------------------------------------------------ #
    # Core pipeline
    # ------------------------------------------------------------------ #
    def generate(
        self,
        task: TaskKind,
        prompt: str,
        *,
        attachments: Sequence[Attachment] = (),
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AIResponse:
        """Run the full pipeline for ``task`` and return the raw response.

        This is the single choke point every public helper funnels into:
        context collection, prompt building, routing, provider selection,
        retry/fallback execution and logging all happen here exactly once.

        Raises:
            AIError subclasses on unrecoverable failure (the GUI worker
            catches these and reports through its failed signal).
        """
        if not prompt or not prompt.strip():
            raise AIConfigError("Prompt must not be empty.")
        context = self._context_engine.collect()
        system = self._prompts.build_system(task, context)
        route = self._router.route(task)
        provider = self._provider_for(task)
        request = AIRequest(
            task=task,
            prompt=prompt.strip(),
            system=system,
            model=route.model,
            attachments=tuple(attachments),
            temperature=(
                temperature if temperature is not None
                else self._config.temperature
            ),
            max_tokens=(
                max_tokens if max_tokens is not None
                else self._config.max_tokens
            ),
        )
        try:
            response = self._retry.execute(
                provider,
                request,
                fallback_models=route.fallbacks,
                observer=self._log_attempt,
            )
        except AIError as exc:
            self._log(
                "error",
                f"AI request failed: task={task.value} error={exc}",
            )
            raise
        self._log(
            "info",
            (
                f"AI ok: task={task.value} provider={response.provider} "
                f"model={response.model} "
                f"latency={response.latency_seconds:.2f}s "
                f"tokens={response.usage.total_tokens} "
                f"cost=${response.usage.cost_usd:.4f}"
            ),
        )
        return response

    def _provider_for(self, task: TaskKind) -> AIProvider:
        """Return the default provider, or any enabled one serving ``task``."""
        default = self._providers.get(self._config.default_provider)
        if default is not None and default.supports(task):
            return default
        for provider in self._providers.values():
            if provider.supports(task):
                return provider
        raise AIConfigError(
            f"No enabled provider supports task '{task.value}'."
        )

    # ------------------------------------------------------------------ #
    # Public capability surface (typed helpers; all funnel into generate)
    # ------------------------------------------------------------------ #
    def chat(self, prompt: str) -> str:
        """Free-form assistant chat; returns plain text."""
        return self.generate(TaskKind.CHAT, prompt).text

    def analyze_video(self, prompt: str = "Analyze this gameplay video.") -> str:
        """Reason about the current video/timeline context; plain text."""
        return self.generate(TaskKind.VIDEO_ANALYSIS, prompt).text

    def analyze_audio(self, prompt: str = "Analyze the audio track.") -> str:
        """Reason about the audio; plain text."""
        return self.generate(TaskKind.AUDIO_ANALYSIS, prompt).text

    def generate_edit_plan(self, prompt: str) -> EditPlan:
        """Generate a validated :class:`EditPlan`."""
        return self._parser.parse_edit_plan(
            self.generate(TaskKind.EDIT_PLAN, prompt)
        )

    def generate_subtitles(self, prompt: str) -> SubtitleResult:
        """Generate validated subtitles."""
        return self._parser.parse_subtitles(
            self.generate(TaskKind.SUBTITLES, prompt)
        )

    def generate_script(self, prompt: str) -> ScriptResult:
        """Generate a validated script."""
        return self._parser.parse_script(
            self.generate(TaskKind.SCRIPT, prompt)
        )

    def generate_title(self, prompt: str) -> TitleResult:
        """Generate validated title suggestions."""
        return self._parser.parse_titles(
            self.generate(TaskKind.TITLE, prompt)
        )

    def generate_description(self, prompt: str) -> str:
        """Generate a video description; plain text."""
        return self.generate(TaskKind.DESCRIPTION, prompt).text

    def generate_tags(self, prompt: str) -> TagsResult:
        """Generate validated tags."""
        return self._parser.parse_tags(self.generate(TaskKind.TAGS, prompt))

    def generate_thumbnail(self, prompt: str) -> ThumbnailPrompt:
        """Generate a validated thumbnail brief (feeds image generation)."""
        return self._parser.parse_thumbnail_prompt(
            self.generate(TaskKind.THUMBNAIL, prompt)
        )

    def generate_effects(self, prompt: str) -> TagsResult:
        """Recommend effects (validated tag list)."""
        return self._parser.parse_tags(
            self.generate(TaskKind.EFFECTS, prompt)
        )

    def generate_transition(self, prompt: str) -> TagsResult:
        """Recommend transitions (validated tag list)."""
        return self._parser.parse_tags(
            self.generate(TaskKind.TRANSITION, prompt)
        )

    def vision(
        self, prompt: str, image: bytes, mime_type: str = "image/png"
    ) -> VisionResult:
        """Analyze an image; returns a validated :class:`VisionResult`."""
        attachment = Attachment(
            modality=Modality.IMAGE, data=image, mime_type=mime_type
        )
        return self._parser.parse_vision(
            self.generate(TaskKind.VISION, prompt, attachments=(attachment,))
        )

    def ocr(
        self, image: bytes, mime_type: str = "image/png"
    ) -> OCRResult:
        """Extract text from an image; validated :class:`OCRResult`."""
        attachment = Attachment(
            modality=Modality.IMAGE, data=image, mime_type=mime_type
        )
        return self._parser.parse_ocr(
            self.generate(
                TaskKind.OCR,
                "Extract all visible text.",
                attachments=(attachment,),
            )
        )

    def voice(self, prompt: str, audio: bytes, mime_type: str = "audio/wav") -> TranscriptResult:
        """Transcribe speech; validated :class:`TranscriptResult`."""
        attachment = Attachment(
            modality=Modality.AUDIO, data=audio, mime_type=mime_type
        )
        return self._parser.parse_transcript(
            self.generate(
                TaskKind.SPEECH_TO_TEXT, prompt, attachments=(attachment,)
            )
        )

    def fix_code(self, code: str, problem: str) -> str:
        """Fix the described problem in ``code``; returns the revised code."""
        return self.generate(
            TaskKind.CODING, f"Fix this problem: {problem}\n\nCODE:\n{code}"
        ).text

    def explain_code(self, code: str) -> str:
        """Explain ``code``; plain text."""
        return self.generate(
            TaskKind.CODING, f"Explain this code:\n{code}"
        ).text

    def complete_code(self, code: str) -> str:
        """Complete ``code``; returns the continued code."""
        return self.generate(
            TaskKind.CODING, f"Complete this code:\n{code}"
        ).text

    # ------------------------------------------------------------------ #
    # Introspection / logging
    # ------------------------------------------------------------------ #
    def current_context(self) -> AIContext:
        """Return a fresh editor-context snapshot (diagnostics/UI)."""
        return self._context_engine.collect()

    def _log_attempt(
        self, model: str, attempt: int, error: Optional[Exception]
    ) -> None:
        """RetryManager observer: log each attempt outcome."""
        if error is None:
            return
        self._log(
            "warning",
            f"AI attempt {attempt} failed: model={model} error={error}",
        )

    def _log(self, level: str, message: str) -> None:
        """Log through the injected logger; never raise from logging."""
        if self._logger is None:
            return
        try:
            getattr(self._logger, level, self._logger.info)(message)
        except Exception:
            pass
