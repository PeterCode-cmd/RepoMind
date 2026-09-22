"""The :class:`Finding` model: a single explainable issue in the codebase."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from repomind.models.enums import Category, Severity


@dataclass(frozen=True, slots=True)
class Finding:
    """An actionable issue produced by a rule.

    Attributes:
        rule_id: Stable identifier of the rule that produced the finding.
        title: Short human readable title, usually the rule title.
        message: Explanation including the measured values.
        severity: Relative importance used for ranking and scoring.
        category: Coarse grouping used by summaries and reports.
        path: Repository-relative POSIX path of the affected file.
        line: One-based line number, when the finding is location specific.
        symbol: Qualified name of the affected function or class.
        suggestion: Short remediation hint.
        details: Machine readable extras (raw metric values and thresholds).
    """

    rule_id: str
    title: str
    message: str
    severity: Severity
    category: Category
    path: str
    line: int | None = None
    symbol: str | None = None
    suggestion: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def location(self) -> str:
        """Return a human readable ``file:line`` location."""
        return f"{self.path}:{self.line}" if self.line is not None else self.path

    def sort_key(self) -> tuple[int, str, int, str]:
        """Return a deterministic ordering key, most severe findings first."""
        return (-int(self.severity), self.path, self.line or 0, self.rule_id)


def sort_findings(findings: list[Finding]) -> list[Finding]:
    """Return a new list ordered by severity, path, line and rule id."""
    return sorted(findings, key=Finding.sort_key)
