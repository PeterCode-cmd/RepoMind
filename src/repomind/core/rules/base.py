"""Shared contracts for analysis rules."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from repomind.config import AnalysisConfig
from repomind.core.graph import DependencyGraph
from repomind.git.history import HistoryReport
from repomind.models.enums import Category, Severity
from repomind.models.findings import Finding
from repomind.models.metrics import ParsedModule


@dataclass(frozen=True, slots=True)
class AnalysisContext:
    """Immutable snapshot of everything a rule is allowed to inspect.

    Rules never read files or parse source code themselves; they work on
    prepared metrics, graphs and history data. This keeps rules fast,
    deterministic and easy to test.
    """

    root: Path
    modules: tuple[ParsedModule, ...]
    graph: DependencyGraph
    config: AnalysisConfig
    history: HistoryReport | None
    total_loc: int


class Rule(Protocol):
    """Contract implemented by every built-in rule."""

    @property
    def id(self) -> str:
        """Stable identifier, e.g. ``complexity/high-cyclomatic-complexity``."""
        ...

    @property
    def title(self) -> str:
        """Short human readable title."""
        ...

    @property
    def description(self) -> str:
        """One-sentence explanation of what the rule detects and why."""
        ...

    @property
    def category(self) -> Category:
        """Category used for report grouping."""
        ...

    def analyze(self, context: AnalysisContext) -> list[Finding]:
        """Inspect the context and return all findings for this rule."""
        ...


def scaled_severity(value: float, warn: float, high: float, critical: float) -> Severity:
    """Map a measured value onto a severity using three thresholds."""
    if value >= critical:
        return Severity.CRITICAL
    if value >= high:
        return Severity.HIGH
    if value >= warn:
        return Severity.MEDIUM
    return Severity.LOW
