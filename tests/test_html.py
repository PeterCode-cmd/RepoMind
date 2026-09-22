"""Tests for the self-contained HTML report."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from repomind.cli.app import app
from repomind.core.engine import AnalysisResult, analyze_repository
from repomind.reporters.html import _escape, render_html

runner = CliRunner()


def _result(sample_project: Path) -> AnalysisResult:
    return analyze_repository(sample_project, use_history=False)


def test_html_is_self_contained(sample_project: Path) -> None:
    document = render_html(_result(sample_project))

    assert document.startswith("<!DOCTYPE html>")
    assert "<style>" in document
    assert "<script>" in document
    assert "https://" not in document
    assert "http://" not in document


def test_html_contains_score_and_findings(sample_project: Path) -> None:
    result = _result(sample_project)

    document = render_html(result)

    assert f"{result.score.value}<small>/100" in document
    assert 'data-severity="critical"' in document
    assert "design/god-object" in document
    assert "samplepkg/god.py:12" in document


def test_html_escapes_content() -> None:
    assert _escape("<script>alert(1)</script>") == "&lt;script&gt;alert(1)&lt;/script&gt;"


def test_html_respects_top_limit(sample_project: Path) -> None:
    document = render_html(_result(sample_project), top=1)
    assert "more findings omitted" in document


def test_cli_writes_html_file(sample_project: Path, tmp_path: Path) -> None:
    destination = tmp_path / "report.html"

    result = runner.invoke(
        app,
        [
            "analyze",
            str(sample_project),
            "--format",
            "html",
            "--output",
            str(destination),
            "--no-history",
        ],
    )

    assert result.exit_code == 0
    assert "<!DOCTYPE html>" in destination.read_text(encoding="utf-8")
