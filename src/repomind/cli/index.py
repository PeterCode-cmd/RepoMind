"""The ``repomind index`` command: build the local semantic index."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from repomind.cli.common import build_config, run_engine
from repomind.cli.console import console
from repomind.errors import RepoMindError
from repomind.semantic.chunking import CodeChunk, build_chunks
from repomind.semantic.embedder import Embedder, create_embedder

if TYPE_CHECKING:
    from repomind.semantic.index import IndexStats


def index(
    path: Annotated[
        Path,
        typer.Argument(
            help="Repository root to index.",
            exists=True,
            file_okay=False,
            resolve_path=True,
        ),
    ] = Path(),
    rebuild: Annotated[
        bool,
        typer.Option("--rebuild", help="Ignore the existing index and embed everything."),
    ] = False,
    exclude: Annotated[
        list[str] | None,
        typer.Option("--exclude", "-x", help="Glob pattern to skip; repeatable."),
    ] = None,
    config_path: Annotated[
        Path | None,
        typer.Option("--config", exists=True, dir_okay=False, help="Explicit configuration file."),
    ] = None,
) -> None:
    """Build or refresh the local semantic index used by semantic search.

    Requires the semantic extra (pip install "repomind-analyzer[semantic]");
    the first run downloads the embedding model.
    """
    try:
        config = build_config(path, config_path, exclude or [])
        result = run_engine(path, config, use_history=False)
        chunks = build_chunks(result.modules)
        if not chunks:
            console.print("[yellow]No code chunks to index.[/yellow]")
            return
        embedder = create_embedder(config.semantic)
        stats = _build(path / config.semantic.index_dir, chunks, embedder, rebuild=rebuild)
    except RepoMindError as error:
        console.print(f"[bold red]error:[/bold red] {error}")
        raise typer.Exit(code=2) from error

    console.print(
        f"[green]Index ready[/green] {stats.path}\n"
        f"  model      {stats.model}\n"
        f"  chunks     {stats.chunks} ({stats.embedded} embedded, "
        f"{stats.reused} reused, {stats.removed} removed)\n"
        f"  dimensions {stats.dimensions}"
    )


def _build(
    index_dir: Path,
    chunks: list[CodeChunk],
    embedder: Embedder,
    *,
    rebuild: bool,
) -> IndexStats:
    """Run the index build with a live progress spinner."""
    from repomind.semantic.index import build_index

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    ) as progress:
        task_id = progress.add_task("Embedding chunks...", total=None)

        def on_batch(done: int, total: int) -> None:
            progress.update(
                task_id,
                description=f"Embedding chunks ({done}/{total})...",
                total=total,
                completed=done,
            )

        return build_index(index_dir, chunks, embedder, rebuild=rebuild, progress=on_batch)
