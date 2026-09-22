"""The ``repomind doctor`` command: check the local environment."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich import box
from rich.console import Console
from rich.table import Table
from rich.text import Text

from repomind.cli.console import console
from repomind.core.doctor import CheckResult, run_checks

_STATUS_STYLES = {"ok": "green", "warn": "yellow", "missing": "bold red"}


def doctor(
    path: Annotated[
        Path,
        typer.Argument(
            help="Repository root to check.",
            exists=True,
            file_okay=False,
            resolve_path=True,
        ),
    ] = Path(),
    config_path: Annotated[
        Path | None,
        typer.Option("--config", exists=True, dir_okay=False, help="Explicit configuration file."),
    ] = None,
) -> None:
    """Check that RepoMind can run here and print what is missing."""
    checks = run_checks(path, config_file=config_path)
    _render(checks, console)
    if all(check.status == "ok" for check in checks):
        console.print("[green]Everything RepoMind needs is available.[/green]")


def _render(checks: list[CheckResult], console: Console) -> None:
    """Print the diagnostic table."""
    table = Table(title="RepoMind doctor", box=box.SIMPLE_HEAD, title_justify="left")
    table.add_column("Check", style="cyan", no_wrap=True)
    table.add_column("Status", no_wrap=True)
    table.add_column("Detail", overflow="fold")
    table.add_column("Hint", overflow="fold", style="dim")
    for check in checks:
        table.add_row(
            check.name,
            Text(check.status.upper(), style=_STATUS_STYLES.get(check.status, "white")),
            check.detail,
            check.hint or "",
        )
    console.print(table)
