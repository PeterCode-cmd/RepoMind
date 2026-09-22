"""Tests for the public Python API."""

from __future__ import annotations

import shutil
from pathlib import Path

import repomind
from conftest import FakeEmbedder
from repomind import api


def test_public_surface_is_exported() -> None:
    assert repomind.__version__
    for name in (
        "analyze",
        "search_code",
        "build_search_index",
        "explain_finding",
        "review_findings",
        "AnalysisResult",
        "Baseline",
    ):
        assert name in api.__all__


def test_analyze_returns_result(sample_project: Path) -> None:
    result = api.analyze(sample_project, use_history=False)

    assert 0 <= result.score.value <= 100
    assert result.findings
    assert result.file_count > 0


def test_search_code_finds_symbol(sample_project: Path) -> None:
    hits = api.search_code(sample_project, "tangled branches", limit=3)

    assert hits
    assert hits[0].chunk.symbol == "samplepkg.complex.tangled_branches"


def test_build_search_index_with_custom_embedder(
    sample_project: Path, tmp_path: Path, fake_embedder: FakeEmbedder
) -> None:
    project = tmp_path / "project"
    shutil.copytree(sample_project, project)

    stats = api.build_search_index(project, embedder=fake_embedder)

    assert stats.chunks > 0
    assert stats.embedded == stats.chunks
    assert (project / ".repomind" / "embeddings.json").is_file()


def test_explain_finding_without_model(sample_project: Path) -> None:
    result = api.analyze(sample_project, use_history=False)

    explanation = api.explain_finding(
        result,
        "design/god-object@samplepkg/god.py",
        client=None,
    )

    assert explanation.summary
    assert explanation.model is None
    assert explanation.notes
