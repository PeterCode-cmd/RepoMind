"""Changed-file discovery for pull-request style analysis."""

from __future__ import annotations

import os
from pathlib import Path

from git import InvalidGitRepositoryError, NoSuchPathError, Repo
from git.diff import Diff
from git.exc import BadName, GitCommandError

from repomind.errors import RepoMindError


def changed_paths(root: Path, since: str) -> frozenset[str]:
    """Return Python files changed since *since*, relative to *root*.

    ``since`` accepts anything Git resolves as a revision (branch, tag, SHA,
    ``HEAD~3``). The comparison covers committed, staged and unstaged changes
    plus untracked files, so local reviews include work in progress.

    Args:
        root: Repository root.
        since: Revision to compare the working tree against.

    Returns:
        Repository-relative POSIX paths of changed Python files.

    Raises:
        RepoMindError: When *root* is not inside a repository or *since* is
            not a known revision.
    """
    root = root.resolve()
    try:
        repo = Repo(root, search_parent_directories=True)
    except (InvalidGitRepositoryError, NoSuchPathError) as exc:
        raise RepoMindError(f"{root} is not inside a Git repository") from exc

    try:
        commit = repo.commit(since)
        diff = commit.diff(None)
    except (BadName, GitCommandError, ValueError) as exc:
        raise RepoMindError(f"unknown revision: {since}") from exc

    working_tree = repo.working_tree_dir
    repo_root = Path(working_tree) if working_tree is not None else root

    paths: set[str] = set()
    for item in diff:
        changed = _changed_file(repo_root, root, item)
        if changed is not None:
            paths.add(changed)
    for name in repo.untracked_files:
        changed = _relative_python_path(repo_root, root, name)
        if changed is not None:
            paths.add(changed)

    return frozenset(paths)


def _changed_file(repo_root: Path, root: Path, item: Diff) -> str | None:
    """Resolve one diff entry to the path that exists in the working tree."""
    candidate = item.b_path or item.a_path
    if candidate is None:
        return None
    return _relative_python_path(repo_root, root, candidate)


def _relative_python_path(
    repo_root: Path,
    root: Path,
    file_path: str | os.PathLike[str],
) -> str | None:
    """Return *file_path* relative to *root* when it is a Python file."""
    try:
        absolute = (repo_root / os.fspath(file_path)).resolve()
        relative = absolute.relative_to(root).as_posix()
    except (OSError, ValueError, TypeError):
        return None
    return relative if relative.endswith(".py") else None
