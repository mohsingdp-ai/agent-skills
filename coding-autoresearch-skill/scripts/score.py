#!/usr/bin/env python3
"""Score the working tree against the locked contract.

This is the ``evaluate_bpb`` of the skill: the one place a number is produced,
and the only thing the loop is allowed to believe. It executes each criterion as
a real subprocess and records the real exit code — an agent cannot assert its way
to a score, only run things.

Three outcomes per criterion:

``pass``   the criterion is satisfied for this phase
``fail``   the command ran and the criterion is not satisfied
``crash``  the command could not run at all (missing binary, timeout)

The pass/fail distinction is phase-dependent. A criterion marked
``expect: fail`` is satisfied at *baseline* precisely when its command fails —
that is the red-green proof, and it is the same rule as autoresearch's "the first
run establishes the baseline".

    score.py --root . --phase baseline
    score.py --root . --phase attempt
    score.py --root . --phase holdout

Exit codes: 0 every criterion satisfied, 1 at least one unsatisfied,
2 at least one crashed, 3 the contract lock is broken.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Never leave __pycache__ in the repository under test: an untracked byte-cache
# directory reads as a dirty tree and would be swept away by a discard.
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

from contract import (  # noqa: E402
    EXPECT_FAIL,
    STATE_DIR,
    ContractError,
    load_contract,
    verify_contract,
)

VERDICT_FILE = "verdict.json"
LOG_DIR = "logs"

PASS = "pass"
FAIL = "fail"
CRASH = "crash"

PHASE_BASELINE = "baseline"
PHASE_ATTEMPT = "attempt"
PHASE_HOLDOUT = "holdout"

#: Exit codes that mean "the command never really ran", not "the check failed".
#: 127 = not found, 126 = found but not executable. Treating these as failures
#: would let a typo'd command stand in for a passing check.
HARNESS_EXITS = {126, 127}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def run_criterion(
    root: Path, criterion: dict[str, Any], phase: str, timeout: int, log_dir: Path
) -> dict[str, Any]:
    """Execute one criterion and classify the result.

    Output is written to a log file rather than returned wholesale: a test suite's
    stdout can be megabytes, and flooding it into the agent's context is exactly
    what autoresearch's ``> run.log 2>&1`` exists to prevent.
    """
    cmd = criterion["cmd"]
    started = time.monotonic()
    log_path = log_dir / f"{phase}-{criterion['id']}.log"
    log_dir.mkdir(parents=True, exist_ok=True)

    try:
        proc = subprocess.run(  # noqa: S602
            cmd, cwd=root, shell=True, capture_output=True, text=True, timeout=timeout, check=False
        )
        returncode = proc.returncode
        log_path.write_text(
            f"$ {cmd}\n--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}\n",
            encoding="utf-8",
        )
        timed_out = False
    except subprocess.TimeoutExpired:
        returncode = -1
        timed_out = True
        log_path.write_text(f"$ {cmd}\n--- timed out after {timeout}s ---\n", encoding="utf-8")
    except OSError as exc:
        returncode = 127
        timed_out = False
        log_path.write_text(f"$ {cmd}\n--- could not launch: {exc} ---\n", encoding="utf-8")

    elapsed = round(time.monotonic() - started, 1)

    # The score must mean the same thing in every phase, or "3 -> 0" compares two
    # different rulers and the keep/discard decision is meaningless. So status is
    # always plain satisfaction: the command exited zero. Whether a criterion was
    # correctly RED at baseline is a separate, non-scoring question, recorded below.
    if timed_out or returncode in HARNESS_EXITS:
        status = CRASH
    else:
        status = PASS if returncode == 0 else FAIL

    must_fail_here = phase == PHASE_BASELINE and criterion.get("expect") == EXPECT_FAIL
    demonstrated = None if not must_fail_here else (status == FAIL)

    return {
        "id": criterion["id"],
        "text": criterion.get("text", ""),
        "cmd": cmd,
        "weight": int(criterion.get("weight", 1)),
        "expect": criterion.get("expect", "pass"),
        "phase": phase,
        "status": status,
        "exit_code": returncode,
        "seconds": elapsed,
        # True  = failed at baseline as required (the problem is real and present)
        # False = passed at baseline when it had to fail (proves nothing)
        # None  = not a baseline red-check
        "demonstrated": demonstrated,
        "log": str(log_path.relative_to(root)) if log_path.is_relative_to(root) else str(log_path),
        "note": _explain(status, demonstrated, returncode, timed_out, timeout),
    }


def _explain(status: str, demonstrated: bool | None, code: int, timed_out: bool, timeout: int) -> str:
    if timed_out:
        return f"timed out after {timeout}s — treated as a crash, not a failure"
    if code in HARNESS_EXITS:
        return f"exit {code}: the command could not run (missing or not executable)"
    if demonstrated is True:
        return "red at baseline as required — the problem is real and present"
    if demonstrated is False:
        return "green at baseline, but it had to be red — this does not reproduce the reported problem"
    return "satisfied" if status == PASS else f"exit {code}"


#: Extensions that count toward the size of the codebase.
SOURCE_SUFFIXES = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".go", ".rs",
    ".java", ".kt", ".rb", ".php", ".cs", ".swift", ".scala", ".c", ".cc",
    ".cpp", ".h", ".hpp", ".sh", ".sql",
}


def complexity(root: Path, contract: dict[str, Any]) -> int:
    """Total source lines in scope — the simplicity criterion's number.

    Deliberately absolute, not the size of the diff. autoresearch's rule is
    "removing something and getting equal results is a great outcome", and that
    is a statement about the code, not about how many lines the patch touched. A
    diff-sized metric starts at zero and can only grow, so it would score every
    refactor as a regression and no simplification could ever be kept.

    Scope-filtered when the contract declares a scope, so unrelated churn
    elsewhere in a monorepo cannot drown out a real reduction.
    """
    scope: list[str] = contract.get("scope") or []
    proc = subprocess.run(  # noqa: S603
        ["git", "ls-files"], cwd=root, capture_output=True, text=True, check=False
    )
    total = 0
    for rel in proc.stdout.splitlines():
        if not rel or Path(rel).suffix not in SOURCE_SUFFIXES:
            continue
        if scope and not any(fnmatch.fnmatch(rel, pat) for pat in scope):
            continue
        path = root / rel
        try:
            with path.open("rb") as handle:
                total += sum(1 for _ in handle)
        except OSError:
            continue
    return total


def score_tree(root: Path, phase: str) -> dict[str, Any]:
    """Run every criterion for ``phase`` and assemble the verdict."""
    intact, message = verify_contract(root)
    if not intact:
        raise ContractError(message)

    contract = load_contract(root)
    timeout = int(contract.get("budget", {}).get("attempt_seconds", 600))
    log_dir = root / STATE_DIR / LOG_DIR

    criteria = contract["holdout"] if phase == PHASE_HOLDOUT else contract["criteria"]
    results = [run_criterion(root, c, phase, timeout, log_dir) for c in criteria]

    earned = sum(r["weight"] for r in results if r["status"] == PASS)
    total = sum(r["weight"] for r in results)
    crashes = [r for r in results if r["status"] == CRASH]
    # Every criterion required to be red at baseline actually was.
    not_demonstrated = [r for r in results if r["demonstrated"] is False]

    verdict: dict[str, Any] = {
        "phase": phase,
        "scored_at": _now(),
        "score": earned,
        "max_score": total,
        "complete": earned == total and not crashes,
        "crashed": bool(crashes),
        "red_ok": not not_demonstrated,
        "not_demonstrated": [r["id"] for r in not_demonstrated],
        "complexity": complexity(root, contract),
        "objective": contract.get("objective", "criteria"),
        "complexity_direction": contract.get("complexity", {}).get("direction", "lower"),
        "criteria": results,
        "contract_digest": contract["lock"]["digest"],
    }
    return verdict


def write_verdict(root: Path, verdict: dict[str, Any]) -> Path:
    path = root / STATE_DIR / VERDICT_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(verdict, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def read_verdict(root: Path) -> dict[str, Any] | None:
    path = root / STATE_DIR / VERDICT_FILE
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def render(verdict: dict[str, Any]) -> str:
    """Human-readable verdict — the thing printed after every attempt."""
    lines = [
        f"phase: {verdict['phase']}   score: {verdict['score']}/{verdict['max_score']}"
        f"   complexity: {verdict['complexity']} changed lines",
        "",
    ]
    symbol = {PASS: "PASS ", FAIL: "FAIL ", CRASH: "CRASH"}
    for item in verdict["criteria"]:
        lines.append(f"  {symbol[item['status']]} [{item['weight']}] {item['id']}: {item['text']}")
        lines.append(f"          {item['note']}  ({item['seconds']}s, log: {item['log']})")
    lines.append("")
    if verdict["crashed"]:
        lines.append("VERDICT: crash — a criterion could not run. Read its log before changing any code.")
    elif verdict["complete"]:
        lines.append("VERDICT: every criterion in this phase is satisfied.")
    else:
        missing = [c["id"] for c in verdict["criteria"] if c["status"] != PASS]
        lines.append(f"VERDICT: unsatisfied — {', '.join(missing)}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", default=".")
    parser.add_argument("--phase", choices=[PHASE_BASELINE, PHASE_ATTEMPT, PHASE_HOLDOUT], default=PHASE_ATTEMPT)
    parser.add_argument("--json", action="store_true", help="print the verdict as JSON")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    try:
        verdict = score_tree(root, args.phase)
    except ContractError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3

    write_verdict(root, verdict)
    if args.json:
        print(json.dumps(verdict, indent=2, ensure_ascii=False))
    elif not args.quiet:
        print(render(verdict))

    if verdict["crashed"]:
        return 2
    return 0 if verdict["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
