"""Module-level dependency graph built from import statements.

Internal imports become directed edges between modules; imports that cannot
be resolved to an analyzed module are tracked as external dependencies. Cycle
detection uses strongly connected components, which is deterministic and
linear in the size of the graph.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field

import networkx as nx

from repomind.models.metrics import ImportInfo, ParsedModule


@dataclass(slots=True)
class DependencyGraph:
    """Directed graph of internal module imports plus external statistics."""

    graph: nx.DiGraph[str] = field(default_factory=nx.DiGraph)
    external_imports: Counter[str] = field(default_factory=Counter)

    @classmethod
    def build(cls, modules: Sequence[ParsedModule]) -> DependencyGraph:
        """Build the dependency graph for parsed *modules*."""
        graph = cls()
        node_names = {module.module_name for module in modules}
        graph.graph.add_nodes_from(sorted(node_names))

        for module in modules:
            for imported in module.imports:
                candidates = _candidate_targets(module, imported)
                resolved = _first_resolvable(candidates, node_names)
                if resolved is None:
                    graph.external_imports[_external_root(candidates[0])] += 1
                elif resolved != module.module_name:
                    graph.graph.add_edge(module.module_name, resolved)

        return graph

    @property
    def module_count(self) -> int:
        """Return the number of internal modules in the graph."""
        return int(self.graph.number_of_nodes())

    @property
    def edge_count(self) -> int:
        """Return the number of internal import edges."""
        return int(self.graph.number_of_edges())

    def cycles(self) -> list[tuple[str, ...]]:
        """Return strongly connected components with more than one module."""
        components = [
            tuple(sorted(component))
            for component in nx.strongly_connected_components(self.graph)
            if len(component) > 1
        ]
        return sorted(components, key=lambda component: (-len(component), component))

    def fan_in(self) -> dict[str, int]:
        """Return how many internal modules import each module."""
        return {node: int(degree) for node, degree in self.graph.in_degree()}

    def fan_out(self) -> dict[str, int]:
        """Return how many internal modules each module imports."""
        return {node: int(degree) for node, degree in self.graph.out_degree()}

    def top_fan_in(self, limit: int = 5) -> list[tuple[str, int]]:
        """Return the *limit* most imported modules."""
        return sorted(self.fan_in().items(), key=lambda item: (-item[1], item[0]))[:limit]

    def top_fan_out(self, limit: int = 5) -> list[tuple[str, int]]:
        """Return the *limit* modules importing the most other modules."""
        return sorted(self.fan_out().items(), key=lambda item: (-item[1], item[0]))[:limit]

    def to_dot(self) -> str:
        """Render the graph in Graphviz DOT format."""
        lines = ["digraph repomind {"]
        lines.extend(f'    "{node}";' for node in sorted(self.graph.nodes))
        lines.extend(
            f'    "{source}" -> "{target}";' for source, target in sorted(self.graph.edges)
        )
        lines.append("}")
        return "\n".join(lines)


def _candidate_targets(module: ParsedModule, imported: ImportInfo) -> list[str]:
    """Return possible internal module names referenced by one import."""
    if not imported.is_from:
        return [imported.module]
    if imported.level == 0:
        return [imported.module]

    package = _package_of(module)
    parts = package.split(".") if package else []
    if imported.level > 1:
        parts = parts[: len(parts) - (imported.level - 1)]
    prefix = ".".join(parts)

    if imported.module:
        return [f"{prefix}.{imported.module}" if prefix else imported.module]
    if prefix and imported.name:
        return [f"{prefix}.{imported.name}", prefix]
    if prefix:
        return [prefix]
    return [imported.name] if imported.name else []


def _first_resolvable(candidates: Sequence[str], nodes: set[str]) -> str | None:
    """Return the first candidate that resolves to an analyzed module."""
    for candidate in candidates:
        resolved = _resolve(candidate, nodes)
        if resolved is not None:
            return resolved
    return None


def _resolve(candidate: str, nodes: set[str]) -> str | None:
    """Resolve a dotted name to a module, trimming components from the right."""
    while candidate:
        if candidate in nodes:
            return candidate
        candidate = candidate.rpartition(".")[0]
    return None


def _package_of(module: ParsedModule) -> str:
    """Return the package a module lives in."""
    if module.is_package:
        return module.module_name
    return module.module_name.rpartition(".")[0]


def _external_root(candidate: str) -> str:
    """Return the distribution-level name of an unresolved import."""
    return candidate.split(".", maxsplit=1)[0] or candidate
