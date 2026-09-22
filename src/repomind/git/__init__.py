"""Git history analysis for RepoMind.

The public entry point is :func:`repomind.git.history.analyze_history`; this
package will also host blame-level and code-ownership analyses on the roadmap.
"""

from __future__ import annotations

from repomind.git.history import FileHistory, HistoryReport, analyze_history

__all__ = ["FileHistory", "HistoryReport", "analyze_history"]
