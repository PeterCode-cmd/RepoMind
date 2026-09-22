"""Tests for the search CLI command."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from repomind.cli.app import app

runner = CliRunner()


def test_search_terminal(sample_project: Path) -> None:
    result = runner.invoke(app, ["search", "tangled branches", str(sample_project)])

    assert result.exit_code == 0
    assert "Search results" in result.stdout
    assert "samplepkg/complex.py:4" in result.stdout
    assert "function" in result.stdout


def test_search_json(sample_project: Path) -> None:
    result = runner.invoke(app, ["search", "god object", str(sample_project), "--format", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["query"] == "god object"
    assert payload["hits"]
    assert {"chunk_id", "kind", "path", "symbol", "score"} <= set(payload["hits"][0])


def test_search_without_matches(sample_project: Path) -> None:
    result = runner.invoke(app, ["search", "zzzzqqqq", str(sample_project)])

    assert result.exit_code == 0
    assert "No matches" in result.stdout


def test_search_writes_json_file(sample_project: Path, tmp_path: Path) -> None:
    destination = tmp_path / "hits.json"

    result = runner.invoke(
        app,
        [
            "search",
            "god",
            str(sample_project),
            "--format",
            "json",
            "--output",
            str(destination),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(destination.read_text(encoding="utf-8"))
    assert payload["hits"]
