"""Tests for agent context packs."""

from __future__ import annotations

from pathlib import Path

import pytest

from repomind.agents.context import build_explain_pack, build_review_pack
from repomind.core.baseline import Baseline
from repomind.core.engine import AnalysisOptions, AnalysisResult, analyze_repository
from repomind.errors import RepoMindError


def _analyze(sample_project: Path) -> AnalysisResult:
    return analyze_repository(sample_project, use_history=False)


def test_explain_pack_contains_facts(sample_project: Path) -> None:
    pack = build_explain_pack(_analyze(sample_project), "design/god-object@samplepkg/god.py")

    assert pack.task == "explain"
    assert len(pack.facts) == 1
    fact = pack.facts[0]
    assert fact.rule_id == "design/god-object"
    assert fact.severity == "high"
    assert fact.suggestion
    assert pack.paths == frozenset({"samplepkg/god.py"})
    assert pack.to_payload()["findings"][0]["rule_id"] == "design/god-object"
    assert pack.repository["files"] > 0


def test_explain_pack_supports_line_reference(sample_project: Path) -> None:
    result = _analyze(sample_project)
    finding = next(finding for finding in result.findings if finding.rule_id == "design/god-object")

    pack = build_explain_pack(result, f"{finding.rule_id}@{finding.path}:{finding.line}")

    assert pack.facts[0].line == finding.line


def test_explain_pack_rejects_unknown_reference(sample_project: Path) -> None:
    result = _analyze(sample_project)

    with pytest.raises(RepoMindError, match="no finding matches"):
        build_explain_pack(result, "design/god-object@nope.py")
    with pytest.raises(RepoMindError, match="invalid finding reference"):
        build_explain_pack(result, "@samplepkg/god.py")


def test_explain_pack_includes_callers(tmp_path: Path) -> None:
    branches = "".join(f"    if value > {index}:\n        result += 1\n" for index in range(10))
    (tmp_path / "app.py").write_text(
        '"""Module."""\n'
        "\n"
        "\n"
        "def tangled(value: int) -> int:\n"
        '    """T."""\n'
        "    result = 0\n"
        f"{branches}"
        "    return result\n"
        "\n"
        "\n"
        "def wrapper(value: int) -> int:\n"
        '    """W."""\n'
        "    return tangled(value)\n",
        encoding="utf-8",
    )

    result = analyze_repository(tmp_path, use_history=False)
    pack = build_explain_pack(result, "complexity/high-cyclomatic-complexity@app.py")

    assert pack.facts[0].callers == 1


def test_review_pack_uses_new_findings_with_baseline(sample_project: Path) -> None:
    result = _analyze(sample_project)
    baseline = Baseline.from_findings(result.findings)
    with_baseline = analyze_repository(
        sample_project,
        use_history=False,
        options=AnalysisOptions(baseline=baseline),
    )

    pack = build_review_pack(with_baseline, limit=10)

    assert pack.facts == ()
    assert pack.to_payload()["scope"] == {}


def test_review_pack_respects_limit_and_scope(sample_project: Path) -> None:
    pack = build_review_pack(_analyze(sample_project), limit=2, scope_label="main")

    assert len(pack.facts) == 2
    assert pack.scope == {"since": "main"}
