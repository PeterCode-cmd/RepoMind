"""Tests for LCOM4 cohesion, module instability and the low-cohesion rule."""

from __future__ import annotations

import json
from pathlib import Path

from repomind.core.discovery import find_python_files
from repomind.core.engine import analyze_repository
from repomind.core.graph import DependencyGraph
from repomind.core.pyparser import parse_module
from repomind.models.metrics import ParsedModule
from repomind.reporters.json_reporter import render_json

_BLOB_SOURCE = (
    '"""Module."""\n'
    "\n"
    "\n"
    "class Blob:\n"
    '    """Disconnected."""\n'
    "\n"
    "    def __init__(self) -> None:\n"
    "        self.left = 0\n"
    "        self.right = 0\n"
    "        self.other = 0\n"
    "\n"
    "    def bump_left(self) -> None:\n"
    '        """Left."""\n'
    "        self.left += 1\n"
    "\n"
    "    def bump_right(self) -> None:\n"
    '        """Right."""\n'
    "        self.right += 1\n"
    "\n"
    "    def bump_other(self) -> None:\n"
    '        """Other."""\n'
    "        self.other += 1\n"
)


def _write(tmp_path: Path, name: str, source: str) -> None:
    (tmp_path / name).write_text(source, encoding="utf-8")


def _first_class(tmp_path: Path, source: str) -> ParsedModule:
    _write(tmp_path, "mod.py", source)
    module = parse_module(tmp_path / "mod.py", tmp_path)
    assert module.classes
    return module


def test_cohesive_class_has_single_component(tmp_path: Path) -> None:
    module = _first_class(
        tmp_path,
        '"""Module."""\n'
        "\n"
        "\n"
        "class Account:\n"
        '    """Cohesive."""\n'
        "\n"
        "    def __init__(self) -> None:\n"
        "        self.balance = 0\n"
        "\n"
        "    def deposit(self, amount: int) -> None:\n"
        '        """Deposit."""\n'
        "        self.balance += amount\n"
        "\n"
        "    def withdraw(self, amount: int) -> None:\n"
        '        """Withdraw."""\n'
        "        self.balance -= amount\n",
    )

    assert module.classes[0].lcom == 1


def test_disconnected_methods_increase_lcom(tmp_path: Path) -> None:
    module = _first_class(tmp_path, _BLOB_SOURCE)

    assert module.classes[0].lcom == 3


def test_method_calls_connect_components(tmp_path: Path) -> None:
    module = _first_class(
        tmp_path,
        '"""Module."""\n'
        "\n"
        "\n"
        "class Pipeline:\n"
        '    """Chained."""\n'
        "\n"
        "    def run(self) -> int:\n"
        '        """Run."""\n'
        "        return self.step()\n"
        "\n"
        "    def step(self) -> int:\n"
        '        """Step."""\n'
        "        return 1\n"
        "\n"
        "    def helper(self) -> int:\n"
        '        """Helper."""\n'
        "        return 2\n",
    )

    assert module.classes[0].lcom == 2


def test_stub_methods_are_excluded_from_lcom(tmp_path: Path) -> None:
    module = _first_class(
        tmp_path,
        '"""Module."""\n'
        "\n"
        "from typing import Protocol\n"
        "\n"
        "\n"
        "class Runner(Protocol):\n"
        '    """Protocol with stub methods."""\n'
        "\n"
        "    def start(self) -> None:\n"
        '        """Start."""\n'
        "        ...\n"
        "\n"
        "    def stop(self) -> None:\n"
        '        """Stop."""\n'
        "        pass\n"
        "\n"
        "    def status(self) -> int:\n"
        '        """Status."""\n'
        "        raise NotImplementedError\n",
    )

    assert module.classes[0].lcom == 0


def test_engine_reports_low_cohesion(tmp_path: Path) -> None:
    _write(tmp_path, "app.py", _BLOB_SOURCE)

    result = analyze_repository(tmp_path, use_history=False)
    findings = [finding for finding in result.findings if finding.rule_id == "design/low-cohesion"]

    assert findings
    assert findings[0].details["lcom"] == 3
    assert findings[0].symbol == "app.Blob"


def test_instability_ranks_coupled_modules(sample_project: Path) -> None:
    modules = [parse_module(path, sample_project) for path in find_python_files(sample_project)]
    graph = DependencyGraph.build(modules)

    values = graph.instability()

    assert values["samplepkg.b"] == 0.5
    assert 0.0 < values["samplepkg.a"] < 1.0
    assert values["samplepkg.broken"] == 0.0
    top = graph.top_unstable(limit=3)
    assert top[0] == ("samplepkg", 1.0)
    assert ("samplepkg.b", 0.5) in top
    assert all(value > 0.0 for _, value in top)


def test_json_includes_instability(sample_project: Path) -> None:
    payload = json.loads(render_json(analyze_repository(sample_project, use_history=False)))

    instability = payload["graph"]["instability"]

    assert instability
    assert {"module", "instability", "afferent", "efferent"} <= set(instability[0])
