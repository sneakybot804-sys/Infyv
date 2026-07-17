"""Backend-only, immutable export pipeline model for gui_core (Qt-free).

Milestone 7 of the backend architecture. This module defines the export
*planning* value types and a pure planner. It performs no encoding, no file
I/O, opens no file dialogs, and has no UI or Qt dependency.

The planner derives an immutable :class:`ExportPlan` from an
:class:`~gui_core.timeline.EditDecisionList` (itself derived from the
authoritative :class:`~gui_core.timeline.Timeline`) and an :class:`ExportSpec`.
Actually running an export (invoking the frozen render producer) is a separate
concern handled by the existing command/runner path and is intentionally not
implemented here.

No Qt symbol is imported here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

from gui_core.timeline import EditDecisionList


class ExportFormat:
    """Frozen string vocabulary of supported container formats."""

    MP4 = "mp4"
    MOV = "mov"
    WEBM = "webm"


#: All valid export formats (validation set).
EXPORT_FORMATS: frozenset[str] = frozenset(
    {ExportFormat.MP4, ExportFormat.MOV, ExportFormat.WEBM}
)


@dataclass(frozen=True)
class ExportSpec:
    """An immutable export specification.

    Attributes:
        output: Output identifier/path (opaque string; no file I/O here).
        format: One of :data:`EXPORT_FORMATS`.
        width: Output width in pixels (``> 0``).
        height: Output height in pixels (``> 0``).
        fps: Output frames per second (``> 0``).
    """

    output: str
    format: str = ExportFormat.MP4
    width: int = 1920
    height: int = 1080
    fps: float = 30.0

    def __post_init__(self) -> None:
        if not self.output:
            raise ValueError("ExportSpec.output must be a non-empty string.")
        if self.format not in EXPORT_FORMATS:
            raise ValueError(
                f"ExportSpec.format must be one of {sorted(EXPORT_FORMATS)}, "
                f"got {self.format!r}."
            )
        if int(self.width) <= 0 or int(self.height) <= 0:
            raise ValueError(
                f"ExportSpec dimensions must be > 0, got "
                f"{self.width!r}x{self.height!r}."
            )
        if float(self.fps) <= 0.0:
            raise ValueError(f"ExportSpec.fps must be > 0, got {self.fps!r}.")

    def to_dict(self) -> Dict[str, object]:
        """Return a plain-dict representation (no framework types)."""
        return {
            "output": self.output,
            "format": self.format,
            "width": self.width,
            "height": self.height,
            "fps": self.fps,
        }


@dataclass(frozen=True)
class ExportSegment:
    """An immutable export segment derived from one edit decision.

    Attributes:
        index: 0-based position within the plan.
        track_index: Source track of the decision.
        source: Optional source identifier carried from the decision.
        timeline_in: Segment start on the timeline (seconds).
        timeline_out: Segment end on the timeline (seconds).
    """

    index: int
    track_index: int
    source: object
    timeline_in: float
    timeline_out: float

    @property
    def duration(self) -> float:
        """Return the segment duration in seconds."""
        return self.timeline_out - self.timeline_in

    def to_dict(self) -> Dict[str, object]:
        """Return a plain-dict representation (no framework types)."""
        return {
            "index": self.index,
            "track_index": self.track_index,
            "source": self.source,
            "timeline_in": self.timeline_in,
            "timeline_out": self.timeline_out,
        }


@dataclass(frozen=True)
class ExportPlan:
    """An immutable export plan: a spec plus ordered segments.

    A read-only projection derived from an EDL + spec. It is not executed here
    and holds no encoding behavior.

    Attributes:
        spec: The :class:`ExportSpec` this plan targets.
        segments: Ordered :class:`ExportSegment` items.
        total_duration: The source timeline/EDL duration (seconds).
    """

    spec: ExportSpec
    segments: Tuple[ExportSegment, ...] = ()
    total_duration: float = 0.0

    def is_empty(self) -> bool:
        """Return whether the plan has no segments."""
        return not self.segments

    def to_dict(self) -> Dict[str, object]:
        """Return a plain-dict representation of the whole plan."""
        return {
            "spec": self.spec.to_dict(),
            "segments": [s.to_dict() for s in self.segments],
            "total_duration": self.total_duration,
        }


def build_export_plan(edl: EditDecisionList, spec: ExportSpec) -> ExportPlan:
    """Build an :class:`ExportPlan` from an EDL and an :class:`ExportSpec`.

    Pure and derived: segments follow the EDL's decision order one-to-one, and
    ``total_duration`` is the EDL's source duration. No encoding or I/O occurs.
    """
    segments = tuple(
        ExportSegment(
            index=i,
            track_index=d.track_index,
            source=d.source,
            timeline_in=d.timeline_in,
            timeline_out=d.timeline_out,
        )
        for i, d in enumerate(edl.decisions)
    )
    return ExportPlan(
        spec=spec, segments=segments, total_duration=edl.duration
    )
