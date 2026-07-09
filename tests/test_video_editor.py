"""Unit tests for the Phase 6 VideoEditor (minimum-viable renderer).

Dependency-light: a fake FFmpegService records trim/merge calls and creates
dummy output files, so the whole render orchestration is exercised without
the FFmpeg binary. All inputs are synthetic edit_plan (5e.1) dicts.
"""
from __future__ import annotations

import json

import pytest

from editor_config import EditorConfig, EditorError
from video_editor import INPUT_SCHEMA_VERSION, VideoEditor


# --------------------------------------------------------------------- #
# Fake FFmpegService
# --------------------------------------------------------------------- #
class FakeFFmpeg:
    """Fake FFmpegService: records calls and creates real dummy files.

    Mirrors the two methods VideoEditor uses (Option A):
    - trim_video(video_path, start, end, output_name) -> Path
    - merge_videos(video_paths, output_name) -> Path
    Files are created under ``out_dir`` so path/never-overwrite/cleanup logic
    behaves like the real service.
    """

    def __init__(self, out_dir):
        self._out = out_dir
        self.trims: list[tuple[str, float, float, str]] = []
        self.merges: list[tuple[list[str], str]] = []

    def trim_video(self, video_path, start, end, output_name=None):
        self.trims.append((str(video_path), start, end, output_name))
        path = self._out / output_name
        path.write_bytes(b"clip")
        return path

    def merge_videos(self, video_paths, output_name="merged.mp4"):
        self.merges.append(([str(p) for p in video_paths], output_name))
        path = self._out / output_name
        path.write_bytes(b"merged")
        return path


def _plan(segments, video="C:/videos/clip.mp4"):
    return {
        "schema_version": "5e.1",
        "source_video": video,
        "decision_source": "fallback",
        "segments": segments,
    }


def _seg(index, start, end, score=50.0):
    return {
        "id": f"segment-{index:04d}",
        "source_scene_index": index,
        "start": start,
        "end": end,
        "score": score,
        "reason": "x",
    }


def _editor(tmp_path, cfg=None):
    from config import AppConfig, PathConfig

    app_config = AppConfig(paths=PathConfig(base_dir=tmp_path))
    out_dir = app_config.paths.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    ffmpeg = FakeFFmpeg(out_dir)
    editor = VideoEditor(app_config, cfg or EditorConfig(), ffmpeg_service=ffmpeg)
    return editor, ffmpeg, out_dir


# --------------------------------------------------------------------- #
# Multi-segment: trim in plan order then concatenate
# --------------------------------------------------------------------- #
def test_renders_segments_in_plan_order_then_merges(tmp_path):
    editor, ffmpeg, out_dir = _editor(tmp_path)
    plan = _plan([_seg(0, 0.0, 4.0), _seg(1, 10.0, 14.0), _seg(2, 20.0, 23.0)])
    output = editor.render(plan)
    # One trim per segment, in order, with the right ranges.
    assert [(t[1], t[2]) for t in ffmpeg.trims] == [(0.0, 4.0), (10.0, 14.0), (20.0, 23.0)]
    # A single merge of the three clips, in order.
    assert len(ffmpeg.merges) == 1
    merged_inputs, merged_name = ffmpeg.merges[0]
    assert len(merged_inputs) == 3
    assert output.name == merged_name
    assert output.exists()


def test_source_video_falls_back_to_plan_field(tmp_path):
    editor, ffmpeg, _ = _editor(tmp_path)
    editor.render(_plan([_seg(0, 0.0, 4.0), _seg(1, 5.0, 9.0)],
                        video="C:/videos/match.mp4"))
    assert all(t[0] == "C:/videos/match.mp4" for t in ffmpeg.trims)


def test_explicit_source_overrides_plan(tmp_path):
    editor, ffmpeg, _ = _editor(tmp_path)
    editor.render(
        _plan([_seg(0, 0.0, 4.0), _seg(1, 5.0, 9.0)], video="C:/videos/a.mp4"),
        source_video="C:/videos/override.mp4",
    )
    assert all(t[0] == "C:/videos/override.mp4" for t in ffmpeg.trims)


# --------------------------------------------------------------------- #
# Single segment: no merge (merge_videos needs >= 2 inputs)
# --------------------------------------------------------------------- #
def test_single_segment_is_emitted_without_merge(tmp_path):
    editor, ffmpeg, out_dir = _editor(tmp_path)
    output = editor.render(_plan([_seg(0, 1.0, 6.0)], video="C:/videos/solo.mp4"))
    assert len(ffmpeg.trims) == 1
    assert ffmpeg.merges == []  # never called for a single clip
    assert output.name == "solo_reel.mp4"
    assert output.exists()


# --------------------------------------------------------------------- #
# Empty / invalid plans -> EditorError (never an empty video)
# --------------------------------------------------------------------- #
def test_empty_segments_raises(tmp_path):
    editor, ffmpeg, _ = _editor(tmp_path)
    with pytest.raises(EditorError):
        editor.render(_plan([]))
    assert ffmpeg.trims == [] and ffmpeg.merges == []


def test_all_segments_too_short_raises(tmp_path):
    editor, _, _ = _editor(tmp_path, EditorConfig(min_segment_seconds=1.0))
    with pytest.raises(EditorError):
        editor.render(_plan([_seg(0, 0.0, 0.2), _seg(1, 5.0, 5.1)]))


def test_wrong_schema_version_raises(tmp_path):
    editor, _, _ = _editor(tmp_path)
    bad = _plan([_seg(0, 0.0, 4.0)])
    bad["schema_version"] = "6.0"
    with pytest.raises(EditorError):
        editor.render(bad)


def test_missing_segments_key_raises(tmp_path):
    editor, _, _ = _editor(tmp_path)
    with pytest.raises(EditorError):
        editor.render({"schema_version": INPUT_SCHEMA_VERSION,
                       "source_video": "C:/v/x.mp4"})


def test_no_source_anywhere_raises(tmp_path):
    editor, _, _ = _editor(tmp_path)
    with pytest.raises(EditorError):
        editor.render(_plan([_seg(0, 0.0, 4.0)], video=""))


# --------------------------------------------------------------------- #
# Selection guards
# --------------------------------------------------------------------- #
def test_short_segments_are_skipped_but_valid_ones_render(tmp_path):
    editor, ffmpeg, _ = _editor(tmp_path, EditorConfig(min_segment_seconds=1.0))
    plan = _plan([_seg(0, 0.0, 0.3), _seg(1, 5.0, 9.0), _seg(2, 10.0, 14.0)])
    editor.render(plan)
    # Only the two >= 1.0s segments are trimmed.
    assert [(t[1], t[2]) for t in ffmpeg.trims] == [(5.0, 9.0), (10.0, 14.0)]


def test_max_segments_caps_rendered_clips(tmp_path):
    editor, ffmpeg, _ = _editor(tmp_path, EditorConfig(max_segments=2))
    plan = _plan([_seg(i, i * 10.0, i * 10.0 + 4.0) for i in range(5)])
    editor.render(plan)
    assert len(ffmpeg.trims) == 2


# --------------------------------------------------------------------- #
# File IO: auto-discovery, never overwrite, temp cleanup
# --------------------------------------------------------------------- #
def test_render_files_auto_discovers_plan(tmp_path):
    editor, ffmpeg, out_dir = _editor(tmp_path)
    video = "C:/videos/clip.mp4"
    (out_dir / "clip_edit_plan.json").write_text(
        json.dumps(_plan([_seg(0, 0.0, 4.0), _seg(1, 5.0, 9.0)], video=video)),
        encoding="utf-8",
    )
    output = editor.render_files(video)
    assert output.exists()
    assert len(ffmpeg.trims) == 2


def test_render_files_missing_plan_raises(tmp_path):
    editor, _, _ = _editor(tmp_path)
    with pytest.raises(EditorError):
        editor.render_files("C:/videos/missing.mp4")


def test_final_output_never_overwrites(tmp_path):
    editor, ffmpeg, out_dir = _editor(tmp_path)
    (out_dir / "clip_reel.mp4").write_bytes(b"existing")
    output = editor.render(_plan([_seg(0, 0.0, 4.0), _seg(1, 5.0, 9.0)]))
    assert output.name != "clip_reel.mp4"
    assert output.exists()
    assert (out_dir / "clip_reel.mp4").read_bytes() == b"existing"


def test_intermediate_clips_are_cleaned_up(tmp_path):
    editor, ffmpeg, out_dir = _editor(tmp_path)
    editor.render(_plan([_seg(0, 0.0, 4.0), _seg(1, 5.0, 9.0)]))
    leftover = list(out_dir.glob("*_part*.mp4"))
    assert leftover == []


# --------------------------------------------------------------------- #
# Config validation
# --------------------------------------------------------------------- #
def test_config_validate_rejects_bad_values():
    with pytest.raises(EditorError):
        EditorConfig(crf=99).validate()
    with pytest.raises(EditorError):
        EditorConfig(video_codec="").validate()
    with pytest.raises(EditorError):
        EditorConfig(min_segment_seconds=0.0).validate()
    with pytest.raises(EditorError):
        EditorConfig(max_segments=0).validate()


def test_editor_construction_validates_config():
    with pytest.raises(EditorError):
        VideoEditor(editor_config=EditorConfig(crf=-1))


# --------------------------------------------------------------------- #
# Decoupling guard
# --------------------------------------------------------------------- #
def test_editor_modules_are_decoupled_from_producers():
    import video_editor as mod_a
    import editor_config as mod_b

    forbidden = {
        "decision_agent", "signal_fusion", "highlight_scorer",
        "video_analyzer", "audio_analyzer", "hud_text_extractor",
        "ocr_engine", "scene_detector",
    }
    for module in (mod_a, mod_b):
        src_names = set(vars(module))
        assert forbidden.isdisjoint(src_names), (
            f"{module.__name__} must not import {forbidden & src_names}"
        )
