"""Tests for the command-line interface."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from typer.testing import CliRunner

from repomind import __version__
from repomind.cli.app import app

runner = CliRunner()


def test_version_flag() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_rules_command_lists_rules() -> None:
    result = runner.invoke(app, ["rules"])
    assert result.exit_code == 0
    assert "complexity/high-cyclomatic-complexity" in result.stdout
    assert "design/god-object" in result.stdout
    assert "complexity" in result.stdout


def test_analyze_terminal_report(sample_project: Path) -> None:
    result = runner.invoke(app, ["analyze", str(sample_project), "--no-history", "--top", "5"])
    assert result.exit_code == 0
    assert "grade" in result.stdout
    assert "Dependency graph" in result.stdout


def test_analyze_json_to_stdout(sample_project: Path) -> None:
    result = runner.invoke(
        app, ["analyze", str(sample_project), "--format", "json", "--no-history"]
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["repository"]["files"] > 0


def test_analyze_writes_markdown_file(sample_project: Path, tmp_path: Path) -> None:
    destination = tmp_path / "report.md"
    result = runner.invoke(
        app,
        [
            "analyze",
            str(sample_project),
            "--format",
            "markdown",
            "--output",
            str(destination),
            "--no-history",
        ],
    )
    assert result.exit_code == 0
    assert destination.is_file()
    assert "RepoMind report" in destination.read_text(encoding="utf-8")


def test_analyze_min_severity_filters_findings(sample_project: Path) -> None:
    result = runner.invoke(
        app,
        [
            "analyze",
            str(sample_project),
            "--format",
            "json",
            "--min-severity",
            "high",
            "--no-history",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["findings"]
    assert all(finding["severity_level"] >= 3 for finding in payload["findings"])


def test_analyze_fail_under_triggers_exit_code(sample_project: Path) -> None:
    result = runner.invoke(
        app,
        ["analyze", str(sample_project), "--no-history", "--fail-under", "99"],
    )
    assert result.exit_code == 1


def test_analyze_unknown_path_fails_validation() -> None:
    result = runner.invoke(app, ["analyze", "does-not-exist"])
    assert result.exit_code != 0


def test_analyze_uses_repository_config(sample_project: Path, tmp_path: Path) -> None:
    project = tmp_path / "project"
    shutil.copytree(sample_project, project)
    (project / "repomind.toml").write_text(
        'exclude = ["broken.py"]\nignore = ["design/god-object@samplepkg/god.py"]\n',
        encoding="utf-8",
    )

    result = runner.invoke(app, ["analyze", str(project), "--format", "json", "--no-history"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert [finding["rule_id"] for finding in payload["suppressed"]] == ["design/god-object"]
    assert all(finding["rule_id"] != "correctness/syntax-error" for finding in payload["findings"])


def test_baseline_command_writes_file(sample_project: Path, tmp_path: Path) -> None:
    project = tmp_path / "project"
    shutil.copytree(sample_project, project)

    result = runner.invoke(app, ["baseline", str(project), "--no-history"])

    assert result.exit_code == 0
    baseline_file = project / ".repomind-baseline.json"
    assert baseline_file.is_file()
    payload = json.loads(baseline_file.read_text(encoding="utf-8"))
    assert payload["findings"]


def test_analyze_fail_on_new_gate(sample_project: Path, tmp_path: Path) -> None:
    project = tmp_path / "project"
    shutil.copytree(sample_project, project)
    assert runner.invoke(app, ["baseline", str(project), "--no-history"]).exit_code == 0

    clean = runner.invoke(app, ["analyze", str(project), "--no-history", "--fail-on-new"])
    assert clean.exit_code == 0
    assert "Baseline:" in clean.stdout

    (project / "samplepkg" / "fresh.py").write_text(
        "def fresh(a: int, b: int, c: int, d: int, e: int, f: int, g: int) -> int:\n"
        "    return a + b + c + d + e + f + g\n",
        encoding="utf-8",
    )
    dirty = runner.invoke(app, ["analyze", str(project), "--no-history", "--fail-on-new"])
    assert dirty.exit_code == 1
    assert "not accepted by the baseline" in dirty.stdout


def test_analyze_no_baseline_ignores_file(sample_project: Path, tmp_path: Path) -> None:
    project = tmp_path / "project"
    shutil.copytree(sample_project, project)
    assert runner.invoke(app, ["baseline", str(project), "--no-history"]).exit_code == 0

    result = runner.invoke(
        app,
        ["analyze", str(project), "--no-history", "--no-baseline", "--format", "json"],
    )

    payload = json.loads(result.stdout)
    assert payload["baseline"] is None
    assert all(finding["is_new"] is None for finding in payload["findings"])
