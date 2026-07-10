"""Dependency-gated pipeline built from the plugin registry.

The pipeline does not hardcode the phase graph; it derives it from whatever is
registered in the :class:`~gui_core.registry.PluginRegistry`. This is what
makes \"add a plugin, it just appears and gates correctly\" true for future
capabilities without touching this module.

Gating rule: a phase is *runnable* when a video is selected and every artifact
produced by its declared dependencies already exists. A phase with no
dependencies is runnable as soon as a video is selected.

No Qt symbol is imported here.
"""
from __future__ import annotations

from typing import Dict, List

from gui_core.artifacts import ArtifactResolver
from gui_core.errors import GuiCoreError, UnknownPhaseError
from gui_core.registry import PhasePlugin, PluginRegistry


class Pipeline:
    """Computes phase gating and validates the dependency graph."""

    def __init__(self, registry: PluginRegistry) -> None:
        """Create a pipeline over ``registry``.

        Args:
            registry: The plugin registry supplying phases and dependencies.
        """
        self._registry = registry

    def dependencies_satisfied(
        self, plugin: PhasePlugin, stem: str, artifacts: ArtifactResolver
    ) -> bool:
        """Return whether every dependency artifact for ``plugin`` exists.

        Args:
            plugin: The phase to check.
            stem: The selected video's filename stem.
            artifacts: Resolver used to test artifact existence.
        """
        for dep_id in plugin.dependencies:
            dep = self._registry.get(dep_id)
            if dep is None:
                raise UnknownPhaseError(
                    f"Phase '{plugin.id}' depends on unknown phase '{dep_id}'."
                )
            if dep.output_artifact is None:
                # A dependency that produces no artifact cannot be verified by
                # presence; treat it as satisfied (reserved for future phases).
                continue
            if not artifacts.exists(stem, dep.output_artifact):
                return False
        return True

    def runnable_phases(
        self, stem: str, artifacts: ArtifactResolver
    ) -> List[PhasePlugin]:
        """Return the phases currently runnable for ``stem`` in registry order."""
        return [
            plugin
            for plugin in self._registry.all()
            if self.dependencies_satisfied(plugin, stem, artifacts)
        ]

    def blocked_phases(
        self, stem: str, artifacts: ArtifactResolver
    ) -> List[PhasePlugin]:
        """Return the phases whose dependencies are not yet satisfied."""
        return [
            plugin
            for plugin in self._registry.all()
            if not self.dependencies_satisfied(plugin, stem, artifacts)
        ]

    def validate_acyclic(self) -> List[str]:
        """Return a topological order of phase ids, or raise on a cycle.

        Raises:
            GuiCoreError: If the dependency graph contains a cycle.
            UnknownPhaseError: If a dependency references an unregistered id.
        """
        indegree: Dict[str, int] = {pid: 0 for pid in self._registry.ids()}
        adjacency: Dict[str, List[str]] = {pid: [] for pid in self._registry.ids()}

        for plugin in self._registry.all():
            for dep_id in plugin.dependencies:
                if dep_id not in indegree:
                    raise UnknownPhaseError(
                        f"Phase '{plugin.id}' depends on unknown phase "
                        f"'{dep_id}'."
                    )
                adjacency[dep_id].append(plugin.id)
                indegree[plugin.id] += 1

        # Kahn's algorithm, preserving registration order for determinism.
        ready = [pid for pid in self._registry.ids() if indegree[pid] == 0]
        order: List[str] = []
        while ready:
            current = ready.pop(0)
            order.append(current)
            for neighbour in adjacency[current]:
                indegree[neighbour] -= 1
                if indegree[neighbour] == 0:
                    ready.append(neighbour)

        if len(order) != len(indegree):
            raise GuiCoreError("Pipeline dependency graph contains a cycle.")
        return order
