"""Tests for the index and semantic search CLI commands."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from tests.conftest import FakeEmbedder
from typer.testing import CliRunner

from repomind.cli.app import app

runner = CliRunner()


def _project(sample_project: Path, tmp_path: Path) -> Path:
    project = tmp_path / "project"
    shutil.copytree(sample_project, project)
    return project


def _index(project: Path, fake_embedder: FakeEmbedder, monkeypatch) -> None:
    monkeypatch.setattr("repomind.cli.index.create_embedder", lambda config: fake_embedder)
    result = runner.invoke(app, ["index", str(project)])
    assert result.exit_code == 0
    assert "Index ready" in result.stdout


def _patch_search_embedder(fake_embedder: FakeEmbedder, monkeypatch) -> None:
    monkeypatch.setattr(
        "repomind.semantic.embedder.create_embedder",
        lambda config: fake_embedder,
    )


def test_index_command_builds_store(
    sample_project: Path, tmp_path: Path, fake_embedder: FakeEmbedder, monkeypatch
) -> None:
    project = _project(sample_project, tmp_path)

    _index(project, fake_embedder, monkeypatch)

    assert (project / ".repomind" / "embeddings.npz").is_file()
    assert (project / ".repomind" / "embeddings.json").is_file()


def test_semantic_search_returns_ranked_hits(
    sample_project: Path, tmp_path: Path, fake_embedder: FakeEmbedder, monkeypatch
) -> None:
    project = _project(sample_project, tmp_path)
    _index(project, fake_embedder, monkeypatch)
    _patch_search_embedder(fake_embedder, monkeypatch)

    result = runner.invoke(
        app,
        ["search", "alpha", str(project), "--mode", "semantic", "--format", "json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["hits"]
    scores = [hit["score"] for hit in payload["hits"]]
    assert scores == sorted(scores, reverse=True)
    assert all(hit["path"].startswith("samplepkg/") for hit in payload["hits"])


def test_semantic_search_terminal_shows_results(
    sample_project: Path, tmp_path: Path, fake_embedder: FakeEmbedder, monkeypatch
) -> None:
    project = _project(sample_project, tmp_path)
    _index(project, fake_embedder, monkeypatch)
    _patch_search_embedder(fake_embedder, monkeypatch)

    result = runner.invoke(app, ["search", "alpha", str(project), "--mode", "semantic"])

    assert result.exit_code == 0
    assert "Search results" in result.stdout


def test_semantic_search_without_index_fails(
    sample_project: Path, tmp_path: Path, fake_embedder: FakeEmbedder, monkeypatch
) -> None:
    project = _project(sample_project, tmp_path)
    _patch_search_embedder(fake_embedder, monkeypatch)

    result = runner.invoke(app, ["search", "alpha", str(project), "--mode", "semantic"])

    assert result.exit_code == 2
    assert "repomind index" in result.stdout


def test_index_without_chunks_reports_nothing_to_do(
    tmp_path: Path, fake_embedder: FakeEmbedder, monkeypatch
) -> None:
    project = tmp_path / "empty"
    project.mkdir()
    monkeypatch.setattr("repomind.cli.index.create_embedder", lambda config: fake_embedder)

    result = runner.invoke(app, ["index", str(project)])

    assert result.exit_code == 0
    assert "No code chunks" in result.stdout
