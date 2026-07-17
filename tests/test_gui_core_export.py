"""Unit tests for the backend-only export pipeline model."""
from __future__ import annotations

import pytest

from gui_core.export import ExportSpec, ExportPlan, build_export_plan
from gui_core.timeline import Clip, Timeline, Track


def test_spec_validation():
    ExportSpec(output="out.mp4")
    with pytest.raises(ValueError):
        ExportSpec(output="")
    with pytest.raises(ValueError):
        ExportSpec(output="o", format="avi")
    with pytest.raises(ValueError):
        ExportSpec(output="o", width=0)
    with pytest.raises(ValueError):
        ExportSpec(output="o", fps=0.0)


def _timeline() -> Timeline:
    return (
        Timeline(duration=60.0, tracks=(Track(index=0, name="V1"),))
        .add_clip(Clip(id="c2", track_index=0, start=20.0, length=5.0, source="g"))
        .add_clip(Clip(id="c1", track_index=0, start=0.0, length=10.0, source="g"))
    )


def test_build_export_plan_orders_and_totals():
    edl = _timeline().to_edl()
    spec = ExportSpec(output="reel.mp4")
    plan = build_export_plan(edl, spec)
    assert isinstance(plan, ExportPlan)
    assert plan.is_empty() is False
    assert plan.total_duration == 60.0
    # Segment order follows the EDL (c1 before c2 by start time).
    assert [s.index for s in plan.segments] == [0, 1]
    assert plan.segments[0].timeline_in == 0.0
    assert plan.segments[0].timeline_out == 10.0
    assert plan.segments[0].duration == 10.0
    assert plan.segments[1].timeline_in == 20.0


def test_build_export_plan_empty():
    edl = Timeline.empty(30.0).to_edl()
    plan = build_export_plan(edl, ExportSpec(output="o.mp4"))
    assert plan.is_empty() is True
    assert plan.total_duration == 30.0


def test_plan_to_dict_shape():
    edl = _timeline().to_edl()
    data = build_export_plan(edl, ExportSpec(output="reel.mp4")).to_dict()
    assert data["spec"]["output"] == "reel.mp4"
    assert data["total_duration"] == 60.0
    assert len(data["segments"]) == 2
