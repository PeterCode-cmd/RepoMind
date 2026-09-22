"""Rules that combine Git history with static metrics."""

from __future__ import annotations

from repomind.config import Thresholds
from repomind.core.rules.base import AnalysisContext
from repomind.git.blame import FunctionChurn
from repomind.git.history import FileHistory
from repomind.models.enums import Category, Severity
from repomind.models.findings import Finding
from repomind.models.metrics import FunctionMetrics, ParsedModule

_SUGGESTION = (
    "Refactor this function first: it is both complex and under constant "
    "change, so improvements compound."
)


class ComplexityHotspotRule:
    """Flag complex functions living in frequently changed code.

    This is the classic hotspot heuristic: complexity alone is a smell, churn
    alone is a smell, but complexity combined with churn is where defects and
    maintenance cost concentrate. When function-level blame data is available
    the rule uses the function's own churn; otherwise it falls back to the
    churn of the containing file.
    """

    id = "history/complexity-hotspot"
    title = "Complexity hotspot"
    description = (
        "Functions in the most frequently changed files that also carry high "
        "cyclomatic complexity deserve refactoring priority."
    )
    category = Category.HISTORY

    def analyze(self, context: AnalysisContext) -> list[Finding]:
        """Return one finding per complex function in a high-churn context."""
        history = context.history
        if history is None or not history.files:
            return []

        thresholds = context.config.thresholds
        churn_floor = max(
            thresholds.hotspot_min_commits,
            int(history.churn_percentile(0.75)),
        )

        findings: list[Finding] = []
        for module in context.modules:
            file_history = history.files.get(module.rel_path)
            if file_history is None or file_history.commits < churn_floor:
                continue
            findings.extend(_module_hotspots(context, module, file_history, thresholds))
        return findings


def _module_hotspots(
    context: AnalysisContext,
    module: ParsedModule,
    file_history: FileHistory,
    thresholds: Thresholds,
) -> list[Finding]:
    """Return hotspot findings for the complex functions of one module."""
    findings: list[Finding] = []
    for function in module.all_functions:
        if function.cyclomatic < thresholds.hotspot_min_cyclomatic:
            continue
        churn = context.function_churn.get(f"{module.rel_path}::{function.qualname}")
        finding = (
            _function_hotspot(module, function, churn, thresholds)
            if churn is not None
            else _file_hotspot(module, function, file_history, thresholds)
        )
        if finding is not None:
            findings.append(finding)
    return findings


def _function_hotspot(
    module: ParsedModule,
    function: FunctionMetrics,
    churn: FunctionChurn,
    thresholds: Thresholds,
) -> Finding | None:
    """Build a finding from the function's own blame history."""
    if churn.commits < thresholds.hotspot_min_commits:
        return None
    last = churn.last_modified.strftime("%Y-%m-%d") if churn.last_modified else "unknown"
    return Finding(
        rule_id=ComplexityHotspotRule.id,
        title=ComplexityHotspotRule.title,
        message=(
            f"`{function.qualname}` has cyclomatic complexity {function.cyclomatic} and "
            f"its lines changed in {churn.commits} commits by {churn.authors} author(s) "
            f"(last change {last})."
        ),
        severity=_severity(function, thresholds),
        category=ComplexityHotspotRule.category,
        path=module.rel_path,
        line=function.lineno,
        symbol=function.qualname,
        suggestion=_SUGGESTION,
        details={
            "scope": "function",
            "cyclomatic": function.cyclomatic,
            "commits": churn.commits,
            "authors": churn.authors,
            "lines": churn.lines,
            "last_modified": churn.last_modified.isoformat() if churn.last_modified else None,
        },
    )


def _file_hotspot(
    module: ParsedModule,
    function: FunctionMetrics,
    file_history: FileHistory,
    thresholds: Thresholds,
) -> Finding:
    """Build a finding from the containing file's churn."""
    return Finding(
        rule_id=ComplexityHotspotRule.id,
        title=ComplexityHotspotRule.title,
        message=(
            f"`{function.qualname}` has cyclomatic complexity {function.cyclomatic} and "
            f"lives in a file changed {file_history.commits} times "
            f"({file_history.churn} lines changed)."
        ),
        severity=_severity(function, thresholds),
        category=ComplexityHotspotRule.category,
        path=module.rel_path,
        line=function.lineno,
        symbol=function.qualname,
        suggestion=_SUGGESTION,
        details={
            "scope": "file",
            "cyclomatic": function.cyclomatic,
            "commits": file_history.commits,
            "churn": file_history.churn,
            "authors": file_history.author_count,
        },
    )


def _severity(function: FunctionMetrics, thresholds: Thresholds) -> Severity:
    """Return the hotspot severity for a function."""
    return Severity.HIGH if function.cyclomatic >= thresholds.cyclomatic_high else Severity.MEDIUM
