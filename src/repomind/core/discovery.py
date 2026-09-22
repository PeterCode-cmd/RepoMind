"""Discovery of Python source files inside a repository.

When the analyzed root lives inside a Git repository, discovery is delegated
to ``git ls-files`` (tracked files plus untracked, non-ignored files). This
makes the scan respect ``.gitignore`` without reimplementing it. Outside a
repository RepoMind walks the filesystem itself.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from git import InvalidGitRepositoryError, NoSuchPathError, Repo
from git.exc import GitCommandError

from repomind.core.paths import matches_patterns

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
        path for path in discovered if not matches_patterns(_relative_path(root, path), exclude)
    ]
    return sorted(selected)


def _git_python_files(root: Path) -> list[Path] | None:
    """List Python files through Git, or ``None`` when *root* is not a repo."""
    opened = _open_git(root)
    if opened is None:
        return None
    repo, repo_root = opened

    try:
        listing = repo.git.ls_files("--cached", "--others", "--exclude-standard", "-z")
    except GitCommandError:
        return None

    return [
        path
        for entry in listing.split("\0")
        if (path := _git_entry_path(repo_root, root, entry)) is not None
    ]


def _open_git(root: Path) -> tuple[Repo, Path] | None:
    """Open the enclosing repository and return it with its working tree."""
    try:
        repo = Repo(root, search_parent_directories=True)
    except (InvalidGitRepositoryError, NoSuchPathError):
        return None
    working_tree = repo.working_tree_dir
    if working_tree is None:
        return None
    return repo, Path(working_tree)


def _git_entry_path(repo_root: Path, root: Path, entry: str) -> Path | None:
    """Resolve one ``git ls-files`` entry to an analyzable absolute path."""
    if not entry or not entry.endswith(".py"):
        return None
    absolute = (repo_root / entry).resolve()
    if not absolute.is_file() or not absolute.is_relative_to(root):
        return None
    if _has_excluded_dir(absolute.relative_to(root)):
        return None
    return absolute


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
            _visit_entry(entry, stack, results)
    return results


def _visit_entry(entry: Path, stack: list[Path], results: list[Path]) -> None:
    """Handle one directory entry during the filesystem walk."""
    if entry.is_symlink():
        return
    if entry.is_dir():
        if not _is_skippable_dir(entry.name):
            stack.append(entry)
    elif _is_python_file(entry):
        results.append(entry)


def _is_skippable_dir(name: str) -> bool:
    """Return ``True`` for hidden and well-known non-source directories."""
    return name.startswith(".") or name in DEFAULT_EXCLUDED_DIRS


def _is_python_file(entry: Path) -> bool:
    """Return ``True`` when *entry* is a Python source file."""
    return entry.suffix == ".py" and entry.is_file()


def _has_excluded_dir(relative: Path) -> bool:
    """Return ``True`` when any parent directory is excluded by default."""
    return any(_is_skippable_dir(part) for part in relative.parts[:-1])


def _relative_path(root: Path, path: Path) -> str:
    """Return the POSIX path of *path* relative to *root*."""
    return path.relative_to(root).as_posix()
