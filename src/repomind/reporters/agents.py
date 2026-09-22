"""Renderers for agent output: explanations and review notes."""

from __future__ import annotations

import json
from typing import Any

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from repomind.agents.explain import Explanation
from repomind.agents.review import ReviewNotes

_SEVERITY_STYLES = {
    "critical": "bold red",
    "high": "dark_orange",
    "medium": "yellow",
    "low": "blue",
    "info": "dim",
}


def render_explanation_terminal(explanation: Explanation, console: Console) -> None:
    """Print an explanation panel with why, risks and actions sections."""
    facts = explanation.facts
    location = f"{facts.path}:{facts.line}" if facts.line else facts.path
    console.print(
        Panel(
            Text(facts.message, style="bold"),
            title=f"[bold]{facts.rule_id}[/bold]",
            subtitle=f"{facts.severity.upper()} | {location}",
            border_style="cyan",
        )
    )
    console.print(explanation.summary)
    _print_section(console, "Why", explanation.why)
    _print_section(console, "Risks", explanation.risks)
    _print_section(console, "Actions", explanation.actions)
    for note in explanation.notes:
        console.print(f"[yellow]note:[/yellow] {note}")
    console.print(f"[dim]model: {explanation.model or 'deterministic'}[/dim]")


def _print_section(console: Console, title: str, values: tuple[str, ...]) -> None:
    """Print one titled bullet list."""
    if not values:
        return
    console.print(f"[bold]{title}[/bold]")
    for value in values:
        console.print(f"  - {value}")


def render_explanation_markdown(explanation: Explanation) -> str:
    """Render an explanation as Markdown."""
    facts = explanation.facts
    location = f"{facts.path}:{facts.line}" if facts.line else facts.path
    symbol = f" | symbol `{facts.symbol}`" if facts.symbol else ""
    lines = [
        f"# Explanation: {facts.title}",
        "",
        f"> `{facts.rule_id}` | {facts.severity.upper()} | `{location}`{symbol}",
        "",
        facts.message,
        "",
        explanation.summary,
        "",
    ]
    for title, values in (
        ("Why", explanation.why),
        ("Risks", explanation.risks),
        ("Actions", explanation.actions),
    ):
        if values:
            lines.append(f"## {title}")
            lines.append("")
            lines.extend(f"- {value}" for value in values)
            lines.append("")
    if explanation.notes:
        lines.append("## Notes")
        lines.append("")
        lines.extend(f"- {note}" for note in explanation.notes)
        lines.append("")
    lines.append(f"_model: {explanation.model or 'deterministic'}_")
    lines.append("")
    return "\n".join(lines)


def explanation_to_dict(explanation: Explanation) -> dict[str, Any]:
    """Convert an explanation into a JSON-serialisable dictionary."""
    return {
        "finding": explanation.facts.to_payload(),
        "summary": explanation.summary,
        "why": list(explanation.why),
        "risks": list(explanation.risks),
        "actions": list(explanation.actions),
        "model": explanation.model,
        "notes": list(explanation.notes),
    }


def render_explanation_json(explanation: Explanation) -> str:
    """Render an explanation as a JSON document."""
    return json.dumps(explanation_to_dict(explanation), indent=2, ensure_ascii=False)


def render_review_terminal(notes: ReviewNotes, console: Console) -> None:
    """Print the review summary and the prioritised items."""
    console.print(Text(notes.summary, style="bold"))
    if notes.items:
        table = Table(
            title=f"Review items ({len(notes.items)})",
            box=box.SIMPLE_HEAD,
            title_justify="left",
        )
        table.add_column("Severity", no_wrap=True)
        table.add_column("Location", style="cyan", no_wrap=True)
        table.add_column("Rationale", overflow="fold", min_width=30)
        table.add_column("Action", overflow="fold", min_width=30)
        for item in notes.items:
            location = f"{item.path}:{item.line}" if item.line else item.path
            table.add_row(
                Text(item.severity.upper(), style=_SEVERITY_STYLES.get(item.severity, "white")),
                location,
                item.rationale,
                item.action,
            )
        console.print(table)
    for note in notes.notes:
        console.print(f"[yellow]note:[/yellow] {note}")
    console.print(f"[dim]model: {notes.model or 'deterministic'}[/dim]")


def render_review_markdown(notes: ReviewNotes) -> str:
    """Render review notes as Markdown."""
    lines = ["# Review notes", "", notes.summary, ""]
    if notes.items:
        lines.extend(
            [
                "| Severity | Location | Rationale | Action |",
                "| --- | --- | --- | --- |",
            ]
        )
        for item in notes.items:
            location = f"{item.path}:{item.line}" if item.line else item.path
            rationale = item.rationale.replace("|", "\\|")
            action = item.action.replace("|", "\\|")
            lines.append(f"| {item.severity.upper()} | `{location}` | {rationale} | {action} |")
        lines.append("")
    if notes.notes:
        lines.append("## Notes")
        lines.append("")
        lines.extend(f"- {note}" for note in notes.notes)
        lines.append("")
    lines.append(f"_model: {notes.model or 'deterministic'}_")
    lines.append("")
    return "\n".join(lines)


def review_to_dict(notes: ReviewNotes) -> dict[str, Any]:
    """Convert review notes into a JSON-serialisable dictionary."""
    return {
        "summary": notes.summary,
        "items": [
            {
                "severity": item.severity,
                "path": item.path,
                "line": item.line,
                "rationale": item.rationale,
                "action": item.action,
            }
            for item in notes.items
        ],
        "model": notes.model,
        "notes": list(notes.notes),
        "findings": [fact.to_payload() for fact in notes.facts],
    }


def render_review_json(notes: ReviewNotes) -> str:
    """Render review notes as a JSON document."""
    return json.dumps(review_to_dict(notes), indent=2, ensure_ascii=False)
