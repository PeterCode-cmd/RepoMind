"""Tests for diff-mode analysis (``--since``)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from repomind.cli.app import app
from repomind.core.engine import AnalysisOptions, AnalysisScope, analyze_repository
from repomind.errors import RepoMindError
from repomind.git.diff import changed_paths

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")

runner = CliRunner()


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "dev@example.com")
    _git(repo, "config", "user.name", "RepoMind Tester")
    return repo


def _commit(repo: Path, message: str) -> None:
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", message)


def test_changed_paths_covers_commits_and_working_tree(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    (repo / "app.py").write_text("value = 1\n", encoding="utf-8")
    (repo / "other.py").write_text("value = 2\n", encoding="utf-8")
    _commit(repo, "initial")

    (repo / "app.py").write_text("value = 3\n", encoding="utf-8")
    _commit(repo, "change app")
    (repo / "untracked.py").write_text("value = 4\n", encoding="utf-8")
    (repo / "notes.txt").write_text("not python\n", encoding="utf-8")

    changed = changed_paths(repo, "HEAD~1")

    assert changed == frozenset({"app.py", "untracked.py"})


def test_changed_paths_rejects_unknown_revision(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    (repo / "app.py").write_text("value = 1\n", encoding="utf-8")
    _commit(repo, "initial")

    with pytest.raises(RepoMindError, match="unknown revision"):
        changed_paths(repo, "does-not-exist")


def test_changed_paths_rejects_non_repository(tmp_path: Path) -> None:
    outside = tmp_path / "plain"
    outside.mkdir()

    with pytest.raises(RepoMindError, match="not inside a Git repository"):
        changed_paths(outside, "HEAD")


def test_engine_limits_analysis_to_given_paths(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    branches = "".join(f"    if value > {index}:\n        result += 1\n" for index in range(10))
    (repo / "complex.py").write_text(
        f"def tangled(value: int) -> int:\n    result = 0\n{branches}    return result\n",
        encoding="utf-8",
    )
    (repo / "clean.py").write_text("value = 1\n", encoding="utf-8")
    _commit(repo, "initial")
    result = analyze_repository(
        repo,
        use_history=False,
        options=AnalysisOptions(scope=AnalysisScope(paths=frozenset({"clean.py"}), label="test")),
    )

    assert [module.rel_path for module in result.modules] == ["clean.py"]
    assert all(
        finding.rule_id != "complexity/high-cyclomatic-complexity" for finding in result.findings
    )
    assert result.scope_label == "test"


def test_analyze_since_limits_scope(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    (repo / "app.py").write_text("value = 1\n", encoding="utf-8")
    (repo / "old.py").write_text("value = 2\n", encoding="utf-8")
    _commit(repo, "initial")

    (repo / "app.py").write_text("value = 3\n", encoding="utf-8")
    (repo / "fresh.py").write_text("value = 4\n", encoding="utf-8")
    _commit(repo, "update")

    result = runner.invoke(
        app,
        ["analyze", str(repo), "--since", "HEAD~1", "--format", "json", "--no-history"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["scope"] == "HEAD~1"
    assert payload["repository"]["files"] == 2


def test_analyze_since_rejects_unknown_revision(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    (repo / "app.py").write_text("value = 1\n", encoding="utf-8")
    _commit(repo, "initial")

    result = runner.invoke(app, ["analyze", str(repo), "--since", "nope", "--no-history"])

    assert result.exit_code == 2
    assert "unknown revision" in result.stdout


def test_analyze_since_with_no_changed_python_files(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    (repo / "app.py").write_text("value = 1\n", encoding="utf-8")
    _commit(repo, "initial")
    (repo / "notes.txt").write_text("hello\n", encoding="utf-8")
    _commit(repo, "docs only")

    result = runner.invoke(app, ["analyze", str(repo), "--since", "HEAD~1", "--no-history"])

    assert result.exit_code == 0
    assert "No Python files changed" in result.stdout
