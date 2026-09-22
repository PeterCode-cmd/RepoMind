"""Git history analysis for RepoMind.

The public entry points are :func:`repomind.git.history.analyze_history`,
:func:`repomind.git.diff.changed_paths` and
:func:`repomind.git.blame.blame_functions`.
"""

from __future__ import annotations

from repomind.git.blame import FunctionChurn, blame_functions
from repomind.git.diff import changed_paths
from repomind.git.history import FileHistory, HistoryReport, analyze_history

__all__ = [
    "FileHistory",
    "FunctionChurn",
    "HistoryReport",
    "analyze_history",
    "blame_functions",
    "changed_paths",
]
