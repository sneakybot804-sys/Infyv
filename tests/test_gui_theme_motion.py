"""Focused tests for gui.theme.motion helpers (offscreen; skip w/o Qt)."""
from __future__ import annotations

import os

import pytest

pytest.importorskip("PySide6", reason="PySide6 not installed; GUI tests skipped")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEasingCurve  # noqa: E402

from gui.theme.motion import duration_ms, easing_curve  # noqa: E402
from gui.theme.palettes import DARK_TOKENS  # noqa: E402


def test_duration_ms_lookup() -> None:
    motion = DARK_TOKENS.motion
    assert duration_ms(motion, "instant") == motion.duration_instant_ms
    assert duration_ms(motion, "fast") == motion.duration_fast_ms
    assert duration_ms(motion, "normal") == motion.duration_normal_ms
    assert duration_ms(motion, "slow") == motion.duration_slow_ms


def test_duration_ms_default_is_normal() -> None:
    motion = DARK_TOKENS.motion
    assert duration_ms(motion) == motion.duration_normal_ms


def test_duration_ms_unknown_raises() -> None:
    with pytest.raises(KeyError):
        duration_ms(DARK_TOKENS.motion, "nope")


def test_easing_curve_known_names() -> None:
    assert isinstance(easing_curve("in_out_cubic"), QEasingCurve)
    assert isinstance(easing_curve("out_cubic"), QEasingCurve)
