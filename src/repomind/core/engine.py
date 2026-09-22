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
from collections.abc import Callable, Collection
from dataclasses import dataclass
from pathlib import Path

from repomind.config import AnalysisConfig, load_config
from repomind.core.baseline import Baseline
from repomind.core.discovery import find_python_files
from repomind.core.graph import DependencyGraph
from repomind.core.pyparser import parse_module
from repomind.core.rules import default_rules
from repomind.core.rules.base import AnalysisContext
from repomind.core.scoring import HealthScore, compute_health_score
from repomind.core.suppression import apply_suppressions, parse_suppressions
from repomind.errors import RepositoryNotFoundError
from repomind.git.blame import FunctionChurn, blame_functions
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


@dataclass(frozen=True, slots=True)
class AnalysisScope:
    """Restriction of an analysis run to a set of changed paths."""

    paths: frozenset[str]
    label: str


@dataclass(frozen=True, slots=True)
class AnalysisOptions:
    """Optional pipeline inputs: accepted findings and an analysis scope."""

    baseline: Baseline | None = None
    scope: AnalysisScope | None = None


@dataclass(slots=True)
class AnalysisResult:
    """Everything produced by a single analysis run."""

    root: Path
    config: AnalysisConfig
    modules: list[ParsedModule]
    graph: DependencyGraph
    findings: list[Finding]
    suppressed: list[Finding]
    new_findings: list[Finding]
    baseline_size: int | None
    scope_label: str | None
    score: HealthScore
    history: HistoryReport | None
    function_churn: dict[str, FunctionChurn]
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


@dataclass(frozen=True, slots=True)
class _GitInsights:
    """History report and function-level churn collected from Git."""

    history: HistoryReport | None
    function_churn: dict[str, FunctionChurn]


@dataclass(frozen=True, slots=True)
class _FindingsSummary:
    """Outcome of the rule, suppression, baseline and scoring stages."""

    findings: list[Finding]
    suppressed: list[Finding]
    new_findings: list[Finding]
    baseline_size: int | None
    score: HealthScore
    warnings: list[str]


def analyze_repository(
    root: Path,
    *,
    config: AnalysisConfig | None = None,
    use_history: bool | None = None,
    options: AnalysisOptions | None = None,
    progress: ProgressCallback | None = None,
) -> AnalysisResult:
    """Run the full analysis pipeline over *root*.

    Args:
        root: Repository root to analyze.
        config: Explicit configuration; discovered from the repository when omitted.
        use_history: Force Git history on/off; ``None`` follows the configuration.
        options: Accepted findings (baseline) and an optional path scope.
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

    options = options or AnalysisOptions()
    config = config or load_config(root)
    history_enabled = config.use_git_history if use_history is None else use_history
    scope = options.scope

    files = _discover_files(root, config, progress, only=scope.paths if scope else None)
    modules = _parse_modules(files, root, progress)
    graph = _build_graph(modules, progress)
    insights = _collect_git_insights(
        root, modules, config, enabled=history_enabled, progress=progress
    )
    context = _build_context(root, modules, graph, config, insights)
    summary = _analyze_context(context, config, options, progress)

    return AnalysisResult(
        root=root,
        config=config,
        modules=modules,
        graph=graph,
        findings=summary.findings,
        suppressed=summary.suppressed,
        new_findings=summary.new_findings,
        baseline_size=summary.baseline_size,
        scope_label=scope.label if scope else None,
        score=summary.score,
        history=insights.history,
        function_churn=insights.function_churn,
        duration_seconds=time.perf_counter() - start,
        warnings=summary.warnings,
    )


def _analyze_context(
    context: AnalysisContext,
    config: AnalysisConfig,
    options: AnalysisOptions,
    progress: ProgressCallback | None,
) -> _FindingsSummary:
    """Run rules, apply suppression and baseline, then score the repository."""
    _notify(progress, "rules", 0, 0)
    findings, warnings = _run_rules(context)
    findings, suppressed = _apply_suppressions(config, findings, warnings)
    new_findings, baseline_size = _compare_with_baseline(findings, options.baseline)
    score = compute_health_score(findings, context.total_loc)
    return _FindingsSummary(
        findings=findings,
        suppressed=suppressed,
        new_findings=new_findings,
        baseline_size=baseline_size,
        score=score,
        warnings=warnings,
    )


def _discover_files(
    root: Path,
    config: AnalysisConfig,
    progress: ProgressCallback | None,
    *,
    only: Collection[str] | None = None,
) -> list[Path]:
    """Run the discovery stage, optionally limited to specific paths."""
    _notify(progress, "discovering", 0, 0)
    files = find_python_files(root, exclude=config.exclude)
    if only is None:
        return files
    return [path for path in files if path.relative_to(root).as_posix() in only]


def _parse_modules(
    files: list[Path],
    root: Path,
    progress: ProgressCallback | None,
) -> list[ParsedModule]:
    """Parse every discovered file into metrics."""
    modules: list[ParsedModule] = []
    for index, path in enumerate(files, start=1):
        _notify(progress, "parsing", index, len(files))
        modules.append(parse_module(path, root))
    return modules


def _build_graph(modules: list[ParsedModule], progress: ProgressCallback | None) -> DependencyGraph:
    """Build the module dependency graph."""
    _notify(progress, "graph", 1, 1)
    return DependencyGraph.build(modules)


def _collect_history(
    root: Path,
    modules: list[ParsedModule],
    config: AnalysisConfig,
    *,
    enabled: bool,
    progress: ProgressCallback | None,
) -> HistoryReport | None:
    """Run the optional Git history stage."""
    if not enabled or not modules:
        return None
    _notify(progress, "history", 0, 0)
    return analyze_history(
        root,
        paths={module.rel_path for module in modules},
        max_commits=config.history_commits,
    )


def _collect_git_insights(
    root: Path,
    modules: list[ParsedModule],
    config: AnalysisConfig,
    *,
    enabled: bool,
    progress: ProgressCallback | None,
) -> _GitInsights:
    """Run the Git history and function-blame stages."""
    history = _collect_history(root, modules, config, enabled=enabled, progress=progress)
    churn = _collect_function_churn(root, modules, history, config, progress)
    return _GitInsights(history=history, function_churn=churn)


def _collect_function_churn(
    root: Path,
    modules: list[ParsedModule],
    history: HistoryReport | None,
    config: AnalysisConfig,
    progress: ProgressCallback | None,
) -> dict[str, FunctionChurn]:
    """Blame the hottest files so churn can be attributed to functions."""
    if history is None or config.blame_files <= 0:
        return {}
    candidates = [
        entry.rel_path
        for entry in history.top_churn(limit=config.blame_files)
        if entry.commits >= config.thresholds.hotspot_min_commits
    ]
    if not candidates:
        return {}

    _notify(progress, "blame", 0, 0)
    modules_by_path = {module.rel_path: module for module in modules}
    churn: dict[str, FunctionChurn] = {}
    for rel_path in candidates:
        module = modules_by_path.get(rel_path)
        if module is None or module.syntax_error is not None:
            continue
        for qualname, entry in blame_functions(root, rel_path, module.all_functions).items():
            churn[f"{rel_path}::{qualname}"] = entry
    return churn


def _build_context(
    root: Path,
    modules: list[ParsedModule],
    graph: DependencyGraph,
    config: AnalysisConfig,
    insights: _GitInsights,
) -> AnalysisContext:
    """Assemble the immutable snapshot passed to every rule."""
    return AnalysisContext(
        root=root,
        modules=tuple(modules),
        graph=graph,
        config=config,
        history=insights.history,
        function_churn=insights.function_churn,
        total_loc=sum(module.loc for module in modules),
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


def _compare_with_baseline(
    findings: list[Finding],
    baseline: Baseline | None,
) -> tuple[list[Finding], int | None]:
    """Return ``(new findings, baseline size)`` for an optional baseline."""
    if baseline is None:
        return [], None
    new_findings, _known = baseline.split(findings)
    return new_findings, baseline.size


def _notify(callback: ProgressCallback | None, stage: str, current: int, total: int) -> None:
    """Emit a :class:`StageUpdate` when a callback is registered."""
    if callback is not None:
        callback(StageUpdate(stage=stage, current=current, total=total))
