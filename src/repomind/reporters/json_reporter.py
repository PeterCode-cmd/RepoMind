"""JSON report generation for machine-readable output."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import asdict
from typing import Any

from repomind import __version__
from repomind.core.baseline import fingerprint
from repomind.core.engine import AnalysisResult
from repomind.models.enums import Severity
from repomind.models.findings import Finding


def render_json(
    result: AnalysisResult,
    *,
    findings: Sequence[Finding] | None = None,
    indent: int = 2,
) -> str:
    """Render the analysis result as a JSON document."""
    return json.dumps(
        result_to_dict(result, findings=findings),
        indent=indent,
        ensure_ascii=False,
    )


def result_to_dict(
    result: AnalysisResult,
    *,
    findings: Sequence[Finding] | None = None,
) -> dict[str, Any]:
    """Convert an analysis result into a JSON-serialisable dictionary."""
    selected = list(result.findings if findings is None else findings)
    new_fingerprints = (
        frozenset(fingerprint(finding) for finding in result.new_findings)
        if result.baseline_size is not None
        else None
    )
    return {
        "tool": {"name": "repomind", "version": __version__},
        "repository": {
            "root": str(result.root),
            "files": result.file_count,
            "source_lines": result.total_loc,
        },
        "score": {
            "value": result.score.value,
            "grade": result.score.grade,
            "penalty": result.score.penalty,
            "density": result.score.density,
            "severity_counts": {
                severity.label: result.score.counts[severity] for severity in Severity
            },
        },
        "graph": {
            "modules": result.graph.module_count,
            "internal_imports": result.graph.edge_count,
            "cycles": [list(cycle) for cycle in result.graph.cycles()],
            "external_packages": dict(result.graph.external_imports.most_common()),
            "instability": _instability_to_dict(result),
        },
        "call_graph": _call_graph_to_dict(result),
        "history": _history_to_dict(result),
        "function_churn": _function_churn_to_dict(result),
        "baseline": _baseline_to_dict(result),
        "scope": result.scope_label,
        "findings": [
            _finding_to_dict(
                finding,
                is_new=(
                    None if new_fingerprints is None else fingerprint(finding) in new_fingerprints
                ),
            )
            for finding in selected
        ],
        "suppressed": [_finding_to_dict(finding) for finding in result.suppressed],
        "warnings": list(result.warnings),
        "duration_seconds": round(result.duration_seconds, 4),
        "thresholds": asdict(result.config.thresholds),
    }


def _finding_to_dict(finding: Finding, *, is_new: bool | None = None) -> dict[str, Any]:
    """Convert one finding into a JSON-serialisable dictionary."""
    return {
        "rule_id": finding.rule_id,
        "title": finding.title,
        "message": finding.message,
        "severity": finding.severity.label,
        "severity_level": int(finding.severity),
        "category": finding.category.value,
        "path": finding.path,
        "line": finding.line,
        "symbol": finding.symbol,
        "suggestion": finding.suggestion,
        "details": finding.details,
        "is_new": is_new,
    }


def _instability_to_dict(result: AnalysisResult) -> list[dict[str, Any]]:
    """Convert the most unstable coupled modules into a JSON-serialisable list."""
    graph = result.graph
    fan_in, fan_out = graph.fan_in(), graph.fan_out()
    return [
        {
            "module": module,
            "instability": round(value, 3),
            "afferent": fan_in[module],
            "efferent": fan_out[module],
        }
        for module, value in graph.top_unstable(limit=5)
    ]


def _call_graph_to_dict(result: AnalysisResult) -> dict[str, Any]:
    """Convert call graph statistics into a JSON-serialisable dictionary."""
    graph = result.call_graph
    return {
        "functions": graph.function_count,
        "edges": graph.edge_count,
        "top_fan_in": [
            {"symbol": symbol, "callers": count} for symbol, count in graph.top_fan_in(limit=10)
        ],
    }


def _function_churn_to_dict(result: AnalysisResult) -> list[dict[str, Any]]:
    """Convert function-level churn into a JSON-serialisable list."""
    entries: list[dict[str, Any]] = []
    for key, churn in sorted(result.function_churn.items()):
        path, separator, symbol = key.partition("::")
        entries.append(
            {
                "path": path,
                "symbol": symbol if separator else key,
                "commits": churn.commits,
                "authors": churn.authors,
                "lines": churn.lines,
                "last_modified": (churn.last_modified.isoformat() if churn.last_modified else None),
            }
        )
    return entries


def _baseline_to_dict(result: AnalysisResult) -> dict[str, Any] | None:
    """Convert baseline statistics into a JSON-serialisable dictionary."""
    if result.baseline_size is None:
        return None
    return {
        "known": len(result.findings) - len(result.new_findings),
        "new": len(result.new_findings),
        "accepted": result.baseline_size,
    }


def _history_to_dict(result: AnalysisResult) -> dict[str, Any] | None:
    """Convert the Git history report into a JSON-serialisable dictionary."""
    history = result.history
    if history is None:
        return None
    files = sorted(
        history.files.values(),
        key=lambda entry: (-entry.commits, -entry.churn, entry.rel_path),
    )
    return {
        "total_commits": history.total_commits,
        "max_commits": history.max_commits,
        "head_sha": history.head_sha,
        "branch": history.branch,
        "files": [
            {
                "path": entry.rel_path,
                "commits": entry.commits,
                "insertions": entry.insertions,
                "deletions": entry.deletions,
                "churn": entry.churn,
                "authors": entry.author_count,
                "last_modified": (entry.last_modified.isoformat() if entry.last_modified else None),
            }
            for entry in files
        ],
    }
