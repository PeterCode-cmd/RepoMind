"""The ``repomind analyze`` command and its rendering helpers."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from repomind.cli.common import build_config, resolve_baseline, run_engine
from repomind.cli.console import console
from repomind.core.baseline import Baseline
from repomind.core.engine import AnalysisOptions, AnalysisResult, AnalysisScope
from repomind.errors import RepoMindError
from repomind.git.diff import changed_paths
from repomind.models.enums import Severity
from repomind.models.findings import Finding
from repomind.reporters.html import render_html
from repomind.reporters.json_reporter import render_json
from repomind.reporters.markdown import render_markdown
from repomind.reporters.sarif import render_sarif
from repomind.reporters.terminal import render_terminal_report


class OutputFormat(StrEnum):
    """Supported report formats."""

    TERMINAL = "terminal"
    MARKDOWN = "markdown"
    JSON = "json"
    SARIF = "sarif"
    HTML = "html"


class SeverityOption(StrEnum):
    """Severity levels accepted on the command line, lowest first."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def severity(self) -> Severity:
        """Return the corresponding :class:`~repomind.models.enums.Severity`."""
        return Severity[self.name]


def analyze(
    path: Annotated[
        Path,
        typer.Argument(
            help="Repository root to analyze.",
            exists=True,
            file_okay=False,
            resolve_path=True,
        ),
    ] = Path(),
    exclude: Annotated[
        list[str] | None,
        typer.Option(
            "--exclude",
            "-x",
            help="Glob pattern to skip; repeatable. A pattern without '/' matches any segment.",
        ),
    ] = None,
    output_format: Annotated[
        OutputFormat,
        typer.Option(
            "--format",
            "-f",
            help="Report format: terminal, markdown, json, sarif or html.",
        ),
    ] = OutputFormat.TERMINAL,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Write markdown/JSON/SARIF reports to this file instead of stdout.",
        ),
    ] = None,
    min_severity: Annotated[
        SeverityOption,
        typer.Option("--min-severity", help="Hide findings below this severity."),
    ] = SeverityOption.INFO,
    top: Annotated[
        int,
        typer.Option("--top", min=1, help="Maximum number of findings to show."),
    ] = 25,
    history: Annotated[
        bool | None,
        typer.Option(
            "--history/--no-history",
            help="Enable or disable Git history analysis (default: auto).",
        ),
    ] = None,
    config_path: Annotated[
        Path | None,
        typer.Option(
            "--config",
            exists=True,
            dir_okay=False,
            help="Explicit configuration file (default: repomind.toml or pyproject.toml).",
        ),
    ] = None,
    baseline_path: Annotated[
        Path | None,
        typer.Option(
            "--baseline",
            exists=True,
            dir_okay=False,
            help="Baseline file of accepted findings (default: .repomind-baseline.json).",
        ),
    ] = None,
    no_baseline: Annotated[
        bool,
        typer.Option("--no-baseline", help="Ignore an existing baseline file."),
    ] = False,
    since: Annotated[
        str | None,
        typer.Option(
            "--since",
            help="Only analyze Python files changed since this Git revision.",
        ),
    ] = None,
    fail_on_new: Annotated[
        bool,
        typer.Option(
            "--fail-on-new",
            help="Exit with code 1 when findings are not accepted by the baseline.",
        ),
    ] = False,
    fail_under: Annotated[
        int | None,
        typer.Option(
            "--fail-under",
            min=0,
            max=100,
            help="Exit with code 1 when the health score is below this value.",
        ),
    ] = None,
) -> None:
    """Analyze a Python repository and report on code health."""
    try:
        config = build_config(path, config_path, exclude or [])
        baseline = resolve_baseline(path, baseline_path, use_baseline=not no_baseline)
        changed = changed_paths(path, since) if since is not None else None
        options = _analysis_options(baseline, changed, since)
        result = run_engine(path, config, use_history=history, options=options)
    except RepoMindError as error:
        console.print(f"[bold red]error:[/bold red] {error}")
        raise typer.Exit(code=2) from error

    if since is not None and result.file_count == 0:
        console.print(f"[yellow]No Python files changed since {since}.[/yellow]")

    findings = result.findings_at_or_above(min_severity.severity)
    _emit_report(result, findings, output_format=output_format, output=output, top=top)

    failures = _gate_failures(result, fail_under=fail_under, fail_on_new=fail_on_new)
    if failures:
        for failure in failures:
            console.print(f"[bold red]{failure}[/bold red]")
        raise typer.Exit(code=1)


def _gate_failures(
    result: AnalysisResult,
    *,
    fail_under: int | None,
    fail_on_new: bool,
) -> list[str]:
    """Return the reasons CI should fail for this result."""
    failures: list[str] = []
    if fail_under is not None and result.score.value < fail_under:
        failures.append(f"Health score {result.score.value} is below --fail-under {fail_under}.")
    if fail_on_new:
        new_count = (
            len(result.new_findings) if result.baseline_size is not None else len(result.findings)
        )
        if new_count:
            failures.append(f"{new_count} finding(s) are not accepted by the baseline.")
    return failures


def _analysis_options(
    baseline: Baseline | None,
    changed: frozenset[str] | None,
    since: str | None,
) -> AnalysisOptions:
    """Combine baseline and diff scope into pipeline options."""
    scope = (
        AnalysisScope(paths=changed, label=since)
        if changed is not None and since is not None
        else None
    )
    return AnalysisOptions(baseline=baseline, scope=scope)


def _emit_report(
    result: AnalysisResult,
    findings: list[Finding],
    *,
    output_format: OutputFormat,
    output: Path | None,
    top: int,
) -> None:
    """Render the report to the terminal, stdout or a file."""
    if output_format is OutputFormat.TERMINAL:
        render_terminal_report(result, console, findings=findings, top=top)
        return

    if output_format is OutputFormat.JSON:
        text = render_json(result, findings=findings)
    elif output_format is OutputFormat.SARIF:
        text = render_sarif(result, findings=findings)
    elif output_format is OutputFormat.HTML:
        text = render_html(result, findings=findings)
    else:
        text = render_markdown(result, findings=findings, top=top)

    if output is None:
        _print_document(text)
        return

    output.write_text(text, encoding="utf-8")
    console.print(f"[green]Report written to[/green] {output}")


def _print_document(text: str) -> None:
    """Print a document to stdout, degrading characters the stream cannot encode.

    Windows consoles may use a legacy code page (for example cp1250) where
    characters such as em dashes raise ``UnicodeEncodeError`` mid-render.
    """
    stream = console.file
    encoding = getattr(stream, "encoding", None) or "utf-8"
    try:
        text.encode(encoding)
    except UnicodeEncodeError:
        text = text.encode(encoding, errors="replace").decode(encoding, errors="replace")
    except LookupError:
        pass
    console.print(text, markup=False, highlight=False, soft_wrap=True)
