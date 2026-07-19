"""Typed AI request/response value objects for ai_core (Qt-free).

Frozen dataclasses following the ``gui_core`` immutable-snapshot convention.
These are the ONLY shapes crossing the AIManager boundary: the UI never sees
raw provider JSON, and providers never see UI types.

No Qt symbol is imported here.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple


class TaskKind(enum.Enum):
    """Stable vocabulary of AI task kinds (drives model routing)."""

    CHAT = "chat"
    REASONING = "reasoning"
    CODING = "coding"
    VISION = "vision"
    OCR = "ocr"
    VIDEO_ANALYSIS = "video_analysis"
    AUDIO_ANALYSIS = "audio_analysis"
    EDIT_PLAN = "edit_plan"
    EFFECTS = "effects"
    TRANSITION = "transition"
    SUBTITLES = "subtitles"
    SCRIPT = "script"
    TITLE = "title"
    DESCRIPTION = "description"
    TAGS = "tags"
    THUMBNAIL = "thumbnail"
    IMAGE_GENERATION = "image_generation"
    VIDEO_GENERATION = "video_generation"
    SPEECH_TO_TEXT = "speech_to_text"
    TEXT_TO_SPEECH = "text_to_speech"


class Modality(enum.Enum):
    """Payload modality of a request part or a response."""

    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"


@dataclass(frozen=True)
class Attachment:
    """A binary attachment (image/audio/video) accompanying a request.

    Attributes:
        modality: The attachment's modality.
        data: Raw bytes (already read; providers do no file I/O).
        mime_type: MIME type (e.g. ``image/png``).
        name: Optional display name.
    """

    modality: Modality
    data: bytes
    mime_type: str
    name: str = ""


@dataclass(frozen=True)
class AIRequest:
    """An immutable, provider-agnostic AI request.

    Attributes:
        task: The task kind (drives routing and prompt building).
        prompt: The user-facing instruction.
        system: Fully built system prompt (PromptBuilder output).
        model: Resolved model id (ModelRouter output; empty = unset).
        attachments: Binary parts for multimodal tasks.
        temperature: Sampling temperature (``None`` = config default).
        max_tokens: Completion budget (``None`` = config default).
        metadata: Free-form request annotations (logged, never sent).
    """

    task: TaskKind
    prompt: str
    system: str = ""
    model: str = ""
    attachments: Tuple[Attachment, ...] = ()
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class AIUsage:
    """Token/cost accounting reported by a provider (zeros when unknown)."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0


@dataclass(frozen=True)
class AIResponse:
    """An immutable, provider-agnostic AI response.

    Attributes:
        text: The primary text output (empty for binary modalities).
        modality: The response payload modality.
        data: Binary payload for image/audio/video outputs.
        model: Model id that produced the response.
        provider: Provider name that served the request.
        usage: Token/cost accounting.
        latency_seconds: Wall-clock request latency.
        raw: The raw decoded payload (diagnostics only; not for the UI).
    """

    text: str = ""
    modality: Modality = Modality.TEXT
    data: bytes = b""
    model: str = ""
    provider: str = ""
    usage: AIUsage = field(default_factory=AIUsage)
    latency_seconds: float = 0.0
    raw: Optional[dict] = None


# --------------------------------------------------------------------- #
# Strongly typed task results (ResponseParser outputs; UI-facing)
# --------------------------------------------------------------------- #
@dataclass(frozen=True)
class EditPlanSegment:
    """One planned segment of an AI edit plan."""

    start: float
    end: float
    label: str = ""
    reason: str = ""

    @property
    def duration(self) -> float:
        """Return the segment length in seconds."""
        return self.end - self.start


@dataclass(frozen=True)
class EditPlan:
    """A validated AI-generated edit plan."""

    segments: Tuple[EditPlanSegment, ...] = ()
    style: str = ""
    notes: str = ""

    def is_empty(self) -> bool:
        """Return whether the plan has no segments."""
        return not self.segments


@dataclass(frozen=True)
class SubtitleLine:
    """One subtitle cue."""

    start: float
    end: float
    text: str


@dataclass(frozen=True)
class SubtitleResult:
    """A validated subtitle set."""

    lines: Tuple[SubtitleLine, ...] = ()
    language: str = ""


@dataclass(frozen=True)
class VisionResult:
    """A validated vision-analysis answer."""

    description: str = ""
    labels: Tuple[str, ...] = ()
    confidence: float = 0.0


@dataclass(frozen=True)
class OCRResult:
    """Validated OCR output."""

    text: str = ""
    regions: Tuple[str, ...] = ()


@dataclass(frozen=True)
class ScriptResult:
    """A validated script/narration answer."""

    script: str = ""
    scenes: Tuple[str, ...] = ()


@dataclass(frozen=True)
class TitleResult:
    """Validated title suggestions."""

    titles: Tuple[str, ...] = ()


@dataclass(frozen=True)
class TagsResult:
    """Validated tag suggestions."""

    tags: Tuple[str, ...] = ()


@dataclass(frozen=True)
class ThumbnailPrompt:
    """A validated thumbnail-generation brief (feeds image generation)."""

    prompt: str = ""
    negative_prompt: str = ""
    style: str = ""


@dataclass(frozen=True)
class TranscriptResult:
    """Validated speech-to-text output."""

    text: str = ""
    segments: Tuple[SubtitleLine, ...] = ()
    language: str = ""


@dataclass(frozen=True)
class GeneratedMedia:
    """Validated binary generation output (image/audio/video)."""

    modality: Modality = Modality.IMAGE
    data: bytes = b""
    mime_type: str = ""
    model: str = ""
