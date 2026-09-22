"""Function-level call graph built from parsed modules.

The graph resolves the raw call names recorded by the parser to analyzed
functions: module-level names, ``self.method``/``ClassName.method`` targets and
imported names (including relative imports). Calls through local variables or
dynamic dispatch cannot be resolved statically and are ignored.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from repomind.models.metrics import ImportInfo, ParsedModule


@dataclass(slots=True)
class CallGraph:
    """Directed graph of resolved function-level calls."""

    edges: dict[str, set[str]] = field(default_factory=dict)
    callers: dict[str, set[str]] = field(default_factory=dict)

    @property
    def function_count(self) -> int:
        """Return the number of analyzed functions."""
        return len(self.edges)

    @property
    def edge_count(self) -> int:
        """Return the number of resolved call edges."""
        return sum(len(targets) for targets in self.edges.values())

    def caller_count(self, qualname: str) -> int:
        """Return how many analyzed functions call *qualname*."""
        return len(self.callers.get(qualname, ()))

    def callee_count(self, qualname: str) -> int:
        """Return how many analyzed functions *qualname* calls."""
        return len(self.edges.get(qualname, ()))

    def top_fan_in(self, limit: int = 5) -> list[tuple[str, int]]:
        """Return the *limit* most called functions."""
        ranked = [(name, len(callers)) for name, callers in self.callers.items()]
        return sorted(ranked, key=lambda item: (-item[1], item[0]))[:limit]


@dataclass(frozen=True, slots=True)
class _Lookups:
    """Resolution tables shared across modules."""

    module_functions: dict[str, dict[str, str]]
    class_methods: dict[tuple[str, str], dict[str, str]]
    qualnames: set[str]
    aliases: dict[str, dict[str, str]]


def build_call_graph(modules: Sequence[ParsedModule]) -> CallGraph:
    """Build the function-level call graph for *modules*."""
    lookups = _build_lookups(modules)
    graph = CallGraph()
    for qualname in lookups.qualnames:
        graph.edges[qualname] = set()
    for module in modules:
        _add_module_edges(module, graph, lookups)
    return graph


def _build_lookups(modules: Sequence[ParsedModule]) -> _Lookups:
    """Index every module, class, function and import alias once."""
    module_functions: dict[str, dict[str, str]] = {}
    class_methods: dict[tuple[str, str], dict[str, str]] = {}
    qualnames: set[str] = set()
    aliases: dict[str, dict[str, str]] = {}

    for module in modules:
        module_functions[module.module_name] = {
            function.name: function.qualname for function in module.functions
        }
        for cls in module.classes:
            class_methods[(module.module_name, cls.name)] = {
                method.name: method.qualname for method in cls.methods
            }
        qualnames.update(function.qualname for function in module.all_functions)
        aliases[module.module_name] = _module_aliases(module)

    return _Lookups(
        module_functions=module_functions,
        class_methods=class_methods,
        qualnames=qualnames,
        aliases=aliases,
    )


def _add_module_edges(module: ParsedModule, graph: CallGraph, lookups: _Lookups) -> None:
    """Add the resolved edges of every function in one module."""
    for function in module.all_functions:
        callees = _resolve_calls(
            module,
            function.qualname,
            function.class_name,
            function.calls,
            lookups,
        )
        graph.edges[function.qualname] |= callees
        for callee in callees:
            graph.callers.setdefault(callee, set()).add(function.qualname)


def _resolve_calls(
    module: ParsedModule,
    qualname: str,
    class_name: str | None,
    calls: tuple[str, ...],
    lookups: _Lookups,
) -> set[str]:
    """Resolve the raw call names of one function to analyzed functions."""
    resolved: set[str] = set()
    for name in calls:
        target = _resolve_call(module, class_name, name, lookups)
        if target is not None and target != qualname:
            resolved.add(target)
    return resolved


def _resolve_call(
    module: ParsedModule,
    class_name: str | None,
    name: str,
    lookups: _Lookups,
) -> str | None:
    """Resolve one raw call name to an analyzed function, if possible."""
    local_functions = lookups.module_functions.get(module.module_name, {})
    if name in local_functions:
        return local_functions[name]

    head, separator, tail = name.partition(".")
    if not separator:
        return _match_qualname(_alias_for(module, lookups, name), lookups.qualnames)
    if head in {"self", "cls"} and class_name is not None:
        methods = lookups.class_methods.get((module.module_name, class_name), {})
        return methods.get(tail)
    same_module_class = lookups.class_methods.get((module.module_name, head))
    if same_module_class is not None:
        return same_module_class.get(tail)
    alias_target = _alias_for(module, lookups, head)
    if alias_target is not None:
        return _match_qualname(f"{alias_target}.{tail}", lookups.qualnames)
    return None


def _alias_for(module: ParsedModule, lookups: _Lookups, name: str) -> str | None:
    """Return the dotted target bound to *name* in *module*, if any."""
    return lookups.aliases.get(module.module_name, {}).get(name)


def _match_qualname(candidate: str | None, qualnames: set[str]) -> str | None:
    """Return the first dotted prefix of *candidate* naming an analyzed function."""
    while candidate:
        if candidate in qualnames:
            return candidate
        candidate = candidate.rpartition(".")[0]
    return None


def _module_aliases(module: ParsedModule) -> dict[str, str]:
    """Map local import names to dotted targets for call resolution."""
    aliases: dict[str, str] = {}
    for imported in module.imports:
        bound = imported.bound_name
        if bound is not None:
            aliases[bound] = _import_target(module, imported)
    return aliases


def _import_target(module: ParsedModule, imported: ImportInfo) -> str:
    """Return the dotted target an import binds to."""
    if not imported.is_from:
        return imported.module

    parts: list[str] = []
    if imported.level > 0:
        package = _package_of(module)
        segments = package.split(".") if package else []
        if imported.level > 1:
            segments = segments[: len(segments) - (imported.level - 1)]
        parts.extend(segments)
    if imported.module:
        parts.append(imported.module)
    if imported.name:
        parts.append(imported.name)
    return ".".join(parts)


def _package_of(module: ParsedModule) -> str:
    """Return the package a module lives in."""
    if module.is_package:
        return module.module_name
    return module.module_name.rpartition(".")[0]
