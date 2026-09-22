"""Tests for security signal extraction and the security rules."""

from __future__ import annotations

from pathlib import Path

from repomind.core.engine import AnalysisResult, analyze_repository
from repomind.core.pyparser import parse_module
from repomind.models.metrics import SecuritySignal


def _analyze(sample_project: Path) -> AnalysisResult:
    return analyze_repository(sample_project, use_history=False)


def _signals(tmp_path: Path, source: str) -> list[SecuritySignal]:
    module = tmp_path / "mod.py"
    module.write_text(source, encoding="utf-8")
    return parse_module(module, tmp_path).security_signals


def _kinds(signals: list[SecuritySignal]) -> set[str]:
    return {signal.kind for signal in signals}


def test_fixture_signals_are_extracted(sample_project: Path) -> None:
    module = parse_module(sample_project / "samplepkg" / "insecure.py", sample_project)

    assert _kinds(module.security_signals) == {
        "dynamic-execution",
        "shell-execution",
        "unsafe-deserialization",
        "weak-hash",
        "insecure-temp-file",
        "hardcoded-secret",
    }
    assert module.security_signals == sorted(
        module.security_signals, key=lambda signal: (signal.lineno, signal.kind)
    )


def test_engine_reports_security_rules(sample_project: Path) -> None:
    rule_ids = {finding.rule_id for finding in _analyze(sample_project).findings}

    assert {
        "security/dynamic-execution",
        "security/shell-execution",
        "security/unsafe-deserialization",
        "security/weak-hash",
        "security/insecure-temp-file",
        "security/hardcoded-secret",
    } <= rule_ids


def test_secret_value_is_never_reported(sample_project: Path) -> None:
    findings = [
        finding
        for finding in _analyze(sample_project).findings
        if finding.rule_id == "security/hardcoded-secret"
    ]

    assert findings
    assert all("super-secret-password" not in finding.message for finding in findings)
    assert all("super-secret-password" not in str(finding.details) for finding in findings)


def test_aliases_are_resolved(tmp_path: Path) -> None:
    signals = _signals(
        tmp_path,
        "import subprocess as sp\n"
        "from os import system\n"
        "from hashlib import md5\n"
        "\n"
        "\n"
        "def run(command: str, data: bytes) -> int:\n"
        "    sp.run(command, shell=True, check=False)\n"
        "    system(command)\n"
        "    md5(data)\n"
        "    return 0\n",
    )

    assert _kinds(signals) == {"shell-execution", "weak-hash"}


def test_safe_variants_are_not_flagged(tmp_path: Path) -> None:
    signals = _signals(
        tmp_path,
        "import hashlib\n"
        "import yaml\n"
        "\n"
        'API_TOKEN = "changeme-placeholder"\n'
        'SHORT_SECRET = "abc"\n'
        "\n"
        "\n"
        "def load(text: str, data: bytes) -> object:\n"
        "    hashlib.md5(data, usedforsecurity=False)\n"
        "    yaml.safe_load(text)\n"
        "    return yaml.load(text, Loader=yaml.SafeLoader)\n",
    )

    assert signals == []


def test_yaml_load_with_unsafe_loader_is_flagged(tmp_path: Path) -> None:
    signals = _signals(
        tmp_path,
        "import yaml\n"
        "\n"
        "\n"
        "def load(text: str) -> object:\n"
        "    return yaml.load(text, Loader=yaml.UnsafeLoader)\n",
    )

    assert _kinds(signals) == {"unsafe-deserialization"}


def test_weak_hash_via_hashlib_new_is_flagged(tmp_path: Path) -> None:
    signals = _signals(
        tmp_path,
        "import hashlib\n"
        "\n"
        "\n"
        "def digest(data: bytes) -> str:\n"
        '    return hashlib.new("md5", data).hexdigest()\n',
    )

    assert _kinds(signals) == {"weak-hash"}


def test_shell_true_on_any_callable_is_flagged(tmp_path: Path) -> None:
    signals = _signals(
        tmp_path,
        "import mytools\n"
        "\n"
        "\n"
        "def run(command: str) -> None:\n"
        "    mytools.execute(command, shell=True)\n",
    )

    assert _kinds(signals) == {"shell-execution"}
