"""Tests for the doctor command and the diagnostics behind it."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

import repomind.core.doctor as doctor_module
from repomind.cli.app import app
from repomind.core.doctor import CheckResult
from repomind.semantic.store import METADATA_FILENAME

runner = CliRunner()


def _statuses(checks: list[CheckResult]) -> dict[str, str]:
    return {check.name: check.status for check in checks}


def _patch_environment(monkeypatch, *, modules: bool = True) -> None:
    monkeypatch.setattr(doctor_module, "_has_module", lambda name: modules)
    monkeypatch.setattr(doctor_module, "_ollama_models", lambda: ["qwen2.5-coder:7b"])


def test_metadata_filename_matches_store() -> None:
    assert doctor_module._INDEX_METADATA == METADATA_FILENAME


def test_checks_run_in_plain_directory(tmp_path: Path, monkeypatch) -> None:
    _patch_environment(monkeypatch)

    checks = doctor_module.run_checks(tmp_path)

    statuses = _statuses(checks)
    assert statuses["python"] == "ok"
    assert statuses["configuration"] == "ok"
    assert statuses["git repository"] == "warn"
    assert statuses["semantic extra"] == "ok"
    assert statuses["semantic index"] == "warn"
    assert statuses["ollama"] == "ok"


def test_missing_extras_produce_install_hints(tmp_path: Path, monkeypatch) -> None:
    _patch_environment(monkeypatch, modules=False)

    checks = doctor_module.run_checks(tmp_path)

    extras = {check.name: check for check in checks}
    assert extras["semantic extra"].status == "warn"
    assert "repomind-analyzer[semantic]" in (extras["semantic extra"].hint or "")
    assert "repomind-analyzer[llm]" in (extras["llm extra"].hint or "")


def test_broken_configuration_is_reported(tmp_path: Path, monkeypatch) -> None:
    _patch_environment(monkeypatch)
    (tmp_path / "repomind.toml").write_text("unknown_key = true\n", encoding="utf-8")

    checks = doctor_module.run_checks(tmp_path)

    assert _statuses(checks)["configuration"] == "missing"
    assert all(check.name != "semantic index" for check in checks)


def test_ollama_without_model_reports_pull_hint(tmp_path: Path, monkeypatch) -> None:
    _patch_environment(monkeypatch)
    monkeypatch.setattr(doctor_module, "_ollama_models", lambda: [])

    checks = doctor_module.run_checks(tmp_path)

    ollama = next(check for check in checks if check.name == "ollama")
    assert ollama.status == "warn"
    assert "ollama pull" in (ollama.hint or "")


def test_cli_doctor_prints_table(tmp_path: Path, monkeypatch) -> None:
    _patch_environment(monkeypatch)

    result = runner.invoke(app, ["doctor", str(tmp_path)])

    assert result.exit_code == 0
    assert "RepoMind doctor" in result.stdout
    assert "configuration" in result.stdout
