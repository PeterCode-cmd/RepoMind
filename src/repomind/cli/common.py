"""Shared helpers for RepoMind CLI commands."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from repomind.cli.console import console
from repomind.config import AnalysisConfig, load_config
from repomind.core.baseline import BASELINE_FILENAME, Baseline, load_baseline
from repomind.core.engine import AnalysisOptions, AnalysisResult, StageUpdate, analyze_repository
from repomind.errors import ConfigurationError


def build_config(path: Path, config_path: Path | None, exclude: list[str]) -> AnalysisConfig:
    """Load configuration and merge CLI exclude patterns into it."""
    config = load_config(path, config_file=config_path)
    if exclude:
        config = replace(config, exclude=(*config.exclude, *exclude))
    return config


def resolve_baseline(
    path: Path,
    baseline_path: Path | None,
    *,
    use_baseline: bool,
) -> Baseline | None:
    """Load the requested baseline file, or auto-detect one in the repository.

    Raises:
        ConfigurationError: When an explicit baseline file does not exist.
    """
    if not use_baseline:
        return None
    candidate = baseline_path or (path / BASELINE_FILENAME)
    if not candidate.is_file():
        if baseline_path is not None:
            raise ConfigurationError(f"baseline file not found: {candidate}")
        return None
    return load_baseline(candidate)


def run_engine(
    path: Path,
    config: AnalysisConfig,
    *,
    use_history: bool | None = None,
    options: AnalysisOptions | None = None,
    description: str = "Discovering Python files...",
) -> AnalysisResult:
    """Run the analysis engine while rendering a live progress spinner."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    ) as progress:
        task_id = progress.add_task(description, total=None)

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
            use_history=use_history,
            options=options,
            progress=on_stage,
        )


def _stage_label(update: StageUpdate) -> str:
    """Format a stage update as a progress description."""
    if update.total:
        return f"{update.stage.capitalize()} ({update.current}/{update.total})..."
    return f"{update.stage.capitalize()}..."
