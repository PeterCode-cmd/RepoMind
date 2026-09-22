"""The ``repomind trend`` command."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from repomind.cli.console import console
from repomind.config import AnalysisConfig, load_config
from repomind.core.engine import StageUpdate
from repomind.core.trend import DEFAULT_SAMPLES, DEFAULT_WINDOW, TrendReport, build_trend
from repomind.errors import RepoMindError
from repomind.reporters.trend import (
    render_trend_json,
    render_trend_markdown,
    render_trend_terminal,
)


class TrendFormat(StrEnum):
    """Supported trend report formats."""

    TERMINAL = "terminal"
    MARKDOWN = "markdown"
    JSON = "json"


def trend(
    path: Annotated[
        Path,
        typer.Argument(
            help="Repository root to analyze.",
            exists=True,
            file_okay=False,
            resolve_path=True,
        ),
    ] = Path(),
    samples: Annotated[
        int,
        typer.Option("--samples", min=2, help="Number of commits to sample."),
    ] = DEFAULT_SAMPLES,
    commits: Annotated[
        int,
        typer.Option("--commits", min=1, help="How far back (in commits) samples are taken from."),
    ] = DEFAULT_WINDOW,
    output_format: Annotated[
        TrendFormat,
        typer.Option("--format", "-f", help="Report format: terminal, markdown or json."),
    ] = TrendFormat.TERMINAL,
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Write markdown/JSON reports to this file."),
    ] = None,
    config_path: Annotated[
        Path | None,
        typer.Option(
            "--config",
            exists=True,
            dir_okay=False,
            help="Explicit configuration file applied to every sample.",
        ),
    ] = None,
) -> None:
    """Show the health score across sampled commits."""
    try:
        config = load_config(path, config_file=config_path)
        report = _run_trend(path, config, samples, commits)
    except RepoMindError as error:
        console.print(f"[bold red]error:[/bold red] {error}")
        raise typer.Exit(code=2) from error

    if not report.samples:
        console.print("[yellow]No commits to analyze.[/yellow]")
        return

    if output_format is TrendFormat.TERMINAL:
        render_trend_terminal(report, console)
        return

    text = (
        render_trend_json(report)
        if output_format is TrendFormat.JSON
        else render_trend_markdown(report)
    )
    if output is None:
        console.print(text, markup=False, highlight=False, soft_wrap=True)
        return
    output.write_text(text, encoding="utf-8")
    console.print(f"[green]Report written to[/green] {output}")


def _run_trend(
    path: Path,
    config: AnalysisConfig,
    samples: int,
    commits: int,
) -> TrendReport:
    """Run the trend with a live progress spinner."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    ) as progress:
        task_id = progress.add_task("Sampling commits...", total=None)

        def on_stage(update: StageUpdate) -> None:
            progress.update(
                task_id,
                description=f"Analyzing {update.stage} ({update.current}/{update.total})...",
                total=update.total or None,
                completed=update.current,
            )

        return build_trend(
            path,
            config=config,
            samples=samples,
            window=commits,
            progress=on_stage,
        )
