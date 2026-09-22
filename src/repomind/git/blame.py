"""Function-level churn via Git line-range tracking.

``git log -L`` follows a line range through history, which gives true churn
per function (how many commits touched it) instead of blame's "who owns the
current lines". Line-range walks are cheap per range but not free, so the
engine only tracks the hottest files and this module only tracks the most
complex functions of each file.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from git import InvalidGitRepositoryError, NoSuchPathError, Repo
from git.exc import GitCommandError

from repomind.models.metrics import FunctionMetrics

_MAX_FUNCTIONS_PER_FILE = 8
_FIELD_SEPARATOR = "\x1f"
_EXPECTED_FIELDS = 3


@dataclass(frozen=True, slots=True)
class FunctionChurn:
    """Change activity of a single function or method."""

    commits: int
    authors: int
    lines: int
    last_modified: datetime | None


def blame_functions(
    root: Path,
    rel_path: str,
    functions: Sequence[FunctionMetrics],
) -> dict[str, FunctionChurn]:
    """Return per-function churn for *rel_path*.

    Only the most complex ``_MAX_FUNCTIONS_PER_FILE`` functions are tracked,
    because line-range history walks dominate the cost of this stage.

    Args:
        root: Repository root.
        rel_path: Repository-relative POSIX path of the file.
        functions: Functions and methods to track.

    Returns:
        A mapping of ``qualname`` to :class:`FunctionChurn`; ranges that
        cannot be tracked are omitted.
    """
    if not functions:
        return {}
    root = root.resolve()
    try:
        repo = Repo(root, search_parent_directories=True)
    except (InvalidGitRepositoryError, NoSuchPathError):
        return {}

    candidates = sorted(functions, key=lambda function: function.cyclomatic, reverse=True)
    churn: dict[str, FunctionChurn] = {}
    for function in candidates[:_MAX_FUNCTIONS_PER_FILE]:
        entry = _range_churn(repo, rel_path, function)
        if entry is not None:
            churn[function.qualname] = entry
    return churn


def _range_churn(repo: Repo, rel_path: str, function: FunctionMetrics) -> FunctionChurn | None:
    """Return churn for one function's line range, or ``None`` when unavailable."""
    spec = f"-L{function.lineno},{function.end_lineno}:{rel_path}"
    try:
        output = repo.git.log(
            "-s",
            f"--format=%H{_FIELD_SEPARATOR}%an{_FIELD_SEPARATOR}%cI",
            spec,
        )
    except (GitCommandError, ValueError):
        return None

    shas: set[str] = set()
    authors: set[str] = set()
    last_modified: datetime | None = None
    for line in output.splitlines():
        parts = line.split(_FIELD_SEPARATOR)
        if len(parts) != _EXPECTED_FIELDS:
            continue
        sha, author, timestamp = parts
        shas.add(sha)
        authors.add(author or "unknown")
        parsed = _parse_timestamp(timestamp)
        if parsed is not None and (last_modified is None or parsed > last_modified):
            last_modified = parsed

    if not shas:
        return None
    return FunctionChurn(
        commits=len(shas),
        authors=len(authors),
        lines=function.end_lineno - function.lineno + 1,
        last_modified=last_modified,
    )


def _parse_timestamp(value: str) -> datetime | None:
    """Parse a strict ISO-8601 timestamp produced by ``git log``."""
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None
