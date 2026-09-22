"""Tests for Git history analysis and hotspot detection."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from repomind.core.engine import analyze_repository
from repomind.git.history import analyze_history

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")

_TANGLED_SOURCE = (
    "def tangled(value: int) -> int:\n"
    "    result = 0\n"
    "    if value > 0:\n"
    "        result += 1\n"
    "    if value > 1:\n"
    "        result += 1\n"
    "    if value > 2:\n"
    "        result += 1\n"
    "    if value > 3:\n"
    "        result += 1\n"
    "    if value > 4:\n"
    "        result += 1\n"
    "    if value > 5:\n"
    "        result += 1\n"
    "    if value > 6:\n"
    "        result += 1\n"
    "    if value > 7:\n"
    "        result += 1\n"
    "    if value > 8:\n"
    "        result += 1\n"
    "    if value > 9:\n"
    "        result += 1\n"
    "    return result\n"
)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _commit(repo: Path, message: str) -> None:
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", message)


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "dev@example.com")
    _git(repo, "config", "user.name", "RepoMind Tester")
    return repo


def test_analyze_history_counts_changes(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    (repo / "app.py").write_text("def main() -> int:\n    return 1\n", encoding="utf-8")
    _commit(repo, "initial")

    report = analyze_history(repo)

    assert report is not None
    assert report.total_commits == 1
    entry = report.files["app.py"]
    assert entry.commits == 1
    assert entry.author_count == 1
    assert entry.last_modified is not None
    assert report.churn_percentile(0.5) == 1.0


def test_analyze_history_returns_none_outside_repository(tmp_path: Path) -> None:
    outside = tmp_path / "plain"
    outside.mkdir()
    assert analyze_history(outside) is None


def test_analyze_history_returns_none_without_commits(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    assert analyze_history(repo) is None


def test_hotspot_rule_flags_complex_churned_file(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    (repo / "app.py").write_text(_TANGLED_SOURCE, encoding="utf-8")
    _commit(repo, "add app")
    for index in range(4):
        with (repo / "app.py").open("a", encoding="utf-8") as handle:
            handle.write(f"\n# touch {index}\n")
        _commit(repo, f"touch {index}")

    result = analyze_repository(repo, use_history=True)
    hotspots = [
        finding for finding in result.findings if finding.rule_id == "history/complexity-hotspot"
    ]

    assert hotspots
    assert hotspots[0].details["commits"] == 5
    assert hotspots[0].path == "app.py"


def test_hotspots_require_history(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    (repo / "app.py").write_text(_TANGLED_SOURCE, encoding="utf-8")
    _commit(repo, "add app")

    result = analyze_repository(repo, use_history=False)

    assert result.history is None
    assert all(finding.rule_id != "history/complexity-hotspot" for finding in result.findings)
