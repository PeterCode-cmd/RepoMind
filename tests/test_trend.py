"""Tests for the health trend over sampled commits."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from repomind.cli.app import app
from repomind.core.trend import build_trend
from repomind.errors import RepoMindError

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")

runner = CliRunner()

_CLEAN_SOURCE = '"""Module."""\n\n\nvalue = 1\n'

_BRANCHES = "".join(f"    if value > {index}:\n        result += 1\n" for index in range(10))
_TANGLED_SOURCE = (
    '"""Module."""\n'
    "\n"
    "\n"
    "def tangled(value: int) -> int:\n"
    '    """Complex."""\n'
    "    result = 0\n"
    f"{_BRANCHES}"
    "    return result\n"
)


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


def _quality_history(tmp_path: Path) -> Path:
    repo = _init_repo(tmp_path)
    module = repo / "app.py"
    module.write_text(_CLEAN_SOURCE, encoding="utf-8")
    _commit(repo, "clean")
    module.write_text(_TANGLED_SOURCE, encoding="utf-8")
    _commit(repo, "add tangled function")
    module.write_text(_CLEAN_SOURCE, encoding="utf-8")
    _commit(repo, "remove tangled function")
    return repo


def test_trend_scores_follow_code_quality(tmp_path: Path) -> None:
    repo = _quality_history(tmp_path)

    report = build_trend(repo, samples=3, window=50)

    scores = [sample.score for sample in report.samples]
    assert len(scores) == 3
    assert scores[0] == 100
    assert scores[1] < scores[0]
    assert scores[2] == 100
    assert report.delta == 0


def test_trend_reports_subjects_and_extremes(tmp_path: Path) -> None:
    repo = _quality_history(tmp_path)

    report = build_trend(repo, samples=3, window=50)

    assert report.samples[0].subject == "clean"
    assert report.samples[-1].subject == "remove tangled function"
    worst = report.worst()
    assert worst is not None
    assert worst.short_sha == report.samples[1].short_sha
    assert report.samples[1].findings > 0


def test_trend_removes_its_worktrees(tmp_path: Path) -> None:
    repo = _quality_history(tmp_path)

    build_trend(repo, samples=3, window=50)

    listing = subprocess.run(
        ["git", "-C", str(repo), "worktree", "list"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "repomind-trend" not in listing
    assert len([line for line in listing.splitlines() if line.strip()]) == 1


def test_trend_rejects_non_repository(tmp_path: Path) -> None:
    outside = tmp_path / "plain"
    outside.mkdir()

    with pytest.raises(RepoMindError, match="not inside a Git repository"):
        build_trend(outside, samples=2, window=10)


def test_trend_uses_all_commits_when_window_is_short(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    (repo / "app.py").write_text(_CLEAN_SOURCE, encoding="utf-8")
    _commit(repo, "first")
    (repo / "app.py").write_text('"""Module."""\n\n\nvalue = 2\n', encoding="utf-8")
    _commit(repo, "second")

    report = build_trend(repo, samples=5, window=50)

    assert len(report.samples) == 2


def test_cli_trend_json(tmp_path: Path) -> None:
    repo = _quality_history(tmp_path)

    result = runner.invoke(
        app,
        ["trend", str(repo), "--samples", "3", "--commits", "50", "--format", "json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert len(payload["samples"]) == 3
    assert payload["delta"] == 0
    assert {"sha", "score", "grade", "findings", "loc"} <= set(payload["samples"][0])


def test_cli_trend_writes_markdown(tmp_path: Path) -> None:
    repo = _quality_history(tmp_path)
    destination = tmp_path / "trend.md"

    result = runner.invoke(
        app,
        [
            "trend",
            str(repo),
            "--samples",
            "3",
            "--commits",
            "50",
            "--format",
            "markdown",
            "--output",
            str(destination),
        ],
    )

    assert result.exit_code == 0
    assert "# RepoMind trend" in destination.read_text(encoding="utf-8")


def test_cli_trend_terminal_summary(tmp_path: Path) -> None:
    repo = _quality_history(tmp_path)

    result = runner.invoke(app, ["trend", str(repo), "--samples", "3", "--commits", "50"])

    assert result.exit_code == 0
    assert "Health trend" in result.stdout
    assert "Score" in result.stdout
