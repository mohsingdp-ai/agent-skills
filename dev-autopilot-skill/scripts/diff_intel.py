#!/usr/bin/env python3
"""Read a diff and report what an unattended run is not allowed to overlook.

Every other gate in this skill is downstream of this file. It answers four
questions about a change, from the diff alone, with no model in the loop:

1. **What moved?**  Files, languages, line counts, whether tests moved with
   the source.
2. **How risky is it?**  Auth, migrations, money, crypto, CI config and
   dependency manifests are weighted; a 20-line change to an auth guard is not
   a 20-line change to a README.
3. **Was the suite silenced?**  A census of every skip / fixme / xfail /
   ignore marker, split into *pre-existing* and *added by this change*. The
   distinction matters: inheriting a skipped test is not a sin, adding one to
   get to green is.
4. **Was the suite focused?**  ``.only`` / ``fit`` / ``fdescribe`` narrow a run
   to a handful of tests while still exiting 0. This is the single most
   dangerous marker in autonomous development because the suite reports
   success while barely running, so it is tracked separately from suppression
   and treated as a hard blocker regardless of count.

Suppression is counted against **added lines only** by default. A change is
judged on what it did, not on the repository it inherited.

Usage:
    python3 diff_intel.py --root . --base origin/main --json
    python3 diff_intel.py --root . --diff-file saved.patch --json
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = "1.0"

#: Extension -> language. Drives both test detection and marker dialects.
LANGS: dict[str, str] = {
    ".py": "python", ".ts": "ts", ".tsx": "ts", ".js": "js", ".jsx": "js",
    ".mjs": "js", ".cjs": "js", ".go": "go", ".rs": "rust", ".java": "java",
    ".kt": "kotlin", ".rb": "ruby", ".cs": "csharp", ".php": "php",
    ".swift": "swift", ".scala": "scala", ".sql": "sql", ".sh": "shell",
    ".yml": "yaml", ".yaml": "yaml", ".json": "json", ".toml": "toml",
    ".md": "markdown",
}

#: Path fragments that mark a file as a test. Checked against the POSIX path.
TEST_PATH_HINTS = (
    "/test/", "/tests/", "/spec/", "/specs/", "/__tests__/", "/e2e/",
    "/integration/", "/testing/",
)
TEST_NAME_RE = re.compile(
    r"(^|[./_-])(test_[^/]*|[^/]*_test|[^/]*\.test|[^/]*\.spec|test[A-Z][^/]*)\.",
)

#: Risk tags: (tag, weight, path regex). Weights are additive, capped at 100.
RISK_RULES: tuple[tuple[str, int, str], ...] = (
    ("auth", 25, r"(auth|login|session|token|jwt|oauth|saml|password|credential|permission|rbac|acl)"),
    ("secrets", 25, r"(secret|vault|keystore|\.env|credentials)"),
    ("crypto", 20, r"(crypto|cipher|encrypt|decrypt|hash|signature|tls|ssl)"),
    ("migration", 20, r"(migrations?/|schema\.(sql|rb|prisma)|alembic|flyway|liquibase)"),
    ("money", 20, r"(payment|billing|invoice|charge|refund|stripe|paypal|ledger|pricing|checkout)"),
    ("pii", 15, r"(gdpr|pii|personal_data|anonymi[sz]e|redact)"),
    ("infra", 12, r"(terraform|\.tf$|helm|k8s|kubernetes|docker-compose|Dockerfile)"),
    ("ci", 12, r"(\.github/workflows/|\.gitlab-ci|Jenkinsfile|azure-pipelines)"),
    ("deps", 10, r"(package\.json|package-lock\.json|yarn\.lock|pnpm-lock|requirements.*\.txt|pyproject\.toml|poetry\.lock|go\.mod|go\.sum|Gemfile|Cargo\.toml)"),
    ("concurrency", 10, r"(worker|queue|thread|async|scheduler|cron|lock|mutex|semaphore)"),
    ("public-api", 10, r"(routes?/|controllers?/|handlers?/|endpoints?/|api/|graphql)"),
)

#: Suppression markers by language dialect: (kind, regex).
#: ``kind`` is one of skip | fixme | todo | xfail | ignore.
SUPPRESSION_RULES: dict[str, tuple[tuple[str, str], ...]] = {
    "js": (
        ("skip", r"\b(?:it|test|describe|suite)\s*\.\s*skip\s*[(`]"),
        ("skip", r"\b(?:xit|xdescribe|xtest)\s*[(`]"),
        ("fixme", r"\b(?:it|test)\s*\.\s*fixme\s*[(`]"),
        ("todo", r"\b(?:it|test)\s*\.\s*todo\s*[(`]"),
        ("skip", r"\btest\.step\s*\.\s*skip\s*[(`]"),
        ("skip", r"\bthis\.skip\s*\("),
    ),
    "python": (
        ("skip", r"@pytest\.mark\.skip\b"),
        ("skip", r"@pytest\.mark\.skipif\b"),
        ("skip", r"@(?:unittest\.)?skip(?:If|Unless)?\s*\("),
        ("skip", r"\bpytest\.skip\s*\("),
        ("xfail", r"@pytest\.mark\.xfail\b"),
        ("xfail", r"\bpytest\.xfail\s*\("),
    ),
    "go": (
        ("skip", r"\bt\.Skip(?:Now|f)?\s*\("),
        ("skip", r"\btestify.*\bT\(\)\.Skip\b"),
    ),
    "rust": (("ignore", r"#\[ignore\b"),),
    "java": (
        ("ignore", r"@(?:Disabled|Ignore)\b"),
        ("skip", r"\bAssum(?:e|ptions)\.assum\w+\s*\("),
    ),
    "kotlin": (("ignore", r"@(?:Disabled|Ignore)\b"),),
    "ruby": (
        ("skip", r"^\s*skip\b"),
        ("skip", r"\bxit\s+"),
        ("skip", r"\bpending\b"),
    ),
    "csharp": (
        ("ignore", r"\[Ignore\b"),
        ("skip", r"\bSkip\s*="),
    ),
    "php": (
        ("skip", r"\$this->mark(?:TestSkipped|TestIncomplete)\s*\("),
    ),
}
# Dialect aliases.
SUPPRESSION_RULES["ts"] = SUPPRESSION_RULES["js"]
SUPPRESSION_RULES["scala"] = SUPPRESSION_RULES["java"]

#: Focus markers — narrow the run while still exiting 0. Always a blocker.
FOCUS_RULES: dict[str, tuple[tuple[str, str], ...]] = {
    "js": (
        ("only", r"\b(?:it|test|describe|suite|bench)\s*\.\s*only\s*[(`]"),
        ("only", r"\b(?:fit|fdescribe|ftest)\s*[(`]"),
        ("only", r"\btest\.step\s*\.\s*only\s*[(`]"),
    ),
    "ruby": (
        ("only", r"\bfit\s+"),
        ("only", r":focus\s*=>\s*true"),
        ("only", r"\bfocus:\s*true"),
    ),
    "go": (("only", r"^//\s*go:build\s+focus\b"),),
}
FOCUS_RULES["ts"] = FOCUS_RULES["js"]

#: Compiled once at import; regexes are hot in the per-line scan.
_COMPILED_SUPPRESSION = {
    lang: tuple((kind, re.compile(pat)) for kind, pat in rules)
    for lang, rules in SUPPRESSION_RULES.items()
}
_COMPILED_FOCUS = {
    lang: tuple((kind, re.compile(pat)) for kind, pat in rules)
    for lang, rules in FOCUS_RULES.items()
}
_COMPILED_RISK = tuple(
    (tag, weight, re.compile(pat, re.IGNORECASE)) for tag, weight, pat in RISK_RULES
)


class GitError(RuntimeError):
    """Raised when git cannot answer — missing repo, bad ref, no git binary."""


def git(root: Path, *args: str, check: bool = True) -> str:
    """Run a git command in ``root`` and return stdout.

    Raises GitError rather than CalledProcessError so callers have one
    exception type to catch across the whole module.
    """
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=120,
        )
    except FileNotFoundError as exc:  # pragma: no cover - environment defect
        raise GitError("git binary not found on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise GitError(f"git {' '.join(args)} timed out") from exc
    if check and proc.returncode != 0:
        raise GitError(
            f"git {' '.join(args)} failed ({proc.returncode}): {proc.stderr.strip()}"
        )
    return proc.stdout


def lang_of(path: str) -> str:
    """Return the language key for a path, or ``other``."""
    return LANGS.get(Path(path).suffix.lower(), "other")


def is_test_path(path: str) -> bool:
    """True when the path looks like a test file.

    Deliberately generous: a false positive costs a slightly weaker
    changed-code-tested signal, while a false negative would let a change
    claim it shipped tests when it did not.
    """
    posix = "/" + path.replace("\\", "/").lstrip("/")
    lowered = posix.lower()
    if any(hint in lowered for hint in TEST_PATH_HINTS):
        return True
    return bool(TEST_NAME_RE.search("/" + Path(path).name))


def resolve_base(root: Path, base: str | None) -> str:
    """Pick the ref to diff against.

    Order: explicit ``--base`` → upstream tracking branch → origin's default
    branch → the repo's first commit. The last fallback is what makes this
    work on a branch that was never pushed.
    """
    if base:
        git(root, "rev-parse", "--verify", f"{base}^{{commit}}")
        return base

    for candidate in ("@{upstream}",):
        try:
            return git(root, "rev-parse", "--abbrev-ref", candidate).strip()
        except GitError:
            pass

    for candidate in ("origin/HEAD", "origin/main", "origin/master", "main", "master"):
        try:
            git(root, "rev-parse", "--verify", f"{candidate}^{{commit}}")
            return candidate
        except GitError:
            continue

    roots = git(root, "rev-list", "--max-parents=0", "HEAD").split()
    if roots:
        return roots[-1]
    raise GitError("cannot resolve a base ref to diff against")


def merge_base(root: Path, base: str) -> str:
    """Return the merge base with ``base``, falling back to ``base`` itself.

    Diffing against the merge base rather than the branch tip keeps unrelated
    commits landed on main out of this change's blast radius.
    """
    try:
        return git(root, "merge-base", "HEAD", base).strip() or base
    except GitError:
        return base


def collect_diff(root: Path, base: str, include_worktree: bool) -> str:
    """Return a unified diff with zero context lines.

    Zero context is deliberate: every line in a hunk body is then either an
    addition or a deletion, so attributing a marker to *this* change needs no
    heuristics.

    The prefixes are pinned explicitly. Git switches to mnemonic prefixes
    (``i/``, ``w/``, ``c/``) under some configurations, and a parser that only
    knows ``b/`` silently mis-reads every path in the diff — which then reads
    downstream as "the reviewer cited a file outside the change".
    """
    args = [
        "diff", "--unified=0", "--no-color", "--no-ext-diff", "-M",
        "--src-prefix=a/", "--dst-prefix=b/",
    ]
    if include_worktree:
        args.append(base)
    else:
        args.extend([f"{base}...HEAD"])
    return git(root, *args)


#: Directories never treated as part of the change under review.
UNTRACKED_EXCLUDE_DIRS = {".dev-autopilot", ".git", "node_modules", "__pycache__", ".venv", "venv"}

MAX_UNTRACKED_BYTES = 400_000


def untracked_files(root: Path) -> list[str]:
    """List new files git has not been told about yet.

    ``git diff`` shows nothing for untracked files, so a change that adds a new
    module — the single most common shape of feature work — would otherwise be
    invisible to every gate here: not counted, not risk-scored, not scanned for
    suppression markers, and not sent to the reviewer. The change would look
    smaller than it is and the new code would never be read.
    """
    try:
        listing = git(root, "ls-files", "--others", "--exclude-standard")
    except GitError:
        return []
    keep: list[str] = []
    for rel in listing.splitlines():
        rel = rel.strip()
        if not rel:
            continue
        parts = Path(rel).parts
        if any(part in UNTRACKED_EXCLUDE_DIRS for part in parts):
            continue
        keep.append(rel)
    return sorted(keep)


def read_untracked(root: Path, paths: list[str]) -> dict[str, list[tuple[int, str]]]:
    """Read new files as if every line were an addition, because it is."""
    added: dict[str, list[tuple[int, str]]] = {}
    for rel in paths:
        target = root / rel
        try:
            if not target.is_file() or target.stat().st_size > MAX_UNTRACKED_BYTES:
                continue
            raw = target.read_bytes()
        except OSError:
            continue
        if b"\0" in raw[:8000]:  # binary
            continue
        text = raw.decode("utf-8", errors="replace")
        added[rel] = list(enumerate(text.splitlines(), start=1))
    return added


def name_status(root: Path, base: str, include_worktree: bool) -> dict[str, str]:
    """Map path -> single-letter git status (A/M/D/R...)."""
    args = ["diff", "--name-status", "--no-renames", "-M"]
    args.append(base if include_worktree else f"{base}...HEAD")
    out = git(root, *args)
    statuses: dict[str, str] = {}
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            statuses[parts[-1]] = parts[0][:1]
    return statuses


HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")

#: Any single-token path prefix git might emit: b/, w/, i/, c/, o/.
DIFF_PREFIX_RE = re.compile(r"^[abciwo]/")


def strip_diff_prefix(target: str) -> str:
    """Drop git's path prefix, whichever variant it used."""
    return DIFF_PREFIX_RE.sub("", target, count=1)


def parse_diff(diff_text: str) -> dict[str, list[tuple[int, str]]]:
    """Parse a unified diff into ``path -> [(new_line_no, added_text)]``.

    Only added lines are returned. Deletions carry no risk of *introducing* a
    suppression marker, and removing one is a fix, never a defect.
    """
    added: dict[str, list[tuple[int, str]]] = {}
    path: str | None = None
    line_no = 0
    for raw in diff_text.splitlines():
        if raw.startswith("+++ "):
            target = raw[4:].strip()
            path = None if target == "/dev/null" else strip_diff_prefix(target)
            if path is not None:
                added.setdefault(path, [])
            continue
        if raw.startswith("--- ") or raw.startswith("diff --git"):
            continue
        match = HUNK_RE.match(raw)
        if match:
            line_no = int(match.group(1))
            continue
        if path is None:
            continue
        if raw.startswith("+"):
            added[path].append((line_no, raw[1:]))
            line_no += 1
    return added


def strip_comment(text: str, lang: str) -> str:
    """Blank out an obvious trailing line comment.

    Keeps ``// test.only(...)`` in a commented-out block from tripping the
    focus gate. Not a parser — string literals containing ``//`` survive, which
    is the safe direction to be wrong in.
    """
    markers = {"python": "#", "ruby": "#", "shell": "#", "yaml": "#"}.get(lang, "//")
    idx = text.find(markers)
    if idx == -1:
        return text
    if text[:idx].count('"') % 2 or text[:idx].count("'") % 2:
        return text
    return text[:idx]


def scan_markers(
    path: str, lines: Iterable[tuple[int, str]], lang: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (suppression_sites, focus_sites) for one file's added lines."""
    sup_rules = _COMPILED_SUPPRESSION.get(lang, ())
    focus_rules = _COMPILED_FOCUS.get(lang, ())
    if not sup_rules and not focus_rules:
        return [], []

    suppressions: list[dict[str, Any]] = []
    focus: list[dict[str, Any]] = []
    for line_no, text in lines:
        code = strip_comment(text, lang)
        if not code.strip():
            continue
        snippet = text.strip()[:160]
        for kind, pattern in focus_rules:
            if pattern.search(code):
                focus.append(
                    {"path": path, "line": line_no, "kind": kind,
                     "lang": lang, "snippet": snippet}
                )
                break
        for kind, pattern in sup_rules:
            if pattern.search(code):
                suppressions.append(
                    {"path": path, "line": line_no, "kind": kind,
                     "lang": lang, "snippet": snippet}
                )
                break
    return suppressions, focus


def scan_tree(root: Path, max_files: int = 4000) -> dict[str, Any]:
    """Census every tracked test file, not just the changed ones.

    Gives the absolute suppression ratio, which contextualises the delta: two
    new skips in a suite of six is a very different signal from two in a suite
    of six hundred.
    """
    try:
        tracked = git(root, "ls-files").splitlines()
    except GitError:
        return {"scanned": 0, "suppressed": 0, "focus": 0, "by_kind": {}, "truncated": False}

    test_files = [p for p in tracked if is_test_path(p)][:max_files]
    truncated = len([p for p in tracked if is_test_path(p)]) > max_files
    by_kind: dict[str, int] = {}
    total = 0
    focus_total = 0
    for rel in test_files:
        file_path = root / rel
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            continue
        lang = lang_of(rel)
        numbered = list(enumerate(content.splitlines(), start=1))
        sup, foc = scan_markers(rel, numbered, lang)
        for site in sup:
            by_kind[site["kind"]] = by_kind.get(site["kind"], 0) + 1
        total += len(sup)
        focus_total += len(foc)
    return {
        "scanned": len(test_files),
        "suppressed": total,
        "focus": focus_total,
        "by_kind": dict(sorted(by_kind.items())),
        "truncated": truncated,
    }


def score_risk(paths: Iterable[str]) -> dict[str, Any]:
    """Weight the change by what it touches, not by how big it is."""
    tags: dict[str, list[str]] = {}
    for path in paths:
        for tag, _weight, pattern in _COMPILED_RISK:
            if pattern.search(path):
                tags.setdefault(tag, []).append(path)
    weights = {tag: weight for tag, weight, _ in RISK_RULES}
    score = min(100, sum(weights[tag] for tag in tags))
    level = "high" if score >= 40 else "medium" if score >= 15 else "low"
    return {
        "score": score,
        "level": level,
        "tags": sorted(tags),
        "evidence": {tag: sorted(set(files))[:8] for tag, files in sorted(tags.items())},
    }


def analyze(
    root: Path,
    base: str | None = None,
    include_worktree: bool = True,
    diff_text: str | None = None,
    scan_whole_tree: bool = True,
) -> dict[str, Any]:
    """Produce the full diff-intelligence report."""
    if diff_text is None:
        resolved = resolve_base(root, base)
        effective_base = merge_base(root, resolved)
        diff_text = collect_diff(root, effective_base, include_worktree)
        statuses = name_status(root, effective_base, include_worktree)
        head = git(root, "rev-parse", "HEAD").strip()
        branch = git(root, "rev-parse", "--abbrev-ref", "HEAD").strip()
    else:
        resolved = base or "(supplied-diff)"
        effective_base = resolved
        statuses = {}
        head = ""
        branch = ""

    added_by_file = parse_diff(diff_text)

    # New files are absent from `git diff` entirely; fold them in as all-added.
    # `head` is only set when we produced the diff from git ourselves; a
    # caller-supplied patch is taken exactly as given.
    untracked: list[str] = []
    if head and include_worktree:
        untracked = untracked_files(root)
        for path, lines in read_untracked(root, untracked).items():
            added_by_file.setdefault(path, []).extend(lines)
            statuses.setdefault(path, "A")
    deleted_counts: dict[str, int] = {}
    current: str | None = None
    for raw in diff_text.splitlines():
        if raw.startswith("+++ "):
            target = raw[4:].strip()
            current = None if target == "/dev/null" else strip_diff_prefix(target)
        elif raw.startswith("-") and not raw.startswith("---") and current:
            deleted_counts[current] = deleted_counts.get(current, 0) + 1

    files: list[dict[str, Any]] = []
    suppression_sites: list[dict[str, Any]] = []
    focus_sites: list[dict[str, Any]] = []

    for path in sorted(added_by_file):
        lines = added_by_file[path]
        lang = lang_of(path)
        sup, foc = scan_markers(path, lines, lang)
        suppression_sites.extend(sup)
        focus_sites.extend(foc)
        files.append(
            {
                "path": path,
                "status": statuses.get(path, "M"),
                "lang": lang,
                "added": len(lines),
                "deleted": deleted_counts.get(path, 0),
                "is_test": is_test_path(path),
            }
        )

    suppression_sites.sort(key=lambda s: (s["path"], s["line"], s["kind"]))
    focus_sites.sort(key=lambda s: (s["path"], s["line"], s["kind"]))

    src_changed = [f for f in files if not f["is_test"] and f["lang"] != "markdown"]
    test_changed = [f for f in files if f["is_test"]]

    by_kind: dict[str, int] = {}
    for site in suppression_sites:
        by_kind[site["kind"]] = by_kind.get(site["kind"], 0) + 1

    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "base": effective_base,
        "base_requested": resolved,
        "head": head,
        "branch": branch,
        "files": files,
        "totals": {
            "files": len(files),
            "added": sum(f["added"] for f in files),
            "deleted": sum(f["deleted"] for f in files),
            "source_files": len(src_changed),
            "test_files": len(test_changed),
        },
        "risk": score_risk(f["path"] for f in files),
        "suppression": {
            "added": len(suppression_sites),
            "by_kind": dict(sorted(by_kind.items())),
            "sites": suppression_sites,
        },
        "focus": {"added": len(focus_sites), "sites": focus_sites},
        "tests_moved_with_source": bool(test_changed) or not src_changed,
    }
    if scan_whole_tree and head:
        report["tree_census"] = scan_tree(root)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--root", default=".", help="Repository root")
    parser.add_argument("--base", default=None, help="Base ref (default: auto)")
    parser.add_argument(
        "--committed-only",
        action="store_true",
        help="Diff base...HEAD only, ignoring uncommitted work",
    )
    parser.add_argument("--diff-file", default=None, help="Read a saved patch instead of git")
    parser.add_argument("--no-tree-scan", action="store_true", help="Skip whole-tree census")
    parser.add_argument("--output", default=None, help="Write JSON here")
    parser.add_argument("--json", action="store_true", help="Print JSON to stdout")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    diff_text = None
    if args.diff_file:
        diff_text = Path(args.diff_file).read_text(encoding="utf-8", errors="replace")

    try:
        report = analyze(
            root,
            base=args.base,
            include_worktree=not args.committed_only,
            diff_text=diff_text,
            scan_whole_tree=not args.no_tree_scan,
        )
    except GitError as exc:
        payload = {"schema_version": SCHEMA_VERSION, "error": str(exc)}
        text = json.dumps(payload, indent=2)
        if args.output:
            Path(args.output).write_text(text + "\n", encoding="utf-8")
        print(text)
        return 1

    text = json.dumps(report, indent=2)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    if args.json or not args.output:
        print(text)
    else:
        totals = report["totals"]
        print(
            f"{totals['files']} files (+{totals['added']}/-{totals['deleted']})  "
            f"risk={report['risk']['level']}  "
            f"suppression+{report['suppression']['added']}  "
            f"focus+{report['focus']['added']}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
