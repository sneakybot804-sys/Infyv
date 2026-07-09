"""Unit tests for the Phase 4A ``VideoPicker`` (pure, GUI-free parts)."""
from __future__ import annotations

from pathlib import Path

from video_picker import VIDEO_EXTENSIONS, VideoPicker


def test_filter_videos_keeps_only_known_extensions(tmp_path: Path) -> None:
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"x")
    upper = tmp_path / "CLIP.MKV"
    upper.write_bytes(b"x")
    note = tmp_path / "notes.txt"
    note.write_bytes(b"x")

    kept = VideoPicker.filter_videos([video, upper, note])
    kept_names = {p.name for p in kept}

    assert "clip.mp4" in kept_names
    assert "CLIP.MKV" in kept_names  # case-insensitive match
    assert "notes.txt" not in kept_names


def test_filter_videos_ignores_directories(tmp_path: Path) -> None:
    sub = tmp_path / "sub.mp4"  # a directory that looks like a video
    sub.mkdir()
    assert VideoPicker.filter_videos([sub]) == []


def test_all_known_extensions_are_recognized(tmp_path: Path) -> None:
    made = []
    for ext in VIDEO_EXTENSIONS:
        f = tmp_path / f"file{ext}"
        f.write_bytes(b"x")
        made.append(f)
    assert len(VideoPicker.filter_videos(made)) == len(VIDEO_EXTENSIONS)


def test_list_videos_missing_dir_returns_empty(tmp_path) -> None:
    from config import AppConfig, PathConfig

    # Inject an isolated config rather than mutating the shared PathConfig
    # class: the latter redirects the global logger's file handler into
    # tmp_path and can leave an open handle, breaking tmp cleanup on Windows.
    app_config = AppConfig(paths=PathConfig(base_dir=tmp_path / "nope"))
    assert VideoPicker(app_config).list_videos() == []
