"""Categorized plugin registry for pipeline phases.

Every runnable step in the application - built-in or future external plugin -
is described by a :class:`PhasePlugin` and registered in a
:class:`PluginRegistry`. The GUI enumerates phases purely through the registry
and never needs to know whether a plugin is built-in or external.

Adding a future capability (Effects, Transitions, Music, Voice, GPU render,
Color Grading, Motion Graphics, ...) means implementing a plugin and calling
``register()`` - no change to existing classes or to the GUI.

No Qt symbol is imported here.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Protocol, Tuple, runtime_checkable

from gui_core.artifacts import ArtifactKind
from gui_core.errors import GuiCoreError


class PhaseId(enum.Enum):
    """Stable identifiers for the built-in pipeline phases.

    External plugins use their own string ids (see :class:`PluginRegistry`);
    this enum only fixes the ids of the shipped built-ins.
    """

    ANALYSIS = "analysis"
    HIGHLIGHT = "highlight"
    OCR = "ocr"
    AUDIO = "audio"
    FUSION = "fusion"
    DECISION = "decision"
    RENDER = "render"
    SUBTITLES = "subtitles"


class PhaseCategory(enum.Enum):
    """High-level grouping used by the GUI to organize phases.

    Future plugins declare one of these categories and automatically appear
    in the matching GUI section with no GUI code change.
    """

    ANALYSIS = "analysis"
    EDITING = "editing"
    RENDERING = "rendering"
    EFFECTS = "effects"
    AUDIO = "audio"
    AI = "ai"
    UTILITY = "utility"


# A command factory builds a fresh, stateless command for one execution. It is
# imported lazily/typed loosely here to avoid a hard import cycle with
# ``gui_core.commands``; the concrete type is ``Callable[[], Command]``.
CommandFactory = Callable[[], object]


@runtime_checkable
class PhasePlugin(Protocol):
    """Contract every registrable phase (built-in or external) must satisfy."""

    #: Unique, stable phase id (string form of :class:`PhaseId` for built-ins).
    id: str
    #: Human-readable label shown in the GUI.
    label: str
    #: Grouping category for GUI organization.
    category: PhaseCategory
    #: Ids of phases whose artifacts must exist before this phase can run.
    dependencies: Tuple[str, ...]
    #: The artifact kind this phase produces, if any.
    output_artifact: Optional[ArtifactKind]

    def build_command(self) -> object:
        """Return a fresh, stateless command instance for one execution."""
        ...


@dataclass(frozen=True)
class PhaseDescriptor:
    """Concrete, immutable :class:`PhasePlugin` implementation.

    Built-ins and simple external plugins can use this directly rather than
    authoring a bespoke class. ``command_factory`` must return a fresh command
    every call so commands remain stateless and safe for future queueing,
    retries and batch/distributed execution.
    """

    id: str
    label: str
    category: PhaseCategory
    command_factory: CommandFactory
    dependencies: Tuple[str, ...] = ()
    output_artifact: Optional[ArtifactKind] = None

    def build_command(self) -> object:
        """Return a fresh command instance (never a shared singleton)."""
        return self.command_factory()


class PluginRegistry:
    """An ordered, duplicate-rejecting registry of phase plugins."""

    def __init__(self) -> None:
        """Create an empty registry."""
        self._plugins: Dict[str, PhasePlugin] = {}
        self._order: List[str] = []

    def register(self, plugin: PhasePlugin) -> None:
        """Register ``plugin``; raise if its id is already registered.

        Args:
            plugin: The plugin to add. Its ``id`` must be unique.

        Raises:
            GuiCoreError: If a plugin with the same id already exists.
        """
        if plugin.id in self._plugins:
            raise GuiCoreError(f"Duplicate phase id registered: '{plugin.id}'.")
        self._plugins[plugin.id] = plugin
        self._order.append(plugin.id)

    def get(self, phase_id: str) -> Optional[PhasePlugin]:
        """Return the plugin for ``phase_id`` or ``None`` if not registered."""
        return self._plugins.get(phase_id)

    def all(self) -> List[PhasePlugin]:
        """Return all plugins in registration order."""
        return [self._plugins[pid] for pid in self._order]

    def by_category(self) -> Dict[PhaseCategory, List[PhasePlugin]]:
        """Return plugins grouped by category, preserving registration order."""
        grouped: Dict[PhaseCategory, List[PhasePlugin]] = {}
        for pid in self._order:
            plugin = self._plugins[pid]
            grouped.setdefault(plugin.category, []).append(plugin)
        return grouped

    def ids(self) -> List[str]:
        """Return all registered phase ids in registration order."""
        return list(self._order)


def register_builtins(registry: PluginRegistry) -> None:
    """Self-register the eight built-in phases into ``registry``.

    Called during gui_core initialization. Dependencies encode the approved
    GUI gating graph:

    * Highlight requires Analysis.
    * Fusion requires Highlight + OCR + Audio.
    * Decision requires Fusion.
    * Render requires Decision.
    * Subtitles requires only the source video (no artifact dependency).

    The command classes are imported lazily to avoid an import cycle between
    the registry and the commands module.
    """
    from gui_core import commands as cmd

    descriptors = (
        PhaseDescriptor(
            id=PhaseId.ANALYSIS.value,
            label="Video Analysis",
            category=PhaseCategory.ANALYSIS,
            command_factory=cmd.RunAnalysisCommand,
            dependencies=(),
            output_artifact=ArtifactKind.ANALYSIS,
        ),
        PhaseDescriptor(
            id=PhaseId.HIGHLIGHT.value,
            label="Highlight Scoring",
            category=PhaseCategory.ANALYSIS,
            command_factory=cmd.RunHighlightCommand,
            dependencies=(PhaseId.ANALYSIS.value,),
            output_artifact=ArtifactKind.HIGHLIGHT,
        ),
        PhaseDescriptor(
            id=PhaseId.OCR.value,
            label="HUD Text (OCR)",
            category=PhaseCategory.ANALYSIS,
            command_factory=cmd.RunOCRCommand,
            dependencies=(),
            output_artifact=ArtifactKind.OCR,
        ),
        PhaseDescriptor(
            id=PhaseId.AUDIO.value,
            label="Audio Analysis",
            category=PhaseCategory.AUDIO,
            command_factory=cmd.RunAudioCommand,
            dependencies=(),
            output_artifact=ArtifactKind.AUDIO,
        ),
        PhaseDescriptor(
            id=PhaseId.FUSION.value,
            label="Signal Fusion",
            category=PhaseCategory.EDITING,
            command_factory=cmd.RunFusionCommand,
            dependencies=(
                PhaseId.HIGHLIGHT.value,
                PhaseId.OCR.value,
                PhaseId.AUDIO.value,
            ),
            output_artifact=ArtifactKind.ENRICHED_HIGHLIGHT,
        ),
        PhaseDescriptor(
            id=PhaseId.DECISION.value,
            label="AI Decision",
            category=PhaseCategory.EDITING,
            command_factory=cmd.RunDecisionCommand,
            dependencies=(PhaseId.FUSION.value,),
            output_artifact=ArtifactKind.EDIT_PLAN,
        ),
        PhaseDescriptor(
            id=PhaseId.RENDER.value,
            label="Render Highlights",
            category=PhaseCategory.RENDERING,
            command_factory=cmd.RunRenderCommand,
            dependencies=(PhaseId.DECISION.value,),
            output_artifact=ArtifactKind.RENDER,
        ),
        PhaseDescriptor(
            id=PhaseId.SUBTITLES.value,
            label="Subtitles",
            category=PhaseCategory.UTILITY,
            command_factory=cmd.RunSubtitleCommand,
            dependencies=(),
            output_artifact=ArtifactKind.SUBTITLES_JSON,
        ),
    )
    for descriptor in descriptors:
        registry.register(descriptor)
