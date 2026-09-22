"""Tests for the report renderers."""

from __future__ import annotations

import json
from io import StringIO
from pathlib import Path

from rich.console import Console

from repomind.config import AnalysisConfig
from repomind.core.engine import AnalysisResult, analyze_repository
from repomind.reporters.json_reporter import render_json, result_to_dict
from repomind.reporters.markdown import render_markdown
from repomind.reporters.terminal import render_terminal_report


def _result(sample_project: Path) -> AnalysisResult:
    return analyze_repository(sample_project, use_history=False)


def test_markdown_contains_key_sections(sample_project: Path) -> None:
    markdown = render_markdown(_result(sample_project))

    assert "# RepoMind report" in markdown
    assert "## Executive summary" in markdown
    assert "## Findings" in markdown
    assert "## Dependency graph" in markdown
    assert "### design" in markdown
    assert "Health score" in markdown


def test_markdown_respects_top_limit(sample_project: Path) -> None:
    result = _result(sample_project)
    full = render_markdown(result, top=1000)
    limited = render_markdown(result, top=1)
    assert len(limited) < len(full)
    assert "more findings omitted" in limited


def test_json_is_valid_and_complete(sample_project: Path) -> None:
    payload = json.loads(render_json(_result(sample_project)))

    assert payload["tool"]["name"] == "repomind"
    assert payload["score"]["value"] <= 100
    assert payload["repository"]["files"] > 0
    assert payload["repository"]["source_lines"] > 0
    assert payload["graph"]["modules"] > 0
    assert payload["graph"]["cycles"] == [["samplepkg.a", "samplepkg.b"]]
    assert any(finding["rule_id"] == "design/god-object" for finding in payload["findings"])


def test_json_respects_filters(sample_project: Path) -> None:
    result = _result(sample_project)
    payload = result_to_dict(result, findings=[])
    assert payload["findings"] == []


def test_suppressed_findings_are_reported(sample_project: Path) -> None:
    baseline = _result(sample_project)
    config = AnalysisConfig(ignore=("design/god-object@samplepkg/god.py",))
    result = analyze_repository(sample_project, config=config, use_history=False)

    markdown = render_markdown(result)
    payload = json.loads(render_json(result))

    assert "## Suppressed findings (1)" in markdown
    assert [finding["rule_id"] for finding in payload["suppressed"]] == ["design/god-object"]
    assert all(finding["rule_id"] != "design/god-object" for finding in payload["findings"])
    assert result.score.penalty < baseline.score.penalty


def test_terminal_renders_to_console(sample_project: Path) -> None:
    stream = StringIO()
    console = Console(file=stream, force_terminal=False, width=140)

    render_terminal_report(_result(sample_project), console, top=5)
    output = stream.getvalue()

    assert "RepoMind" in output
    assert "grade" in output
    assert "Top findings" in output
    assert "Dependency graph" in output
