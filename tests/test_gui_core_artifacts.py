"""Tests for the read-only artifact contract and discovery (Qt-free)."""
from __future__ import annotations

from pathlib import Path

from gui_core.artifacts import ARTIFACT_SUFFIXES, ArtifactKind, ArtifactResolver


def test_suffix_contract_matches_frozen_producer_names() -> None:
    assert ARTIFACT_SUFFIXES[ArtifactKind.ANALYSIS] == "_analysis.json"
    assert ARTIFACT_SUFFIXES[ArtifactKind.HIGHLIGHT] == "_highlight.json"
    assert ARTIFACT_SUFFIXES[ArtifactKind.OCR] == "_ocr.json"
    assert ARTIFACT_SUFFIXES[ArtifactKind.AUDIO] == "_audio.json"
    assert ARTIFACT_SUFFIXES[ArtifactKind.ENRICHED_HIGHLIGHT] == "_enriched_highlight.json"
    assert ARTIFACT_SUFFIXES[ArtifactKind.EDIT_PLAN] == "_edit_plan.json"
    assert ARTIFACT_SUFFIXES[ArtifactKind.RENDER] == "_reel.mp4"
    assert ARTIFACT_SUFFIXES[ArtifactKind.SUBTITLES_JSON] == "_subtitles.json"
    assert ARTIFACT_SUFFIXES[ArtifactKind.SUBTITLES_SRT] == ".srt"


def test_expected_path_and_find(tmp_path: Path) -> None:
    resolver = ArtifactResolver(tmp_path)
    stem = "clip"
    assert resolver.exists(stem, ArtifactKind.ANALYSIS) is False
    assert resolver.find(stem, ArtifactKind.ANALYSIS) is None

    expected = resolver.expected_path(stem, ArtifactKind.ANALYSIS)
    assert expected == tmp_path / "clip_analysis.json"
    expected.write_text("{}", encoding="utf-8")

    assert resolver.exists(stem, ArtifactKind.ANALYSIS) is True
    assert resolver.find(stem, ArtifactKind.ANALYSIS) == expected


def test_discover_returns_only_existing(tmp_path: Path) -> None:
    resolver = ArtifactResolver(tmp_path)
    (tmp_path / "clip_analysis.json").write_text("{}", encoding="utf-8")
    (tmp_path / "clip_audio.json").write_text("{}", encoding="utf-8")

    kinds = {info.kind for info in resolver.discover("clip")}
    assert kinds == {ArtifactKind.ANALYSIS, ArtifactKind.AUDIO}
