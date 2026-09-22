"""Tests for file discovery."""

from __future__ import annotations

from pathlib import Path

from repomind.core.discovery import find_python_files


def _write(path: Path, content: str = "value = 1\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_walks_tree_and_skips_excluded_dirs(tmp_path: Path) -> None:
    _write(tmp_path / "pkg" / "mod.py")
    _write(tmp_path / ".venv" / "lib.py")
    _write(tmp_path / "__pycache__" / "cache.py")
    _write(tmp_path / ".hidden" / "secret.py")
    _write(tmp_path / "notes.txt")

    found = find_python_files(tmp_path)

    assert [path.name for path in found] == ["mod.py"]


def test_exclude_patterns_match_any_segment(tmp_path: Path) -> None:
    _write(tmp_path / "pkg" / "mod.py")
    _write(tmp_path / "migrations" / "0001.py")
    _write(tmp_path / "pkg" / "migrations" / "0002.py")

    found = find_python_files(tmp_path, exclude=["migrations"])

    assert [path.name for path in found] == ["mod.py"]


def test_glob_exclude_patterns(tmp_path: Path) -> None:
    _write(tmp_path / "pkg" / "mod.py")
    _write(tmp_path / "pkg" / "generated_pb2.py")

    found = find_python_files(tmp_path, exclude=["*_pb2.py"])

    assert [path.name for path in found] == ["mod.py"]


def test_exclude_directory_prefix(tmp_path: Path) -> None:
    _write(tmp_path / "pkg" / "mod.py")
    _write(tmp_path / "pkg" / "migrations" / "0001.py")
    _write(tmp_path / "tests" / "fixtures" / "sample.py")

    found = find_python_files(tmp_path, exclude=["pkg/migrations", "tests/fixtures"])

    assert [path.name for path in found] == ["mod.py"]


def test_results_are_sorted(tmp_path: Path) -> None:
    _write(tmp_path / "b.py")
    _write(tmp_path / "a.py")

    found = find_python_files(tmp_path)

    assert [path.name for path in found] == ["a.py", "b.py"]


def test_discovers_checked_in_sample_project(sample_project: Path) -> None:
    found = find_python_files(sample_project)
    names = {path.relative_to(sample_project).as_posix() for path in found}
    assert "samplepkg/a.py" in names
    assert "samplepkg/broken.py" in names
