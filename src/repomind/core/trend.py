"""Health-score trend over sampled commits.

Every sample is analyzed in a detached Git worktree, so historical snapshots
are measured with the same rules, thresholds and configuration as the current
tree. The history and blame stages are skipped per sample: they would be
expensive and biased by each snapshot's own commit window.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from git import Commit, InvalidGitRepositoryError, NoSuchPathError, Repo
from git.exc import GitCommandError

from repomind.config import AnalysisConfig, load_config
from repomind.core.engine import AnalysisResult, ProgressCallback, StageUpdate, analyze_repository
from repomind.errors import RepoMindError
from repomind.models.enums import Severity

DEFAULT_SAMPLES = 10
DEFAULT_WINDOW = 200
MIN_TREND_SAMPLES = 2


@dataclass(frozen=True, slots=True)
class TrendSample:
    """One analyzed commit in the trend."""

    sha: str
    short_sha: str
    committed_at: datetime
    subject: str
    score: int
    grade: str
    findings: int
    critical: int
    high: int
    loc: int
    files: int


@dataclass(slots=True)
class TrendReport:
    """Health scores for sampled commits, ordered oldest to newest."""

    samples: list[TrendSample]
    window: int

    @property
    def delta(self) -> int:
        """Return the score change between the first and the last sample."""
        if len(self.samples) < MIN_TREND_SAMPLES:
            return 0
        return self.samples[-1].score - self.samples[0].score

    def best(self) -> TrendSample | None:
        """Return the sample with the highest score."""
        return max(self.samples, key=lambda sample: sample.score) if self.samples else None

    def worst(self) -> TrendSample | None:
        """Return the sample with the lowest score."""
        return min(self.samples, key=lambda sample: sample.score) if self.samples else None


def build_trend(
    root: Path,
    *,
    config: AnalysisConfig | None = None,
    samples: int = DEFAULT_SAMPLES,
    window: int = DEFAULT_WINDOW,
    progress: ProgressCallback | None = None,
) -> TrendReport:
    """Analyze evenly spaced commits and return their health scores.

    Args:
        root: Repository root.
        config: Configuration applied to every sample; discovered when omitted.
        samples: Number of commits to analyze.
        window: How far back (in commits) samples may be taken from.
        progress: Optional callback receiving :class:`StageUpdate` events.

    Raises:
        RepoMindError: When *root* is not a repository or has no commits.
    """
    root = root.resolve()
    repo = _open_repository(root)
    commits = _sample_commits(repo, window=window, samples=samples)
    if not commits:
        raise RepoMindError(f"{root} has no commits to analyze")

    resolved_config = config or load_config(root)
    results: list[TrendSample] = []
    with tempfile.TemporaryDirectory(prefix="repomind-trend-") as tmp:
        for index, commit in enumerate(commits, start=1):
            _notify(progress, commit, index, len(commits))
            worktree = Path(tmp) / commit.hexsha[:12]
            _add_worktree(repo, worktree, commit.hexsha)
            try:
                analysis = analyze_repository(worktree, config=resolved_config, use_history=False)
            finally:
                _remove_worktree(repo, worktree)
            results.append(_sample(commit, analysis))

    return TrendReport(samples=results, window=window)


def _open_repository(root: Path) -> Repo:
    """Open the enclosing repository, raising RepoMindError when absent."""
    try:
        return Repo(root, search_parent_directories=True)
    except (InvalidGitRepositoryError, NoSuchPathError) as exc:
        raise RepoMindError(f"{root} is not inside a Git repository") from exc


def _sample_commits(repo: Repo, *, window: int, samples: int) -> list[Commit]:
    """Return evenly spaced commits from the last *window*, oldest first."""
    history = list(repo.iter_commits("HEAD", max_count=window))
    if not history:
        return []
    if len(history) <= samples:
        return list(reversed(history))

    step = (len(history) - 1) / (samples - 1)
    indices = sorted({round(index * step) for index in range(samples)})
    return [history[len(history) - 1 - index] for index in indices]


def _add_worktree(repo: Repo, path: Path, sha: str) -> None:
    """Check out *sha* into a detached worktree at *path*."""
    try:
        repo.git.worktree("add", "--detach", str(path), sha)
    except GitCommandError as exc:
        raise RepoMindError(f"cannot create a worktree for {sha[:7]}: {exc}") from exc


def _remove_worktree(repo: Repo, path: Path) -> None:
    """Remove a worktree, pruning stale metadata if removal fails."""
    try:
        repo.git.worktree("remove", "--force", str(path))
    except GitCommandError:
        repo.git.worktree("prune")


def _notify(progress: ProgressCallback | None, commit: Commit, current: int, total: int) -> None:
    """Emit a stage update for the commit currently being analyzed."""
    if progress is not None:
        progress(StageUpdate(stage=f"trend {commit.hexsha[:7]}", current=current, total=total))


def _sample(commit: Commit, analysis: AnalysisResult) -> TrendSample:
    """Convert one analysis run into a trend sample."""
    counts = analysis.score.counts
    return TrendSample(
        sha=str(commit.hexsha),
        short_sha=str(commit.hexsha)[:7],
        committed_at=commit.committed_datetime,
        subject=_subject(commit),
        score=analysis.score.value,
        grade=analysis.score.grade,
        findings=len(analysis.findings),
        critical=counts[Severity.CRITICAL],
        high=counts[Severity.HIGH],
        loc=analysis.total_loc,
        files=analysis.file_count,
    )


def _subject(commit: Commit) -> str:
    """Return the commit subject as text."""
    summary = commit.summary
    if isinstance(summary, bytes):
        return summary.decode("utf-8", errors="replace")
    return summary or ""
