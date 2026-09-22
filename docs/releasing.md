# Releasing

RepoMind uses [Semantic Versioning](https://semver.org/) and PyPI trusted
publishing (no API tokens stored in the repository).

## Checklist

1. Bump the version in `pyproject.toml` and `src/repomind/__init__.py`.
2. Move the `Unreleased` entries of `CHANGELOG.md` into a new version section.
3. Run the full quality gates:

   ```console
   ruff format --check .
   ruff check .
   mypy
   pytest --cov
   repomind analyze . --no-history --fail-under 95
   ```

4. Build and inspect the distributions:

   ```console
   uv build          # or: python -m build
   ```

5. Tag and push:

   ```console
   git tag v0.2.0
   git push origin v0.2.0
   ```

6. The `release` workflow builds the distributions, publishes them to PyPI
   through trusted publishing and creates a GitHub release with generated
   notes.

## One-time PyPI setup

The distribution name is `repomind-analyzer` (the plain `repomind` name is
taken by an unrelated project); the import package and the CLI command remain
`repomind`.

Add a trusted publisher for the `repomind-analyzer` project on PyPI:

- Owner / repository: `PeterCode-cmd/RepoMind`
- Workflow: `release.yml`
- Environment: `pypi`

After that, tagging is the only action required to publish.
