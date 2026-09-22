"""Tests for the agent CLI commands."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from repomind.cli.app import app

runner = CliRunner()

_REFERENCE = "design/god-object@samplepkg/god.py"


def test_explain_no_llm(sample_project: Path) -> None:
    result = runner.invoke(
        app,
        ["explain", _REFERENCE, str(sample_project), "--no-llm", "--no-history"],
    )

    assert result.exit_code == 0
    assert "design/god-object" in result.stdout
    assert "deterministic" in result.stdout


def test_explain_unknown_reference(sample_project: Path) -> None:
    result = runner.invoke(
        app,
        ["explain", "design/god-object@nope.py", str(sample_project), "--no-llm", "--no-history"],
    )

    assert result.exit_code == 2
    assert "no finding matches" in result.stdout


def test_explain_json_format(sample_project: Path) -> None:
    result = runner.invoke(
        app,
        [
            "explain",
            _REFERENCE,
            str(sample_project),
            "--no-llm",
            "--no-history",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["finding"]["rule_id"] == "design/god-object"
    assert payload["summary"]


def test_review_no_llm(sample_project: Path) -> None:
    result = runner.invoke(
        app,
        ["review", str(sample_project), "--no-llm", "--no-history", "--top", "3"],
    )

    assert result.exit_code == 0
    assert "need attention" in result.stdout


def test_review_markdown_output(sample_project: Path, tmp_path: Path) -> None:
    destination = tmp_path / "review.md"

    result = runner.invoke(
        app,
        [
            "review",
            str(sample_project),
            "--no-llm",
            "--no-history",
            "--format",
            "markdown",
            "--output",
            str(destination),
        ],
    )

    assert result.exit_code == 0
    assert "# Review notes" in destination.read_text(encoding="utf-8")


def test_explain_falls_back_when_llm_unavailable(sample_project: Path) -> None:
    result = runner.invoke(
        app,
        [
            "explain",
            _REFERENCE,
            str(sample_project),
            "--model",
            "ollama/definitely-not-running",
            "--no-history",
        ],
    )

    assert result.exit_code == 0
    assert "deterministic" in result.stdout
