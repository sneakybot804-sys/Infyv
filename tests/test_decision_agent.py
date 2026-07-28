"""Unit tests for the Phase 5E AI Decision Pipeline.

Dependency-light: a fake LlmClient replaces Ollama so the whole pipeline is
exercised without a network. All inputs are synthetic enriched dicts.
"""
from __future__ import annotations

import json

import pytest

from decision_agent import SCHEMA_VERSION, DecisionAgent, EditPlan
from decision_config import DecisionConfig, DecisionError, FallbackStrategy


# --------------------------------------------------------------------- #
# Fakes + builders
# --------------------------------------------------------------------- #
class FakeLlm:
    """Fake LlmClient returning a canned response (or raising)."""

    def __init__(self, response="", raise_exc=None):
        self._response = response
        self._raise = raise_exc
        self.calls = 0

    def generate(self, system, prompt):
        self.calls += 1
        if self._raise is not None:
            raise self._raise
        return self._response


def _scene(index, start, end, score, classification="Good", ocr=None):
    return {
        "index": index,
        "start": start,
        "end": end,
        "duration": round(end - start, 3),
        "score": score,
        "classification": classification,
        "rank": 0,
        "signals": {"base_highlight": score / 100.0, "ocr": 0.0,
                    "audio_energy": 0.0, "voice_excitement": 0.0},
        "ocr": ocr or [],
    }


def _enriched(scenes, video="clip.mp4"):
    return {
        "schema_version": "5d.1",
        "video": video,
        "sources": {},
        "scenes": scenes,
    }


def _cfg(**kw):
    base = dict(use_llm=False, fallback_strategy=FallbackStrategy.HYBRID,
                max_segments=10, top_n=5, min_score=20.0,
                merge_adjacent=False)
    base.update(kw)
    return DecisionConfig(**base)


def _agent(cfg=None, llm=None):
    return DecisionAgent(decision_config=cfg or _cfg(), llm_client=llm)


# --------------------------------------------------------------------- #
# Deterministic fallback selection strategies
# --------------------------------------------------------------------- #
def test_fallback_top_n_keeps_highest_scored():
    scenes = [_scene(i, i * 4, i * 4 + 3, i * 20.0) for i in range(5)]
    cfg = _cfg(fallback_strategy=FallbackStrategy.TOP_N, top_n=2, min_score=0.0)
    plan = _agent(cfg).decide(_enriched(scenes))
    assert plan.decision_source == "fallback"
    assert [s.source_scene_index for s in plan.segments] == [4, 3]


def test_fallback_threshold_filters_by_min_score():
    scenes = [_scene(0, 0, 3, 10.0), _scene(1, 4, 7, 50.0), _scene(2, 8, 11, 80.0)]
    cfg = _cfg(fallback_strategy=FallbackStrategy.THRESHOLD, min_score=40.0)
    plan = _agent(cfg).decide(_enriched(scenes))
    indices = {s.source_scene_index for s in plan.segments}
    assert indices == {1, 2}


def test_fallback_hybrid_thresholds_then_caps():
    scenes = [_scene(i, i * 4, i * 4 + 3, 30.0 + i) for i in range(5)]
    cfg = _cfg(fallback_strategy=FallbackStrategy.HYBRID, min_score=20.0, top_n=2)
    plan = _agent(cfg).decide(_enriched(scenes))
    # All pass threshold; top_n=2 keeps the two highest (indices 4, 3).
    assert [s.source_scene_index for s in plan.segments] == [4, 3]


def test_fallback_is_deterministic_across_runs():
    scenes = [_scene(i, i * 4, i * 4 + 3, 50.0) for i in range(4)]
    a = _agent().decide(_enriched(scenes))
    b = _agent().decide(_enriched(scenes))
    assert [s.source_scene_index for s in a.segments] == [
        s.source_scene_index for s in b.segments
    ]
    assert [s.id for s in a.segments] == [s.id for s in b.segments]


def test_max_segments_caps_plan_length():
    scenes = [_scene(i, i * 4, i * 4 + 3, 90.0 - i) for i in range(8)]
    cfg = _cfg(fallback_strategy=FallbackStrategy.TOP_N, top_n=8, max_segments=3,
               min_score=0.0)
    plan = _agent(cfg).decide(_enriched(scenes))
    assert len(plan.segments) == 3


# --------------------------------------------------------------------- #
# LLM path (valid) + validation/fallback (invalid)
# --------------------------------------------------------------------- #
def test_llm_valid_response_is_used():
    scenes = [_scene(0, 0, 4, 80.0), _scene(1, 4, 8, 60.0)]
    response = json.dumps({"segments": [
        {"source_scene_index": 0, "start": 0.0, "end": 4.0, "reason": "clutch"}
    ]})
    cfg = _cfg(use_llm=True, min_score=0.0)
    plan = _agent(cfg, llm=FakeLlm(response=response)).decide(_enriched(scenes))
    assert plan.decision_source == "llm"
    assert len(plan.segments) == 1
    assert plan.segments[0].source_scene_index == 0
    assert plan.segments[0].reason == "clutch"
    assert plan.segments[0].score == 80.0  # carried from the scene


def test_llm_think_block_is_stripped():
    scenes = [_scene(0, 0, 4, 70.0)]
    response = (
        "<think>deliberating</think>"
        + json.dumps({"segments": [
            {"source_scene_index": 0, "start": 0.0, "end": 4.0, "reason": "x"}]})
    )
    cfg = _cfg(use_llm=True, min_score=0.0)
    plan = _agent(cfg, llm=FakeLlm(response=response)).decide(_enriched(scenes))
    assert plan.decision_source == "llm"
    assert plan.segments[0].source_scene_index == 0


def test_llm_json_embedded_in_prose_is_extracted():
    scenes = [_scene(2, 0, 4, 90.0)]
    response = (
        "Sure! Here is the plan:\n"
        + json.dumps({"segments": [
            {"source_scene_index": 2, "start": 0.0, "end": 4.0, "reason": "ace"}]})
        + "\nHope that helps."
    )
    cfg = _cfg(use_llm=True, min_score=0.0)
    plan = _agent(cfg, llm=FakeLlm(response=response)).decide(_enriched(scenes))
    assert plan.decision_source == "llm"
    assert plan.segments[0].source_scene_index == 2


def test_llm_unreachable_falls_back():
    scenes = [_scene(0, 0, 4, 80.0)]
    cfg = _cfg(use_llm=True, min_score=0.0)
    llm = FakeLlm(raise_exc=RuntimeError("connection refused"))
    plan = _agent(cfg, llm=llm).decide(_enriched(scenes))
    assert plan.decision_source == "fallback"
    assert len(plan.segments) == 1


def test_llm_invalid_json_falls_back():
    scenes = [_scene(0, 0, 4, 80.0)]
    cfg = _cfg(use_llm=True, min_score=0.0)
    plan = _agent(cfg, llm=FakeLlm(response="not json at all")).decide(_enriched(scenes))
    assert plan.decision_source == "fallback"


def test_llm_unknown_scene_index_falls_back():
    scenes = [_scene(0, 0, 4, 80.0)]
    response = json.dumps({"segments": [
        {"source_scene_index": 99, "start": 0.0, "end": 4.0, "reason": "bogus"}
    ]})
    cfg = _cfg(use_llm=True, min_score=0.0)
    plan = _agent(cfg, llm=FakeLlm(response=response)).decide(_enriched(scenes))
    assert plan.decision_source == "fallback"


def test_llm_end_not_after_start_falls_back():
    scenes = [_scene(0, 0, 4, 80.0)]
    response = json.dumps({"segments": [
        {"source_scene_index": 0, "start": 4.0, "end": 4.0, "reason": "bad"}
    ]})
    cfg = _cfg(use_llm=True, min_score=0.0)
    plan = _agent(cfg, llm=FakeLlm(response=response)).decide(_enriched(scenes))
    assert plan.decision_source == "fallback"


def test_use_llm_false_never_calls_client():
    scenes = [_scene(0, 0, 4, 80.0)]
    llm = FakeLlm(response="{}")
    _agent(_cfg(use_llm=False, min_score=0.0), llm=llm).decide(_enriched(scenes))
    assert llm.calls == 0


# --------------------------------------------------------------------- #
# Segment shaping: padding + adjacency merge
# --------------------------------------------------------------------- #
def test_padding_extends_bounds_and_clamps_at_zero():
    scenes = [_scene(0, 1.0, 4.0, 80.0)]
    cfg = _cfg(pre_roll_seconds=2.0, post_roll_seconds=1.0, min_score=0.0)
    plan = _agent(cfg).decide(_enriched(scenes))
    seg = plan.segments[0]
    assert seg.start == 0.0  # 1.0 - 2.0 clamped to 0
    assert seg.end == 5.0    # 4.0 + 1.0


def test_adjacent_segments_merge_within_gap():
    scenes = [_scene(0, 0.0, 4.0, 80.0), _scene(1, 4.2, 8.0, 60.0)]
    cfg = _cfg(fallback_strategy=FallbackStrategy.TOP_N, top_n=5, min_score=0.0,
               merge_adjacent=True, merge_gap_seconds=0.5)
    plan = _agent(cfg).decide(_enriched(scenes))
    assert len(plan.segments) == 1
    assert plan.segments[0].start == 0.0
    assert plan.segments[0].end == 8.0


def test_non_adjacent_segments_do_not_merge():
    scenes = [_scene(0, 0.0, 4.0, 80.0), _scene(1, 10.0, 14.0, 60.0)]
    cfg = _cfg(fallback_strategy=FallbackStrategy.TOP_N, top_n=5, min_score=0.0,
               merge_adjacent=True, merge_gap_seconds=0.5)
    plan = _agent(cfg).decide(_enriched(scenes))
    assert len(plan.segments) == 2


# --------------------------------------------------------------------- #
# Schema shape + ids
# --------------------------------------------------------------------- #
def test_document_schema_shape():
    scenes = [_scene(0, 0, 4, 90.0, ocr=["ACE"])]
    plan = _agent().decide(_enriched(scenes))
    doc = plan.to_dict()
    assert doc["schema_version"] == SCHEMA_VERSION
    assert set(doc) == {"schema_version", "source_video", "decision_source", "segments"}
    seg = doc["segments"][0]
    assert set(seg) == {"id", "source_scene_index", "start", "end", "score", "reason"}
    assert seg["id"] == "segment-0001"
    assert json.loads(plan.to_json())["schema_version"] == SCHEMA_VERSION


def test_empty_scenes_produce_empty_segments():
    plan = _agent().decide(_enriched([]))
    assert plan.segments == []
    assert plan.to_dict()["segments"] == []


def test_segment_ids_are_sequential_after_shaping():
    scenes = [_scene(i, i * 5, i * 5 + 3, 90.0 - i) for i in range(3)]
    cfg = _cfg(fallback_strategy=FallbackStrategy.TOP_N, top_n=3, min_score=0.0)
    plan = _agent(cfg).decide(_enriched(scenes))
    assert [s.id for s in plan.segments] == ["segment-0001", "segment-0002", "segment-0003"]


# --------------------------------------------------------------------- #
# File IO: auto-discovery + never overwrite
# --------------------------------------------------------------------- #
def test_decide_to_file_never_overwrites(tmp_path):
    from config import config

    out_dir = config.paths.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    video = "clip.mp4"
    (out_dir / "clip_enriched_highlight.json").write_text(
        json.dumps(_enriched([_scene(0, 0, 4, 80.0)], video=video)), encoding="utf-8"
    )
    agent = DecisionAgent(decision_config=_cfg(min_score=0.0))
    first = agent.decide_to_file(video)
    second = agent.decide_to_file(video)
    assert first.exists() and second.exists()
    assert first != second
    assert first.suffix == ".json"


def test_decide_files_missing_enriched_raises(tmp_path):
    from config import config

    config.paths.output_dir.mkdir(parents=True, exist_ok=True)
    with pytest.raises(DecisionError):
        DecisionAgent(decision_config=_cfg()).decide_files("missing.mp4")


def test_decide_requires_scenes_key():
    with pytest.raises(DecisionError):
        _agent().decide({"schema_version": "5d.1", "video": "x"})


# --------------------------------------------------------------------- #
# Config validation
# --------------------------------------------------------------------- #
def test_config_validate_rejects_bad_values():
    with pytest.raises(DecisionError):
        DecisionConfig(max_segments=0).validate()
    with pytest.raises(DecisionError):
        DecisionConfig(top_n=0).validate()
    with pytest.raises(DecisionError):
        DecisionConfig(min_score=150.0).validate()
    with pytest.raises(DecisionError):
        DecisionConfig(pre_roll_seconds=-1.0).validate()
    with pytest.raises(DecisionError):
        DecisionConfig(merge_gap_seconds=-0.1).validate()


def test_engine_construction_validates_config():
    with pytest.raises(DecisionError):
        DecisionAgent(decision_config=DecisionConfig(top_n=-1))


# --------------------------------------------------------------------- #
# Decoupling + immutability guards
# --------------------------------------------------------------------- #
def test_decision_modules_are_decoupled_from_producers():
    import decision_agent as mod_a
    import decision_config as mod_b

    forbidden = {
        "signal_fusion", "highlight_scorer", "video_analyzer",
        "audio_analyzer", "hud_text_extractor", "ocr_engine", "scene_detector",
    }
    for module in (mod_a, mod_b):
        src_names = set(vars(module))
        assert forbidden.isdisjoint(src_names), (
            f"{module.__name__} must not import {forbidden & src_names}"
        )


def test_decision_agent_does_not_import_gaming_editor_agent():
    import decision_agent as mod

    # Independence from agent.py: neither the agent class nor its error type.
    assert "GamingEditorAgent" not in vars(mod)
    assert "OllamaConnectionError" not in vars(mod)


def test_decide_does_not_mutate_input():
    enriched = _enriched([_scene(0, 0, 4, 80.0)])
    snapshot = json.dumps(enriched, sort_keys=True)
    _agent().decide(enriched)
    assert json.dumps(enriched, sort_keys=True) == snapshot
