"""Unit tests for the ai_core pipeline (Qt-free).

Covers config, router, memory, context, prompts, parser, retry and the
AIManager end to end with fake providers. No network access anywhere.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from ai_core import (
    AIConfig,
    AIManager,
    AIRetryConfig,
    ContextEngine,
    MemoryEngine,
    ModelRouter,
    PromptBuilder,
    ResponseFormatError,
    ResponseParser,
    RetryExhaustedError,
    RetryManager,
    TaskKind,
    default_ai_config,
)
from ai_core.config import AIProviderConfig
from ai_core.errors import ProviderUnavailableError, RateLimitError
from ai_core.providers.base import AIProvider
from ai_core.types import AIRequest, AIResponse, AIUsage


# --------------------------------------------------------------------- #
# Fakes
# --------------------------------------------------------------------- #
class FakeProvider(AIProvider):
    """Scriptable provider: returns queued responses or raises queued errors."""

    def __init__(self, name="fake", script=None):
        super().__init__(AIProviderConfig(name=name), api_key="k")
        self.script = list(script or [])
        self.requests = []

    def supports(self, task):
        return True

    def complete(self, request):
        self.requests.append(request)
        action = self.script.pop(0) if self.script else "ok"
        if isinstance(action, Exception):
            raise action
        text = action if isinstance(action, str) and action != "ok" else "hello"
        return AIResponse(
            text=text,
            model=request.model,
            provider=self.name,
            usage=AIUsage(total_tokens=10),
            latency_seconds=0.01,
        )


def make_manager(script=None, **config_kwargs):
    config = AIConfig(
        providers={"fake": AIProviderConfig(name="fake")},
        default_provider="fake",
        **config_kwargs,
    )
    provider = FakeProvider(script=script)
    manager = AIManager(
        config, providers={"fake": provider}, sleep=lambda _s: None
    )
    return manager, provider


# --------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------- #
def test_default_config_has_omniroute_primary():
    config = default_ai_config()
    assert config.default_provider == "omniroute"
    assert "omniroute" in config.providers
    assert config.auto_mode is True


def test_api_key_resolution_from_env(monkeypatch):
    monkeypatch.setenv("AI_FAKE_API_KEY", "secret-from-env")
    cfg = AIProviderConfig(name="fake")
    assert cfg.resolve_api_key() == "secret-from-env"


def test_api_key_resolution_from_file(tmp_path):
    (tmp_path / "ai_keys.json").write_text(
        json.dumps({"fake": "secret-from-file"}), encoding="utf-8"
    )
    cfg = AIProviderConfig(name="fake")
    assert cfg.resolve_api_key(tmp_path) == "secret-from-file"


# --------------------------------------------------------------------- #
# Router
# --------------------------------------------------------------------- #
def test_router_auto_mode_routes_by_task():
    router = ModelRouter(default_ai_config())
    assert "claude" in router.route(TaskKind.CODING).model
    assert "gpt" in router.route(TaskKind.CHAT).model
    assert "gemini" in router.route(TaskKind.VISION).model
    assert "flux" in router.route(TaskKind.THUMBNAIL).model
    assert "whisper" in router.route(TaskKind.SPEECH_TO_TEXT).model
    assert "veo" in router.route(TaskKind.VIDEO_GENERATION).model


def test_router_manual_mode_uses_manual_model_for_text():
    config = AIConfig(auto_mode=False, manual_model="my/model")
    router = ModelRouter(config)
    assert router.route(TaskKind.CHAT).model == "my/model"
    assert router.route(TaskKind.CODING).model == "my/model"
    # Generation tasks stay auto-routed even in manual mode.
    assert router.route(TaskKind.THUMBNAIL).model != "my/model"


def test_router_override_beats_table():
    config = AIConfig(model_overrides={"chat": "override/model"})
    router = ModelRouter(config)
    route = router.route(TaskKind.CHAT)
    assert route.model == "override/model"
    assert route.fallbacks  # table becomes the fallback chain


def test_router_fallback_chain_has_primary_first():
    route = ModelRouter(default_ai_config()).route(TaskKind.CODING)
    chain = route.chain()
    assert chain[0] == route.model
    assert len(chain) >= 2


# --------------------------------------------------------------------- #
# Memory
# --------------------------------------------------------------------- #
def test_memory_persists_roundtrip(tmp_path):
    path = tmp_path / "memory.json"
    memory = MemoryEngine(path)
    memory.remember("style", "cyberpunk")
    memory.remember("game", "valorant")
    # Fresh instance reads the persisted file.
    reloaded = MemoryEngine(path)
    assert reloaded.recall("style") == "cyberpunk"
    assert reloaded.all() == {"style": "cyberpunk", "game": "valorant"}
    reloaded.forget("game")
    assert MemoryEngine(path).recall("game") == ""


def test_memory_tolerates_corrupt_file(tmp_path):
    path = tmp_path / "memory.json"
    path.write_text("{not json", encoding="utf-8")
    memory = MemoryEngine(path)
    assert memory.all() == {}
    memory.remember("style", "anime")
    assert MemoryEngine(path).recall("style") == "anime"


def test_memory_preference_lines_render():
    memory = MemoryEngine(None)
    memory.remember("style", "anime")
    assert "- style: anime" in memory.preference_lines()


# --------------------------------------------------------------------- #
# Context
# --------------------------------------------------------------------- #
class _FakeTimelineClip(SimpleNamespace):
    pass


def _fake_controller(tmp_path):
    from gui_core.timeline import Clip, Timeline, Track

    timeline = Timeline(
        duration=60.0,
        tracks=(Track(index=0, name="Video 1"),),
        clips=(
            Clip(id="c1", track_index=0, start=0.0, length=10.0, label="Intro"),
        ),
    )
    state = SimpleNamespace(
        video_path=tmp_path / "clip.mp4",
        project_path=tmp_path,
        artifacts=(),
        settings={"clip.opacity": 80.0},
        timeline=timeline,
    )
    return SimpleNamespace(
        project_state=lambda: state,
        timeline=lambda: timeline,
        available_phases=lambda: [SimpleNamespace(id="analysis")],
    )


def test_context_engine_collects_from_controller(tmp_path):
    engine = ContextEngine(_fake_controller(tmp_path))
    context = engine.collect()
    assert context.video_name == "clip.mp4"
    assert context.timeline_duration == 60.0
    assert context.track_names == ("Video 1",)
    assert "Intro" in context.clip_summaries[0]
    assert context.runnable_phases == ("analysis",)
    assert context.settings["clip.opacity"] == 80.0
    assert not context.is_empty()


def test_context_engine_headless_is_empty():
    assert ContextEngine(None).collect().is_empty()


def test_context_engine_view_state_merged(tmp_path):
    engine = ContextEngine(
        _fake_controller(tmp_path),
        view_state=lambda: {"selected_clip": "Intro", "playhead_seconds": 4.2},
    )
    context = engine.collect()
    assert context.selected_clip == "Intro"
    assert context.playhead_seconds == 4.2


# --------------------------------------------------------------------- #
# Prompt builder
# --------------------------------------------------------------------- #
def test_prompt_builder_includes_context_and_memory(tmp_path):
    memory = MemoryEngine(None)
    memory.remember("style", "cyberpunk")
    builder = PromptBuilder(memory)
    context = ContextEngine(_fake_controller(tmp_path)).collect()
    system = builder.build_system(TaskKind.EDIT_PLAN, context)
    assert "INFY EDIT PRO" in system
    assert '"segments"' in system            # task contract
    assert "clip.mp4" in system              # context
    assert "- style: cyberpunk" in system    # memory


def test_prompt_builder_sparse_context_omits_blocks():
    builder = PromptBuilder(MemoryEngine(None))
    system = builder.build_system(TaskKind.CHAT, ContextEngine(None).collect())
    assert "EDITOR CONTEXT" not in system
    assert "USER PREFERENCES" not in system


# --------------------------------------------------------------------- #
# Parser
# --------------------------------------------------------------------- #
def _resp(text):
    return AIResponse(text=text)


def test_parser_edit_plan_valid():
    plan = ResponseParser().parse_edit_plan(_resp(json.dumps({
        "segments": [
            {"start": 0, "end": 5, "label": "Intro", "reason": "hook"},
            {"start": 5, "end": 9.5, "label": "Play"},
        ],
        "style": "cinematic",
    })))
    assert len(plan.segments) == 2
    assert plan.segments[1].duration == 4.5
    assert plan.style == "cinematic"


def test_parser_edit_plan_tolerates_fenced_json():
    text = '```json\n{"segments": [{"start": 0, "end": 1}]}\n```'
    plan = ResponseParser().parse_edit_plan(_resp(text))
    assert len(plan.segments) == 1


def test_parser_edit_plan_rejects_bad_range():
    with pytest.raises(ResponseFormatError):
        ResponseParser().parse_edit_plan(_resp(json.dumps({
            "segments": [{"start": 5, "end": 2}]
        })))


def test_parser_subtitles_valid():
    result = ResponseParser().parse_subtitles(_resp(json.dumps({
        "language": "en",
        "lines": [{"start": 0, "end": 2, "text": "Nice shot!"}],
    })))
    assert result.language == "en"
    assert result.lines[0].text == "Nice shot!"


def test_parser_vision_clamps_confidence():
    result = ResponseParser().parse_vision(_resp(json.dumps({
        "description": "a gameplay frame", "labels": ["hud"], "confidence": 3.0
    })))
    assert result.confidence == 1.0


def test_parser_rejects_non_json():
    with pytest.raises(ResponseFormatError):
        ResponseParser().parse_tags(_resp("no json here"))


def test_parser_thumbnail_requires_prompt():
    with pytest.raises(ResponseFormatError):
        ResponseParser().parse_thumbnail_prompt(_resp(json.dumps({"style": "x"})))


# --------------------------------------------------------------------- #
# Retry manager
# --------------------------------------------------------------------- #
def _request(model="m1"):
    return AIRequest(task=TaskKind.CHAT, prompt="hi", model=model)


def test_retry_succeeds_after_transient_failures():
    provider = FakeProvider(script=[
        ProviderUnavailableError("down", provider="fake"),
        RateLimitError("429", provider="fake"),
        "ok",
    ])
    manager = RetryManager(AIRetryConfig(max_attempts=3), sleep=lambda _s: None)
    response = manager.execute(provider, _request())
    assert response.provider == "fake"
    assert len(provider.requests) == 3


def test_retry_falls_back_to_next_model():
    provider = FakeProvider(script=[
        ProviderUnavailableError("down"),
        ProviderUnavailableError("down"),
        "ok",  # first attempt on fallback model
    ])
    manager = RetryManager(AIRetryConfig(max_attempts=2), sleep=lambda _s: None)
    response = manager.execute(
        provider, _request("m1"), fallback_models=("m2",)
    )
    assert provider.requests[-1].model == "m2"
    assert response.model == "m2"


def test_retry_exhaustion_raises_typed_error():
    provider = FakeProvider(script=[
        ProviderUnavailableError("down"),
        ProviderUnavailableError("down"),
    ])
    manager = RetryManager(AIRetryConfig(max_attempts=2), sleep=lambda _s: None)
    with pytest.raises(RetryExhaustedError) as excinfo:
        manager.execute(provider, _request())
    assert excinfo.value.attempts == 2


def test_retry_observer_sees_every_attempt():
    seen = []
    provider = FakeProvider(script=[ProviderUnavailableError("down"), "ok"])
    manager = RetryManager(AIRetryConfig(max_attempts=2), sleep=lambda _s: None)
    manager.execute(
        provider, _request(),
        observer=lambda model, attempt, error: seen.append((model, error)),
    )
    assert len(seen) == 2
    assert seen[0][1] is not None and seen[1][1] is None


# --------------------------------------------------------------------- #
# AIManager end to end (fake provider)
# --------------------------------------------------------------------- #
def test_manager_chat_returns_text():
    manager, provider = make_manager()
    assert manager.chat("hello") == "hello"
    # The request carried a built system prompt and a routed model.
    request = provider.requests[0]
    assert request.system
    assert request.model


def test_manager_rejects_empty_prompt():
    manager, _ = make_manager()
    with pytest.raises(Exception):
        manager.chat("   ")


def test_manager_edit_plan_is_typed():
    plan_json = json.dumps({
        "segments": [{"start": 0, "end": 3, "label": "Clutch"}],
        "style": "cinematic",
    })
    manager, _ = make_manager(script=[plan_json])
    plan = manager.generate_edit_plan("make it cinematic")
    assert plan.segments[0].label == "Clutch"


def test_manager_vision_carries_attachment():
    vision_json = json.dumps({
        "description": "frame", "labels": ["hud"], "confidence": 0.9
    })
    manager, provider = make_manager(script=[vision_json])
    result = manager.vision("what is this", b"\x89PNG", "image/png")
    assert result.labels == ("hud",)
    assert provider.requests[0].attachments[0].mime_type == "image/png"


def test_manager_memory_reaches_prompts():
    manager, provider = make_manager()
    manager.memory.remember("style", "anime")
    manager.chat("hi")
    assert "- style: anime" in provider.requests[0].system


def test_manager_logs_success():
    class Log:
        def __init__(self):
            self.lines = []

        def info(self, message):
            self.lines.append(("info", message))

        def warning(self, message):
            self.lines.append(("warning", message))

        def error(self, message):
            self.lines.append(("error", message))

    log = Log()
    config = AIConfig(
        providers={"fake": AIProviderConfig(name="fake")},
        default_provider="fake",
    )
    manager = AIManager(
        config, providers={"fake": FakeProvider()},
        logger=log, sleep=lambda _s: None,
    )
    manager.chat("hi")
    assert any(
        "provider=fake" in message and "tokens=10" in message
        for level, message in log.lines if level == "info"
    )


def test_manager_provider_failure_raises_and_logs():
    provider = FakeProvider(script=[
        ProviderUnavailableError("down"),
        ProviderUnavailableError("down"),
        ProviderUnavailableError("down"),
    ])
    config = AIConfig(
        providers={"fake": AIProviderConfig(name="fake")},
        default_provider="fake",
        retry=AIRetryConfig(max_attempts=3, use_fallbacks=False),
    )
    manager = AIManager(
        config, providers={"fake": provider}, sleep=lambda _s: None
    )
    with pytest.raises(RetryExhaustedError):
        manager.chat("hi")


def test_manager_context_flows_into_prompt(tmp_path):
    config = AIConfig(
        providers={"fake": AIProviderConfig(name="fake")},
        default_provider="fake",
    )
    provider = FakeProvider()
    manager = AIManager(
        config,
        controller=_fake_controller(tmp_path),
        providers={"fake": provider},
        sleep=lambda _s: None,
    )
    manager.chat("what should I cut?")
    assert "clip.mp4" in provider.requests[0].system
