#!/usr/bin/env python3
"""Executable guards referenced by contract criteria.

Each subcommand is a *machine observation*, not an opinion: it inspects the diff,
the working tree, or the result of running something, and exits 0 (pass) or
non-zero (fail). Contract criteria point at these commands so the loop's score is
computed from evidence rather than from the agent's account of its own work.

Subcommands
-----------
    focus            no .only / fit / fdescribe added to the diff
    suppression      no net-new skipped or fixme'd tests
    scope            no file changed outside the contract's declared scope
    tests-unchanged  no test file modified (behaviour-preservation for refactors)
    findings         findings.md exists and carries real, anchored content
    review-anchors   every cited file:line lands inside the reviewed diff
    sources          every section of findings.md cites a file:line or URL
    mutation         the new tests actually fail when the code is mutated
    examples         every runnable example in the docs executes
    benchmark        the measured metric improved on the recorded baseline

All subcommands take ``--root``; diff-based ones also take ``--base``.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable

# Never leave __pycache__ in the repository under test: an untracked byte-cache
# directory reads as a dirty tree and would be swept away by a discard.
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

from contract import STATE_DIR, load_contract  # noqa: E402

FINDINGS_FILE = "findings.md"
BENCH_BASELINE = "benchmark_baseline.json"

#: Focus markers, per ecosystem. Matching added diff lines only.
FOCUS_PATTERNS = [
    r"\bdescribe\.only\b",
    r"\bit\.only\b",
    r"\btest\.only\b",
    r"\bcontext\.only\b",
    r"\bfdescribe\s*\(",
    r"\bfit\s*\(",
    r"\bfcontext\s*\(",
    r"\.only\s*\(",
]

#: Suppression markers — a test that no longer runs.
SUPPRESSION_PATTERNS = [
    r"\bdescribe\.skip\b",
    r"\bit\.skip\b",
    r"\btest\.skip\b",
    r"\btest\.fixme\b",
    r"\bxdescribe\s*\(",
    r"\bxit\s*\(",
    r"\.skip\s*\(",
    r"@pytest\.mark\.skip",
    r"@pytest\.mark\.xfail",
    r"@unittest\.skip",
    r"\bt\.Skip\s*\(",
    r"#\[ignore\]",
]

TEST_PATH_PATTERNS = [
    "*test*",
    "*spec*",
    "*/tests/*",
    "*/__tests__/*",
    "*_test.go",
]

CITATION_RE = re.compile(
    r"(?:(?P<path>[\w./\-]+\.[A-Za-z0-9]{1,6}):(?P<line>\d+))|(?P<url>https?://\S+)"
)


class GuardError(RuntimeError):
    """Raised when a guard cannot run at all (as distinct from failing)."""


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def git(root: Path, *args: str, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        ["git", *args], cwd=root, capture_output=True, text=True, check=check
    )


def diff_text(root: Path, base: str) -> str:
    """Unified diff of the working tree against ``base``, including untracked files."""
    tracked = git(root, "diff", base, "--unified=0").stdout
    untracked = git(root, "ls-files", "--others", "--exclude-standard").stdout.split()
    extra: list[str] = []
    for rel in untracked:
        path = root / rel
        if not path.is_file() or _looks_binary(path):
            continue
        extra.append(f"+++ b/{rel}")
        try:
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                extra.append("+" + line)
        except OSError:
            continue
    return tracked + "\n" + "\n".join(extra)


def changed_files(root: Path, base: str) -> list[str]:
    """Every path that differs from ``base``, tracked or not."""
    out = git(root, "diff", "--name-only", base).stdout.split()
    untracked = git(root, "ls-files", "--others", "--exclude-standard").stdout.split()
    seen: dict[str, None] = {}
    for rel in [*out, *untracked]:
        if rel and not rel.startswith(STATE_DIR):
            seen[rel] = None
    return list(seen)


def added_lines(diff: str) -> list[str]:
    return [ln[1:] for ln in diff.splitlines() if ln.startswith("+") and not ln.startswith("+++")]


def removed_lines(diff: str) -> list[str]:
    return [ln[1:] for ln in diff.splitlines() if ln.startswith("-") and not ln.startswith("---")]


def _looks_binary(path: Path) -> bool:
    try:
        return b"\0" in path.open("rb").read(2048)
    except OSError:
        return True


#: Only source files can be "a modified test". A .pyc under __pycache__ matches
#: every naive *test* glob and would otherwise fail tests-unchanged on a clean tree.
SOURCE_SUFFIXES = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".go", ".rs",
    ".java", ".kt", ".rb", ".php", ".cs", ".swift", ".scala", ".c", ".cc",
    ".cpp", ".h", ".hpp", ".sh", ".sql",
}


def is_test_path(rel: str) -> bool:
    low = rel.lower()
    if Path(low).suffix not in SOURCE_SUFFIXES:
        return False
    return any(fnmatch.fnmatch(low, pat) for pat in TEST_PATH_PATTERNS)


def count_matches(lines: Iterable[str], patterns: list[str]) -> list[tuple[str, str]]:
    hits: list[tuple[str, str]] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(("//", "#", "*")):
            continue
        for pat in patterns:
            if re.search(pat, line):
                hits.append((pat, line.strip()))
                break
    return hits


def findings_path(root: Path) -> Path:
    return root / STATE_DIR / FINDINGS_FILE


def ok(message: str) -> int:
    print(f"PASS: {message}")
    return 0


def fail(message: str, detail: Iterable[str] = ()) -> int:
    print(f"FAIL: {message}", file=sys.stderr)
    for line in detail:
        print(f"  {line}", file=sys.stderr)
    return 1


# --------------------------------------------------------------------------
# diff guards
# --------------------------------------------------------------------------


def guard_focus(root: Path, base: str) -> int:
    hits = count_matches(added_lines(diff_text(root, base)), FOCUS_PATTERNS)
    if hits:
        return fail(
            f"{len(hits)} focus marker(s) added — the suite is silently narrowed",
            [line for _, line in hits[:10]],
        )
    return ok("no focus markers added")


def guard_suppression(root: Path, base: str, budget: int = 0) -> int:
    diff = diff_text(root, base)
    added = count_matches(added_lines(diff), SUPPRESSION_PATTERNS)
    removed = count_matches(removed_lines(diff), SUPPRESSION_PATTERNS)
    net = len(added) - len(removed)
    if net > budget:
        return fail(
            f"{net} net-new suppressed test(s), budget is {budget} — green reached by not running tests",
            [line for _, line in added[:10]],
        )
    return ok(f"suppression delta {net} within budget {budget}")


def guard_scope(root: Path, base: str) -> int:
    try:
        contract = load_contract(root)
    except Exception as exc:  # noqa: BLE001 - guard must report, not crash the loop
        return fail(f"cannot read contract: {exc}")
    scope: list[str] = contract.get("scope") or []
    if not scope:
        return ok("no scope declared — whole repo permitted")
    violations = [
        rel
        for rel in changed_files(root, base)
        if not any(fnmatch.fnmatch(rel, pat) for pat in scope)
    ]
    if violations:
        return fail(
            f"{len(violations)} file(s) changed outside declared scope {scope}",
            violations[:10],
        )
    return ok(f"all changes inside scope {scope}")


def guard_tests_unchanged(root: Path, base: str) -> int:
    touched = [rel for rel in changed_files(root, base) if is_test_path(rel)]
    if touched:
        return fail(
            f"{len(touched)} test file(s) modified — a refactor that edits its own tests "
            "is changing the metric, not preserving behaviour",
            touched[:10],
        )
    return ok("no test files modified")


# --------------------------------------------------------------------------
# deliverable guards
# --------------------------------------------------------------------------


def _read_findings(root: Path) -> str:
    path = findings_path(root)
    if not path.is_file():
        raise GuardError(f"no findings at {path}")
    return path.read_text(encoding="utf-8")


def guard_findings(root: Path, min_words: int = 80) -> int:
    try:
        text = _read_findings(root)
    except GuardError as exc:
        return fail(str(exc), [f"write your conclusions to {findings_path(root)}"])
    words = len(text.split())
    if words < min_words:
        return fail(f"findings.md has {words} words, minimum {min_words} — that is a placeholder, not a finding")
    if not CITATION_RE.search(text):
        return fail("findings.md contains no file:line or URL citation — an uncited claim is a guess")
    return ok(f"findings.md present ({words} words, cited)")


def guard_sources(root: Path) -> int:
    try:
        text = _read_findings(root)
    except GuardError as exc:
        return fail(str(exc))
    sections = re.split(r"^##+\s+", text, flags=re.MULTILINE)
    body = [s for s in sections[1:] if s.strip()] or [text]
    uncited = [s.splitlines()[0].strip() for s in body if not CITATION_RE.search(s)]
    if uncited:
        return fail(
            f"{len(uncited)} section(s) of findings.md cite nothing",
            uncited[:10],
        )
    return ok(f"all {len(body)} section(s) cite a source")


def guard_review_anchors(root: Path, base: str) -> int:
    try:
        text = _read_findings(root)
    except GuardError as exc:
        return fail(str(exc))
    reviewed = set(changed_files(root, base))
    if not reviewed:
        return fail("the diff is empty — there is nothing to review")
    cited = {m.group("path") for m in CITATION_RE.finditer(text) if m.group("path")}
    if not cited:
        return fail("no finding cites a file:line inside the diff")
    stray = sorted(
        p for p in cited if p not in reviewed and not any(r.endswith(p) for r in reviewed)
    )
    if stray:
        return fail(
            f"{len(stray)} citation(s) point outside the reviewed diff",
            stray[:10],
        )
    return ok(f"all {len(cited)} citation(s) anchored inside the diff")


# --------------------------------------------------------------------------
# mutation guard — proves new tests can actually fail
# --------------------------------------------------------------------------

#: Each entry is (regex, replacement). Applied one at a time to a single file.
MUTATIONS: list[tuple[str, str]] = [
    (r"\btrue\b", "false"),
    (r"\bFalse\b", "True"),
    (r"(?<![!<>=])==(?!=)", "!="),
    (r"(?<![!<>=])!=(?!=)", "=="),
    (r"(?<![-+*/<>=!])<=(?!=)", ">"),
    (r"(?<![-+*/<>=!])>=(?!=)", "<"),
    (r"(?<=[\s(=])\+(?=[\s(])", "-"),
]


def _mutation_targets(root: Path, contract: dict[str, Any], base: str) -> list[Path]:
    configured = (contract.get("mutation") or {}).get("targets")
    if configured:
        found: list[Path] = []
        for pattern in configured:
            found.extend(p for p in root.glob(pattern) if p.is_file())
        return found
    return [
        root / rel
        for rel in changed_files(root, base)
        if not is_test_path(rel) and (root / rel).is_file() and not _looks_binary(root / rel)
    ]


def guard_mutation(root: Path, base: str, timeout: int = 900) -> int:
    """Mutate the code under test and require the suite to notice.

    A test that passes no matter what the source does buys false confidence. This
    applies one small textual mutation at a time, runs the suite, and requires at
    least one mutation to be *killed* (suite goes red). Every file is restored in a
    ``finally`` block, including on interrupt.
    """
    try:
        contract = load_contract(root)
    except Exception as exc:  # noqa: BLE001
        return fail(f"cannot read contract: {exc}")

    test_cmd = (contract.get("toolchain") or {}).get("test")
    if not test_cmd:
        return fail("no test command in the contract — cannot run a mutation check")

    targets = _mutation_targets(root, contract, base)
    if not targets:
        return fail(
            "no non-test source file to mutate",
            ["declare mutation.targets in the contract, or change a source file"],
        )

    baseline = subprocess.run(  # noqa: S602
        test_cmd, cwd=root, shell=True, capture_output=True, text=True, timeout=timeout, check=False
    )
    if baseline.returncode != 0:
        return fail(
            "the suite is already red before mutating — fix it first, "
            "a red suite kills every mutation trivially"
        )

    attempted = 0
    for target in targets[:5]:
        try:
            original = target.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for pattern, replacement in MUTATIONS:
            mutated, count = re.subn(pattern, replacement, original, count=1)
            if count == 0 or mutated == original:
                continue
            attempted += 1
            try:
                target.write_text(mutated, encoding="utf-8")
                proc = subprocess.run(  # noqa: S602
                    test_cmd, cwd=root, shell=True, capture_output=True,
                    text=True, timeout=timeout, check=False,
                )
            except subprocess.TimeoutExpired:
                proc = None
            finally:
                target.write_text(original, encoding="utf-8")
            if proc is not None and proc.returncode != 0:
                rel = target.relative_to(root)
                return ok(f"mutation killed: '{pattern}' -> '{replacement}' in {rel} turned the suite red")
    if attempted == 0:
        return fail(
            "no mutation could be applied to any target file",
            [f"tried {len(targets)} file(s); none contained a mutable construct"],
        )
    return fail(
        f"all {attempted} mutation(s) survived — the tests pass regardless of what the code does",
        ["a test that cannot fail is worse than no test: it buys false confidence"],
    )


# --------------------------------------------------------------------------
# examples guard — documented examples must actually run
# --------------------------------------------------------------------------

RUNNABLE_LANGS = {
    "bash": ["bash"],
    "sh": ["sh"],
    "shell": ["bash"],
    "python": [sys.executable],
    "py": [sys.executable],
}

FENCE_RE = re.compile(r"^```(\w+)[^\n]*\n(.*?)^```", re.MULTILINE | re.DOTALL)


def guard_examples(root: Path, timeout: int = 120) -> int:
    """Execute every fenced, runnable example in the docs touched by this run."""
    try:
        contract = load_contract(root)
    except Exception as exc:  # noqa: BLE001
        return fail(f"cannot read contract: {exc}")

    patterns = (contract.get("docs") or {}).get("paths") or contract.get("scope") or ["**/*.md"]
    docs: list[Path] = []
    for pattern in patterns:
        docs.extend(p for p in root.glob(pattern) if p.is_file() and p.suffix.lower() == ".md")
    docs = [d for d in docs if STATE_DIR not in d.parts and "node_modules" not in d.parts]
    if not docs:
        return fail("no markdown files matched", [f"patterns tried: {patterns}"])

    ran = 0
    failures: list[str] = []
    for doc in sorted(set(docs)):
        text = doc.read_text(encoding="utf-8", errors="replace")
        for index, match in enumerate(FENCE_RE.finditer(text), start=1):
            lang, body = match.group(1).lower(), match.group(2)
            interpreter = RUNNABLE_LANGS.get(lang)
            if not interpreter or "no-run" in match.group(0).split("\n", 1)[0]:
                continue
            ran += 1
            with tempfile.NamedTemporaryFile("w", suffix=f".{lang}", delete=False, encoding="utf-8") as handle:
                handle.write(body)
                script = handle.name
            try:
                proc = subprocess.run(  # noqa: S603
                    [*interpreter, script], cwd=root, capture_output=True,
                    text=True, timeout=timeout, check=False,
                )
                if proc.returncode != 0:
                    first = (proc.stderr.strip().splitlines() or ["(no stderr)"])[-1]
                    failures.append(f"{doc.relative_to(root)} block #{index} ({lang}) exit {proc.returncode}: {first}")
            except subprocess.TimeoutExpired:
                failures.append(f"{doc.relative_to(root)} block #{index} ({lang}) timed out after {timeout}s")
            finally:
                os.unlink(script)

    if ran == 0:
        return fail(
            "no runnable examples found",
            ["documentation with no executable example cannot be verified;",
             "add a ```bash or ```python block, or mark the criterion not applicable"],
        )
    if failures:
        return fail(f"{len(failures)} of {ran} example(s) failed", failures[:10])
    return ok(f"all {ran} example(s) executed successfully")


# --------------------------------------------------------------------------
# benchmark guard — the val_bpb analogue
# --------------------------------------------------------------------------

METRIC_RE = re.compile(r"^\s*(?:metric|score|time|duration|ops|latency)\s*[:=]\s*([0-9]*\.?[0-9]+)", re.MULTILINE | re.IGNORECASE)


def guard_benchmark(root: Path, record_baseline: bool = False, timeout: int = 1800) -> int:
    """Run the configured benchmark and compare against the recorded baseline.

    The contract's ``benchmark`` block declares ``cmd`` (what to run),
    ``direction`` (``lower`` or ``higher`` is better) and optionally ``pattern``
    (a regex whose first group is the number). With ``--record`` the measurement
    becomes the baseline instead of being compared — that is what the baseline
    attempt does.
    """
    try:
        contract = load_contract(root)
    except Exception as exc:  # noqa: BLE001
        return fail(f"cannot read contract: {exc}")

    bench = contract.get("benchmark") or {}
    cmd = bench.get("cmd")
    if not cmd:
        return fail(
            "no benchmark declared in the contract",
            ['add {"benchmark": {"cmd": "...", "direction": "lower"}} before locking'],
        )
    direction = bench.get("direction", "lower")
    pattern = re.compile(bench["pattern"], re.MULTILINE) if bench.get("pattern") else METRIC_RE

    try:
        proc = subprocess.run(  # noqa: S602
            cmd, cwd=root, shell=True, capture_output=True, text=True, timeout=timeout, check=False
        )
    except subprocess.TimeoutExpired:
        return fail(f"benchmark exceeded {timeout}s")
    if proc.returncode != 0:
        tail = (proc.stderr.strip().splitlines() or ["(no stderr)"])[-3:]
        return fail(f"benchmark command exited {proc.returncode}", tail)

    match = pattern.search(proc.stdout) or pattern.search(proc.stderr)
    if not match:
        return fail(
            "benchmark produced no parseable metric",
            ["expected a line like 'metric: 12.34' or a custom benchmark.pattern"],
        )
    value = float(match.group(1))

    store = root / STATE_DIR / BENCH_BASELINE
    if record_baseline or not store.is_file():
        store.parent.mkdir(parents=True, exist_ok=True)
        store.write_text(json.dumps({"value": value, "direction": direction}, indent=2), encoding="utf-8")
        if record_baseline:
            return ok(f"baseline recorded: {value} ({direction} is better)")
        # Implicit first measurement. Recording is not improving: report this as a
        # failure so the baseline attempt is honestly red and the loop has a number
        # to beat rather than free credit for having measured anything at all.
        return fail(
            f"baseline recorded: {value} ({direction} is better) — no improvement yet",
            ["this is the expected result at baseline; beat this number to satisfy the criterion"],
        )

    previous = json.loads(store.read_text(encoding="utf-8"))["value"]
    improved = value < previous if direction == "lower" else value > previous
    delta = value - previous
    if improved:
        return ok(f"benchmark improved: {previous} -> {value} (delta {delta:+.6g})")
    return fail(f"benchmark did not improve: {previous} -> {value} (delta {delta:+.6g})")


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="guard", required=True)

    def add(name: str, *, base: bool = False, help_text: str = "") -> argparse.ArgumentParser:
        sp = sub.add_parser(name, help=help_text)
        sp.add_argument("--root", default=".")
        if base:
            sp.add_argument("--base", default="HEAD")
        return sp

    add("focus", base=True, help_text="no focus markers added")
    add("suppression", base=True, help_text="no net-new skipped tests").add_argument("--budget", type=int, default=0)
    add("scope", base=True, help_text="changes stay inside declared scope")
    add("tests-unchanged", base=True, help_text="no test file modified")
    add("findings", help_text="findings.md exists and is anchored").add_argument("--min-words", type=int, default=80)
    add("sources", help_text="every section cites a source")
    add("review-anchors", base=True, help_text="citations land inside the diff")
    add("mutation", base=True, help_text="new tests fail when code is mutated")
    add("examples", help_text="documented examples execute")
    add("benchmark", help_text="metric improved on baseline").add_argument("--record", action="store_true")

    return parser


DISPATCH = {
    "focus": lambda a: guard_focus(Path(a.root).resolve(), a.base),
    "suppression": lambda a: guard_suppression(Path(a.root).resolve(), a.base, a.budget),
    "scope": lambda a: guard_scope(Path(a.root).resolve(), a.base),
    "tests-unchanged": lambda a: guard_tests_unchanged(Path(a.root).resolve(), a.base),
    "findings": lambda a: guard_findings(Path(a.root).resolve(), a.min_words),
    "sources": lambda a: guard_sources(Path(a.root).resolve()),
    "review-anchors": lambda a: guard_review_anchors(Path(a.root).resolve(), a.base),
    "mutation": lambda a: guard_mutation(Path(a.root).resolve(), a.base),
    "examples": lambda a: guard_examples(Path(a.root).resolve()),
    "benchmark": lambda a: guard_benchmark(Path(a.root).resolve(), a.record),
}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if shutil.which("git") is None:
        print("error: git is required", file=sys.stderr)
        return 2
    try:
        return int(DISPATCH[args.guard](args))
    except GuardError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
