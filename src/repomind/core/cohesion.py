"""Class cohesion via LCOM4 (lack of cohesion of methods).

Methods are graph nodes; two methods are connected when they touch a common
``self.<name>`` reference or one calls the other. LCOM4 is the number of
connected components: 1 means the class is cohesive, higher values mean the
class bundles several responsibilities that could be split.

Dunder methods are excluded on purpose: constructors tend to touch every
attribute and would collapse the graph to a single component, hiding the
structure of the remaining methods. Stub methods (protocol members whose body
is only a docstring, ``...``, ``pass`` or ``raise NotImplementedError``) are
excluded too: they carry no state by design.
"""

from __future__ import annotations

from collections.abc import Sequence

from repomind.models.metrics import FunctionMetrics


def lcom4(methods: Sequence[FunctionMetrics]) -> int:
    """Return the number of connected components of a class's methods."""
    participants = [
        method for method in methods if not method.name.startswith("__") and not method.is_stub
    ]
    if not participants:
        return 0

    parent = {method.qualname: method.qualname for method in participants}

    def find(name: str) -> str:
        while parent[name] != name:
            parent[name] = parent[parent[name]]
            name = parent[name]
        return name

    def union(left: str, right: str) -> None:
        root_left, root_right = find(left), find(right)
        if root_left != root_right:
            parent[root_right] = root_left

    for index, first in enumerate(participants):
        for second in participants[index + 1 :]:
            if _connected(first, second):
                union(first.qualname, second.qualname)

    return len({find(method.qualname) for method in participants})


def _connected(first: FunctionMetrics, second: FunctionMetrics) -> bool:
    """Return ``True`` when two methods share state or call each other."""
    if set(first.attributes) & set(second.attributes):
        return True
    return f"self.{second.name}" in first.calls or f"self.{first.name}" in second.calls
