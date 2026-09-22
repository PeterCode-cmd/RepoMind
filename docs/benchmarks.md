# Benchmarks: RepoMind on popular open-source projects

Date: 2026-09-22 · RepoMind 0.1.0 · Python 3.12.3 · Windows 11 · default
thresholds · 500-commit history window.

These runs answer a simple question: what does RepoMind actually say about
well-known, actively maintained Python codebases — on the very first run, with
no configuration, no excludes and no baseline?

## Methodology

```console
git clone --depth 500 https://github.com/<project>
repomind analyze <project> --format json --output report.json
```

- Each repository was analyzed at the commit recorded below.
- The 500-commit window is RepoMind's default; it keeps runtime predictable.
- Wall time covers discovery, parsing, the dependency graph, Git history
  analysis and all rules.
- Raw runs use **no** `repomind.toml`, no `--exclude` and no baseline — the
  honest first-run experience.

## Raw results (everything included)

| Project | Commit | Files | Source lines | Score | Critical | High | Medium | Low | Import cycles | Findings | Wall time |
| --- | --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| psf/requests | `611c616` | 37 | 8,029 | 66/100 C | 7 | 35 | 40 | 38 | 0 | 120 | 18.6 s |
| pallets/flask | `d73fa1c` | 83 | 10,740 | 72/100 C | 7 | 28 | 90 | 4 | 0 | 129 | 19.7 s |
| tqdm/tqdm | `9cf5a12` | 65 | 5,901 | 37/100 D | 13 | 39 | 66 | 26 | 0 | 144 | 18.9 s |
| psf/black | `64631f6` | 351 | 118,690 | 86/100 B | 74 | 151 | 282 | 181 | 0 | 688 | 22.2 s |

## What the runs show

**1. Git history dominates runtime.** Parsing 118,690 lines (black) takes
2.3 seconds; the 500-commit history walk takes ~20 of the 22 seconds. For CI,
`--no-history` (as in the GitHub Action) keeps runs fast and deterministic.

**2. Tests and tooling own the findings.** black: 282 of 688 findings are in
tests, and 174 of its 177 unused imports are in tests/tooling. tqdm: 52/144,
flask: 58/129. requests is the opposite: only 7/120 findings are in tests, and
its 37 unused imports are all in `src/` — mature libraries accumulate
side-effect imports and re-exports that reference-based dead-code analysis
cannot always prove.

**3. No import cycles in any of the four projects.** The strongly-connected
component detector produced zero findings here, which matches the reputation of
these codebases — a sign the rule is not noisy.

**4. Findings that look like real maintenance work:**

- requests: `RequestEncodingMixin._encode_files` (cognitive complexity 44),
  `HTTPAdapter.send` (cyclomatic 20), `RequestsCookieJar` (18 methods,
  286 lines).
- flask: `Flask` (32 methods, 1,519 lines, WMC 161), `App` (34 methods),
  `Blueprint.register` (cyclomatic 22).
- tqdm: test helpers with cyclomatic 27, `examples/7zx.py` with cognitive 40.
- black: generated `profiling/dict_huge.py` (41,440 lines), unused imports in
  test tooling.

**5. Size normalisation matters.** black has 688 findings but grades B because
it also has 118k source lines; tqdm has 144 findings against 5.9k lines and
grades D. The score measures problem *density*, not absolute counts.

**6. Excluding code can lower the score.** Re-running black without tests,
profiling fixtures and examples:

| Scope | Files | Source lines | Findings | Score |
| --- | ---: | ---: | ---: | --- |
| everything | 351 | 118,690 | 688 | 86/100 B |
| `--exclude tests profiling examples` | 52 | 13,415 | 389 | 5/100 F |
| tqdm: everything | 65 | 5,901 | 144 | 37/100 D |
| tqdm: `--exclude tests examples` | 33 | 3,029 | 88 | 30/100 F |

The remaining findings are now measured against a nine times smaller code
base. **Scores are only comparable within the same scope** — pick the scope
you care about once and keep it stable (in `repomind.toml`), then track the
score over time rather than comparing across projects.

## Reproducing

```console
git clone --depth 500 https://github.com/psf/requests /tmp/requests
repomind analyze /tmp/requests
repomind analyze /tmp/requests --exclude tests --format html --output requests.html
repomind baseline /tmp/requests          # then gate CI with --fail-on-new
```

## Limitations

- Thresholds are opinionated defaults, not ground truth; tune them per project
  in `repomind.toml`.
- Reference-based dead-code analysis can flag side-effect imports and
  re-exports that lack `__all__`; use `ignore` for accepted cases.
- Only the last 500 commits are analyzed; older churn is invisible.
- Line counts are physical source lines (comments and blanks excluded), so they
  differ slightly from tools counting logical lines.
