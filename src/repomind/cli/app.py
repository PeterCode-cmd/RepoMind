"""RepoMind command-line interface."""

from __future__ import annotations

from typing import Annotated

import typer
from rich import box
from rich.table import Table

from repomind import __version__
from repomind.cli.agents import explain, review
from repomind.cli.analyze import analyze
from repomind.cli.baseline import baseline
from repomind.cli.console import console
from repomind.cli.index import index
from repomind.cli.search import search
from repomind.cli.trend import trend
from repomind.core.rules import default_rules

app = typer.Typer(
    name="repomind",
    help="Local-first code intelligence for Python repositories.",
    no_args_is_help=True,
    add_completion=False,
)
app.command()(analyze)
app.command()(baseline)
app.command()(trend)
app.command()(explain)
app.command()(review)
app.command()(search)
app.command()(index)


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


def main() -> None:
    """Run the RepoMind CLI."""
    app(prog_name="repomind")
