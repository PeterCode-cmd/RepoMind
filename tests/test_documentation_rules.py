"""Tests for the missing-docstring rule."""

from __future__ import annotations

from pathlib import Path

from repomind.core.engine import analyze_repository
from repomind.core.pyparser import parse_module


def _write(tmp_path: Path, source: str) -> None:
    (tmp_path / "mod.py").write_text(source, encoding="utf-8")


def _missing_docstrings(tmp_path: Path) -> list[str]:
    result = analyze_repository(tmp_path, use_history=False)
    return [
        finding.symbol or finding.message
        for finding in result.findings
        if finding.rule_id == "documentation/missing-docstring"
    ]


def test_parser_records_docstrings(sample_project: Path) -> None:
    documented = parse_module(sample_project / "samplepkg" / "a.py", sample_project)
    undocumented = parse_module(sample_project / "samplepkg" / "undocumented.py", sample_project)

    assert documented.has_docstring
    assert documented.functions[0].has_docstring
    assert undocumented.has_docstring
    assert not undocumented.classes[0].has_docstring
    assert not undocumented.classes[0].methods[0].has_docstring


def test_engine_reports_missing_docstrings(sample_project: Path) -> None:
    result = analyze_repository(sample_project, use_history=False)
    symbols = {
        finding.symbol
        for finding in result.findings
        if finding.rule_id == "documentation/missing-docstring"
    }

    assert "samplepkg.undocumented.Worker" in symbols
    assert "samplepkg.undocumented.Worker.run" in symbols


def test_undocumented_module_is_reported(tmp_path: Path) -> None:
    _write(tmp_path, "def public() -> int:\n    return 1\n")

    findings = _missing_docstrings(tmp_path)

    assert any("Module" in finding for finding in findings)
    assert "mod.public" in findings


def test_private_and_dunder_names_are_exempt(tmp_path: Path) -> None:
    _write(
        tmp_path,
        '"""Module."""\n'
        "\n"
        "\n"
        "def _helper() -> int:\n"
        "    return 1\n"
        "\n"
        "\n"
        "class Service:\n"
        '    """Documented."""\n'
        "\n"
        "    def __init__(self) -> None:\n"
        "        self.value = 1\n",
    )

    assert _missing_docstrings(tmp_path) == []


def test_decorated_functions_are_exempt(tmp_path: Path) -> None:
    _write(
        tmp_path,
        '"""Module."""\n'
        "\n"
        "\n"
        "def command(function: object) -> object:\n"
        '    """Register a callable."""\n'
        "    return function\n"
        "\n"
        "\n"
        "@command\n"
        "def serve() -> None:\n"
        "    return None\n",
    )

    assert _missing_docstrings(tmp_path) == []


def test_test_modules_are_exempt(tmp_path: Path) -> None:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_api.py").write_text(
        "def test_something() -> None:\n    pass\n", encoding="utf-8"
    )

    assert _missing_docstrings(tmp_path) == []
