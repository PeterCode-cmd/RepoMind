"""Rules about documentation coverage of the public API."""

from __future__ import annotations

from pathlib import PurePosixPath

from repomind.core.rules.base import AnalysisContext
from repomind.models.enums import Category, Severity
from repomind.models.findings import Finding
from repomind.models.metrics import FunctionMetrics, ParsedModule


class MissingDocstringRule:
    """Flag public modules, classes, functions and methods without docstrings.

    Private and dunder names, decorated definitions (framework hooks such as
    CLI commands or pytest fixtures) and test modules are exempt: they are
    either not public API or their contract lives elsewhere.
    """

    id = "documentation/missing-docstring"
    title = "Missing docstring"
    description = (
        "Public API without a docstring is undiscoverable: users cannot tell "
        "what a symbol does, what it returns or what it raises."
    )
    category = Category.DOCUMENTATION

    def analyze(self, context: AnalysisContext) -> list[Finding]:
        """Return one finding per undocumented public symbol."""
        findings: list[Finding] = []
        for module in context.modules:
            findings.extend(_module_findings(module))
        return findings


def _module_findings(module: ParsedModule) -> list[Finding]:
    """Return the missing-docstring findings for a single module."""
    if module.syntax_error is not None or _is_test_module(module.rel_path):
        return []

    findings: list[Finding] = []
    if not module.has_docstring:
        findings.append(_finding(module, line=1, subject=f"Module `{module.rel_path}`"))
    findings.extend(
        finding
        for function in module.functions
        if (finding := _function_finding(module, function)) is not None
    )

    for cls in module.classes:
        if _needs_docstring(cls.name) and not cls.has_docstring:
            findings.append(
                _finding(
                    module,
                    line=cls.lineno,
                    subject=f"Class `{module.module_name}.{cls.name}`",
                    symbol=f"{module.module_name}.{cls.name}",
                )
            )
        findings.extend(
            finding
            for method in cls.methods
            if (finding := _function_finding(module, method)) is not None
        )
    return findings


def _function_finding(module: ParsedModule, function: FunctionMetrics) -> Finding | None:
    """Return a finding when *function* is public, undecorated and undocumented."""
    if not _needs_docstring(function.name) or function.is_decorated:
        return None
    if function.has_docstring:
        return None
    return _finding(
        module,
        line=function.lineno,
        subject=f"`{function.qualname}`",
        symbol=function.qualname,
    )


def _finding(
    module: ParsedModule,
    *,
    line: int,
    subject: str,
    symbol: str | None = None,
) -> Finding:
    """Build a missing-docstring finding."""
    return Finding(
        rule_id=MissingDocstringRule.id,
        title=MissingDocstringRule.title,
        message=f"{subject} has no docstring.",
        severity=Severity.LOW,
        category=Category.DOCUMENTATION,
        path=module.rel_path,
        line=line,
        symbol=symbol,
        suggestion=(
            "Add a short docstring describing intent, inputs, return value and side effects."
        ),
        details={"module": module.module_name},
    )


def _needs_docstring(name: str) -> bool:
    """Return ``True`` for public names (not private, not dunder)."""
    return not name.startswith("_")


def _is_test_module(rel_path: str) -> bool:
    """Return ``True`` for test modules, whose contract is the test itself."""
    pure = PurePosixPath(rel_path)
    if pure.parts and pure.parts[0] in {"tests", "test"}:
        return True
    name = pure.name
    return name == "conftest.py" or name.startswith("test_") or name.endswith("_test.py")
