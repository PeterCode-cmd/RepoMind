"""Configuration models and loading for RepoMind.

Configuration can be provided in a ``repomind.toml`` file at the root of the
analyzed repository or under ``[tool.repomind]`` in ``pyproject.toml``::

    [tool.repomind]
    exclude = ["migrations/*"]
    use_git_history = true
    history_commits = 500

    [tool.repomind.thresholds]
    cyclomatic_warn = 12
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

from repomind.errors import ConfigurationError


@dataclass(frozen=True, slots=True)
class Thresholds:
    """Numeric thresholds that drive rule decisions.

    All complexity thresholds are intentionally conservative; projects with a
    different maturity level can raise or lower them per repository.
    """

    cyclomatic_warn: int = 10
    cyclomatic_high: int = 15
    cyclomatic_critical: int = 20
    cognitive_warn: int = 15
    cognitive_high: int = 25
    cognitive_critical: int = 40
    function_length_warn: int = 60
    function_length_high: int = 100
    function_length_critical: int = 200
    parameters_warn: int = 5
    parameters_high: int = 8
    nesting_warn: int = 4
    nesting_high: int = 6
    file_loc_warn: int = 400
    file_loc_high: int = 800
    file_loc_critical: int = 1500
    god_object_methods: int = 15
    god_object_loc: int = 250
    god_object_wmc: int = 70
    hotspot_min_cyclomatic: int = 10
    hotspot_min_commits: int = 5


@dataclass(frozen=True, slots=True)
class AnalysisConfig:
    """Complete configuration for one analysis run."""

    thresholds: Thresholds = field(default_factory=Thresholds)
    exclude: tuple[str, ...] = ()
    use_git_history: bool = True
    history_commits: int = 500


CONFIG_FILENAMES = ("repomind.toml", "pyproject.toml")
_SECTION_KEYS = frozenset({"thresholds", "exclude", "use_git_history", "history_commits"})


def load_config(root: Path, *, config_file: Path | None = None) -> AnalysisConfig:
    """Load configuration for *root*, falling back to sensible defaults.

    Discovery reads ``repomind.toml`` (whole file is the config) and
    ``pyproject.toml`` (only the ``[tool.repomind]`` table) in that order.
    An explicit ``config_file`` may be either style.

    Args:
        root: Analyzed repository root.
        config_file: Explicit configuration file overriding repository discovery.

    Returns:
        The merged :class:`AnalysisConfig`.

    Raises:
        ConfigurationError: If a present configuration file is invalid.
    """
    if config_file is not None:
        return _parse_config(_read_table(config_file, explicit=True))

    for filename in CONFIG_FILENAMES:
        candidate = root / filename
        if not candidate.is_file():
            continue
        table = _read_table(candidate, explicit=False)
        if table:
            return _parse_config(table)

    return AnalysisConfig()


def _read_table(path: Path, *, explicit: bool) -> dict[str, Any]:
    """Read and normalise the RepoMind table from *path*.

    A ``[tool.repomind]`` or ``[repomind]`` section wins; a bare
    ``repomind.toml`` (or an explicit ``--config`` file) is treated as the
    table itself. Unrelated ``pyproject.toml`` content yields an empty table.
    """
    document = _load_toml(path)

    tool = document.get("tool")
    if isinstance(tool, dict) and isinstance(tool.get("repomind"), dict):
        return dict(tool["repomind"])
    nested = document.get("repomind")
    if isinstance(nested, dict):
        return dict(nested)
    if explicit or path.name == "repomind.toml":
        return document
    return {}


def _load_toml(path: Path) -> dict[str, Any]:
    """Read a TOML document, converting failures into ConfigurationError."""
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigurationError(f"{path}: invalid TOML: {exc}") from exc
    except OSError as exc:
        raise ConfigurationError(f"{path}: cannot be read: {exc}") from exc


def _parse_config(table: dict[str, Any]) -> AnalysisConfig:
    """Validate *table* and build an :class:`AnalysisConfig`."""
    unknown = sorted(set(table) - _SECTION_KEYS)
    if unknown:
        valid = ", ".join(sorted(_SECTION_KEYS))
        raise ConfigurationError(
            f"unknown configuration keys: {', '.join(unknown)} (valid keys: {valid})"
        )

    thresholds = Thresholds()
    if "thresholds" in table:
        thresholds = _parse_thresholds(table["thresholds"])

    exclude: tuple[str, ...] = ()
    if "exclude" in table:
        raw = table["exclude"]
        if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
            raise ConfigurationError("'exclude' must be a list of glob patterns")
        exclude = tuple(raw)

    use_git_history = True
    if "use_git_history" in table:
        raw_flag = table["use_git_history"]
        if not isinstance(raw_flag, bool):
            raise ConfigurationError("'use_git_history' must be a boolean")
        use_git_history = raw_flag

    history_commits = 500
    if "history_commits" in table:
        raw_commits = table["history_commits"]
        if not isinstance(raw_commits, int) or isinstance(raw_commits, bool):
            raise ConfigurationError("'history_commits' must be an integer")
        if raw_commits < 1:
            raise ConfigurationError("'history_commits' must be a positive integer")
        history_commits = raw_commits

    return AnalysisConfig(
        thresholds=thresholds,
        exclude=exclude,
        use_git_history=use_git_history,
        history_commits=history_commits,
    )


def _parse_thresholds(table: object) -> Thresholds:
    """Validate the ``[tool.repomind.thresholds]`` table."""
    if not isinstance(table, dict):
        raise ConfigurationError("'thresholds' must be a table")

    valid = {item.name for item in fields(Thresholds)}
    unknown = sorted(set(table) - valid)
    if unknown:
        valid_names = ", ".join(sorted(valid))
        raise ConfigurationError(
            f"unknown thresholds: {', '.join(unknown)} (valid thresholds: {valid_names})"
        )

    values: dict[str, int] = {}
    for key, value in table.items():
        if not isinstance(value, int) or isinstance(value, bool):
            raise ConfigurationError(f"threshold '{key}' must be an integer")
        values[key] = value

    return Thresholds(**values)
