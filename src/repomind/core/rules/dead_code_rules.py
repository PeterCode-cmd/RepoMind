"""Rules that find dead code: unused imports and unreferenced privates."""

from __future__ import annotations

from collections.abc import Iterator, Sequence

from repomind.core.rules.base import AnalysisContext
from repomind.models.enums import Category, Severity
from repomind.models.findings import Finding
from repomind.models.metrics import FunctionMetrics, ParsedModule


class UnusedImportRule:
    """Flag imports whose bound name is never used in the module."""

    id = "dead-code/unused-import"
    title = "Unused import"
    description = (
        "Unused imports suggest refactoring leftovers, hide real dependencies "
        "and slow down module imports."
    )
    category = Category.DEAD_CODE

    def analyze(self, context: AnalysisContext) -> list[Finding]:
        """Return one finding per unused import binding."""
        findings: list[Finding] = []
        for module in context.modules:
            findings.extend(
                Finding(
                    rule_id=self.id,
                    title=self.title,
                    message=f"`{imported.display}` in {module.rel_path} is never used.",
                    severity=Severity.LOW,
                    category=self.category,
                    path=module.rel_path,
                    line=imported.lineno,
                    suggestion=(
                        "Remove the import; if it exists for re-export purposes, "
                        "make that explicit with an ``as`` alias or ``__all__``."
                    ),
                    details={"import": imported.display, "module": module.module_name},
                )
                for imported in module.unused_imports
            )
        return findings


class UnusedPrivateFunctionRule:
    """Flag private functions and methods that nothing references.

    The check is repository-wide and reference-based: a private symbol counts
    as used when its name appears as a loaded name, an attribute access or an
    identifier-like string anywhere in the analyzed code (which covers
    ``getattr`` dispatch and registry dictionaries).

    Decorated definitions are exempt on purpose: decorators usually register
    callables with a framework (CLI commands, pytest fixtures, event
    handlers), so the code never references them by name.
    """

    id = "dead-code/unused-private-function"
    title = "Unused private function"
    description = (
        "Private helpers that no code calls are dead weight; they mislead "
        "readers about the module's real surface. Decorated definitions are "
        "exempt because decorators register them with frameworks."
    )
    category = Category.DEAD_CODE

    def analyze(self, context: AnalysisContext) -> list[Finding]:
        """Return one finding per unreferenced private function or method."""
        referenced, exports = _referenced_names(context.modules)
        findings: list[Finding] = []
        for module in context.modules:
            findings.extend(_module_dead_findings(module, referenced, exports, rule=self))
        return findings


def _referenced_names(modules: Sequence[ParsedModule]) -> tuple[set[str], set[str]]:
    """Collect every referenced name and declared export across modules."""
    referenced: set[str] = set()
    exports: set[str] = set()
    for module in modules:
        referenced |= module.references
        exports |= module.all_exports
    return referenced, exports


def _module_dead_findings(
    module: ParsedModule,
    referenced: set[str],
    exports: set[str],
    *,
    rule: UnusedPrivateFunctionRule,
) -> list[Finding]:
    """Return the dead private definitions of a single parsed module."""
    if module.syntax_error is not None:
        return []
    return [
        finding
        for function in _private_definitions(module)
        if (
            finding := _dead_function_finding(
                module, function, referenced=referenced, exports=exports, rule=rule
            )
        )
        is not None
    ]


def _private_definitions(module: ParsedModule) -> Iterator[FunctionMetrics]:
    """Yield module-level functions and methods that are private."""
    methods = [method for cls in module.classes for method in cls.methods]
    return (function for function in [*module.functions, *methods] if function.is_private)


def _dead_function_finding(
    module: ParsedModule,
    function: FunctionMetrics,
    *,
    referenced: set[str],
    exports: set[str],
    rule: UnusedPrivateFunctionRule,
) -> Finding | None:
    """Build a finding when *function* is private and never referenced."""
    if function.is_decorated:
        return None
    if function.name in referenced or function.name in exports:
        return None
    kind = "method" if function.is_method else "function"
    return Finding(
        rule_id=rule.id,
        title=rule.title,
        message=f"Private {kind} `{function.qualname}` is never referenced.",
        severity=Severity.LOW,
        category=rule.category,
        path=module.rel_path,
        line=function.lineno,
        symbol=function.qualname,
        suggestion=(
            "Delete it, or make it public if it is part of the intended API; "
            "dynamic usage hides under string lookups and can be whitelisted "
            "by configuring ``exclude``."
        ),
        details={"name": function.name, "kind": kind},
    )
