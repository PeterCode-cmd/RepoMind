"""Configuration models and loading for RepoMind.

Configuration can be provided in a ``repomind.toml`` file at the root of the
analyzed repository or under ``[tool.repomind]`` in ``pyproject.toml``::

    [tool.repomind]
    exclude = ["migrations/*"]
    use_git_history = true
    history_commits = 500
    ignore = ["maintainability/too-many-parameters@src/app/cli.py"]

    [tool.repomind.thresholds]
    cyclomatic_warn = 12
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

from repomind.core.suppression import parse_suppression
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
    lcom_warn: int = 3
    lcom_high: int = 5
    hotspot_min_cyclomatic: int = 10
    hotspot_min_commits: int = 5


_DEFAULT_HISTORY_COMMITS = 500
_DEFAULT_BLAME_FILES = 10
DEFAULT_LLM_MODEL = "ollama/qwen2.5-coder:7b"
DEFAULT_LLM_TIMEOUT = 60
DEFAULT_LLM_MAX_FINDINGS = 20
DEFAULT_SEMANTIC_PROVIDER = "fastembed"
DEFAULT_SEMANTIC_MODEL = "BAAI/bge-small-en-v1.5"
DEFAULT_SEMANTIC_INDEX_DIR = ".repomind"
DEFAULT_SEMANTIC_TOP_K = 8
DEFAULT_SEMANTIC_MIN_SCORE = 0.25
_SEMANTIC_PROVIDERS = frozenset({"fastembed", "api"})


@dataclass(frozen=True, slots=True)
class SemanticConfig:
    """Settings for the optional semantic layer.

    ``provider`` selects where embeddings come from: ``fastembed`` runs a
    small ONNX model locally, ``api`` calls an embedding model through litellm
    with the user's own API key from the environment.
    """

    provider: str = DEFAULT_SEMANTIC_PROVIDER
    model: str = DEFAULT_SEMANTIC_MODEL
    index_dir: str = DEFAULT_SEMANTIC_INDEX_DIR
    top_k: int = DEFAULT_SEMANTIC_TOP_K
    min_score: float = DEFAULT_SEMANTIC_MIN_SCORE


@dataclass(frozen=True, slots=True)
class LlmConfig:
    """LLM settings for the optional agent layer.

    ``model`` uses litellm's provider prefix (``ollama/...``, ``gemini/...``,
    ``gpt-4o-mini``, ...). API keys are read from the environment by litellm
    and are never stored in configuration.
    """

    model: str = DEFAULT_LLM_MODEL
    timeout: int = DEFAULT_LLM_TIMEOUT
    max_findings: int = DEFAULT_LLM_MAX_FINDINGS


@dataclass(frozen=True, slots=True)
class AnalysisConfig:
    """Complete configuration for one analysis run."""

    thresholds: Thresholds = field(default_factory=Thresholds)
    exclude: tuple[str, ...] = ()
    ignore: tuple[str, ...] = ()
    use_git_history: bool = True
    history_commits: int = _DEFAULT_HISTORY_COMMITS
    blame_files: int = _DEFAULT_BLAME_FILES
    llm: LlmConfig = field(default_factory=LlmConfig)
    semantic: SemanticConfig = field(default_factory=SemanticConfig)


CONFIG_FILENAMES = ("repomind.toml", "pyproject.toml")
_SECTION_KEYS = frozenset(
    {
        "thresholds",
        "exclude",
        "ignore",
        "use_git_history",
        "history_commits",
        "blame_files",
        "llm",
        "semantic",
    }
)


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
    _reject_unknown_keys(table)
    return AnalysisConfig(
        thresholds=_parse_thresholds(table.get("thresholds", {})),
        exclude=_parse_exclude(table),
        ignore=_parse_ignore(table),
        use_git_history=_parse_bool(table, "use_git_history", default=True),
        history_commits=_parse_history_commits(table),
        blame_files=_parse_blame_files(table),
        llm=_parse_llm(table),
        semantic=_parse_semantic(table),
    )


def _parse_semantic(table: dict[str, Any]) -> SemanticConfig:
    """Validate the optional ``[semantic]`` table."""
    if "semantic" not in table:
        return SemanticConfig()
    raw = table["semantic"]
    if not isinstance(raw, dict):
        raise ConfigurationError("'semantic' must be a table")
    _reject_unknown_semantic_keys(raw)
    return SemanticConfig(
        provider=_parse_semantic_provider(raw),
        model=_parse_semantic_model(raw),
        index_dir=_parse_semantic_index_dir(raw),
        top_k=_parse_positive_int(raw, "top_k", DEFAULT_SEMANTIC_TOP_K, prefix="semantic"),
        min_score=_parse_semantic_min_score(raw),
    )


def _parse_semantic_provider(raw: dict[str, Any]) -> str:
    """Validate the ``[semantic]`` embedding provider."""
    provider = raw.get("provider", DEFAULT_SEMANTIC_PROVIDER)
    if provider not in _SEMANTIC_PROVIDERS:
        valid = ", ".join(sorted(_SEMANTIC_PROVIDERS))
        raise ConfigurationError(f"'semantic.provider' must be one of: {valid}")
    return str(provider)


def _parse_semantic_model(raw: dict[str, Any]) -> str:
    """Validate the ``[semantic]`` model identifier."""
    model = raw.get("model", DEFAULT_SEMANTIC_MODEL)
    if not isinstance(model, str) or not model.strip():
        raise ConfigurationError("'semantic.model' must be a non-empty string")
    return model


def _parse_semantic_index_dir(raw: dict[str, Any]) -> str:
    """Validate the ``[semantic]`` index directory."""
    index_dir = raw.get("index_dir", DEFAULT_SEMANTIC_INDEX_DIR)
    if not isinstance(index_dir, str) or not index_dir.strip():
        raise ConfigurationError("'semantic.index_dir' must be a non-empty string")
    return index_dir


def _parse_semantic_min_score(raw: dict[str, Any]) -> float:
    """Validate the ``[semantic]`` similarity threshold."""
    value = raw.get("min_score", DEFAULT_SEMANTIC_MIN_SCORE)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ConfigurationError("'semantic.min_score' must be a number")
    if not 0.0 <= float(value) <= 1.0:
        raise ConfigurationError("'semantic.min_score' must be between 0 and 1")
    return float(value)


def _reject_unknown_semantic_keys(raw: dict[str, Any]) -> None:
    """Reject unknown ``[semantic]`` keys."""
    valid = {"provider", "model", "index_dir", "top_k", "min_score"}
    unknown = sorted(set(raw) - valid)
    if unknown:
        raise ConfigurationError(
            f"unknown semantic keys: {', '.join(unknown)} (valid keys: {', '.join(sorted(valid))})"
        )


def _reject_unknown_keys(table: dict[str, Any]) -> None:
    """Fail loudly on configuration typos instead of ignoring them."""
    unknown = sorted(set(table) - _SECTION_KEYS)
    if unknown:
        valid = ", ".join(sorted(_SECTION_KEYS))
        raise ConfigurationError(
            f"unknown configuration keys: {', '.join(unknown)} (valid keys: {valid})"
        )


def _parse_exclude(table: dict[str, Any]) -> tuple[str, ...]:
    """Validate the ``exclude`` list of glob patterns."""
    if "exclude" not in table:
        return ()
    raw = table["exclude"]
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        raise ConfigurationError("'exclude' must be a list of glob patterns")
    return tuple(raw)


def _parse_bool(table: dict[str, Any], key: str, *, default: bool) -> bool:
    """Read a boolean flag from *table*, falling back to *default*."""
    if key not in table:
        return default
    value = table[key]
    if not isinstance(value, bool):
        raise ConfigurationError(f"'{key}' must be a boolean")
    return value


def _parse_history_commits(table: dict[str, Any]) -> int:
    """Validate the ``history_commits`` window size."""
    if "history_commits" not in table:
        return _DEFAULT_HISTORY_COMMITS
    value = table["history_commits"]
    if not isinstance(value, int) or isinstance(value, bool):
        raise ConfigurationError("'history_commits' must be an integer")
    if value < 1:
        raise ConfigurationError("'history_commits' must be a positive integer")
    return value


def _parse_blame_files(table: dict[str, Any]) -> int:
    """Validate how many hot files may be blamed for function-level churn."""
    if "blame_files" not in table:
        return _DEFAULT_BLAME_FILES
    value = table["blame_files"]
    if not isinstance(value, int) or isinstance(value, bool):
        raise ConfigurationError("'blame_files' must be an integer")
    if value < 0:
        raise ConfigurationError("'blame_files' must be zero or a positive integer")
    return value


def _parse_llm(table: dict[str, Any]) -> LlmConfig:
    """Validate the optional ``[llm]`` table."""
    if "llm" not in table:
        return LlmConfig()
    raw = table["llm"]
    if not isinstance(raw, dict):
        raise ConfigurationError("'llm' must be a table")
    _reject_unknown_llm_keys(raw)
    return LlmConfig(
        model=_parse_llm_model(raw),
        timeout=_parse_positive_int(raw, "timeout", DEFAULT_LLM_TIMEOUT, prefix="llm"),
        max_findings=_parse_positive_int(
            raw, "max_findings", DEFAULT_LLM_MAX_FINDINGS, prefix="llm"
        ),
    )


def _reject_unknown_llm_keys(raw: dict[str, Any]) -> None:
    """Reject unknown ``[llm]`` keys, including accidentally stored API keys."""
    valid = {"model", "timeout", "max_findings"}
    unknown = sorted(set(raw) - valid)
    if unknown:
        raise ConfigurationError(
            f"unknown llm keys: {', '.join(unknown)} (valid keys: {', '.join(sorted(valid))})"
        )


def _parse_llm_model(raw: dict[str, Any]) -> str:
    """Validate the ``[llm]`` model identifier."""
    model = raw.get("model", DEFAULT_LLM_MODEL)
    if not isinstance(model, str) or not model.strip():
        raise ConfigurationError("'llm.model' must be a non-empty string")
    return model


def _parse_positive_int(raw: dict[str, Any], key: str, default: int, *, prefix: str) -> int:
    """Validate a positive integer setting in a configuration table."""
    value = raw.get(key, default)
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ConfigurationError(f"'{prefix}.{key}' must be a positive integer")
    return value


def _parse_ignore(table: dict[str, Any]) -> tuple[str, ...]:
    """Validate the ``ignore`` list of ``rule-id`` / ``rule-id@glob`` entries."""
    if "ignore" not in table:
        return ()
    raw = table["ignore"]
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        raise ConfigurationError("'ignore' must be a list of 'rule-id[@glob]' strings")
    for entry in raw:
        parse_suppression(entry)
    return tuple(raw)


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
