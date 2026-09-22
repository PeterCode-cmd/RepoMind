"""Git history analysis for RepoMind.

The public entry points are :func:`repomind.git.history.analyze_history` and
:func:`repomind.git.diff.changed_paths`; this package will also host
blame-level and code-ownership analyses on the roadmap.
"""

from __future__ import annotations

from repomind.git.diff import changed_paths
from repomind.git.history import FileHistory, HistoryReport, analyze_history

__all__ = ["FileHistory", "HistoryReport", "analyze_history", "changed_paths"]
