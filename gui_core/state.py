"""Immutable application state and its sole mutator, :class:`StateStore`.

:class:`ProjectState` is a frozen snapshot: no object anywhere mutates it in
place. State transitions happen exclusively through :class:`StateStore`, which
builds a *new* snapshot and publishes the relevant persistent-state event on
the bus so late-joining subscribers can synchronize via replay.

Widgets and other front-end objects hold no business state; they render the
current :class:`ProjectState`.

No Qt symbol is imported here.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Dict, Optional, Tuple

from gui_core.artifacts import ArtifactInfo, ArtifactResolver
from gui_core.events import Event, EventBus


@dataclass(frozen=True)
class ProjectState:
    """An immutable snapshot of the application's business state.

    Attributes:
        project_path: Root of the currently open project/workspace, if any.
        video_path: The selected source video, if any.
        artifacts: The artifacts discovered for the selected video.
        settings: A read-only view of current settings key/value pairs.
    """

    project_path: Optional[Path] = None
    video_path: Optional[Path] = None
    artifacts: Tuple[ArtifactInfo, ...] = ()
    settings: Dict[str, object] = field(default_factory=dict)

    @property
    def video_stem(self) -> Optional[str]:
        """Return the selected video's filename stem, or ``None``."""
        return self.video_path.stem if self.video_path is not None else None


class StateStore:
    """The single owner and mutator of :class:`ProjectState`.

    Every mutation replaces the current snapshot with a new one and publishes
    the corresponding persistent-state event. Reads return the current
    immutable snapshot.
    """

    def __init__(self, bus: EventBus, artifacts: ArtifactResolver) -> None:
        """Create a store with an initial empty state.

        Args:
            bus: Event bus used to publish persistent-state events.
            artifacts: Resolver used to refresh discovered artifacts.
        """
        self._bus = bus
        self._artifacts = artifacts
        self._state = ProjectState()

    @property
    def state(self) -> ProjectState:
        """Return the current immutable state snapshot."""
        return self._state

    def load_project(self, project_path: Path) -> ProjectState:
        """Set the active project root and publish ``ProjectLoaded``."""
        self._state = replace(self._state, project_path=project_path)
        self._bus.publish(Event.ProjectLoaded, {"project_path": str(project_path)})
        return self._state

    def select_video(self, video_path: Path) -> ProjectState:
        """Set the active video, refresh artifacts, publish ``VideoSelected``."""
        artifacts = tuple(self._artifacts.discover(video_path.stem))
        self._state = replace(
            self._state, video_path=video_path, artifacts=artifacts
        )
        self._bus.publish(
            Event.VideoSelected,
            {
                "video_path": str(video_path),
                "artifacts": [a.kind.value for a in artifacts],
            },
        )
        return self._state

    def refresh_artifacts(self) -> ProjectState:
        """Re-discover artifacts for the selected video without an event.

        Used after a phase run to keep gating current. No persistent-state
        event is published because the selection itself did not change; a
        volatile ArtifactCreated event is emitted by the command instead.
        """
        if self._state.video_path is None:
            return self._state
        artifacts = tuple(self._artifacts.discover(self._state.video_path.stem))
        self._state = replace(self._state, artifacts=artifacts)
        return self._state

    def update_setting(self, key: str, value: object) -> ProjectState:
        """Set one setting and publish ``SettingsChanged``."""
        new_settings = dict(self._state.settings)
        new_settings[key] = value
        self._state = replace(self._state, settings=new_settings)
        self._bus.publish(Event.SettingsChanged, {"key": key, "value": value})
        return self._state
