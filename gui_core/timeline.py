"""Immutable, Qt-free timeline data model for gui_core.

Phase 2 (backend architecture), Milestone 1. This module defines the timeline
*value types* only: :class:`Marker`, :class:`Clip`, :class:`Track` and the
aggregate :class:`Timeline`. They are frozen dataclasses -- no object mutates
them in place. Every transformation returns a **new** :class:`Timeline`
snapshot, mirroring the immutable-snapshot convention already used by
:class:`gui_core.state.ProjectState` / :class:`~gui_core.state.StateStore`.

This milestone is deliberately standalone: the model is *not* yet wired into
the :class:`~gui_core.state.StateStore`, the event bus, or the
:class:`~gui_core.facade.ApplicationFacade`. That integration is a separate,
later milestone so the model can stabilize first. The UI is not touched.

Validation is eager and total: constructing a :class:`Timeline` (directly or
via a transformation) validates the whole invariant set and raises
:class:`ValueError` with a clear message on any violation, matching the
"fail loud, normalized" convention in :mod:`gui_core.commands` and
:mod:`gui_core.state`.

No Qt symbol is imported here.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Dict, Optional, Tuple

#: Allowed track kinds. Kept as a small frozen vocabulary (mirrors the frozen
#: state vocabularies elsewhere in gui_core) rather than an enum to keep the
#: model trivially serializable and dependency-free.
TRACK_KINDS: frozenset[str] = frozenset({"video", "audio"})


@dataclass(frozen=True)
class Marker:
    """An immutable point annotation on the timeline.

    Attributes:
        id: Stable, unique identifier within a timeline.
        time: Position in seconds (``>= 0``).
        label: Human-readable label (may be empty).
        kind: Optional free-form category (e.g. ``"chapter"``, ``"beat"``).
    """

    id: str
    time: float
    label: str = ""
    kind: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("Marker.id must be a non-empty string.")
        if float(self.time) < 0.0:
            raise ValueError(f"Marker.time must be >= 0, got {self.time!r}.")

    def to_dict(self) -> Dict[str, object]:
        """Return a plain-dict representation (no framework types)."""
        return {
            "id": self.id,
            "time": self.time,
            "label": self.label,
            "kind": self.kind,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, object]) -> "Marker":
        """Build a validated :class:`Marker` from a plain dict."""
        return cls(
            id=str(data["id"]),
            time=float(data["time"]),
            label=str(data.get("label", "")),
            kind=(None if data.get("kind") is None else str(data["kind"])),
        )


@dataclass(frozen=True)
class Clip:
    """An immutable clip placed on a single track.

    Attributes:
        id: Stable, unique identifier within a timeline.
        track_index: Index of the owning :class:`Track` (``>= 0``).
        start: Start time in seconds (``>= 0``).
        length: Duration in seconds (``> 0``).
        source: Optional source identifier (e.g. a media filename/stem).
        label: Optional human-readable label.
    """

    id: str
    track_index: int
    start: float
    length: float
    source: Optional[str] = None
    label: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("Clip.id must be a non-empty string.")
        if int(self.track_index) < 0:
            raise ValueError(
                f"Clip.track_index must be >= 0, got {self.track_index!r}."
            )
        if float(self.start) < 0.0:
            raise ValueError(f"Clip.start must be >= 0, got {self.start!r}.")
        if float(self.length) <= 0.0:
            raise ValueError(f"Clip.length must be > 0, got {self.length!r}.")

    @property
    def end(self) -> float:
        """Return the clip's end time in seconds (``start + length``)."""
        return self.start + self.length

    def overlaps(self, other: "Clip") -> bool:
        """Return whether this clip overlaps ``other`` on the same track.

        Clips on different tracks never overlap. Touching edges (one clip's
        ``end`` equal to another's ``start``) do not count as an overlap.
        """
        if self.track_index != other.track_index:
            return False
        return self.start < other.end and other.start < self.end

    def to_dict(self) -> Dict[str, object]:
        """Return a plain-dict representation (no framework types)."""
        return {
            "id": self.id,
            "track_index": self.track_index,
            "start": self.start,
            "length": self.length,
            "source": self.source,
            "label": self.label,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, object]) -> "Clip":
        """Build a validated :class:`Clip` from a plain dict."""
        return cls(
            id=str(data["id"]),
            track_index=int(data["track_index"]),
            start=float(data["start"]),
            length=float(data["length"]),
            source=(None if data.get("source") is None else str(data["source"])),
            label=str(data.get("label", "")),
        )


@dataclass(frozen=True)
class Track:
    """An immutable track lane.

    Attributes:
        index: Position of the track (``>= 0``); unique within a timeline.
        name: Human-readable track name.
        kind: One of :data:`TRACK_KINDS`.
        enabled: Whether the track is enabled (visible/audible).
        locked: Whether the track is locked against edits.
    """

    index: int
    name: str
    kind: str = "video"
    enabled: bool = True
    locked: bool = False

    def __post_init__(self) -> None:
        if int(self.index) < 0:
            raise ValueError(f"Track.index must be >= 0, got {self.index!r}.")
        if self.kind not in TRACK_KINDS:
            raise ValueError(
                f"Track.kind must be one of {sorted(TRACK_KINDS)}, "
                f"got {self.kind!r}."
            )

    def to_dict(self) -> Dict[str, object]:
        """Return a plain-dict representation (no framework types)."""
        return {
            "index": self.index,
            "name": self.name,
            "kind": self.kind,
            "enabled": self.enabled,
            "locked": self.locked,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, object]) -> "Track":
        """Build a validated :class:`Track` from a plain dict."""
        return cls(
            index=int(data["index"]),
            name=str(data.get("name", "")),
            kind=str(data.get("kind", "video")),
            enabled=bool(data.get("enabled", True)),
            locked=bool(data.get("locked", False)),
        )


@dataclass(frozen=True)
class Timeline:
    """An immutable timeline aggregate: tracks, clips and markers.

    A timeline has a fixed positive ``duration`` and holds ordered, immutable
    tuples of :class:`Track`, :class:`Clip` and :class:`Marker`. Construction
    validates the full invariant set; every transformation method returns a
    new validated snapshot and never mutates ``self``.

    Invariants (validated on construction):

    * ``duration > 0``.
    * Track indices are unique.
    * Clip ids are unique; each clip's ``track_index`` refers to an existing
      track; each clip lies within ``[0, duration]``.
    * Clips sharing a track do not overlap.
    * Marker ids are unique; each marker's ``time`` lies within
      ``[0, duration]``.
    """

    duration: float
    tracks: Tuple[Track, ...] = ()
    clips: Tuple[Clip, ...] = ()
    markers: Tuple[Marker, ...] = ()

    # ------------------------------------------------------------------ #
    # Construction / validation
    # ------------------------------------------------------------------ #
    def __post_init__(self) -> None:
        if float(self.duration) <= 0.0:
            raise ValueError(
                f"Timeline.duration must be > 0, got {self.duration!r}."
            )
        self._validate_tracks()
        self._validate_clips()
        self._validate_markers()

    @classmethod
    def empty(cls, duration: float) -> "Timeline":
        """Return an empty timeline of ``duration`` seconds (no tracks/clips)."""
        return cls(duration=float(duration))

    def _validate_tracks(self) -> None:
        indices = [t.index for t in self.tracks]
        if len(set(indices)) != len(indices):
            raise ValueError("Timeline track indices must be unique.")

    def _validate_clips(self) -> None:
        ids = [c.id for c in self.clips]
        if len(set(ids)) != len(ids):
            raise ValueError("Timeline clip ids must be unique.")
        track_indices = {t.index for t in self.tracks}
        for clip in self.clips:
            if clip.track_index not in track_indices:
                raise ValueError(
                    f"Clip {clip.id!r} references unknown track "
                    f"{clip.track_index!r}."
                )
            if clip.end > self.duration:
                raise ValueError(
                    f"Clip {clip.id!r} ends at {clip.end} beyond timeline "
                    f"duration {self.duration}."
                )
        self._validate_no_overlaps()

    def _validate_no_overlaps(self) -> None:
        by_track: Dict[int, list] = {}
        for clip in self.clips:
            by_track.setdefault(clip.track_index, []).append(clip)
        for track_index, clips in by_track.items():
            ordered = sorted(clips, key=lambda c: c.start)
            for earlier, later in zip(ordered, ordered[1:]):
                if earlier.overlaps(later):
                    raise ValueError(
                        f"Clips {earlier.id!r} and {later.id!r} overlap on "
                        f"track {track_index}."
                    )

    def _validate_markers(self) -> None:
        ids = [m.id for m in self.markers]
        if len(set(ids)) != len(ids):
            raise ValueError("Timeline marker ids must be unique.")
        for marker in self.markers:
            if marker.time > self.duration:
                raise ValueError(
                    f"Marker {marker.id!r} at {marker.time} is beyond timeline "
                    f"duration {self.duration}."
                )

    # ------------------------------------------------------------------ #
    # Queries (read-only)
    # ------------------------------------------------------------------ #
    def track_by_index(self, index: int) -> Optional[Track]:
        """Return the track with ``index``, or ``None``."""
        for track in self.tracks:
            if track.index == index:
                return track
        return None

    def clip_by_id(self, clip_id: str) -> Optional[Clip]:
        """Return the clip with ``clip_id``, or ``None``."""
        for clip in self.clips:
            if clip.id == clip_id:
                return clip
        return None

    def marker_by_id(self, marker_id: str) -> Optional[Marker]:
        """Return the marker with ``marker_id``, or ``None``."""
        for marker in self.markers:
            if marker.id == marker_id:
                return marker
        return None

    def clips_on_track(self, track_index: int) -> Tuple[Clip, ...]:
        """Return the clips on ``track_index`` ordered by ``start``."""
        return tuple(
            sorted(
                (c for c in self.clips if c.track_index == track_index),
                key=lambda c: c.start,
            )
        )

    def sorted_markers(self) -> Tuple[Marker, ...]:
        """Return the markers ordered by ``time``."""
        return tuple(sorted(self.markers, key=lambda m: m.time))

    def is_empty(self) -> bool:
        """Return whether the timeline has no clips and no markers."""
        return not self.clips and not self.markers

    def track_count(self) -> int:
        """Return the number of tracks."""
        return len(self.tracks)

    def clip_count(self) -> int:
        """Return the number of clips."""
        return len(self.clips)

    def marker_count(self) -> int:
        """Return the number of markers."""
        return len(self.markers)

    def duration_used(self) -> float:
        """Return the max clip end time (``0.0`` when there are no clips)."""
        return max((c.end for c in self.clips), default=0.0)

    # ------------------------------------------------------------------ #
    # Serialization (plain dicts; no persistence/file-format decision)
    # ------------------------------------------------------------------ #
    def to_dict(self) -> Dict[str, object]:
        """Return a plain-dict representation of the whole timeline."""
        return {
            "duration": self.duration,
            "tracks": [t.to_dict() for t in self.tracks],
            "clips": [c.to_dict() for c in self.clips],
            "markers": [m.to_dict() for m in self.markers],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, object]) -> "Timeline":
        """Build a validated :class:`Timeline` from a plain dict."""
        return cls(
            duration=float(data["duration"]),
            tracks=tuple(Track.from_dict(t) for t in data.get("tracks", ())),
            clips=tuple(Clip.from_dict(c) for c in data.get("clips", ())),
            markers=tuple(Marker.from_dict(m) for m in data.get("markers", ())),
        )

    # ------------------------------------------------------------------ #
    # Transformations (pure; return a new validated Timeline)
    # ------------------------------------------------------------------ #
    def with_duration(self, duration: float) -> "Timeline":
        """Return a copy with a new ``duration`` (revalidated).

        Raises:
            ValueError: If shrinking the duration would leave a clip or marker
                outside ``[0, duration]`` (surfaced by validation).
        """
        return replace(self, duration=float(duration))

    def add_track(self, track: Track) -> "Timeline":
        """Return a copy with ``track`` appended (revalidated for uniqueness)."""
        return replace(self, tracks=self.tracks + (track,))

    def add_clip(self, clip: Clip) -> "Timeline":
        """Return a copy with ``clip`` added (revalidated)."""
        return replace(self, clips=self.clips + (clip,))

    def remove_clip(self, clip_id: str) -> "Timeline":
        """Return a copy without the clip ``clip_id``.

        Raises:
            ValueError: If no clip with ``clip_id`` exists.
        """
        if self.clip_by_id(clip_id) is None:
            raise ValueError(f"No clip with id {clip_id!r}.")
        return replace(
            self, clips=tuple(c for c in self.clips if c.id != clip_id)
        )

    def move_clip(self, clip_id: str, *, track_index: int, start: float) -> "Timeline":
        """Return a copy with ``clip_id`` moved to ``track_index`` / ``start``.

        Raises:
            ValueError: If the clip does not exist, or the move violates an
                invariant (unknown track, out of bounds, overlap).
        """
        clip = self.clip_by_id(clip_id)
        if clip is None:
            raise ValueError(f"No clip with id {clip_id!r}.")
        moved = replace(clip, track_index=int(track_index), start=float(start))
        return replace(
            self,
            clips=tuple(moved if c.id == clip_id else c for c in self.clips),
        )

    def trim_clip(
        self,
        clip_id: str,
        *,
        start: Optional[float] = None,
        length: Optional[float] = None,
    ) -> "Timeline":
        """Return a copy with ``clip_id`` resized (start/length; revalidated).

        Omitted values keep their current value. Validation enforces
        ``start >= 0``, ``length > 0``, within-duration and no-overlap.

        Raises:
            ValueError: If the clip does not exist or the result is invalid.
        """
        clip = self.clip_by_id(clip_id)
        if clip is None:
            raise ValueError(f"No clip with id {clip_id!r}.")
        new_start = clip.start if start is None else float(start)
        new_length = clip.length if length is None else float(length)
        resized = replace(clip, start=new_start, length=new_length)
        return replace(
            self,
            clips=tuple(resized if c.id == clip_id else c for c in self.clips),
        )

    def add_marker(self, marker: Marker) -> "Timeline":
        """Return a copy with ``marker`` added (revalidated)."""
        return replace(self, markers=self.markers + (marker,))

    def remove_marker(self, marker_id: str) -> "Timeline":
        """Return a copy without the marker ``marker_id``.

        Raises:
            ValueError: If no marker with ``marker_id`` exists.
        """
        if self.marker_by_id(marker_id) is None:
            raise ValueError(f"No marker with id {marker_id!r}.")
        return replace(
            self, markers=tuple(m for m in self.markers if m.id != marker_id)
        )
