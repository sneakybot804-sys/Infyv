"""Shared pytest fixtures for Phase 4A tests.

Generates small synthetic videos on disk using OpenCV so the analyzer can be
exercised end-to-end without shipping binary media in the repository.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest


def _write_video(
    path: Path,
    frames: list[np.ndarray],
    fps: float = 8.0,
) -> Path:
    """Write a list of BGR frames to an MP4/AVI file and return the path."""
    height, width = frames[0].shape[:2]
    # MJPG in an AVI container is broadly available across OpenCV builds.
    fourcc = cv2.VideoWriter_fourcc(*"MJPG")
    writer = cv2.VideoWriter(str(path), fourcc, fps, (width, height))
    if not writer.isOpened():
        raise RuntimeError("OpenCV VideoWriter could not be opened.")
    try:
        for frame in frames:
            writer.write(frame)
    finally:
        writer.release()
    return path


@pytest.fixture
def synthetic_video(tmp_path: Path):
    """Factory to build a synthetic video from named segments.

    Each segment is a tuple ``(kind, seconds)`` where ``kind`` is one of:
    ``"black"``, ``"static"`` (mid-grey still frame) or ``"motion"``
    (frames whose content changes every frame).
    """
    width, height, fps = 160, 90, 8.0

    def _make(segments: list[tuple[str, float]], name: str = "clip.avi") -> Path:
        frames: list[np.ndarray] = []
        for kind, seconds in segments:
            count = max(int(round(seconds * fps)), 1)
            for i in range(count):
                if kind == "black":
                    frame = np.zeros((height, width, 3), dtype=np.uint8)
                elif kind == "static":
                    frame = np.full((height, width, 3), 128, dtype=np.uint8)
                elif kind == "motion":
                    frame = np.full((height, width, 3), 128, dtype=np.uint8)
                    # A moving bright block => large frame-to-frame diff.
                    x = (i * 17) % (width - 20)
                    frame[10:70, x : x + 20] = 255
                else:  # pragma: no cover - guard against typos in tests
                    raise ValueError(f"Unknown segment kind: {kind}")
                frames.append(frame)
        return _write_video(tmp_path / name, frames, fps=fps)

    return _make
