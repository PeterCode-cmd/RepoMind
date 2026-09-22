# Benchmarks: RepoMind on popular open-source projects

Date: 2026-09-22 · RepoMind `main` @ `eab2bf1` (0.1.0 plus the unreleased
security, documentation and function-level-churn work) · Python 3.12.3 ·
Windows 11 · default thresholds · 500-commit history window · `blame_files = 10`.

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
  analysis, function-level churn for the ten hottest files, and all 18 rules.
- Raw runs use **no** `repomind.toml`, no `--exclude` and no baseline — the
  honest first-run experience.

## Raw results (everything included)

| Project | Commit | Files | Source lines | Score | Critical | High | Medium | Low | Import cycles | Findings | Wall time |
| --- | --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| psf/requests | `611c616` | 37 | 8,029 | 60/100 C | 7 | 43 | 38 | 71 | 0 | 159 | 21.9 s |
| pallets/flask | `d73fa1c` | 83 | 10,740 | 68/100 C | 7 | 28 | 85 | 92 | 0 | 212 | 25.2 s |
| tqdm/tqdm | `9cf5a12` | 65 | 5,901 | 30/100 D | 13 | 39 | 66 | 103 | 0 | 221 | 24.6 s |
| psf/black | `64631f6` | 351 | 118,690 | 85/100 B | 74 | 158 | 273 | 381 | 0 | 886 | 25.3 s |

## What the runs show

**1. Git analysis dominates runtime.** Parsing 118,690 lines (black) takes
2.3 seconds. The 500-commit history walk plus line-range tracking for the ten
hottest files takes the remaining ~23 seconds. `--no-history` (as in the GitHub
Action) disables both stages and keeps CI runs fast and deterministic.

**2. Tests and tooling own the findings.** black: 296 of 886 findings are in
tests; flask 52/212, tqdm 52/221. requests is the opposite: only 15/159, and
its 37 unused imports all live in `src/` — mature libraries accumulate
side-effect imports and re-exports that reference-based dead-code analysis
cannot always prove.

**3. No import cycles in any of the four projects.** The strongly-connected
component detector produced zero findings here, which matches the reputation of
these codebases — a sign the rule is not noisy.

**4. Findings that look like real maintenance work:**

- requests: `RequestEncodingMixin._encode_files` (cognitive complexity 44),
  `HTTPAdapter.send` (cyclomatic 20), `RequestsCookieJar` (18 methods,
  286 lines).
- flask: `Flask` (32 methods, 1,519 lines, WMC 161), `Blueprint.register`
  (cyclomatic 22), 88 public symbols without docstrings.
- tqdm: test helpers with cyclomatic 27, `examples/7zx.py` with cognitive 40.
- black: generated `profiling/dict_huge.py` (41,440 lines), 174 unused imports
  in test tooling, 200 missing docstrings.

**5. Security findings are worth a look, not automatically vulnerabilities.**
requests has 8 (all `pickle.loads` in tests); black has 22, including
`pickle.load` in `src/black/cache.py` (cache deserialization) and `eval()` in
`src/blib2to3/pgen2/conv.py` (grammar tooling). Each one is a deliberate review
candidate; RepoMind reports the pattern, not a verdict.

**6. Function-level churn sharpens hotspots.** With `git log -L` tracking the
ten hottest files, requests gets 12 of 12 hotspot findings from a function's own
commit history; black gets 26 function-level plus 41 file-level fallbacks
(only the eight most complex functions per file are tracked to bound cost);
flask 11+7 and tqdm 22+11. Example from black: `black.main` (cyclomatic 48)
changed in 10 commits by 7 authors, `read_pyproject_toml` (18) in 5 commits by
5 authors.

**7. Size normalisation matters.** black has 886 findings but grades B because
it also has 118k source lines; tqdm has 221 findings against 5.9k lines and
grades D. The score measures problem *density*, not absolute counts.

**8. Excluding code can lower the score.** Re-running without tests, profiling
fixtures and examples:

| Scope | Files | Source lines | Findings | Score |
| --- | ---: | ---: | ---: | --- |
| black: everything | 351 | 118,690 | 886 | 85/100 B |
| black: `--exclude tests profiling examples` | 52 | 13,415 | 562 | 1/100 F |
| tqdm: everything | 65 | 5,901 | 221 | 30/100 D |
| tqdm: `--exclude tests examples` | 33 | 3,029 | 154 | 19/100 F |

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
- Security rules match patterns (and resolve import aliases), but they cannot
  prove exploitability; treat findings as review candidates.
- Only the last 500 commits are analyzed and only the ten hottest files get
  function-level churn; older activity is invisible.
- Line counts are physical source lines (comments and blanks excluded), so they
  differ slightly from tools counting logical lines.
