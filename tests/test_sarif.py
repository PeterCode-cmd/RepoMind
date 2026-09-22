"""Tests for SARIF output."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from repomind.cli.app import app
from repomind.core.engine import AnalysisResult, analyze_repository
from repomind.reporters.sarif import SARIF_VERSION, render_sarif, result_to_sarif

runner = CliRunner()


def _result(sample_project: Path) -> AnalysisResult:
    return analyze_repository(sample_project, use_history=False)


def test_sarif_document_structure(sample_project: Path) -> None:
    document = json.loads(render_sarif(_result(sample_project)))

    assert document["version"] == SARIF_VERSION
    assert document["$schema"].startswith("https://")
    run = document["runs"][0]
    assert run["tool"]["driver"]["name"] == "RepoMind"
    assert run["tool"]["driver"]["rules"]
    assert run["results"]


def test_sarif_levels_and_locations(sample_project: Path) -> None:
    results = result_to_sarif(_result(sample_project))["runs"][0]["results"]
    by_rule = {result["ruleId"]: result for result in results}

    assert by_rule["correctness/syntax-error"]["level"] == "error"
    assert by_rule["dead-code/unused-import"]["level"] == "note"

    location = by_rule["design/god-object"]["locations"][0]["physicalLocation"]
    assert location["artifactLocation"]["uri"] == "samplepkg/god.py"
    assert location["artifactLocation"]["uriBaseId"] == "%SRCROOT%"
    assert location["region"]["startLine"] > 0


def test_sarif_includes_fingerprints_and_suggestions(sample_project: Path) -> None:
    results = result_to_sarif(_result(sample_project))["runs"][0]["results"]

    assert all(result["partialFingerprints"]["repomind/v1"] for result in results)
    assert any("Suggestion" in result["message"].get("markdown", "") for result in results)


def test_sarif_rules_are_deduplicated(sample_project: Path) -> None:
    document = result_to_sarif(_result(sample_project))
    rules = [rule["id"] for rule in document["runs"][0]["tool"]["driver"]["rules"]]
    assert len(rules) == len(set(rules))


def test_cli_writes_sarif_file(sample_project: Path, tmp_path: Path) -> None:
    destination = tmp_path / "repomind.sarif"

    result = runner.invoke(
        app,
        [
            "analyze",
            str(sample_project),
            "--format",
            "sarif",
            "--output",
            str(destination),
            "--no-history",
        ],
    )

    assert result.exit_code == 0
    document = json.loads(destination.read_text(encoding="utf-8"))
    assert document["runs"][0]["results"]


def test_cli_prints_sarif_to_stdout(sample_project: Path) -> None:
    result = runner.invoke(
        app, ["analyze", str(sample_project), "--format", "sarif", "--no-history"]
    )

    assert result.exit_code == 0
    document = json.loads(result.stdout)
    assert document["version"] == SARIF_VERSION
