"""Shared glob matching for repository-relative POSIX paths."""

from __future__ import annotations

import fnmatch
from collections.abc import Sequence
from pathlib import PurePosixPath


def matches_patterns(rel_path: str, patterns: Sequence[str]) -> bool:
    """Return ``True`` when *rel_path* matches any of *patterns*.

    A pattern matches when it equals the full path, is a directory prefix of
    the path, matches any single path segment (for patterns without ``/``) or
    matches the file name. This keeps ``-x migrations``, ``-x pkg/migrations``
    and ``-x *_pb2.py`` all behaving the way users expect.
    """
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
