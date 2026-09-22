"""Discovery of Python source files inside a repository.

When the analyzed root lives inside a Git repository, discovery is delegated
to ``git ls-files`` (tracked files plus untracked, non-ignored files). This
makes the scan respect ``.gitignore`` without reimplementing it. Outside a
repository RepoMind walks the filesystem itself.
"""

from __future__ import annotations

import fnmatch
from collections.abc import Sequence
from pathlib import Path, PurePosixPath

from git import InvalidGitRepositoryError, NoSuchPathError, Repo
from git.exc import GitCommandError

DEFAULT_EXCLUDED_DIRS = frozenset(
    {
        ".eggs",
        ".git",
        ".hg",
        ".mypy_cache",
        ".nox",
        ".pytest_cache",
        ".ruff_cache",
        ".svn",
        ".tox",
        ".venv",
        "__pycache__",
        "build",
        "dist",
        "env",
        "htmlcov",
        "node_modules",
        "site-packages",
        "venv",
    }
)


def find_python_files(root: Path, *, exclude: Sequence[str] = ()) -> list[Path]:
    """Return the sorted Python files that should be analyzed.

    Args:
        root: Repository root to scan.
        exclude: Additional glob patterns; a pattern without ``/`` matches any
            path segment, so ``-x migrations`` skips every ``migrations`` dir.

    Returns:
        Absolute paths of all discovered ``.py`` files, sorted for determinism.
    """
    root = root.resolve()
    discovered = _git_python_files(root)
    if discovered is None:
        discovered = _walk_python_files(root)
    selected = [
        path for path in discovered if not _is_excluded(_relative_path(root, path), exclude)
    ]
    return sorted(selected)


def _git_python_files(root: Path) -> list[Path] | None:
    """List Python files through Git, or ``None`` when *root* is not a repo."""
    try:
        repo = Repo(root, search_parent_directories=True)
    except (InvalidGitRepositoryError, NoSuchPathError):
        return None

    working_tree = repo.working_tree_dir
    if working_tree is None:
        return None

    try:
        listing = repo.git.ls_files("--cached", "--others", "--exclude-standard", "-z")
    except GitCommandError:
        return None

    repo_root = Path(working_tree)
    results: list[Path] = []
    for entry in listing.split("\0"):
        if not entry or not entry.endswith(".py"):
            continue
        absolute = (repo_root / entry).resolve()
        if not absolute.is_file() or not absolute.is_relative_to(root):
            continue
        if _has_excluded_dir(absolute.relative_to(root)):
            continue
        results.append(absolute)
    return results


def _walk_python_files(root: Path) -> list[Path]:
    """Walk the filesystem, skipping caches, virtualenvs and hidden dirs."""
    results: list[Path] = []
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            entries = sorted(current.iterdir())
        except OSError:
            continue
        for entry in entries:
            if entry.is_symlink():
                continue
            if entry.is_dir():
                if entry.name.startswith(".") or entry.name in DEFAULT_EXCLUDED_DIRS:
                    continue
                stack.append(entry)
            elif entry.suffix == ".py" and entry.is_file():
                results.append(entry)
    return results


def _has_excluded_dir(relative: Path) -> bool:
    """Return ``True`` when any parent directory is excluded by default."""
    return any(
        part.startswith(".") or part in DEFAULT_EXCLUDED_DIRS for part in relative.parts[:-1]
    )


def _relative_path(root: Path, path: Path) -> str:
    """Return the POSIX path of *path* relative to *root*."""
    return path.relative_to(root).as_posix()


def _is_excluded(rel_path: str, patterns: Sequence[str]) -> bool:
    """Return ``True`` when *rel_path* matches any user provided pattern."""
    if not patterns:
        return False
    pure = PurePosixPath(rel_path)
    for pattern in patterns:
        cleaned = pattern.strip("/")
        if not cleaned:
            continue
        if fnmatch.fnmatch(rel_path, cleaned):
            return True
        if rel_path.startswith(f"{cleaned}/"):
            return True
        if "/" not in cleaned and any(fnmatch.fnmatch(part, cleaned) for part in pure.parts):
            return True
        if fnmatch.fnmatch(pure.name, cleaned):
            return True
    return False
