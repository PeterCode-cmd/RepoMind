"""Tests for configuration loading and validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from repomind.config import AnalysisConfig, Thresholds, load_config
from repomind.errors import ConfigurationError


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_defaults_without_configuration_file(tmp_path: Path) -> None:
    config = load_config(tmp_path)
    assert config == AnalysisConfig()
    assert config.thresholds.cyclomatic_warn == 10


def test_unrelated_pyproject_is_ignored(tmp_path: Path) -> None:
    _write(
        tmp_path / "pyproject.toml",
        "[build-system]\nrequires = ['hatchling']\n\n[project]\nname = 'demo'\n",
    )
    assert load_config(tmp_path) == AnalysisConfig()


def test_pyproject_tool_table_is_loaded(tmp_path: Path) -> None:
    _write(
        tmp_path / "pyproject.toml",
        "[project]\nname = 'demo'\n\n"
        "[tool.repomind]\nexclude = ['migrations']\nhistory_commits = 42\n\n"
        "[tool.repomind.thresholds]\ncyclomatic_warn = 3\n",
    )
    config = load_config(tmp_path)
    assert config.exclude == ("migrations",)
    assert config.history_commits == 42
    assert config.thresholds.cyclomatic_warn == 3
    assert config.thresholds.cyclomatic_high == 15


def test_repomind_toml_takes_precedence(tmp_path: Path) -> None:
    _write(tmp_path / "pyproject.toml", "[tool.repomind]\nhistory_commits = 7\n")
    _write(tmp_path / "repomind.toml", "use_git_history = false\n")

    config = load_config(tmp_path)

    assert config.use_git_history is False
    assert config.history_commits == 500


def test_explicit_config_file(tmp_path: Path) -> None:
    path = tmp_path / "custom.toml"
    _write(path, "exclude = ['vendor']\n")
    config = load_config(tmp_path, config_file=path)
    assert config.exclude == ("vendor",)


def test_unknown_keys_are_rejected(tmp_path: Path) -> None:
    _write(tmp_path / "repomind.toml", "unknown_option = true\n")
    with pytest.raises(ConfigurationError, match="unknown configuration keys"):
        load_config(tmp_path)


def test_ignore_entries_are_loaded(tmp_path: Path) -> None:
    _write(
        tmp_path / "repomind.toml",
        'ignore = ["complexity/deep-nesting@src/app.py", "dead-code/unused-import"]\n',
    )
    config = load_config(tmp_path)
    assert config.ignore == (
        "complexity/deep-nesting@src/app.py",
        "dead-code/unused-import",
    )


def test_invalid_ignore_entry_is_rejected(tmp_path: Path) -> None:
    _write(tmp_path / "repomind.toml", 'ignore = ["@src/app.py"]\n')
    with pytest.raises(ConfigurationError, match="missing rule id"):
        load_config(tmp_path)


def test_ignore_must_be_a_list_of_strings(tmp_path: Path) -> None:
    _write(tmp_path / "repomind.toml", 'ignore = "dead-code/unused-import"\n')
    with pytest.raises(ConfigurationError, match="'ignore' must be a list"):
        load_config(tmp_path)


def test_unknown_threshold_is_rejected(tmp_path: Path) -> None:
    _write(tmp_path / "repomind.toml", "[thresholds]\nnot_a_threshold = 3\n")
    with pytest.raises(ConfigurationError, match="unknown thresholds"):
        load_config(tmp_path)


def test_invalid_types_are_rejected(tmp_path: Path) -> None:
    _write(tmp_path / "repomind.toml", "history_commits = 'many'\n")
    with pytest.raises(ConfigurationError, match="must be an integer"):
        load_config(tmp_path)


def test_invalid_toml_is_rejected(tmp_path: Path) -> None:
    _write(tmp_path / "repomind.toml", "exclude = [\n")
    with pytest.raises(ConfigurationError, match="invalid TOML"):
        load_config(tmp_path)


def test_thresholds_are_frozen() -> None:
    thresholds = Thresholds()
    with pytest.raises(AttributeError):
        thresholds.cyclomatic_warn = 99  # type: ignore[misc]


def test_repository_own_configuration_is_valid() -> None:
    root = Path(__file__).resolve().parents[1]
    config = load_config(root)
    assert "tests/fixtures" in config.exclude
    assert config.ignore


def test_llm_config_is_loaded(tmp_path: Path) -> None:
    _write(
        tmp_path / "repomind.toml",
        '[llm]\nmodel = "gemini/gemini-3.8-flash"\ntimeout = 30\nmax_findings = 5\n',
    )

    config = load_config(tmp_path)

    assert config.llm.model == "gemini/gemini-3.8-flash"
    assert config.llm.timeout == 30
    assert config.llm.max_findings == 5


def test_llm_defaults_are_used(tmp_path: Path) -> None:
    config = load_config(tmp_path)
    assert config.llm.model.startswith("ollama/")


def test_llm_api_keys_are_rejected(tmp_path: Path) -> None:
    _write(tmp_path / "repomind.toml", '[llm]\napi_key = "secret"\n')
    with pytest.raises(ConfigurationError, match="unknown llm keys"):
        load_config(tmp_path)


def test_invalid_llm_timeout_is_rejected(tmp_path: Path) -> None:
    _write(tmp_path / "repomind.toml", "[llm]\ntimeout = 0\n")
    with pytest.raises(ConfigurationError, match=r"'llm\.timeout'"):
        load_config(tmp_path)
