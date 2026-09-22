"""Rules about the module dependency graph."""

from __future__ import annotations

from repomind.core.rules.base import AnalysisContext
from repomind.models.enums import Category, Severity
from repomind.models.findings import Finding

_LARGE_CYCLE_SIZE = 3


class CyclicDependencyRule:
    """Flag groups of modules that import each other in a cycle."""

    id = "dependencies/cyclic-import"
    title = "Cyclic import dependency"
    description = (
        "Import cycles couple modules in both directions, break layering and "
        "often cause fragile import-time behaviour or circular import errors."
    )
    category = Category.DEPENDENCIES

    def analyze(self, context: AnalysisContext) -> list[Finding]:
        """Return one finding per strongly connected module group."""
        paths = {module.module_name: module.rel_path for module in context.modules}
        findings: list[Finding] = []
        for cycle in context.graph.cycles():
            anchor = cycle[0]
            path = paths.get(anchor, f"{anchor.replace('.', '/')}.py")
            severity = Severity.HIGH if len(cycle) >= _LARGE_CYCLE_SIZE else Severity.MEDIUM
            findings.append(
                Finding(
                    rule_id=self.id,
                    title=self.title,
                    message=(f"{len(cycle)} modules form an import cycle: {' <-> '.join(cycle)}."),
                    severity=severity,
                    category=self.category,
                    path=path,
                    suggestion=(
                        "Extract the shared abstractions into a new module both "
                        "sides can import, or invert one direction with an "
                        "interface/protocol."
                    ),
                    details={"modules": list(cycle), "size": len(cycle)},
                )
            )
        return findings
