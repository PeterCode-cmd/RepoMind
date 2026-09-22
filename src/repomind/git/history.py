"""Git history analysis: churn, authorship and change recency."""

from __future__ import annotations

import math
import os
from collections.abc import Collection
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from git import InvalidGitRepositoryError, NoSuchPathError, Repo
from git.exc import GitCommandError


@dataclass(slots=True)
class FileHistory:
    """Change activity of a single file inside the analyzed window."""

    rel_path: str
    commits: int = 0
    insertions: int = 0
    deletions: int = 0
    authors: set[str] = field(default_factory=set)
    last_modified: datetime | None = None

    @property
    def churn(self) -> int:
        """Return the total number of inserted plus deleted lines."""
        return self.insertions + self.deletions

    @property
    def author_count(self) -> int:
        """Return the number of distinct authors touching the file."""
        return len(self.authors)


@dataclass(slots=True)
class HistoryReport:
    """Aggregated Git history for the analyzed window."""

    total_commits: int
    max_commits: int
    head_sha: str
    branch: str | None
    files: dict[str, FileHistory]

    def churn_percentile(self, fraction: float) -> float:
        """Return the commit-count percentile across analyzed files.

        Uses linear interpolation between the two neighbouring values, which
        keeps the result stable for small repositories.
        """
        if not self.files:
            return 0.0
        values = sorted(file.commits for file in self.files.values())
        if fraction <= 0.0:
            return float(values[0])
        if fraction >= 1.0:
            return float(values[-1])
        position = fraction * (len(values) - 1)
        lower = int(position)
        upper = min(lower + 1, len(values) - 1)
        weight = position - lower
        return float(values[lower] * (1.0 - weight) + values[upper] * weight)

    def top_churn(self, limit: int = 5) -> list[FileHistory]:
        """Return the *limit* most frequently changed files."""
        return sorted(
            self.files.values(),
            key=lambda entry: (-entry.commits, -entry.churn, entry.rel_path),
        )[:limit]

    def hotspots(self, limit: int = 5) -> list[tuple[FileHistory, float]]:
        """Return files ranked by ``churn * log(1 + commits)``.

        The returned float is a 0-100 score relative to the hottest file, so
        the number is easy to display and compare within one report.
        """
        if not self.files:
            return []
        scored = [(entry, entry.churn * math.log1p(entry.commits)) for entry in self.files.values()]
        top = max(score for _, score in scored)
        if top <= 0.0:
            return []
        ranked = [(entry, round(score / top * 100.0, 1)) for entry, score in scored]
        return sorted(ranked, key=lambda item: (-item[1], item[0].rel_path))[:limit]


def analyze_history(
    root: Path,
    *,
    paths: Collection[str] | None = None,
    max_commits: int = 500,
) -> HistoryReport | None:
    """Analyze Git history for *root*.

    Args:
        root: Directory to analyze; the enclosing repository is discovered
            automatically.
        paths: Repository-relative POSIX paths to track. ``None`` tracks all
            files touched by the analyzed commits.
        max_commits: Maximum number of commits to walk, newest first.

    Returns:
        A :class:`HistoryReport`, or ``None`` when *root* is not inside a Git
        repository or the repository has no commits yet.
    """
    root = root.resolve()
    try:
        repo = Repo(root, search_parent_directories=True)
    except (InvalidGitRepositoryError, NoSuchPathError):
        return None

    try:
        head = repo.head.commit
    except (ValueError, GitCommandError):
        return None

    working_tree = repo.working_tree_dir
    if working_tree is None:
        return None
    repo_root = Path(working_tree)

    tracked = set(paths) if paths is not None else None
    files: dict[str, FileHistory] = {}
    commit_count = 0

    for commit in repo.iter_commits(head, max_count=max_commits):
        commit_count += 1
        try:
            stats = commit.stats.files
        except (GitCommandError, ValueError):
            continue
        if not stats:
            continue

        author = commit.author.name or commit.author.email or "unknown"
        committed_at = commit.committed_datetime
        for file_path, file_stats in stats.items():
            rel_path = _relative_to_root(repo_root, root, os.fspath(file_path))
            if rel_path is None or (tracked is not None and rel_path not in tracked):
                continue
            entry = files.setdefault(rel_path, FileHistory(rel_path=rel_path))
            entry.commits += 1
            entry.insertions += int(file_stats.get("insertions", 0))
            entry.deletions += int(file_stats.get("deletions", 0))
            entry.authors.add(author)
            if entry.last_modified is None or committed_at > entry.last_modified:
                entry.last_modified = committed_at

    return HistoryReport(
        total_commits=commit_count,
        max_commits=max_commits,
        head_sha=str(head.hexsha),
        branch=_branch_name(repo),
        files=files,
    )


def _relative_to_root(repo_root: Path, root: Path, file_path: str) -> str | None:
    """Return *file_path* relative to *root*, or ``None`` when outside it."""
    try:
        absolute = (repo_root / file_path).resolve()
        return absolute.relative_to(root).as_posix()
    except (OSError, ValueError):
        return None


def _branch_name(repo: Repo) -> str | None:
    """Return the active branch name, or ``None`` on a detached HEAD."""
    try:
        name = repo.active_branch.name
    except TypeError:
        return None
    return str(name) if name else None
