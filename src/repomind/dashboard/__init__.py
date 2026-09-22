"""Interactive dashboard (roadmap).

Streamlit-based dashboard that visualizes the same :class:`AnalysisResult`
the CLI reports: health score, findings explorer, dependency graph and change
hotspots. The dashboard must remain a thin presentation layer over
:mod:`repomind.core` and :mod:`repomind.reporters`.
"""

from __future__ import annotations
