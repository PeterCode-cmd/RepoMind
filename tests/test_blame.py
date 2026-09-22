"""Tests for function-level churn via git blame."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from repomind.core.pyparser import parse_module
from repomind.git.blame import blame_functions

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")

_SOURCE = (
    '"""Module."""\n'
    "\n"
    "\n"
    "def stable(value: int) -> int:\n"
    '    """Never changes."""\n'
    "    return value\n"
    "\n"
    "\n"
    "def evolving(value: int) -> int:\n"
    '    """Changes often."""\n'
    "    return value + 0\n"
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


def test_blame_attributes_churn_per_function(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    module_path = repo / "app.py"
    module_path.write_text(_SOURCE, encoding="utf-8")
    _commit(repo, "initial")
    for index in range(1, 4):
        module_path.write_text(
            _SOURCE.replace("value + 0", f"value + {index}"),
            encoding="utf-8",
        )
        _commit(repo, f"change {index}")

    module = parse_module(module_path, repo)
    churn = blame_functions(repo, "app.py", module.all_functions)

    assert churn["app.stable"].commits == 1
    assert churn["app.evolving"].commits == 4
    assert churn["app.evolving"].authors == 1
    assert churn["app.evolving"].lines > 0
    assert churn["app.evolving"].last_modified is not None


def test_blame_returns_empty_outside_repository(tmp_path: Path) -> None:
    outside = tmp_path / "plain"
    outside.mkdir()
    module_path = outside / "app.py"
    module_path.write_text(_SOURCE, encoding="utf-8")
    module = parse_module(module_path, outside)

    assert blame_functions(outside, "app.py", module.all_functions) == {}


def test_blame_without_functions_is_empty(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    assert blame_functions(repo, "app.py", []) == {}
