"""Backend-only, immutable render-queue model for gui_core (Qt-free).

Milestone 6 of the backend architecture. This module defines the render-queue
*value types* only: :class:`RenderJob` and the aggregate :class:`RenderQueue`.
They are frozen dataclasses with pure transitions returning new snapshots,
mirroring the immutable-snapshot convention used throughout ``gui_core``.

The model owns no timer, thread, event loop, event bus, or file I/O, and has no
UI. A later milestone can drive queue execution and publish progress on the
existing :class:`~gui_core.events.EventBus` without changing this model.

No Qt symbol is imported here.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Optional, Tuple


class RenderJobStatus:
    """Frozen string vocabulary for a render job's lifecycle status."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


#: All valid statuses (validation set).
RENDER_JOB_STATUSES: frozenset[str] = frozenset(
    {
        RenderJobStatus.QUEUED,
        RenderJobStatus.RUNNING,
        RenderJobStatus.SUCCEEDED,
        RenderJobStatus.FAILED,
        RenderJobStatus.CANCELLED,
    }
)

#: Terminal statuses (no further transition).
_TERMINAL: frozenset[str] = frozenset(
    {RenderJobStatus.SUCCEEDED, RenderJobStatus.FAILED, RenderJobStatus.CANCELLED}
)


@dataclass(frozen=True)
class RenderJob:
    """An immutable render job.

    Attributes:
        id: Stable, unique identifier within a queue.
        source: Source identifier for the render (e.g. a video stem / edit
            plan id). Opaque to this model.
        output: Optional produced output identifier/path (set on success).
        status: One of :data:`RENDER_JOB_STATUSES`.
        message: Human-readable status/error detail.
    """

    id: str
    source: str
    output: Optional[str] = None
    status: str = RenderJobStatus.QUEUED
    message: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("RenderJob.id must be a non-empty string.")
        if not self.source:
            raise ValueError("RenderJob.source must be a non-empty string.")
        if self.status not in RENDER_JOB_STATUSES:
            raise ValueError(
                f"RenderJob.status must be one of {sorted(RENDER_JOB_STATUSES)}, "
                f"got {self.status!r}."
            )

    @property
    def is_terminal(self) -> bool:
        """Return whether the job is in a terminal status."""
        return self.status in _TERMINAL

    def mark_running(self) -> "RenderJob":
        """Return a copy marked running."""
        return replace(self, status=RenderJobStatus.RUNNING)

    def mark_succeeded(self, output: Optional[str] = None) -> "RenderJob":
        """Return a copy marked succeeded, optionally recording ``output``."""
        return replace(
            self,
            status=RenderJobStatus.SUCCEEDED,
            output=output if output is not None else self.output,
        )

    def mark_failed(self, message: str = "") -> "RenderJob":
        """Return a copy marked failed with an optional ``message``."""
        return replace(self, status=RenderJobStatus.FAILED, message=message)

    def mark_cancelled(self) -> "RenderJob":
        """Return a copy marked cancelled."""
        return replace(self, status=RenderJobStatus.CANCELLED)


@dataclass(frozen=True)
class RenderQueue:
    """An immutable, ordered queue of :class:`RenderJob`.

    Job ids are unique. Every operation returns a new queue snapshot; nothing
    is mutated in place.
    """

    jobs: Tuple[RenderJob, ...] = ()

    def __post_init__(self) -> None:
        ids = [j.id for j in self.jobs]
        if len(set(ids)) != len(ids):
            raise ValueError("RenderQueue job ids must be unique.")

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #
    def is_empty(self) -> bool:
        """Return whether the queue has no jobs."""
        return not self.jobs

    def job_by_id(self, job_id: str) -> Optional[RenderJob]:
        """Return the job with ``job_id``, or ``None``."""
        for job in self.jobs:
            if job.id == job_id:
                return job
        return None

    def jobs_with_status(self, status: str) -> Tuple[RenderJob, ...]:
        """Return the jobs whose status equals ``status`` (in order)."""
        return tuple(j for j in self.jobs if j.status == status)

    def next_queued(self) -> Optional[RenderJob]:
        """Return the first queued job (FIFO), or ``None``."""
        for job in self.jobs:
            if job.status == RenderJobStatus.QUEUED:
                return job
        return None

    def pending_count(self) -> int:
        """Return the number of non-terminal jobs."""
        return sum(1 for j in self.jobs if not j.is_terminal)

    # ------------------------------------------------------------------ #
    # Transformations (pure; return a new queue)
    # ------------------------------------------------------------------ #
    def enqueue(self, job: RenderJob) -> "RenderQueue":
        """Return a copy with ``job`` appended (unique id enforced)."""
        return replace(self, jobs=self.jobs + (job,))

    def remove(self, job_id: str) -> "RenderQueue":
        """Return a copy without ``job_id``.

        Raises:
            ValueError: If no job with ``job_id`` exists.
        """
        if self.job_by_id(job_id) is None:
            raise ValueError(f"No render job with id {job_id!r}.")
        return replace(self, jobs=tuple(j for j in self.jobs if j.id != job_id))

    def replace_job(self, job: RenderJob) -> "RenderQueue":
        """Return a copy with the job sharing ``job.id`` replaced by ``job``.

        Raises:
            ValueError: If no job with ``job.id`` exists.
        """
        if self.job_by_id(job.id) is None:
            raise ValueError(f"No render job with id {job.id!r}.")
        return replace(
            self, jobs=tuple(job if j.id == job.id else j for j in self.jobs)
        )
