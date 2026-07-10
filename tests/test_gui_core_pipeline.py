"""Tests for registry-derived pipeline gating and acyclicity (Qt-free)."""
from __future__ import annotations

from pathlib import Path

from gui_core.artifacts import ArtifactKind, ArtifactResolver
from gui_core.pipeline import Pipeline
from gui_core.registry import PhaseId, PluginRegistry, register_builtins


def _pipeline() -> Pipeline:
    registry = PluginRegistry()
    register_builtins(registry)
    return Pipeline(registry)


def _write(resolver: ArtifactResolver, stem: str, kind: ArtifactKind) -> None:
    resolver.expected_path(stem, kind).write_text("{}", encoding="utf-8")


def test_no_artifacts_only_dependency_free_runnable(tmp_path: Path) -> None:
    resolver = ArtifactResolver(tmp_path)
    runnable = {p.id for p in _pipeline().runnable_phases("clip", resolver)}
    assert PhaseId.ANALYSIS.value in runnable
    assert PhaseId.OCR.value in runnable
    assert PhaseId.AUDIO.value in runnable
    assert PhaseId.SUBTITLES.value in runnable
    assert PhaseId.HIGHLIGHT.value not in runnable
    assert PhaseId.FUSION.value not in runnable


def test_highlight_unlocks_after_analysis(tmp_path: Path) -> None:
    resolver = ArtifactResolver(tmp_path)
    _write(resolver, "clip", ArtifactKind.ANALYSIS)
    runnable = {p.id for p in _pipeline().runnable_phases("clip", resolver)}
    assert PhaseId.HIGHLIGHT.value in runnable


def test_fusion_requires_highlight_ocr_audio(tmp_path: Path) -> None:
    resolver = ArtifactResolver(tmp_path)
    pipe = _pipeline()
    _write(resolver, "clip", ArtifactKind.HIGHLIGHT)
    _write(resolver, "clip", ArtifactKind.OCR)
    assert PhaseId.FUSION.value not in {p.id for p in pipe.runnable_phases("clip", resolver)}
    _write(resolver, "clip", ArtifactKind.AUDIO)
    assert PhaseId.FUSION.value in {p.id for p in pipe.runnable_phases("clip", resolver)}


def test_render_requires_decision(tmp_path: Path) -> None:
    resolver = ArtifactResolver(tmp_path)
    pipe = _pipeline()
    assert PhaseId.RENDER.value not in {p.id for p in pipe.runnable_phases("clip", resolver)}
    _write(resolver, "clip", ArtifactKind.EDIT_PLAN)
    assert PhaseId.RENDER.value in {p.id for p in pipe.runnable_phases("clip", resolver)}


def test_validate_acyclic_returns_topological_order() -> None:
    order = _pipeline().validate_acyclic()
    assert order.index(PhaseId.ANALYSIS.value) < order.index(PhaseId.HIGHLIGHT.value)
    assert order.index(PhaseId.FUSION.value) < order.index(PhaseId.DECISION.value)
    assert order.index(PhaseId.DECISION.value) < order.index(PhaseId.RENDER.value)
