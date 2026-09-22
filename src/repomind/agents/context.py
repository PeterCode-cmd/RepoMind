"""Context packs: the structured facts handed to agents.

Agents never read source code or re-run analysis. They receive findings with
their measured values, call-graph caller counts and function churn, plus a
repository summary, and their answers must stay inside those facts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from repomind.core.engine import AnalysisResult
from repomind.errors import RepoMindError
from repomind.models.findings import Finding


@dataclass(frozen=True, slots=True)
class FindingFacts:
    """One finding plus the facts an agent may rely on."""

    rule_id: str
    severity: str
    category: str
    title: str
    message: str
    path: str
    line: int | None
    symbol: str | None
    suggestion: str | None
    details: dict[str, Any]
    callers: int | None = None
    churn: dict[str, Any] | None = None

    def to_payload(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation of the facts."""
        return {
            "rule_id": self.rule_id,
            "severity": self.severity,
            "category": self.category,
            "title": self.title,
            "message": self.message,
            "path": self.path,
            "line": self.line,
            "symbol": self.symbol,
            "suggestion": self.suggestion,
            "details": self.details,
            "callers": self.callers,
            "churn": self.churn,
        }


@dataclass(frozen=True, slots=True)
class ContextPack:
    """Prompt-ready facts plus the paths an agent is allowed to cite."""

    task: str
    facts: tuple[FindingFacts, ...]
    repository: dict[str, Any] = field(default_factory=dict)
    scope: dict[str, Any] = field(default_factory=dict)

    @property
    def paths(self) -> frozenset[str]:
        """Return every path that appears in the context."""
        return frozenset(fact.path for fact in self.facts)

    def to_payload(self) -> dict[str, Any]:
        """Return the JSON payload embedded in prompts."""
        return {
            "task": self.task,
            "repository": self.repository,
            "scope": self.scope,
            "findings": [fact.to_payload() for fact in self.facts],
        }


def build_explain_pack(result: AnalysisResult, reference: str) -> ContextPack:
    """Build the pack for one finding addressed as ``rule-id@path[:line]``.

    Raises:
        RepoMindError: When *reference* is malformed or matches no finding.
    """
    rule_id, path, line = _parse_reference(reference)
    finding = _find_finding(result, rule_id, path, line)
    if finding is None:
        raise RepoMindError(f"no finding matches {reference!r}")
    return ContextPack(
        task="explain",
        facts=(_facts(result, finding),),
        repository=_repository_summary(result),
    )


def build_review_pack(
    result: AnalysisResult,
    *,
    limit: int,
    scope_label: str | None = None,
) -> ContextPack:
    """Build the pack for the findings that need review attention.

    When a baseline is active only new findings are included; otherwise every
    finding is a candidate. *limit* caps how many findings reach the model.
    """
    candidates = result.new_findings if result.baseline_size is not None else result.findings
    scope = {"since": scope_label} if scope_label is not None else {}
    return ContextPack(
        task="review",
        facts=tuple(_facts(result, finding) for finding in candidates[:limit]),
        repository=_repository_summary(result),
        scope=scope,
    )


def _parse_reference(reference: str) -> tuple[str, str | None, int | None]:
    """Split ``rule-id@path[:line]`` into its parts."""
    rule_id, _, rest = reference.partition("@")
    if not rule_id.strip():
        raise RepoMindError(f"invalid finding reference {reference!r}; use rule-id@path[:line]")
    if not rest:
        return rule_id.strip(), None, None
    path, _, line_text = rest.rpartition(":")
    if path and line_text.isdigit():
        return rule_id.strip(), path, int(line_text)
    return rule_id.strip(), rest, None


def _find_finding(
    result: AnalysisResult,
    rule_id: str,
    path: str | None,
    line: int | None,
) -> Finding | None:
    """Return the first finding matching the reference parts."""
    for finding in result.findings:
        if finding.rule_id != rule_id:
            continue
        if path is not None and finding.path != path:
            continue
        if line is not None and finding.line != line:
            continue
        return finding
    return None


def _facts(result: AnalysisResult, finding: Finding) -> FindingFacts:
    """Collect every fact known about one finding."""
    return FindingFacts(
        rule_id=finding.rule_id,
        severity=finding.severity.label,
        category=finding.category.value,
        title=finding.title,
        message=finding.message,
        path=finding.path,
        line=finding.line,
        symbol=finding.symbol,
        suggestion=finding.suggestion,
        details=dict(finding.details),
        callers=_callers(result, finding),
        churn=_churn(result, finding),
    )


def _callers(result: AnalysisResult, finding: Finding) -> int | None:
    """Return how many analyzed functions call the finding's symbol."""
    if finding.symbol is None or finding.symbol not in result.call_graph.edges:
        return None
    return result.call_graph.caller_count(finding.symbol)


def _churn(result: AnalysisResult, finding: Finding) -> dict[str, Any] | None:
    """Return function-level churn for the finding's symbol, if tracked."""
    if finding.symbol is None:
        return None
    entry = result.function_churn.get(f"{finding.path}::{finding.symbol}")
    if entry is None:
        return None
    return {
        "commits": entry.commits,
        "authors": entry.authors,
        "lines": entry.lines,
        "last_modified": entry.last_modified.isoformat() if entry.last_modified else None,
    }


def _repository_summary(result: AnalysisResult) -> dict[str, Any]:
    """Return the repository-level facts shared by all packs."""
    return {
        "root": result.root.name,
        "files": result.file_count,
        "source_lines": result.total_loc,
        "score": result.score.value,
        "grade": result.score.grade,
        "import_cycles": len(result.graph.cycles()),
    }
