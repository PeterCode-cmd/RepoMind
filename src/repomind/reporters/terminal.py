"""Rich-powered terminal report."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from repomind import __version__
from repomind.core.engine import AnalysisResult
from repomind.models.enums import Severity
from repomind.models.findings import Finding

SEVERITY_STYLES: dict[Severity, str] = {
    Severity.INFO: "dim",
    Severity.LOW: "blue",
    Severity.MEDIUM: "yellow",
    Severity.HIGH: "dark_orange",
    Severity.CRITICAL: "bold red",
}

GRADE_STYLES: dict[str, str] = {
    "A": "green",
    "B": "cyan",
    "C": "yellow",
    "D": "dark_orange",
    "F": "bold red",
}


def render_terminal_report(
    result: AnalysisResult,
    console: Console,
    *,
    findings: Sequence[Finding] | None = None,
    top: int = 25,
) -> None:
    """Print the complete analysis report to *console*.

    Args:
        result: The analysis result to render.
        console: Rich console to write to.
        findings: Optional pre-filtered findings; defaults to all findings.
        top: Maximum number of findings shown in the detail table.
    """
    selected = list(result.findings if findings is None else findings)
    _render_header(result, console)
    _render_health(result, console)
    _render_summary(selected, console)
    _render_findings(selected, console, top=top)
    _render_baseline(result, console)
    _render_suppressed(result, console)
    _render_graph(result, console)
    _render_history(result, console)
    _render_warnings(result, console)
    _render_footer(console)


def _render_header(result: AnalysisResult, console: Console) -> None:
    """Render the repository overview panel."""
    info = Table.grid(padding=(0, 2))
    info.add_column(style="bold")
    info.add_column()
    info.add_row("Repository", str(result.root))
    info.add_row(
        "Python code",
        f"{result.file_count} files | {result.total_loc:,} source lines",
    )
    info.add_row("Duration", f"{result.duration_seconds:.2f} s")
    info.add_row("Git history", "analyzed" if result.history is not None else "skipped")
    console.print(
        Panel(
            info,
            title="[bold]RepoMind[/bold]",
            subtitle=f"v{__version__}",
            border_style="cyan",
        )
    )


def _render_health(result: AnalysisResult, console: Console) -> None:
    """Render the health score bar and grade."""
    score = result.score
    style = GRADE_STYLES.get(score.grade, "white")
    filled_char, empty_char = _bar_characters(console)
    filled = max(0, min(10, score.value // 10))
    bar = Text()
    bar.append(filled_char * filled, style=style)
    bar.append(empty_char * (10 - filled), style="grey50")
    bar.append(f"  {score.value}/100 | grade {score.grade}", style=f"bold {style}")
    console.print()
    console.print(bar)


def _bar_characters(console: Console) -> tuple[str, str]:
    """Return bar characters the console stream can safely encode."""
    encoding = getattr(console.file, "encoding", None) or "utf-8"
    try:
        "█░".encode(encoding)
    except (UnicodeEncodeError, LookupError):
        return "#", "-"
    return "█", "░"


def _render_summary(findings: Sequence[Finding], console: Console) -> None:
    """Render severity and category counts."""
    if not findings:
        console.print("[green]No findings above the configured thresholds.[/green]")
        return

    severity_counts = Counter(finding.severity for finding in findings)
    category_counts = Counter(finding.category for finding in findings)

    severity_table = Table(title="Severity", box=box.SIMPLE_HEAD, title_justify="left")
    severity_table.add_column("Level")
    severity_table.add_column("Count", justify="right")
    for severity in reversed(list(Severity)):
        count = severity_counts.get(severity, 0)
        if not count:
            continue
        severity_table.add_row(
            Text(severity.label.upper(), style=SEVERITY_STYLES[severity]),
            str(count),
        )

    category_table = Table(title="Category", box=box.SIMPLE_HEAD, title_justify="left")
    category_table.add_column("Group")
    category_table.add_column("Count", justify="right")
    for category, count in sorted(category_counts.items(), key=lambda item: item[0].value):
        category_table.add_row(category.value, str(count))

    console.print(severity_table)
    console.print(category_table)


def _render_findings(findings: Sequence[Finding], console: Console, *, top: int) -> None:
    """Render the ranked findings table."""
    if not findings:
        return

    table = Table(
        title=f"Top findings ({min(len(findings), top)} of {len(findings)})",
        box=box.SIMPLE_HEAD,
        title_justify="left",
    )
    table.add_column("Severity", no_wrap=True)
    table.add_column("Rule", style="dim", no_wrap=True)
    table.add_column("Location", style="cyan", no_wrap=True)
    table.add_column("Message", overflow="fold", min_width=24)

    for finding in findings[:top]:
        table.add_row(
            Text(finding.severity.label.upper(), style=SEVERITY_STYLES[finding.severity]),
            _shorten(finding.rule_id, 36),
            _shorten_location(finding.location),
            finding.message,
        )
    console.print(table)


def _shorten(text: str, limit: int) -> str:
    """Truncate *text* with an ASCII ellipsis marker."""
    if len(text) <= limit:
        return text
    return f"{text[: limit - 3]}..."


def _shorten_location(location: str, limit: int = 38) -> str:
    """Keep the informative tail of a path-like location."""
    if len(location) <= limit:
        return location
    tail = location[-(limit - 3) :]
    separator = tail.find("/")
    if separator != -1:
        tail = tail[separator + 1 :]
    return f"...{tail}"


def _render_baseline(result: AnalysisResult, console: Console) -> None:
    """Render known/new counts when a baseline is active."""
    if result.baseline_size is None:
        return
    known = len(result.findings) - len(result.new_findings)
    console.print(
        f"[dim]Baseline: {known} known, {len(result.new_findings)} new "
        f"({result.baseline_size} accepted entries).[/dim]"
    )


def _render_suppressed(result: AnalysisResult, console: Console) -> None:
    """Render a note about findings hidden by configuration."""
    if not result.suppressed:
        return
    console.print(
        f"[dim]{len(result.suppressed)} finding(s) suppressed by configuration "
        f"(details in --format json).[/dim]"
    )


def _render_graph(result: AnalysisResult, console: Console) -> None:
    """Render dependency graph statistics and detected cycles."""
    graph = result.graph
    if graph.module_count == 0:
        return

    table = Table(title="Dependency graph", box=box.SIMPLE_HEAD, title_justify="left")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_row("Internal modules", str(graph.module_count))
    table.add_row("Internal imports", str(graph.edge_count))
    table.add_row("Import cycles", str(len(graph.cycles())))
    table.add_row("External packages", str(len(graph.external_imports)))
    console.print(table)

    if graph.external_imports:
        top_external = ", ".join(name for name, _ in graph.external_imports.most_common(5))
        console.print(f"[dim]Most used external packages:[/dim] {top_external}")

    for cycle in graph.cycles():
        console.print(f"  [bold red]cycle[/bold red] {' <-> '.join(cycle)}")


def _render_history(result: AnalysisResult, console: Console) -> None:
    """Render the Git churn hotspots table."""
    history = result.history
    if history is None or not history.files:
        return

    window = history.total_commits
    branch = history.branch or "detached HEAD"
    table = Table(
        title=f"Change hotspots (last {window} commits on {branch})",
        box=box.SIMPLE_HEAD,
        title_justify="left",
    )
    table.add_column("File", style="cyan", overflow="fold")
    table.add_column("Commits", justify="right")
    table.add_column("Churn", justify="right")
    table.add_column("Authors", justify="right")
    table.add_column("Last change", no_wrap=True)
    table.add_column("Heat", justify="right")

    for entry, heat in history.hotspots(limit=5):
        last = entry.last_modified.strftime("%Y-%m-%d") if entry.last_modified else "-"
        table.add_row(
            entry.rel_path,
            str(entry.commits),
            str(entry.churn),
            str(entry.author_count),
            last,
            f"{heat:.0f}",
        )
    console.print(table)


def _render_warnings(result: AnalysisResult, console: Console) -> None:
    """Render engine warnings, if any."""
    if not result.warnings:
        return
    console.print("[yellow]Warnings[/yellow]")
    for warning in result.warnings:
        console.print(f"  [yellow]![/yellow] {warning}")


def _render_footer(console: Console) -> None:
    """Render hints about other report formats."""
    console.print(
        "[dim]Tip: use --format markdown --output report.md for a shareable report "
        "or --format json for machine-readable output.[/dim]"
    )
