#!/usr/bin/env python3
"""Git mechanics for the keep/discard loop.

autoresearch advances a branch when ``val_bpb`` improves and ``git reset``s when
it does not, so the branch itself becomes a record of monotonic improvement and
a bad idea costs nothing. This module is that mechanic, plus the preflight that
stops a run before it starts wasting the night on a repo it cannot work in.

Commands
--------
    gitops.py preflight [--root .]
    gitops.py start --tag mar5 [--root .]
    gitops.py commit --message "..." [--root .]
    gitops.py reset --to <sha> [--root .]
    gitops.py head [--root .]

Exit codes: 0 ok, 1 problem (each finding carries the command that fixes it),
2 hard stop (not a git repo, no git binary).
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

# Never leave __pycache__ in the repository under test: an untracked byte-cache
# directory reads as a dirty tree and would be swept away by a discard.
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

from contract import STATE_DIR  # noqa: E402

PROTECTED_BRANCHES = {"main", "master", "develop", "trunk", "release"}
BRANCH_PREFIX = "autoresearch/"


class GitError(RuntimeError):
    """Raised when a git operation cannot be completed."""


def git(root: Path, *args: str, check: bool = True) -> str:
    proc = subprocess.run(  # noqa: S603
        ["git", *args], cwd=root, capture_output=True, text=True, check=False
    )
    if check and proc.returncode != 0:
        raise GitError(f"git {' '.join(args)} failed: {proc.stderr.strip() or proc.stdout.strip()}")
    return proc.stdout.strip()


def is_repo(root: Path) -> bool:
    proc = subprocess.run(  # noqa: S603
        ["git", "rev-parse", "--is-inside-work-tree"], cwd=root,
        capture_output=True, text=True, check=False,
    )
    return proc.returncode == 0 and proc.stdout.strip() == "true"


def current_branch(root: Path) -> str:
    return git(root, "rev-parse", "--abbrev-ref", "HEAD", check=False)


def head_sha(root: Path, short: bool = True) -> str:
    return git(root, "rev-parse", "--short" if short else "HEAD", "HEAD" if short else "HEAD", check=False)


def short_head(root: Path) -> str:
    return git(root, "rev-parse", "--short=7", "HEAD", check=False)


#: Untracked paths that are never work a human cares about losing. Flagging these
#: as a dirty tree would block every real repository on build noise.
NOISE_PREFIXES = (
    STATE_DIR, "__pycache__/", ".pytest_cache/", ".mypy_cache/", ".ruff_cache/",
    "node_modules/", ".venv/", "dist/", "build/", ".next/", "target/",
    "coverage/", "test-results/", "playwright-report/", ".DS_Store",
)


def _is_noise(path: str) -> bool:
    cleaned = path.strip().strip('"')
    return any(
        cleaned.startswith(prefix) or f"/{prefix}" in cleaned or cleaned.endswith(".pyc")
        for prefix in NOISE_PREFIXES
    )


def preflight(root: Path) -> list[dict[str, str]]:
    """Return findings that must be resolved before the loop can run.

    These are the expensive-because-late failures: discovering at attempt 30 that
    every commit landed on ``main`` is a bad morning.
    """
    findings: list[dict[str, str]] = []

    if not is_repo(root):
        findings.append({
            "id": "not-a-repo",
            "problem": f"{root} is not a git repository — keep/discard needs one",
            "fix": "git init && git add -A && git commit -m 'initial'",
            "severity": "hard",
        })
        return findings

    branch = current_branch(root)
    if branch == "HEAD":
        findings.append({
            "id": "detached-head",
            "problem": "HEAD is detached; commits would be unreachable after a reset",
            "fix": "git checkout -b autoresearch/<tag>",
            "severity": "hard",
        })
    elif branch in PROTECTED_BRANCHES:
        findings.append({
            "id": "protected-branch",
            "problem": f"on '{branch}' — the loop commits on every kept attempt",
            "fix": "python3 scripts/gitops.py start --tag <tag>",
            "severity": "fixable",
        })

    if not git(root, "log", "-1", "--format=%H", check=False):
        findings.append({
            "id": "no-commits",
            "problem": "the repository has no commits, so there is no base to diff against",
            "fix": "git add -A && git commit -m 'initial'",
            "severity": "hard",
        })

    if not git(root, "config", "user.email", check=False):
        findings.append({
            "id": "no-identity",
            "problem": "git user.email is unset; commits will fail mid-loop",
            "fix": "git config user.email you@example.com && git config user.name 'Your Name'",
            "severity": "fixable",
        })

    dirty = git(root, "status", "--porcelain", check=False)
    tracked_dirty = [ln for ln in dirty.splitlines() if ln.strip() and not _is_noise(ln[3:])]
    if tracked_dirty:
        findings.append({
            "id": "dirty-tree",
            "problem": f"{len(tracked_dirty)} uncommitted change(s) — they would be mixed into the first attempt "
                       "and destroyed by the first discard",
            "fix": "git stash --include-untracked   # or commit them first",
            "severity": "fixable",
        })

    return findings


def start_branch(root: Path, tag: str) -> str:
    """Create and check out ``autoresearch/<tag>``. Refuses to reuse a branch."""
    name = f"{BRANCH_PREFIX}{tag}"
    existing = git(root, "branch", "--list", name, check=False)
    if existing.strip():
        raise GitError(
            f"branch {name} already exists — this must be a fresh run.\n"
            f"Pick another tag, or delete it with: git branch -D {name}"
        )
    git(root, "checkout", "-b", name)
    _ensure_ignored(root)
    return name


def ensure_ignored(root: Path) -> None:
    """Public entry point — see :func:`_ensure_ignored`.

    Must be called once before the first score, not merely before the first
    commit: the baseline diff is computed against untracked files too, so build
    noise left unexcluded shows up as "a test file changed" on attempt zero.
    """
    _ensure_ignored(root)


def _ensure_ignored(root: Path) -> None:
    """Keep run state and build noise untracked, as autoresearch keeps ``results.tsv``.

    Two reasons. Committing the ledger would put the previous attempt's record
    inside the next attempt's diff, polluting both the complexity metric and the
    scope check. And byte-cache directories written by running the tests would
    otherwise be staged, counted as changed lines, and committed.

    This writes to ``.git/info/exclude`` — local to the clone, never committed, and
    it deliberately matches ``NOISE_PREFIXES`` so preflight and commit agree on what
    counts as noise. Already-tracked files are unaffected: git only ignores
    untracked paths.
    """
    exclude = root / ".git" / "info" / "exclude"
    marker = "# coding-autoresearch run state"
    entries = [f"/{STATE_DIR}/", "__pycache__/", "*.pyc", *(
        p for p in NOISE_PREFIXES if p not in {STATE_DIR, "__pycache__/", ".DS_Store"}
    )]
    try:
        current = exclude.read_text(encoding="utf-8") if exclude.is_file() else ""
        if marker in current:
            return
        exclude.parent.mkdir(parents=True, exist_ok=True)
        with exclude.open("a", encoding="utf-8") as handle:
            handle.write("\n" + marker + "\n" + "\n".join(entries) + "\n")
    except OSError:
        pass


class NothingToCommit(GitError):
    """The tree is identical to HEAD — distinct from a git failure."""


def commit_attempt(root: Path, message: str) -> str:
    """Stage everything not excluded and commit. Returns the short sha.

    The state directory and build noise are handled by ``_ensure_ignored`` rather
    than by an ``:(exclude)`` pathspec: pointing a pathspec at an already-ignored
    path makes ``git add`` exit non-zero with an "ignored by .gitignore" warning,
    which would abort every commit.
    """
    _ensure_ignored(root)
    git(root, "add", "-A")
    staged = git(root, "diff", "--cached", "--name-only", check=False)
    if not staged.strip():
        raise NothingToCommit("nothing to commit — the attempt changed no files")
    git(root, "commit", "-m", message, "--no-verify")
    return short_head(root)


def reset_to(root: Path, sha: str) -> str:
    """Discard the attempt: hard reset and remove new files, preserving run state."""
    git(root, "reset", "--hard", sha)
    subprocess.run(  # noqa: S603
        ["git", "clean", "-fd", "-e", STATE_DIR], cwd=root,
        capture_output=True, text=True, check=False,
    )
    return short_head(root)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def _cmd_preflight(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    findings = preflight(root)
    if not findings:
        print(f"preflight: ready (branch {current_branch(root)}, head {short_head(root)})")
        return 0
    hard = [f for f in findings if f["severity"] == "hard"]
    for finding in findings:
        print(f"[{finding['severity']}] {finding['id']}: {finding['problem']}", file=sys.stderr)
        print(f"           fix: {finding['fix']}", file=sys.stderr)
    return 2 if hard else 1


def _cmd_start(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    name = start_branch(root, args.tag)
    print(f"on branch {name} at {short_head(root)}")
    return 0


def _cmd_commit(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    sha = commit_attempt(root, args.message)
    print(sha)
    return 0


def _cmd_reset(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    sha = reset_to(root, args.to)
    print(f"discarded; back at {sha}")
    return 0


def _cmd_head(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    print(short_head(root))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    pre = sub.add_parser("preflight", help="check the repo can host a run")
    pre.add_argument("--root", default=".")
    pre.set_defaults(func=_cmd_preflight)

    start = sub.add_parser("start", help="create the run branch")
    start.add_argument("--tag", required=True)
    start.add_argument("--root", default=".")
    start.set_defaults(func=_cmd_start)

    commit = sub.add_parser("commit", help="commit the current attempt")
    commit.add_argument("--message", required=True)
    commit.add_argument("--root", default=".")
    commit.set_defaults(func=_cmd_commit)

    reset = sub.add_parser("reset", help="discard the current attempt")
    reset.add_argument("--to", required=True)
    reset.add_argument("--root", default=".")
    reset.set_defaults(func=_cmd_reset)

    head = sub.add_parser("head", help="print the short HEAD sha")
    head.add_argument("--root", default=".")
    head.set_defaults(func=_cmd_head)

    return parser


def main(argv: list[str] | None = None) -> int:
    if shutil.which("git") is None:
        print("error: git is not installed", file=sys.stderr)
        return 2
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except GitError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
