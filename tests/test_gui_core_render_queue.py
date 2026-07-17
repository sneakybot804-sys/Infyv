"""Unit tests for the backend-only immutable render queue model."""
from __future__ import annotations

import pytest

from gui_core.render_queue import RenderJob, RenderJobStatus, RenderQueue


def test_job_validation():
    RenderJob(id="j1", source="clip")
    with pytest.raises(ValueError):
        RenderJob(id="", source="clip")
    with pytest.raises(ValueError):
        RenderJob(id="j1", source="")
    with pytest.raises(ValueError):
        RenderJob(id="j1", source="clip", status="bogus")


def test_job_transitions_are_pure():
    j = RenderJob(id="j1", source="clip")
    assert j.status == RenderJobStatus.QUEUED
    assert j.is_terminal is False

    running = j.mark_running()
    assert running.status == RenderJobStatus.RUNNING
    assert j.status == RenderJobStatus.QUEUED  # original unchanged

    ok = running.mark_succeeded(output="out.mp4")
    assert ok.status == RenderJobStatus.SUCCEEDED
    assert ok.output == "out.mp4"
    assert ok.is_terminal is True

    failed = running.mark_failed("boom")
    assert failed.status == RenderJobStatus.FAILED
    assert failed.message == "boom"

    cancelled = j.mark_cancelled()
    assert cancelled.status == RenderJobStatus.CANCELLED
    assert cancelled.is_terminal is True


def test_queue_enqueue_and_unique_ids():
    q = RenderQueue().enqueue(RenderJob(id="a", source="s"))
    assert q.is_empty() is False
    assert len(q.jobs) == 1
    with pytest.raises(ValueError):
        q.enqueue(RenderJob(id="a", source="s2"))


def test_queue_next_queued_fifo():
    q = (
        RenderQueue()
        .enqueue(RenderJob(id="a", source="s").mark_running())
        .enqueue(RenderJob(id="b", source="s"))
        .enqueue(RenderJob(id="c", source="s"))
    )
    assert q.next_queued().id == "b"


def test_queue_remove_and_replace():
    q = RenderQueue().enqueue(RenderJob(id="a", source="s"))
    q2 = q.replace_job(RenderJob(id="a", source="s").mark_running())
    assert q.job_by_id("a").status == RenderJobStatus.QUEUED  # original pure
    assert q2.job_by_id("a").status == RenderJobStatus.RUNNING
    q3 = q2.remove("a")
    assert q3.is_empty() is True
    with pytest.raises(ValueError):
        q.remove("missing")
    with pytest.raises(ValueError):
        q.replace_job(RenderJob(id="missing", source="s"))


def test_queue_status_queries():
    q = (
        RenderQueue()
        .enqueue(RenderJob(id="a", source="s").mark_running())
        .enqueue(RenderJob(id="b", source="s"))
        .enqueue(RenderJob(id="c", source="s").mark_succeeded())
    )
    assert [j.id for j in q.jobs_with_status(RenderJobStatus.RUNNING)] == ["a"]
    assert q.pending_count() == 2  # a (running) + b (queued); c terminal
