"""Tests for the dependency graph."""

from __future__ import annotations

from pathlib import Path

from repomind.core.discovery import find_python_files
from repomind.core.graph import DependencyGraph
from repomind.core.pyparser import parse_module


def _build(sample_project: Path) -> DependencyGraph:
    modules = [parse_module(path, sample_project) for path in find_python_files(sample_project)]
    return DependencyGraph.build(modules)


def test_cycles_are_detected(sample_project: Path) -> None:
    graph = _build(sample_project)
    cycles = graph.cycles()
    assert len(cycles) == 1
    assert cycles[0] == ("samplepkg.a", "samplepkg.b")


def test_fan_in_and_fan_out(sample_project: Path) -> None:
    graph = _build(sample_project)
    assert graph.fan_in()["samplepkg.b"] == 1
    assert graph.fan_in()["samplepkg.a"] == 2
    assert graph.fan_out()["samplepkg.a"] == 1
    assert graph.fan_out()["samplepkg"] == 1


def test_external_imports_are_tracked(sample_project: Path) -> None:
    graph = _build(sample_project)
    assert "json" in graph.external_imports
    assert "collections" in graph.external_imports


def test_counts_and_dot_export(sample_project: Path) -> None:
    graph = _build(sample_project)
    assert graph.module_count == 8
    assert graph.edge_count >= 3
    dot = graph.to_dot()
    assert "digraph repomind" in dot
    assert '"samplepkg.a" -> "samplepkg.b"' in dot


def test_top_hubs_are_sorted(sample_project: Path) -> None:
    graph = _build(sample_project)
    hubs = graph.top_fan_in(limit=3)
    assert hubs
    assert hubs[0][1] >= hubs[-1][1]
