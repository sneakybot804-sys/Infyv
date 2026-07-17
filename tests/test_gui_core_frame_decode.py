"""Tests for facade decode/metadata delegation to the FFmpegService seam."""
from __future__ import annotations

from types import SimpleNamespace

from gui_core.facade import ApplicationFacade
from gui_core.registry import PluginRegistry


class _FakeFrameService:
    def __init__(self):
        self.calls = []

    def read_metadata(self, path):
        self.calls.append(("meta", str(path)))
        return SimpleNamespace(width=1920, height=1080, fps=30.0, duration=12.0)

    def extract_frame_at(self, path, timestamp):
        self.calls.append(("frame", str(path), timestamp))
        return f"frame@{timestamp}"


def _facade(tmp_path, frame_service):
    config = SimpleNamespace(paths=SimpleNamespace(output_dir=tmp_path))
    return ApplicationFacade(
        config,
        producers=object(),
        registry=PluginRegistry(),
        frame_service=frame_service,
    )


def test_facade_decode_frame_delegates(tmp_path):
    fake = _FakeFrameService()
    facade = _facade(tmp_path, fake)
    assert facade.frame_service() is fake
    assert facade.decode_frame("clip.mp4", 2.5) == "frame@2.5"
    assert ("frame", "clip.mp4", 2.5) in fake.calls


def test_facade_media_metadata_delegates(tmp_path):
    fake = _FakeFrameService()
    facade = _facade(tmp_path, fake)
    meta = facade.media_metadata("clip.mp4")
    assert meta.fps == 30.0 and meta.duration == 12.0
    assert ("meta", "clip.mp4") in fake.calls
