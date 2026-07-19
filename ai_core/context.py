"""Context engine for ai_core: collect editor state into a snapshot.

Read-only observer over the EXISTING seams: everything comes from the
injected WorkflowController-compatible object (``project_state()``,
``timeline()``, ``available_phases()``, ``settings()``) — the engine never
touches widgets, never mutates state, and never bypasses the controller.

The produced :class:`AIContext` is a plain immutable snapshot the
PromptBuilder renders into prompt text.

No Qt symbol is imported here (duck-typed controller injection keeps this
module importable without PySide6).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple


@dataclass(frozen=True)
class AIContext:
    """An immutable snapshot of the editor state relevant to AI calls.

    Every field is optional/empty-safe: a missing controller or an empty
    project yields an (honest) sparse context, never an error.
    """

    video_name: str = ""
    video_path: str = ""
    project_path: str = ""
    timeline_duration: float = 0.0
    track_names: Tuple[str, ...] = ()
    clip_summaries: Tuple[str, ...] = ()
    marker_count: int = 0
    selected_clip: str = ""
    playhead_seconds: float = 0.0
    artifacts: Tuple[str, ...] = ()
    runnable_phases: Tuple[str, ...] = ()
    settings: Dict[str, object] = field(default_factory=dict)

    def is_empty(self) -> bool:
        """Return whether no meaningful context was collected."""
        return not (
            self.video_name
            or self.clip_summaries
            or self.artifacts
            or self.settings
        )


class ContextEngine:
    """Collects an :class:`AIContext` from the existing controller seam.

    Args:
        controller: A WorkflowController-compatible object (or ``None``
            for headless use). Only its read accessors are used.
        view_state: Optional callable returning a dict of view-only state
            the controller cannot know (playhead seconds, selected clip
            label). The screen wires this in; headless callers omit it.
    """

    def __init__(self, controller=None, view_state=None) -> None:
        self._controller = controller
        self._view_state = view_state

    def collect(self) -> AIContext:
        """Build a fresh snapshot; every failure degrades to empty fields."""
        video_name = ""
        video_path = ""
        project_path = ""
        duration = 0.0
        tracks: Tuple[str, ...] = ()
        clips: Tuple[str, ...] = ()
        markers = 0
        artifacts: Tuple[str, ...] = ()
        phases: Tuple[str, ...] = ()
        settings: Dict[str, object] = {}

        if self._controller is not None:
            try:
                state = self._controller.project_state()
                if state.video_path is not None:
                    video_name = state.video_path.name
                    video_path = str(state.video_path)
                if state.project_path is not None:
                    project_path = str(state.project_path)
                artifacts = tuple(
                    getattr(a.kind, "value", str(a.kind))
                    for a in state.artifacts
                )
                settings = dict(state.settings)
            except Exception:
                pass
            try:
                timeline = self._controller.timeline()
                if timeline is not None:
                    duration = float(timeline.duration)
                    tracks = tuple(t.name for t in timeline.tracks)
                    clips = tuple(
                        f"{c.label or c.source or c.id} "
                        f"[track {c.track_index}, {c.start:.1f}s"
                        f"-{c.end:.1f}s]"
                        for c in timeline.clips
                    )
                    markers = timeline.marker_count()
            except Exception:
                pass
            try:
                phases = tuple(
                    getattr(p, "id", "")
                    for p in self._controller.available_phases()
                )
            except Exception:
                pass

        selected = ""
        playhead = 0.0
        if self._view_state is not None:
            try:
                view = self._view_state() or {}
                selected = str(view.get("selected_clip", ""))
                playhead = float(view.get("playhead_seconds", 0.0) or 0.0)
            except Exception:
                pass

        return AIContext(
            video_name=video_name,
            video_path=video_path,
            project_path=project_path,
            timeline_duration=duration,
            track_names=tracks,
            clip_summaries=clips,
            marker_count=markers,
            selected_clip=selected,
            playhead_seconds=playhead,
            artifacts=artifacts,
            runnable_phases=phases,
            settings=settings,
        )
