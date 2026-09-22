"""Terminal, Markdown and JSON renderers for health trends."""

from __future__ import annotations

import json
from typing import Any

from rich import box
from rich.console import Console
from rich.table import Table
from rich.text import Text

from repomind.core.trend import MIN_TREND_SAMPLES, TrendReport

_GRADE_STYLES = {
    "A": "green",
    "B": "cyan",
    "C": "yellow",
    "D": "dark_orange",
    "F": "bold red",
}


def render_trend_terminal(report: TrendReport, console: Console) -> None:
    """Print the trend table and a summary line."""
    if not report.samples:
        console.print("[yellow]No samples to show.[/yellow]")
        return

    table = Table(
        title=f"Health trend (last {report.window} commits)",
        box=box.SIMPLE_HEAD,
        title_justify="left",
    )
    table.add_column("Date", no_wrap=True)
    table.add_column("Commit", no_wrap=True, style="cyan")
    table.add_column("Subject", overflow="fold", max_width=40)
    table.add_column("Score", justify="right")
    table.add_column("Grade", no_wrap=True)
    table.add_column("Findings", justify="right")
    table.add_column("Crit/High", justify="right")
    table.add_column("LOC", justify="right")

    for sample in report.samples:
        table.add_row(
            sample.committed_at.strftime("%Y-%m-%d"),
            sample.short_sha,
            sample.subject,
            str(sample.score),
            Text(sample.grade, style=_GRADE_STYLES.get(sample.grade, "white")),
            str(sample.findings),
            f"{sample.critical}/{sample.high}",
            f"{sample.loc:,}",
        )
    console.print(table)
    console.print(_summary(report))


def render_trend_markdown(report: TrendReport) -> str:
    """Render the trend as a Markdown document."""
    lines = [
        "# RepoMind trend",
        "",
        f"> Sampled {len(report.samples)} commits from the last {report.window}.",
        "",
        "| Date | Commit | Subject | Score | Grade | Findings | Critical | High | LOC |",
        "| --- | --- | --- | ---: | --- | ---: | ---: | ---: | ---: |",
    ]
    for sample in report.samples:
        subject = sample.subject.replace("|", "\\|")
        lines.append(
            f"| {sample.committed_at.strftime('%Y-%m-%d')} | `{sample.short_sha}` | {subject} "
            f"| {sample.score} | {sample.grade} | {sample.findings} | {sample.critical} "
            f"| {sample.high} | {sample.loc:,} |"
        )
    lines.extend(["", _summary_text(report), ""])
    return "\n".join(lines)


def render_trend_json(report: TrendReport) -> str:
    """Render the trend as a JSON document."""
    return json.dumps(report_to_dict(report), indent=2, ensure_ascii=False)


def report_to_dict(report: TrendReport) -> dict[str, Any]:
    """Convert a trend report into a JSON-serialisable dictionary."""
    return {
        "window": report.window,
        "delta": report.delta,
        "samples": [
            {
                "sha": sample.sha,
                "short_sha": sample.short_sha,
                "date": sample.committed_at.isoformat(),
                "subject": sample.subject,
                "score": sample.score,
                "grade": sample.grade,
                "findings": sample.findings,
                "critical": sample.critical,
                "high": sample.high,
                "loc": sample.loc,
                "files": sample.files,
            }
            for sample in report.samples
        ],
    }


def _summary(report: TrendReport) -> Text:
    """Build the styled summary line for the terminal."""
    first, last = report.samples[0], report.samples[-1]
    delta = report.delta
    style = "green" if delta > 0 else "red" if delta < 0 else "dim"
    text = Text()
    text.append(
        f"Score {first.score} ({first.short_sha}) -> {last.score} ({last.short_sha}) ",
        style="bold",
    )
    text.append(f"({delta:+d})", style=style)
    best, worst = report.best(), report.worst()
    if best is not None and worst is not None:
        text.append(
            f"  best {best.score} ({best.short_sha}), worst {worst.score} ({worst.short_sha})",
            style="dim",
        )
    return text


def _summary_text(report: TrendReport) -> str:
    """Build the plain summary line for Markdown."""
    first, last = report.samples[0], report.samples[-1]
    best, worst = report.best(), report.worst()
    parts = [f"Score {first.score} (`{first.short_sha}`) -> {last.score} (`{last.short_sha}`)"]
    if len(report.samples) >= MIN_TREND_SAMPLES:
        parts.append(f"change {report.delta:+d}")
    if best is not None and worst is not None:
        parts.append(
            f"best {best.score} (`{best.short_sha}`), worst {worst.score} (`{worst.short_sha}`)"
        )
    return "**" + " | ".join(parts) + "**"
