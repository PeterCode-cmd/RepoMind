"""Exception hierarchy and user-facing errors for RepoMind."""

from __future__ import annotations


class RepoMindError(Exception):
    """Base class for every error raised deliberately by RepoMind."""


class RepositoryNotFoundError(RepoMindError):
    """Raised when the analyzed path does not exist or is not a directory."""


class ConfigurationError(RepoMindError):
    """Raised when a configuration file is malformed or contains unknown keys."""
