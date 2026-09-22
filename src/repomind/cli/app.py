"""RepoMind command-line interface."""

from __future__ import annotations

from dataclasses import replace
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer
from rich import box
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from repomind import __version__
from repomind.config import AnalysisConfig, load_config
from repomind.core.engine import AnalysisResult, StageUpdate, analyze_repository
from repomind.core.rules import default_rules
from repomind.errors import RepoMindError
from repomind.models.enums import Severity
from repomind.models.findings import Finding
from repomind.reporters.json_reporter import render_json
from repomind.reporters.markdown import render_markdown
from repomind.reporters.terminal import render_terminal_report

app = typer.Typer(
    name="repomind",
    help="Local-first code intelligence for Python repositories.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


class OutputFormat(StrEnum):
    """Supported report formats."""

    TERMINAL = "terminal"
    MARKDOWN = "markdown"
    JSON = "json"


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


def _version_callback(value: bool) -> None:
    """Print the version and exit when ``--version`` is passed."""
    if value:
        console.print(f"RepoMind {__version__}")
        raise typer.Exit


@app.callback()
def _root(
    version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            callback=_version_callback,
            is_eager=True,
            help="Show the version and exit.",
        ),
    ] = None,
) -> None:
    """Analyze Python repositories for complexity, dead code and risk."""


@app.command()
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
            help=(
                "Glob pattern to skip; repeatable. A pattern without '/' matches "
                "any path segment, e.g. -x migrations."
            ),
        ),
    ] = None,
    output_format: Annotated[
        OutputFormat,
        typer.Option("--format", "-f", help="Report format."),
    ] = OutputFormat.TERMINAL,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Write markdown/JSON reports to this file instead of stdout.",
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
        config = _build_config(path, config_path, exclude or [])
        result = _run_analysis(path, config, history)
    except RepoMindError as error:
        console.print(f"[bold red]error:[/bold red] {error}")
        raise typer.Exit(code=2) from error

    findings = result.findings_at_or_above(min_severity.severity)
    _emit_report(result, findings, output_format=output_format, output=output, top=top)

    if fail_under is not None and result.score.value < fail_under:
        console.print(
            f"[bold red]Health score {result.score.value} is below "
            f"--fail-under {fail_under}.[/bold red]"
        )
        raise typer.Exit(code=1)


@app.command()
def rules() -> None:
    """List the built-in analysis rules."""
    console.print("[bold]Built-in rules[/bold]")
    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    table.add_column(style="cyan", no_wrap=True)
    table.add_column()
    for rule in default_rules():
        table.add_row(
            rule.id,
            f"[bold]{rule.title}[/bold]\n"
            f"[dim]{rule.description}[/dim]\n"
            f"[dim]category: {rule.category.value}[/dim]",
        )
    console.print(table)


def _build_config(
    path: Path,
    config_path: Path | None,
    exclude: list[str],
) -> AnalysisConfig:
    """Load configuration and merge CLI exclude patterns into it."""
    config = load_config(path, config_file=config_path)
    if exclude:
        config = replace(config, exclude=(*config.exclude, *exclude))
    return config


def _run_analysis(
    path: Path,
    config: AnalysisConfig,
    history: bool | None,
) -> AnalysisResult:
    """Run the engine while rendering a live progress spinner."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    ) as progress:
        task_id = progress.add_task("Discovering Python files...", total=None)

        def on_stage(update: StageUpdate) -> None:
            progress.update(
                task_id,
                description=_stage_label(update),
                total=update.total or None,
                completed=update.current if update.total else 0,
            )

        return analyze_repository(
            path,
            config=config,
            use_history=history,
            progress=on_stage,
        )


def _stage_label(update: StageUpdate) -> str:
    """Format a stage update as a progress description."""
    if update.total:
        return f"{update.stage.capitalize()} ({update.current}/{update.total})..."
    return f"{update.stage.capitalize()}..."


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


def main() -> None:
    """Run the RepoMind CLI."""
    app(prog_name="repomind")
