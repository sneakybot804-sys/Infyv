"""ai_core: the AI orchestration layer of INFY EDIT PRO (Qt-free).

Public surface re-exports. The ONLY public entry point for AI capabilities
is :class:`AIManager`; providers, router, retry and parser are internal
pipeline stages (exported for tests and configuration only).

Architecture:

    AIManager -> ContextEngine -> MemoryEngine -> PromptBuilder
              -> ModelRouter -> RetryManager -> Provider (OmniRoute/...)
              -> ResponseParser -> typed results

No Qt symbol is imported anywhere in this package; the GUI reaches it
through :class:`gui.integration.ai_worker.AIWorker`.
"""
from __future__ import annotations

from ai_core.config import (
    AIConfig,
    AIProviderConfig,
    AIRetryConfig,
    default_ai_config,
)
from ai_core.context import AIContext, ContextEngine
from ai_core.errors import (
    AIConfigError,
    AIError,
    AuthenticationError,
    ModelNotFoundError,
    ProviderError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    RateLimitError,
    ResponseFormatError,
    RetryExhaustedError,
)
from ai_core.manager import AIManager
from ai_core.memory import MemoryEngine
from ai_core.parser import ResponseParser
from ai_core.prompts import PromptBuilder
from ai_core.retry import RetryManager
from ai_core.router import ModelRouter, Route
from ai_core.types import (
    AIRequest,
    AIResponse,
    AIUsage,
    Attachment,
    EditPlan,
    EditPlanSegment,
    GeneratedMedia,
    Modality,
    OCRResult,
    ScriptResult,
    SubtitleLine,
    SubtitleResult,
    TagsResult,
    TaskKind,
    ThumbnailPrompt,
    TitleResult,
    TranscriptResult,
    VisionResult,
)

__all__ = [
    "AIManager",
    "AIConfig",
    "AIProviderConfig",
    "AIRetryConfig",
    "default_ai_config",
    "AIContext",
    "ContextEngine",
    "MemoryEngine",
    "PromptBuilder",
    "ModelRouter",
    "Route",
    "RetryManager",
    "ResponseParser",
    "TaskKind",
    "Modality",
    "AIRequest",
    "AIResponse",
    "AIUsage",
    "Attachment",
    "EditPlan",
    "EditPlanSegment",
    "SubtitleLine",
    "SubtitleResult",
    "VisionResult",
    "OCRResult",
    "ScriptResult",
    "TitleResult",
    "TagsResult",
    "ThumbnailPrompt",
    "TranscriptResult",
    "GeneratedMedia",
    "AIError",
    "AIConfigError",
    "ProviderError",
    "ProviderTimeoutError",
    "ProviderUnavailableError",
    "RateLimitError",
    "AuthenticationError",
    "ModelNotFoundError",
    "ResponseFormatError",
    "RetryExhaustedError",
]
