# Contributing to RepoMind

Thanks for considering a contribution! RepoMind aims to be a serious, useful
open-source tool, and every issue, rule idea and bug report helps.

## Development setup

```console
git clone https://github.com/repomind/repomind.git
cd repomind
uv venv
uv pip install -e ".[dev]"
pre-commit install
```

Without `uv`, any Python 3.12+ virtual environment works:

```console
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # Linux/macOS
pip install -e ".[dev]"
```

## Quality gates

All of these run in CI and must pass:

```console
ruff format --check .
ruff check .
mypy
pytest --cov
```

## Project conventions

- **Type hints everywhere**, strict mypy is enforced on `src/`.
- **Google-style docstrings** on every public module, class and function.
- **No comments** unless they explain *why* something non-obvious is done.
- Rules live in `src/repomind/core/rules/` and must satisfy the `Rule` protocol;
  register new rules in `default_rules()`.
- Every new rule needs a test. The sample project in
  `tests/fixtures/sample_project/` is deliberately flawed — extend it if your
  rule needs a new smell.
- Keep the deterministic core free of optional dependencies: `litellm`,
  `chromadb` and `streamlit` must never be imported from `repomind.core`.

## Adding a rule in five steps

1. Pick the right module (`complexity_rules.py`, `dead_code_rules.py`, ...).
2. Implement `id`, `title`, `description`, `category` and `analyze(context)`.
3. Include measured values in `details` and a concrete `suggestion`.
4. Register the rule in `core/rules/__init__.py`.
5. Add tests and run the quality gates above.

## Reporting issues

Please include:

- the RepoMind version (`repomind --version`),
- Python version and OS,
- the smallest possible repository or code snippet that reproduces the problem,
- the full command you ran and its output.

## Commit style

Short imperative subjects (`add cognitive complexity rule`), one logical change
per commit. Reference issues with `#123` when relevant.
