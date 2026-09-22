"""The ``repomind explain`` and ``repomind review`` commands."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from repomind.agents.client import LiteLLMClient, LLMClient
from repomind.agents.explain import Explanation, explain_finding
from repomind.agents.review import ReviewNotes, review_findings
from repomind.cli.common import build_config, resolve_baseline, run_engine
from repomind.cli.console import console
from repomind.config import AnalysisConfig
from repomind.core.baseline import Baseline
from repomind.core.engine import AnalysisOptions, AnalysisScope
from repomind.errors import RepoMindError
from repomind.git.diff import changed_paths
from repomind.reporters.agents import (
    render_explanation_json,
    render_explanation_markdown,
    render_explanation_terminal,
    render_review_json,
    render_review_markdown,
    render_review_terminal,
)


class AgentFormat(StrEnum):
    """Supported agent report formats."""

    TERMINAL = "terminal"
    MARKDOWN = "markdown"
    JSON = "json"


def explain(
    reference: Annotated[
        str,
        typer.Argument(
            help='Finding reference: "rule-id@path[:line]", e.g. "design/god-object@app.py:12".'
        ),
    ],
    path: Annotated[
        Path,
        typer.Argument(
            help="Repository root to analyze.",
            exists=True,
            file_okay=False,
            resolve_path=True,
        ),
    ] = Path(),
    model: Annotated[
        str | None,
        typer.Option("--model", help="LLM model in litellm format (default: [llm].model)."),
    ] = None,
    no_llm: Annotated[
        bool,
        typer.Option("--no-llm", help="Skip the model and print deterministic facts."),
    ] = False,
    output_format: Annotated[
        AgentFormat,
        typer.Option("--format", "-f", help="Report format: terminal, markdown or json."),
    ] = AgentFormat.TERMINAL,
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Write markdown/JSON reports to this file."),
    ] = None,
    config_path: Annotated[
        Path | None,
        typer.Option("--config", exists=True, dir_okay=False, help="Explicit configuration file."),
    ] = None,
    history: Annotated[
        bool | None,
        typer.Option("--history/--no-history", help="Git history analysis (default: auto)."),
    ] = None,
) -> None:
    """Explain one finding, using the configured LLM when available.

    Defaults to a local Ollama model; --model switches to any cloud provider
    (API key from the environment) and --no-llm prints deterministic facts.
    """
    try:
        config = build_config(path, config_path, [])
        result = run_engine(path, config, use_history=history)
        client, model_name = _client(config, model, no_llm)
        explanation = explain_finding(result, reference, client=client, model=model_name)
    except RepoMindError as error:
        console.print(f"[bold red]error:[/bold red] {error}")
        raise typer.Exit(code=2) from error

    _emit_explanation(explanation, output_format=output_format, output=output)


def review(
    path: Annotated[
        Path,
        typer.Argument(
            help="Repository root to analyze.",
            exists=True,
            file_okay=False,
            resolve_path=True,
        ),
    ] = Path(),
    since: Annotated[
        str | None,
        typer.Option("--since", help="Only review Python files changed since this Git revision."),
    ] = None,
    model: Annotated[
        str | None,
        typer.Option("--model", help="LLM model in litellm format (default: [llm].model)."),
    ] = None,
    no_llm: Annotated[
        bool,
        typer.Option("--no-llm", help="Skip the model and print the deterministic summary."),
    ] = False,
    top: Annotated[
        int,
        typer.Option("--top", min=1, help="Maximum number of findings in the review."),
    ] = 20,
    output_format: Annotated[
        AgentFormat,
        typer.Option("--format", "-f", help="Report format: terminal, markdown or json."),
    ] = AgentFormat.TERMINAL,
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Write markdown/JSON reports to this file."),
    ] = None,
    config_path: Annotated[
        Path | None,
        typer.Option("--config", exists=True, dir_okay=False, help="Explicit configuration file."),
    ] = None,
    history: Annotated[
        bool | None,
        typer.Option("--history/--no-history", help="Git history analysis (default: auto)."),
    ] = None,
) -> None:
    """Prioritise the findings that need attention, optionally only changed files.

    Uses the configured LLM (Ollama by default) and falls back to the
    deterministic summary with --no-llm or when no model is available.
    """
    try:
        config = build_config(path, config_path, [])
        baseline = resolve_baseline(path, None, use_baseline=True)
        changed = changed_paths(path, since) if since is not None else None
        options = _review_options(baseline, changed, since)
        result = run_engine(path, config, use_history=history, options=options)
        client, model_name = _client(config, model, no_llm)
        notes = review_findings(
            result,
            client=client,
            model=model_name,
            limit=min(top, config.llm.max_findings),
            scope_label=since,
        )
    except RepoMindError as error:
        console.print(f"[bold red]error:[/bold red] {error}")
        raise typer.Exit(code=2) from error

    _emit_review(notes, output_format=output_format, output=output)


def _review_options(
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


def _client(
    config: AnalysisConfig,
    model: str | None,
    no_llm: bool,
) -> tuple[LLMClient | None, str | None]:
    """Build the LLM client, or ``(None, None)`` for deterministic output."""
    if no_llm:
        return None, None
    resolved = model or config.llm.model
    return LiteLLMClient(model=resolved, timeout=config.llm.timeout), resolved


def _emit_explanation(
    explanation: Explanation,
    *,
    output_format: AgentFormat,
    output: Path | None,
) -> None:
    """Render an explanation to the terminal, stdout or a file."""
    if output_format is AgentFormat.TERMINAL:
        render_explanation_terminal(explanation, console)
        return
    text = (
        render_explanation_json(explanation)
        if output_format is AgentFormat.JSON
        else render_explanation_markdown(explanation)
    )
    _write_or_print(text, output)


def _emit_review(
    notes: ReviewNotes,
    *,
    output_format: AgentFormat,
    output: Path | None,
) -> None:
    """Render review notes to the terminal, stdout or a file."""
    if output_format is AgentFormat.TERMINAL:
        render_review_terminal(notes, console)
        return
    text = (
        render_review_json(notes)
        if output_format is AgentFormat.JSON
        else render_review_markdown(notes)
    )
    _write_or_print(text, output)


def _write_or_print(text: str, output: Path | None) -> None:
    """Write *text* to a file, or print it unwrapped to stdout."""
    if output is None:
        console.print(text, markup=False, highlight=False, soft_wrap=True)
        return
    output.write_text(text, encoding="utf-8")
    console.print(f"[green]Report written to[/green] {output}")
