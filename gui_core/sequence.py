"""Immutable, Qt-free Sequence model for gui_core.

Roadmap item #4. A :class:`Sequence` is an ordered collection of named
:class:`~gui_core.timeline.Timeline` snapshots (e.g. multiple edits/variants),
with an optional active selection. It follows the same immutable-snapshot
convention as the timeline model: frozen dataclasses, eager validation, and
pure transitions that return new snapshots.

No Qt symbol is imported here.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Dict, Optional, Tuple

from gui_core.timeline import Timeline


@dataclass(frozen=True)
class SequenceEntry:
    """An immutable named timeline within a sequence.

    Attributes:
        name: Unique, non-empty name within the owning sequence.
        timeline: The immutable :class:`Timeline` snapshot.
    """

    name: str
    timeline: Timeline

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("SequenceEntry.name must be a non-empty string.")

    def to_dict(self) -> Dict[str, object]:
        """Return a plain-dict representation (no framework types)."""
        return {"name": self.name, "timeline": self.timeline.to_dict()}

    @classmethod
    def from_dict(cls, data: Dict[str, object]) -> "SequenceEntry":
        """Build a validated :class:`SequenceEntry` from a plain dict."""
        return cls(
            name=str(data["name"]),
            timeline=Timeline.from_dict(data["timeline"]),
        )


@dataclass(frozen=True)
class Sequence:
    """An immutable, ordered collection of named timelines.

    Entry names are unique. ``active_name`` (when set) must name an existing
    entry. Every transformation returns a new validated snapshot.
    """

    entries: Tuple[SequenceEntry, ...] = ()
    active_name: Optional[str] = None

    def __post_init__(self) -> None:
        names = [e.name for e in self.entries]
        if len(set(names)) != len(names):
            raise ValueError("Sequence entry names must be unique.")
        if self.active_name is not None and self.active_name not in names:
            raise ValueError(
                f"Sequence.active_name {self.active_name!r} does not name an "
                f"existing entry."
            )

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #
    def is_empty(self) -> bool:
        """Return whether the sequence has no entries."""
        return not self.entries

    def count(self) -> int:
        """Return the number of entries."""
        return len(self.entries)

    def names(self) -> Tuple[str, ...]:
        """Return the entry names in order."""
        return tuple(e.name for e in self.entries)

    def timeline_for(self, name: str) -> Optional[Timeline]:
        """Return the timeline named ``name``, or ``None``."""
        for entry in self.entries:
            if entry.name == name:
                return entry.timeline
        return None

    def active_timeline(self) -> Optional[Timeline]:
        """Return the active timeline, or ``None`` when no active selection."""
        if self.active_name is None:
            return None
        return self.timeline_for(self.active_name)

    # ------------------------------------------------------------------ #
    # Transformations (pure; return a new validated Sequence)
    # ------------------------------------------------------------------ #
    def add(self, name: str, timeline: Timeline) -> "Sequence":
        """Return a copy with a new entry appended (unique name enforced).

        When the sequence was empty, the added entry becomes active.
        """
        entry = SequenceEntry(name=name, timeline=timeline)
        new_active = self.active_name if self.entries else name
        return replace(
            self, entries=self.entries + (entry,), active_name=new_active
        )

    def replace_entry(self, name: str, timeline: Timeline) -> "Sequence":
        """Return a copy with the entry ``name`` replaced by ``timeline``.

        Raises:
            ValueError: If no entry named ``name`` exists.
        """
        if self.timeline_for(name) is None:
            raise ValueError(f"No sequence entry named {name!r}.")
        return replace(
            self,
            entries=tuple(
                SequenceEntry(name=name, timeline=timeline)
                if e.name == name
                else e
                for e in self.entries
            ),
        )

    def with_timeline_update(self, name: str, new_timeline: Timeline) -> "Sequence":
        """Alias of :meth:`replace_entry` for update-by-name semantics."""
        return self.replace_entry(name, new_timeline)

    def remove(self, name: str) -> "Sequence":
        """Return a copy without the entry ``name``.

        Clears ``active_name`` when the removed entry was active.

        Raises:
            ValueError: If no entry named ``name`` exists.
        """
        if self.timeline_for(name) is None:
            raise ValueError(f"No sequence entry named {name!r}.")
        new_active = None if self.active_name == name else self.active_name
        return replace(
            self,
            entries=tuple(e for e in self.entries if e.name != name),
            active_name=new_active,
        )

    def set_active(self, name: Optional[str]) -> "Sequence":
        """Return a copy with ``active_name`` set (validated) or cleared."""
        return replace(self, active_name=name)

    # ------------------------------------------------------------------ #
    # Serialization
    # ------------------------------------------------------------------ #
    def to_dict(self) -> Dict[str, object]:
        """Return a plain-dict representation of the whole sequence."""
        return {
            "entries": [e.to_dict() for e in self.entries],
            "active_name": self.active_name,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, object]) -> "Sequence":
        """Build a validated :class:`Sequence` from a plain dict."""
        return cls(
            entries=tuple(
                SequenceEntry.from_dict(e) for e in data.get("entries", ())
            ),
            active_name=(
                None if data.get("active_name") is None
                else str(data["active_name"])
            ),
        )
