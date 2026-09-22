"""Module with intentionally dead code used by RepoMind's test-suite."""

import json
from collections import Counter


def public_api() -> int:
    """Return a value produced by a used private helper."""
    return _used_helper()


def _used_helper() -> int:
    """Private helper referenced by the public API."""
    return 42


def _never_used() -> None:
    """Private helper that is never referenced anywhere."""
    return None
