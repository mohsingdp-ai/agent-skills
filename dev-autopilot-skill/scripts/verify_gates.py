#!/usr/bin/env python3
"""Decide whether a change is PR-ready, from evidence rather than opinion.

This is the file that makes the loop autonomous rather than merely automated.

An agent that wrote a change is the worst possible judge of it: it already
believes the code is correct, because it wrote what it believed. So the verdict
here is never derived from anything the agent *says*. Every gate is a pure
function of a machine-produced observation — a diff, an exit code, a parsed
test count, an audited review record — and a gate that has no observation to
read does not pass. It reports ``skip``, and a skipped required gate makes
``pr_ready`` unreachable.

That is the single rule the whole design rests on:

    A gate is green only when something ran and left evidence.
    Silence is never success.

The practical consequence is that an agent cannot reach ``pr_ready`` by
asserting things went well. It has to actually run the suite, actually collect
the review, and actually record the outcome — because the only path to a green
verdict is through observations it cannot fabricate without lying in a file
that a human can diff.

Usage:
    python3 verify_gates.py --run run.json --output verdict.json
    python3 verify_gates.py --run run.json --max-new-suppression 2 --json
"""

from __future__ import annotations

import argparse
import json
import sys
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Callable

SCHEMA_VERSION = "1.0"

#: Verdicts, worst first. The final verdict is the worst one any gate produces.
VERDICT_BLOCKED = "blocked"
VERDICT_NEEDS_EVIDENCE = "needs_evidence"
VERDICT_PR_READY = "pr_ready"

#: Kinds of work. ``bugfix`` carries an extra, non-negotiable gate.
KINDS = ("feature", "bugfix", "refactor", "chore")

DEFAULTS = {
    "max_new_suppression": 0,
    "max_suppression_ratio": 0.20,
    "large_diff_lines": 400,
    "require_review": True,
    "require_scope": False,
}


class Gate:
    """One check, its evidence, and what it means when absent.

    ``required`` gates gate the verdict: failing one blocks, and *skipping*
    one — meaning nothing was observed — downgrades the verdict to
    ``needs_evidence``. Non-required gates only ever contribute warnings.
    """

    def __init__(
        self,
        gate_id: str,
        title: str,
        required: bool,
        fn: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]],
    ) -> None:
        self.id = gate_id
        self.title = title
        self.required = required
        self.fn = fn

    def run(self, run: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
        result = self.fn(run, cfg)
        result.setdefault("evidence", {})
        return {
            "id": self.id,
            "title": self.title,
            "required": self.required,
            "status": result["status"],
            "evidence": result["evidence"],
            "finding": result.get("finding"),
        }


def _skip(reason: str, fix: str) -> dict[str, Any]:
    """No observation available. Never green, never a hard failure."""
    return {
        "status": "skip",
        "evidence": {},
        "finding": {
            "code": "no_evidence",
            "severity": "blocker",
            "message": reason,
            "fix": fix,
        },
    }


def _fail(code: str, message: str, fix: str, evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "fail",
        "evidence": evidence,
        "finding": {
            "code": code,
            "severity": "blocker",
            "message": message,
            "fix": fix,
        },
    }


def _pass(evidence: dict[str, Any], note: dict[str, Any] | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"status": "pass", "evidence": evidence}
    if note:
        out["finding"] = note
    return out


# --------------------------------------------------------------------------
# Gates
# --------------------------------------------------------------------------

def gate_diff_present(run: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    """There is a change at all, and we could read it."""
    diff = run.get("diff")
    if not isinstance(diff, dict) or "totals" not in diff:
        return _skip(
            "No diff report was collected, so nothing about this change is known.",
            "Run: python3 scripts/diff_intel.py --root . --output .dev-autopilot/diff.json",
        )
    if diff.get("error"):
        return _fail(
            "diff_unreadable",
            f"The diff could not be read: {diff['error']}",
            "Fix the git state (valid base ref, inside a repo) and re-run diff_intel.py.",
            {"error": diff["error"]},
        )
    totals = diff["totals"]
    if totals.get("files", 0) == 0:
        return _fail(
            "empty_diff",
            "The change is empty — no files differ from the base ref.",
            "Implement the change, or if work is committed elsewhere, pass the correct --base.",
            {"base": diff.get("base"), "files": 0},
        )
    return _pass(
        {
            "base": diff.get("base"),
            "branch": diff.get("branch"),
            "files": totals.get("files"),
            "added": totals.get("added"),
            "deleted": totals.get("deleted"),
        }
    )


def gate_focus(run: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    """No focus markers added.

    ``.only`` / ``fit`` / ``fdescribe`` are the nastiest marker in autonomous
    work: the suite exits 0 while running a handful of tests, so every
    downstream gate reads green off a run that proved nothing. Count is
    irrelevant — one is a blocker.
    """
    diff = run.get("diff") or {}
    focus = diff.get("focus")
    if focus is None:
        return _skip(
            "Focus-marker census missing, so a silently narrowed test run cannot be ruled out.",
            "Run diff_intel.py to produce the focus census.",
        )
    sites = focus.get("sites", [])
    if sites:
        where = ", ".join(f"{s['path']}:{s['line']}" for s in sites[:5])
        return _fail(
            "focus_marker_added",
            (
                f"{len(sites)} focus marker(s) added ({where}). A focused suite exits 0 "
                "while running only the focused tests, so every green signal downstream "
                "of it is meaningless."
            ),
            "Remove every .only / fit / fdescribe marker, then re-run the suite.",
            {"count": len(sites), "sites": sites[:20]},
        )
    return _pass({"count": 0, "scanned_added_lines": diff.get("totals", {}).get("added", 0)})


def gate_suppression(run: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    """The change did not buy green by switching tests off."""
    diff = run.get("diff") or {}
    suppression = diff.get("suppression")
    if suppression is None:
        return _skip(
            "Suppression census missing, so newly disabled tests cannot be ruled out.",
            "Run diff_intel.py to produce the suppression census.",
        )
    added = suppression.get("added", 0)
    budget = cfg["max_new_suppression"]
    sites = suppression.get("sites", [])
    evidence: dict[str, Any] = {
        "added": added,
        "budget": budget,
        "by_kind": suppression.get("by_kind", {}),
        "sites": sites[:20],
    }

    census = diff.get("tree_census") or {}
    scanned = census.get("scanned") or 0
    if scanned:
        ratio = census.get("suppressed", 0) / max(scanned, 1)
        evidence["tree_ratio"] = round(ratio, 4)
        evidence["tree_scanned"] = scanned

    if added > budget:
        where = ", ".join(f"{s['path']}:{s['line']} ({s['kind']})" for s in sites[:5])
        return _fail(
            "suppression_over_budget",
            (
                f"This change adds {added} test-suppression marker(s), budget is {budget} "
                f"({where}). Disabling a test converts a red suite into a green one "
                "without fixing anything, and nobody re-reads a green suite."
            ),
            (
                "Fix or delete the underlying test instead of skipping it. If a skip is "
                "genuinely correct, raise the budget deliberately with "
                "--max-new-suppression N and say why in the PR body."
            ),
            evidence,
        )

    note = None
    if evidence.get("tree_ratio", 0) > cfg["max_suppression_ratio"]:
        note = {
            "code": "suppression_ratio_high",
            "severity": "warning",
            "message": (
                f"{evidence['tree_ratio']:.0%} of test files in the repository already "
                "contain suppression markers. This change did not add to it, but the "
                "suite's green signal is weaker than it appears."
            ),
            "fix": "Schedule a pass to re-enable or delete long-skipped tests.",
        }
    return _pass(evidence, note)


def _test_record(run: dict[str, Any]) -> dict[str, Any] | None:
    checks = run.get("checks") or {}
    record = checks.get("tests")
    return record if isinstance(record, dict) and record.get("ran") else None


def gate_tests_pass(run: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    """The suite actually ran, and it was green."""
    record = _test_record(run)
    if record is None:
        return _skip(
            "No test run was recorded, so the change is unverified.",
            (
                "Run the project's suite and record it: "
                "python3 scripts/record_check.py --check tests --command '<test cmd>'"
            ),
        )
    exit_code = record.get("exit_code")
    evidence = {
        "command": record.get("command"),
        "exit_code": exit_code,
        "passed": record.get("passed"),
        "failed": record.get("failed"),
        "skipped": record.get("skipped"),
        "duration_s": record.get("duration_s"),
    }
    harness_error = record.get("harness_error")
    if harness_error:
        return _fail(
            "test_harness_error",
            (
                f"The test command did not actually run tests: {harness_error}. Its exit "
                "code describes the harness, not the code under test, so it is not "
                "evidence either way."
            ),
            "Fix the test command (install the runner, correct the path) and re-record.",
            {**evidence, "harness_error": harness_error},
        )
    if exit_code is None:
        return _skip(
            "A test run was claimed but carries no exit code, so its outcome is unknown.",
            "Re-run the suite through record_check.py so the exit code is captured.",
        )
    if exit_code != 0:
        return _fail(
            "tests_failing",
            (
                f"The test suite exited {exit_code} "
                f"({record.get('failed') or 'unknown'} failing). A change with a red "
                "suite is not PR-ready regardless of how correct it looks."
            ),
            "Fix the failing tests — do not skip them; the suppression gate will catch that.",
            evidence,
        )
    if (record.get("passed") or 0) == 0 and record.get("passed") is not None:
        return _fail(
            "tests_vacuous",
            (
                "The suite exited 0 but reported zero passing tests. An empty run is "
                "not evidence of anything — this is what a mis-scoped selector or a "
                "collection error looks like."
            ),
            "Check the test command's path/pattern arguments actually select tests.",
            evidence,
        )
    return _pass(evidence)


def gate_red_green(run: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    """For a bug fix: prove a test failed before the fix and passes after.

    This is the gate people skip, and it is the reason "fixed" bugs come back.
    A passing suite after a fix proves nothing on its own — the suite passed
    before the fix too, which is precisely why the bug shipped. The only proof
    that a fix addresses the reported bug is a test that fails without it.
    """
    if run.get("kind") != "bugfix":
        return _pass({"applicable": False, "kind": run.get("kind")})

    checks = run.get("checks") or {}
    # Accept both spellings: the CLI flag is `--check red-green`, so that is the
    # key on disk, but `red_green` is the natural spelling in hand-written
    # fixtures and was the original key. Reading only one silently loses the proof.
    record = checks.get("red-green") or checks.get("red_green")
    if not isinstance(record, dict) or not record.get("ran"):
        return _skip(
            (
                "This is a bug fix with no red-green proof. A suite that is green after "
                "the fix is not evidence: it was green before the fix as well, which is "
                "how the bug reached production."
            ),
            (
                "Write a regression test that reproduces the bug, confirm it FAILS "
                "against the unfixed code, then apply the fix and confirm it passes: "
                "python3 scripts/record_check.py --check red-green --test '<test id>' "
                "--before-exit 1 --after-exit 0"
            ),
        )
    before = record.get("before_exit")
    after = record.get("after_exit")
    evidence = {
        "test": record.get("test"),
        "before_exit": before,
        "after_exit": after,
        "command": record.get("command"),
    }
    # Checked before completeness so a broken command is reported the moment it
    # is recorded, rather than after the agent has gone and recorded the second
    # phase against the same broken command.
    #
    # A broken command exits non-zero too. Treating that as "the test failed"
    # would let a typo stand in for the entire proof.
    for phase in ("before", "after"):
        harness_error = record.get(f"{phase}_harness_error")
        if harness_error:
            return _fail(
                "red_green_harness_error",
                (
                    f"The '{phase}' run did not execute the test: {harness_error}. A "
                    "non-zero exit from a command that never ran a test is not a red "
                    "phase, so there is no proof the bug was ever reproduced."
                ),
                f"Fix the command so it actually runs '{record.get('test')}', then re-record both phases.",
                {**evidence, f"{phase}_harness_error": harness_error},
            )

    if before is None or after is None:
        return _skip(
            "Red-green proof is incomplete — one of the two runs has no exit code.",
            "Record both the pre-fix (red) and post-fix (green) run.",
        )

    if before == 0:
        return _fail(
            "regression_test_not_red",
            (
                f"The regression test '{record.get('test')}' already passed against the "
                "unfixed code. It does not reproduce the bug, so it cannot prove the fix "
                "and will not catch the bug if it returns."
            ),
            "Rewrite the test so it fails against the unfixed code, then re-verify.",
            evidence,
        )
    if after != 0:
        return _fail(
            "regression_test_still_red",
            f"The regression test still fails after the fix (exit {after}). The bug is not fixed.",
            "Keep working: the test that reproduces the bug must pass.",
            evidence,
        )
    return _pass(evidence)


def gate_changed_code_tested(run: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    """Source moved, so tests should have moved too."""
    diff = run.get("diff") or {}
    totals = diff.get("totals")
    if totals is None:
        return _skip(
            "No diff report, so test co-movement is unknown.",
            "Run diff_intel.py.",
        )
    source_files = totals.get("source_files", 0)
    test_files = totals.get("test_files", 0)
    evidence = {"source_files": source_files, "test_files": test_files}
    if source_files and not test_files:
        docs_only = all(
            f["lang"] in ("markdown", "yaml", "json", "toml")
            for f in diff.get("files", [])
            if not f.get("is_test")
        )
        if docs_only:
            return _pass({**evidence, "reason": "non-code change"})
        return _fail(
            "no_tests_changed",
            (
                f"{source_files} source file(s) changed and no test file did. Either the "
                "new behaviour is untested, or an existing test should have needed "
                "updating and did not — both mean the suite is not watching this change."
            ),
            (
                "Add or update tests covering the changed behaviour. If the change is "
                "genuinely untestable (pure config, generated code), record it as "
                "kind=chore and say so in the PR body."
            ),
            evidence,
        )
    return _pass(evidence)


def gate_scope(run: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    """The change stayed inside the scope the plan declared.

    Scope drift is how a small approved change quietly becomes a large
    unreviewed one. Only enforced when a scope was actually declared.
    """
    scope = run.get("scope")
    diff = run.get("diff") or {}
    files = diff.get("files")
    if files is None:
        return _skip("No diff report, so scope cannot be checked.", "Run diff_intel.py.")
    if not scope:
        if cfg["require_scope"]:
            return _skip(
                "No scope was declared but scope enforcement is on.",
                "Declare the intended paths in the run record's 'scope' list.",
            )
        return _pass({"declared": False, "files": len(files)})

    patterns = list(scope)
    outside = [
        f["path"]
        for f in files
        if not any(fnmatch(f["path"], pat) for pat in patterns)
    ]
    evidence = {"declared": True, "patterns": patterns, "outside": sorted(outside)[:20]}
    if outside:
        return _fail(
            "scope_drift",
            (
                f"{len(outside)} file(s) changed outside the declared scope "
                f"({', '.join(sorted(outside)[:5])}). The plan a reviewer approved no "
                "longer describes the change in front of them."
            ),
            (
                "Revert the out-of-scope edits, or widen the declared scope deliberately "
                "and re-state the plan."
            ),
            evidence,
        )
    return _pass(evidence)


def gate_review(run: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    """A deep review ran, was credible, and left nothing unresolved.

    The audit that decides credibility lives in review_pack.py; this gate only
    reads its verdict. A review that found nothing on a large, risky diff is
    treated as *no review at all*, because that is the most common way
    self-review fails: the author-agent confirms its own work.
    """
    if not cfg["require_review"]:
        return _pass({"required": False})
    review = run.get("review")
    if not isinstance(review, dict) or not review.get("audited"):
        return _skip(
            "No audited review record, so the change has never been read critically.",
            (
                "Build the pack, run the review, then audit it: "
                "python3 scripts/review_pack.py build --output .dev-autopilot/pack.json "
                "&& python3 scripts/review_pack.py audit --findings <findings.json>"
            ),
        )
    evidence = {
        "credible": review.get("credible"),
        "findings": review.get("total_findings"),
        "by_severity": review.get("by_severity", {}),
        "unresolved_high": review.get("unresolved_high", []),
        "reviewer": review.get("reviewer"),
    }
    if not review.get("credible", False):
        return _fail(
            "review_not_credible",
            review.get("reason")
            or "The review did not meet the credibility bar for a change this size or risk.",
            "Re-run the review with fresh context against the full pack, then re-audit.",
            evidence,
        )
    unresolved = review.get("unresolved_high") or []
    if unresolved:
        titles = ", ".join(str(u.get("title", u)) for u in unresolved[:3])
        return _fail(
            "unresolved_high_findings",
            f"{len(unresolved)} high-severity review finding(s) are unresolved ({titles}).",
            "Fix each high finding, or waive it explicitly with a written reason.",
            evidence,
        )
    return _pass(evidence)


def gate_static(run: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    """Lint and type checks, when the project has them."""
    checks = run.get("checks") or {}
    results = {
        name: checks.get(name)
        for name in ("lint", "typecheck", "build")
        if isinstance(checks.get(name), dict) and checks[name].get("ran")
    }
    if not results:
        return _skip(
            "No lint / typecheck / build run was recorded.",
            (
                "Record whichever the project has: python3 scripts/record_check.py "
                "--check lint --command '<cmd>'. If the project has none, record "
                "--check lint --none to say so explicitly."
            ),
        )
    failed = {n: r for n, r in results.items() if r.get("exit_code") not in (0, None)}
    # Flat strings rather than nested dicts: this evidence is rendered into a
    # PR table, where a nested object collapses to a useless "2 item(s)".
    evidence = {
        name: (
            f"declared absent ({record.get('reason')})"
            if record.get("kind") == "declared-absent"
            else f"`{record.get('command')}` exit {record.get('exit_code')}"
        )
        for name, record in results.items()
    }
    if failed:
        names = ", ".join(sorted(failed))
        return _fail(
            "static_checks_failing",
            f"Static checks failing: {names}.",
            "Fix the reported errors; do not disable the rule to silence them.",
            evidence,
        )
    return _pass(evidence)


GATES: tuple[Gate, ...] = (
    Gate("diff-present", "A readable, non-empty change exists", True, gate_diff_present),
    Gate("focus-guard", "No focus markers narrow the suite", True, gate_focus),
    Gate("suppression-budget", "No tests were disabled to reach green", True, gate_suppression),
    Gate("tests-pass", "The suite ran and passed", True, gate_tests_pass),
    Gate("red-green-proof", "A bug fix is proven by a test that was red", True, gate_red_green),
    Gate("changed-code-tested", "Tests moved with the source", True, gate_changed_code_tested),
    Gate("static-checks", "Lint / types / build are clean", False, gate_static),
    Gate("scope", "The change stayed inside its declared scope", False, gate_scope),
    Gate("review-credible", "A credible deep review found nothing unresolved", True, gate_review),
)


def evaluate(run: dict[str, Any], cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run every gate over a run record and return the verdict."""
    config = {**DEFAULTS, **(cfg or {})}
    kind = run.get("kind") or "feature"
    if kind not in KINDS:
        kind = "feature"

    results = [gate.run(run, config) for gate in GATES]

    blockers: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    for result in results:
        finding = result.get("finding")
        if not finding:
            continue
        entry = {"gate": result["id"], **finding}
        if result["status"] == "fail":
            blockers.append(entry)
        elif result["status"] == "skip" and result["required"]:
            missing.append(entry)
        elif finding.get("severity") == "warning":
            warnings.append(entry)

    blockers.sort(key=lambda f: (f["code"], f["gate"]))
    missing.sort(key=lambda f: (f["code"], f["gate"]))
    warnings.sort(key=lambda f: (f["code"], f["gate"]))

    if blockers:
        verdict = VERDICT_BLOCKED
    elif missing:
        verdict = VERDICT_NEEDS_EVIDENCE
    else:
        verdict = VERDICT_PR_READY

    required = [r for r in results if r["required"]]
    return {
        "schema_version": SCHEMA_VERSION,
        "verdict": verdict,
        "kind": kind,
        "intent": run.get("intent"),
        "pr_ready": verdict == VERDICT_PR_READY,
        "evidence_complete": not missing,
        "summary": {
            "gates_total": len(results),
            "passed": sum(1 for r in results if r["status"] == "pass"),
            "failed": sum(1 for r in results if r["status"] == "fail"),
            "skipped": sum(1 for r in results if r["status"] == "skip"),
            "required_total": len(required),
            "required_passed": sum(1 for r in required if r["status"] == "pass"),
        },
        "gates": results,
        "blockers": blockers,
        "missing_evidence": missing,
        "warnings": warnings,
        "config": config,
    }


def render_text(verdict: dict[str, Any]) -> str:
    """Human-readable summary for a terminal."""
    icons = {"pass": "PASS", "fail": "FAIL", "skip": "MISS"}
    lines = [
        f"verdict: {verdict['verdict'].upper()}  ({verdict['kind']})",
        "",
    ]
    for gate in verdict["gates"]:
        mark = icons.get(gate["status"], "?")
        req = "*" if gate["required"] else " "
        lines.append(f"  [{mark}]{req} {gate['id']:<22} {gate['title']}")
    if verdict["blockers"]:
        lines.append("")
        lines.append("BLOCKERS")
        for blocker in verdict["blockers"]:
            lines.append(f"  - ({blocker['gate']}) {blocker['message']}")
            lines.append(f"    fix: {blocker['fix']}")
    if verdict["missing_evidence"]:
        lines.append("")
        lines.append("MISSING EVIDENCE  (a gate cannot pass on silence)")
        for miss in verdict["missing_evidence"]:
            lines.append(f"  - ({miss['gate']}) {miss['message']}")
            lines.append(f"    fix: {miss['fix']}")
    if verdict["warnings"]:
        lines.append("")
        lines.append("WARNINGS")
        for warn in verdict["warnings"]:
            lines.append(f"  - ({warn['gate']}) {warn['message']}")
    lines.append("")
    lines.append("* = required for pr_ready")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--run", required=True, help="Run-record JSON")
    parser.add_argument("--output", default=None, help="Write the verdict JSON here")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of text")
    parser.add_argument("--max-new-suppression", type=int, default=None)
    parser.add_argument("--max-suppression-ratio", type=float, default=None)
    parser.add_argument("--no-review", action="store_true", help="Do not require a review")
    parser.add_argument("--require-scope", action="store_true")
    parser.add_argument(
        "--exit-zero",
        action="store_true",
        help="Always exit 0; the verdict is in the output (for pipelines that parse it)",
    )
    args = parser.parse_args()

    run_path = Path(args.run)
    if not run_path.exists():
        print(f"run record not found: {run_path}", file=sys.stderr)
        return 2
    try:
        run = json.loads(run_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"run record is not valid JSON: {exc}", file=sys.stderr)
        return 2

    cfg: dict[str, Any] = {}
    if args.max_new_suppression is not None:
        cfg["max_new_suppression"] = args.max_new_suppression
    if args.max_suppression_ratio is not None:
        cfg["max_suppression_ratio"] = args.max_suppression_ratio
    if args.no_review:
        cfg["require_review"] = False
    if args.require_scope:
        cfg["require_scope"] = True

    verdict = evaluate(run, cfg)
    text = json.dumps(verdict, indent=2)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    if args.json or not args.output:
        print(text)
    else:
        print(render_text(verdict))

    if args.exit_zero:
        return 0
    return {VERDICT_PR_READY: 0, VERDICT_NEEDS_EVIDENCE: 3}.get(verdict["verdict"], 1)


if __name__ == "__main__":
    sys.exit(main())
