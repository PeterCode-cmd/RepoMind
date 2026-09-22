"""The ``repomind baseline`` command."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Annotated

import typer

from repomind.cli.console import console
from repomind.config import load_config
from repomind.core.baseline import BASELINE_FILENAME, save_baseline
from repomind.core.engine import analyze_repository
from repomind.errors import RepoMindError


def baseline(
    path: Annotated[
        Path,
        typer.Argument(help="Repository root to analyze.", exists=True),
    ] = Path(),
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Baseline file to write."),
    ] = None,
    exclude: Annotated[
        list[str] | None,
        typer.Option("--exclude", "-x", help="Glob pattern to skip; repeatable."),
    ] = None,
    history: Annotated[
        bool | None,
        typer.Option("--history/--no-history", help="Git history analysis (default: auto)."),
    ] = None,
) -> None:
    """Accept all current findings as a baseline for --fail-on-new."""
    try:
        config = load_config(path)
        if exclude:
            config = replace(config, exclude=(*config.exclude, *exclude))
        result = analyze_repository(path, config=config, use_history=history)
    except RepoMindError as error:
        console.print(f"[bold red]error:[/bold red] {error}")
        raise typer.Exit(code=2) from error

    destination = output or (path / BASELINE_FILENAME)
    save_baseline(result.findings, destination)
    console.print(
        f"[green]Baseline written to[/green] {destination} "
        f"({len(result.findings)} accepted, {len(result.suppressed)} suppressed)."
    )
