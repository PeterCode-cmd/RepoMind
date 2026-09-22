"""Environment diagnostics behind ``repomind doctor``.

Checks answer one question: can RepoMind run here, and if not, what is
missing? Every failing check carries an actionable hint.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from git import InvalidGitRepositoryError, NoSuchPathError, Repo

from repomind.config import AnalysisConfig, load_config
from repomind.errors import ConfigurationError

_INDEX_METADATA = "embeddings.json"
_OLLAMA_TAGS_URL = "http://localhost:11434/api/tags"
_OLLAMA_TIMEOUT_SECONDS = 1.5


@dataclass(frozen=True, slots=True)
class CheckResult:
    """One diagnostic check."""

    name: str
    status: str
    detail: str
    hint: str | None = None


def run_checks(root: Path, *, config_file: Path | None = None) -> list[CheckResult]:
    """Check that RepoMind can run in *root* and report what is missing."""
    root = root.resolve()
    results = [_check_python()]
    config, config_check = _load_configuration(root, config_file)
    results.append(config_check)
    results.extend(_check_git(root))
    results.extend(_check_extras())
    if config is not None:
        results.append(_check_index(root, config))
        results.append(_check_llm_backend(config))
    return results


def _check_python() -> CheckResult:
    """Report the interpreter version.

    The package cannot be installed on older interpreters, so this check is
    informational: it shows exactly which Python is in use.
    """
    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    return CheckResult("python", "ok", f"{version} (>= 3.12 required)")


def _load_configuration(
    root: Path,
    config_file: Path | None,
) -> tuple[AnalysisConfig | None, CheckResult]:
    """Load the configuration, reporting errors as a check result."""
    try:
        config = load_config(root, config_file=config_file)
    except ConfigurationError as error:
        return None, CheckResult(
            "configuration",
            "missing",
            str(error),
            "fix the configuration file; unknown keys are rejected loudly",
        )
    source = str(config_file) if config_file is not None else "discovered or defaults"
    return config, CheckResult("configuration", "ok", source)


def _check_git(root: Path) -> list[CheckResult]:
    """Report Git availability and whether *root* is a repository."""
    if shutil.which("git") is None:
        return [
            CheckResult(
                "git",
                "missing",
                "git executable not found",
                "install Git to enable history, churn and trend",
            )
        ]
    try:
        Repo(root, search_parent_directories=True)
    except (InvalidGitRepositoryError, NoSuchPathError):
        return [
            CheckResult(
                "git repository",
                "warn",
                "not inside a Git repository",
                "history analysis, hotspots and trend are unavailable",
            )
        ]
    return [CheckResult("git repository", "ok", str(root))]


def _check_extras() -> list[CheckResult]:
    """Report whether the optional dependency groups are installed."""
    return [
        _check_modules(
            "semantic extra",
            ("fastembed", "numpy"),
            'pip install "repomind-analyzer[semantic]"',
        ),
        _check_modules(
            "llm extra",
            ("litellm", "tenacity"),
            'pip install "repomind-analyzer[llm]"',
        ),
    ]


def _check_modules(name: str, modules: tuple[str, ...], hint: str) -> CheckResult:
    """Report which of *modules* are importable."""
    missing = [module for module in modules if not _has_module(module)]
    if not missing:
        return CheckResult(name, "ok", ", ".join(modules))
    return CheckResult(name, "warn", f"missing: {', '.join(missing)}", hint)


def _has_module(name: str) -> bool:
    """Return ``True`` when *name* can be imported."""
    return importlib.util.find_spec(name) is not None


def _check_index(root: Path, config: AnalysisConfig) -> CheckResult:
    """Report whether a semantic index exists for the repository."""
    index_dir = root / config.semantic.index_dir
    if (index_dir / _INDEX_METADATA).is_file():
        return CheckResult("semantic index", "ok", str(index_dir))
    return CheckResult(
        "semantic index",
        "warn",
        f"no index in {index_dir}",
        "run 'repomind index .' to enable semantic search",
    )


def _check_llm_backend(config: AnalysisConfig) -> CheckResult:
    """Report the configured LLM backend and its availability."""
    model = config.llm.model
    if not model.startswith("ollama/"):
        return CheckResult("llm backend", "ok", f"model {model} (API key from the environment)")
    return _check_ollama(model.removeprefix("ollama/"))


def _check_ollama(wanted: str) -> CheckResult:
    """Report whether Ollama serves the configured model."""
    models = _ollama_models()
    if models is None:
        return CheckResult(
            "ollama",
            "warn",
            "not reachable on localhost:11434",
            "start it with 'ollama serve', or use --model for a cloud provider",
        )
    if any(entry == wanted or entry.startswith(f"{wanted}:") for entry in models):
        return CheckResult("ollama", "ok", f"{wanted} available")
    return CheckResult(
        "ollama",
        "warn",
        f"model {wanted} is not pulled",
        f"run 'ollama pull {wanted}'",
    )


def _ollama_models() -> list[str] | None:
    """Return the model tags served by Ollama, or ``None`` when unreachable."""
    try:
        with urllib.request.urlopen(_OLLAMA_TAGS_URL, timeout=_OLLAMA_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError):
        return None
    models = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(models, list):
        return None
    return [
        entry["name"]
        for entry in models
        if isinstance(entry, dict) and isinstance(entry.get("name"), str)
    ]
