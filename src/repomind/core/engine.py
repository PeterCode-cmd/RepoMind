"""Analysis pipeline orchestration.

The engine glues the pipeline stages together and is the only module the CLI
needs to call:

1. discover Python files,
2. parse each file into metrics,
3. build the module dependency graph,
4. analyze Git history (optional),
5. run every registered rule,
6. score the repository.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from repomind.config import AnalysisConfig, load_config
from repomind.core.discovery import find_python_files
from repomind.core.graph import DependencyGraph
from repomind.core.pyparser import parse_module
from repomind.core.rules import default_rules
from repomind.core.rules.base import AnalysisContext
from repomind.core.scoring import HealthScore, compute_health_score
from repomind.core.suppression import apply_suppressions, parse_suppressions
from repomind.errors import RepositoryNotFoundError
from repomind.git.history import HistoryReport, analyze_history
from repomind.models.enums import Severity
from repomind.models.findings import Finding, sort_findings
from repomind.models.metrics import ParsedModule


@dataclass(frozen=True, slots=True)
class StageUpdate:
    """Progress notification emitted between pipeline stages.

    ``total`` is zero for stages with unknown or irrelevant size, which lets
    the CLI render an indeterminate spinner.
    """

    stage: str
    current: int = 0
    total: int = 0


ProgressCallback = Callable[[StageUpdate], None]


@dataclass(slots=True)
class AnalysisResult:
    """Everything produced by a single analysis run."""

    root: Path
    config: AnalysisConfig
    modules: list[ParsedModule]
    graph: DependencyGraph
    findings: list[Finding]
    suppressed: list[Finding]
    score: HealthScore
    history: HistoryReport | None
    duration_seconds: float
    warnings: list[str]

    @property
    def file_count(self) -> int:
        """Return the number of analyzed Python files."""
        return len(self.modules)

    @property
    def total_loc(self) -> int:
        """Return the total number of source lines of code."""
        return sum(module.loc for module in self.modules)

    def findings_at_or_above(self, severity: Severity) -> list[Finding]:
        """Return findings with a severity of at least *severity*."""
        return [finding for finding in self.findings if finding.severity >= severity]


def analyze_repository(
    root: Path,
    *,
    config: AnalysisConfig | None = None,
    use_history: bool | None = None,
    progress: ProgressCallback | None = None,
) -> AnalysisResult:
    """Run the full analysis pipeline over *root*.

    Args:
        root: Repository root to analyze.
        config: Explicit configuration; discovered from the repository when
            omitted.
        use_history: Force Git history analysis on or off. ``None`` (default)
            follows ``config.use_git_history``.
        progress: Optional callback receiving :class:`StageUpdate` events.

    Returns:
        The complete :class:`AnalysisResult`.

    Raises:
        RepositoryNotFoundError: If *root* does not exist or is not a directory.
    """
    start = time.perf_counter()
    root = root.resolve()
    if not root.is_dir():
        raise RepositoryNotFoundError(f"{root} is not a directory")

    config = config or load_config(root)
    history_enabled = config.use_git_history if use_history is None else use_history

    _notify(progress, "discovering", 0, 0)
    files = find_python_files(root, exclude=config.exclude)

    modules: list[ParsedModule] = []
    for index, path in enumerate(files, start=1):
        _notify(progress, "parsing", index, len(files))
        modules.append(parse_module(path, root))

    _notify(progress, "graph", 1, 1)
    graph = DependencyGraph.build(modules)

    history: HistoryReport | None = None
    if history_enabled and modules:
        _notify(progress, "history", 0, 0)
        history = analyze_history(
            root,
            paths={module.rel_path for module in modules},
            max_commits=config.history_commits,
        )

    context = AnalysisContext(
        root=root,
        modules=tuple(modules),
        graph=graph,
        config=config,
        history=history,
        total_loc=sum(module.loc for module in modules),
    )

    _notify(progress, "rules", 0, 0)
    findings, warnings = _run_rules(context)
    findings, suppressed = _apply_suppressions(config, findings, warnings)
    score = compute_health_score(findings, context.total_loc)

    return AnalysisResult(
        root=root,
        config=config,
        modules=modules,
        graph=graph,
        findings=findings,
        suppressed=suppressed,
        score=score,
        history=history,
        duration_seconds=time.perf_counter() - start,
        warnings=warnings,
    )


def _run_rules(context: AnalysisContext) -> tuple[list[Finding], list[str]]:
    """Run every registered rule, isolating rule failures from the run."""
    findings: list[Finding] = []
    warnings: list[str] = []
    for rule in default_rules():
        try:
            findings.extend(rule.analyze(context))
        except Exception as exc:  # a broken rule must not abort the whole run
            warnings.append(f"rule {rule.id} failed: {exc}")
    return sort_findings(findings), warnings


def _apply_suppressions(
    config: AnalysisConfig,
    findings: list[Finding],
    warnings: list[str],
) -> tuple[list[Finding], list[Finding]]:
    """Remove findings matched by ``ignore`` entries and warn about typos."""
    suppressions = parse_suppressions(config.ignore)
    if not suppressions:
        return findings, []

    known_rule_ids = {rule.id for rule in default_rules()}
    warnings.extend(
        f"ignore entry references unknown rule: {rule_id}"
        for rule_id in sorted({entry.rule_id for entry in suppressions} - known_rule_ids)
    )

    return apply_suppressions(findings, suppressions)


def _notify(callback: ProgressCallback | None, stage: str, current: int, total: int) -> None:
    """Emit a :class:`StageUpdate` when a callback is registered."""
    if callback is not None:
        callback(StageUpdate(stage=stage, current=current, total=total))
