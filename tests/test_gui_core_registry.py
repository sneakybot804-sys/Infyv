"""Tests for the categorized plugin registry (Qt-free)."""
from __future__ import annotations

import pytest

from gui_core.artifacts import ArtifactKind
from gui_core.errors import GuiCoreError
from gui_core.registry import (
    PhaseCategory,
    PhaseDescriptor,
    PhaseId,
    PluginRegistry,
    register_builtins,
)


def _fresh() -> PluginRegistry:
    registry = PluginRegistry()
    register_builtins(registry)
    return registry


def test_builtins_all_present() -> None:
    registry = _fresh()
    assert set(registry.ids()) == {p.value for p in PhaseId}


def test_builtin_dependencies_encode_gating() -> None:
    registry = _fresh()
    fusion = registry.get(PhaseId.FUSION.value)
    render = registry.get(PhaseId.DECISION.value)
    subtitles = registry.get(PhaseId.SUBTITLES.value)
    assert set(fusion.dependencies) == {
        PhaseId.HIGHLIGHT.value,
        PhaseId.OCR.value,
        PhaseId.AUDIO.value,
    }
    assert render.dependencies == (PhaseId.FUSION.value,)
    assert subtitles.dependencies == ()


def test_duplicate_id_rejected() -> None:
    registry = _fresh()
    with pytest.raises(GuiCoreError):
        registry.register(
            PhaseDescriptor(
                id=PhaseId.ANALYSIS.value,
                label="dup",
                category=PhaseCategory.ANALYSIS,
                command_factory=lambda: object(),
            )
        )


def test_external_plugin_added_without_touching_existing() -> None:
    registry = _fresh()
    registry.register(
        PhaseDescriptor(
            id="color_grading",
            label="Color Grading",
            category=PhaseCategory.EFFECTS,
            command_factory=lambda: object(),
            dependencies=(PhaseId.RENDER.value,),
            output_artifact=None,
        )
    )
    plugin = registry.get("color_grading")
    assert plugin is not None
    assert plugin.category == PhaseCategory.EFFECTS
    grouped = registry.by_category()
    assert plugin in grouped[PhaseCategory.EFFECTS]


def test_build_command_returns_fresh_instances() -> None:
    registry = _fresh()
    analysis = registry.get(PhaseId.ANALYSIS.value)
    assert analysis.build_command() is not analysis.build_command()


def test_output_artifact_mapping() -> None:
    registry = _fresh()
    assert registry.get(PhaseId.ANALYSIS.value).output_artifact is ArtifactKind.ANALYSIS
    assert registry.get(PhaseId.RENDER.value).output_artifact is ArtifactKind.RENDER
