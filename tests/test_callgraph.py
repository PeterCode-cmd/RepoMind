"""Tests for the function-level call graph and caller enrichment."""

from __future__ import annotations

import json
from pathlib import Path

from repomind.core.callgraph import build_call_graph
from repomind.core.discovery import find_python_files
from repomind.core.engine import analyze_repository
from repomind.core.pyparser import parse_module
from repomind.models.metrics import ParsedModule
from repomind.reporters.json_reporter import render_json


def _module(tmp_path: Path, name: str, source: str) -> ParsedModule:
    path = tmp_path / name
    path.write_text(source, encoding="utf-8")
    return parse_module(path, tmp_path)


def test_parser_records_calls(tmp_path: Path) -> None:
    module = _module(
        tmp_path,
        "mod.py",
        '"""Module."""\n'
        "\n"
        "\n"
        "def helper() -> int:\n"
        '    """Help."""\n'
        "    return 1\n"
        "\n"
        "\n"
        "def caller() -> int:\n"
        '    """Call."""\n'
        "    return helper() + int('1')\n",
    )

    caller = next(function for function in module.functions if function.name == "caller")

    assert caller.calls == ("helper", "int")


def test_call_graph_resolves_local_and_method_calls(tmp_path: Path) -> None:
    module = _module(
        tmp_path,
        "mod.py",
        '"""Module."""\n'
        "\n"
        "\n"
        "class Service:\n"
        '    """Service."""\n'
        "\n"
        "    def run(self) -> int:\n"
        '        """Run."""\n'
        "        return self.step()\n"
        "\n"
        "    def step(self) -> int:\n"
        '        """Step."""\n'
        "        return Other().value()\n"
        "\n"
        "\n"
        "class Other:\n"
        '    """Other."""\n'
        "\n"
        "    def value(self) -> int:\n"
        '        """Value."""\n'
        "        return 2\n"
        "\n"
        "\n"
        "def entry() -> int:\n"
        '    """Entry."""\n'
        "    return Service().run()\n",
    )

    graph = build_call_graph([module])

    assert graph.edges["mod.Service.run"] == {"mod.Service.step"}
    assert graph.caller_count("mod.Service.step") == 1
    assert graph.caller_count("mod.Service.run") == 1
    assert graph.edges["mod.entry"] == {"mod.Service.run"}
    assert graph.callee_count("mod.Service.run") == 1


def test_call_graph_resolves_imported_calls(tmp_path: Path) -> None:
    (tmp_path / "__init__.py").write_text('"""Package."""\n', encoding="utf-8")
    helper = _module(
        tmp_path,
        "helper.py",
        '"""Helper."""\n\n\ndef beta(value: int) -> int:\n    """Beta."""\n    return value\n',
    )
    caller = _module(
        tmp_path,
        "caller.py",
        '"""Caller."""\n'
        "\n"
        "from .helper import beta\n"
        "\n"
        "\n"
        "def alpha() -> int:\n"
        '    """Alpha."""\n'
        "    return beta(1)\n",
    )

    graph = build_call_graph([helper, caller])

    assert graph.edges["caller.alpha"] == {"helper.beta"}


def test_fixture_cycle_has_bidirectional_call_edges(sample_project: Path) -> None:
    modules = [parse_module(path, sample_project) for path in find_python_files(sample_project)]

    graph = build_call_graph(modules)

    assert "samplepkg.b.beta" in graph.edges["samplepkg.a.alpha"]
    assert "samplepkg.a.alpha" in graph.edges["samplepkg.b.beta"]
    assert "samplepkg.dead._used_helper" in graph.edges["samplepkg.dead.public_api"]


def test_engine_enriches_findings_with_caller_counts(tmp_path: Path) -> None:
    branches = "".join(f"    if value > {index}:\n        result += 1\n" for index in range(10))
    (tmp_path / "app.py").write_text(
        '"""Module."""\n'
        "\n"
        "\n"
        "def tangled(value: int) -> int:\n"
        '    """Tangled."""\n'
        "    result = 0\n"
        f"{branches}"
        "    return result\n"
        "\n"
        "\n"
        "def wrapper(value: int) -> int:\n"
        '    """Wrapper."""\n'
        "    return tangled(value)\n",
        encoding="utf-8",
    )

    result = analyze_repository(tmp_path, use_history=False)
    finding = next(
        finding
        for finding in result.findings
        if finding.rule_id == "complexity/high-cyclomatic-complexity"
    )

    assert finding.details["callers"] == 1
    assert result.call_graph.edge_count == 1


def test_json_includes_call_graph(sample_project: Path) -> None:
    payload = json.loads(render_json(analyze_repository(sample_project, use_history=False)))

    assert payload["call_graph"]["functions"] > 0
    assert payload["call_graph"]["edges"] > 0
    assert payload["call_graph"]["top_fan_in"]
