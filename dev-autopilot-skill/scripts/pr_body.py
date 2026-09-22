#!/usr/bin/env python3
"""Write the PR description as an evidence trail, not a summary.

A PR opened by an agent asks a human for something specific: trust. The way to
earn it is not a tidier summary of the diff — the reviewer can read the diff.
It is to show the work: which gates ran, what they observed, what the review
found, and — most importantly — what is still uncertain.

So this deliberately publishes the unflattering parts. Warnings appear.
Waived findings appear with their reasons. A change that reached PR-ready with
a suppression already in the tree says so. An agent that hides its soft spots
teaches reviewers to stop reading its PRs, and then the loop has automated
nothing.

Usage:
    python3 pr_body.py --root . --output .dev-autopilot/PR.md
    python3 pr_body.py --root . --verdict verdict.json --stdout
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import dev_state  # noqa: E402
import verify_gates  # noqa: E402

STATE_DIR = ".dev-autopilot"

STATUS_MARK = {"pass": "✅", "fail": "❌", "skip": "⚠️"}

KIND_TITLE = {
    "feature": "feat",
    "bugfix": "fix",
    "refactor": "refactor",
    "chore": "chore",
}


#: Leading verbs that would read as a stutter after the conventional prefix
#: ("fix: fix the login redirect").
REDUNDANT_LEADS = {
    "fix": ("fix", "fixes", "fixed", "fixing"),
    "feat": ("add", "adds", "added", "adding", "implement", "implements", "implementing"),
    "refactor": ("refactor", "refactors", "refactoring"),
    "chore": ("bump", "bumps", "update", "updates", "updating"),
}


def title_for(state: dict[str, Any]) -> str:
    """Conventional-commit style title from the intent."""
    prefix = KIND_TITLE.get(state.get("kind", "feature"), "feat")
    intent = (state.get("intent") or "change").strip().rstrip(".")
    if intent and intent[0].isupper() and not intent.isupper():
        intent = intent[0].lower() + intent[1:]

    words = intent.split()
    if words and words[0].lower() in REDUNDANT_LEADS.get(prefix, ()):
        remainder = " ".join(words[1:]).strip()
        if remainder:
            intent = remainder
    return f"{prefix}: {intent}"[:100]


def gate_table(verdict: dict[str, Any]) -> list[str]:
    lines = [
        "| Gate | Result | Evidence |",
        "|---|---|---|",
    ]
    for gate in verdict["gates"]:
        mark = STATUS_MARK.get(gate["status"], "?")
        evidence = gate.get("evidence") or {}
        if gate["status"] == "skip":
            detail = "no observation recorded"
        elif not evidence:
            detail = "—"
        else:
            parts = []
            for key, value in list(evidence.items())[:3]:
                if isinstance(value, (dict, list)):
                    if not value:
                        continue
                    value = f"{len(value)} item(s)"
                parts.append(f"{key}={value}")
            detail = ", ".join(parts) or "—"
        detail = detail.replace("|", "\\|")[:160]
        lines.append(f"| `{gate['id']}` | {mark} | {detail} |")
    return lines


def review_section(review: dict[str, Any] | None) -> list[str]:
    if not review:
        return ["_No review record._"]
    lines: list[str] = []
    by_sev = review.get("by_severity", {})
    lines.append(
        f"Reviewer: `{review.get('reviewer') or 'unknown'}` — "
        f"{review.get('total_findings', 0)} finding(s) "
        f"(high {by_sev.get('high', 0)}, medium {by_sev.get('medium', 0)}, "
        f"low {by_sev.get('low', 0)}); "
        f"credible: {'yes' if review.get('credible') else 'no'}."
    )
    findings = review.get("findings") or []
    if findings:
        lines.append("")
        for finding in sorted(
            findings, key=lambda f: ({"high": 0, "medium": 1, "low": 2}.get(f["severity"], 3), f["file"])
        ):
            status = ""
            if finding.get("waived"):
                status = f" _(waived: {finding.get('waiver_reason') or 'no reason given'})_"
            elif finding.get("resolved"):
                status = " _(resolved)_"
            location = f"`{finding['file']}`"
            if finding.get("line"):
                location += f":{finding['line']}"
            lines.append(
                f"- **{finding['severity']}** {location} — {finding.get('title') or ''}{status}"
            )
            why = (finding.get("why") or "").strip()
            if why:
                lines.append(f"  - {why}")
    return lines


def build_body(
    state: dict[str, Any],
    verdict: dict[str, Any],
    review: dict[str, Any] | None,
    run: dict[str, Any],
) -> str:
    diff = run.get("diff") or {}
    totals = diff.get("totals", {})
    risk = diff.get("risk", {})
    checks = run.get("checks", {})

    lines: list[str] = []
    lines.append("## What changed and why")
    lines.append("")
    lines.append(state.get("intent") or "_No intent recorded._")
    if state.get("ticket"):
        lines.append("")
        lines.append(f"Ticket: {state['ticket']}")
    lines.append("")
    # Prefer the ref name the user asked for; the resolved merge base is a raw
    # SHA, which tells a reviewer nothing about what this branched from.
    base_label = diff.get("base_requested") or diff.get("base") or "unknown"
    lines.append(
        f"`{totals.get('files', 0)}` files, `+{totals.get('added', 0)}/-{totals.get('deleted', 0)}` "
        f"lines against `{base_label}`. Risk: **{risk.get('level', 'unknown')}**"
        + (f" ({', '.join(risk.get('tags', []))})" if risk.get("tags") else "")
        + "."
    )

    lines.append("")
    lines.append("## Verification")
    lines.append("")
    lines.append(
        f"Verdict: **{verdict['verdict']}** — "
        f"{verdict['summary']['required_passed']}/{verdict['summary']['required_total']} "
        "required gates passed with evidence."
    )
    lines.append("")
    lines.extend(gate_table(verdict))

    tests = checks.get("tests") or {}
    if tests.get("ran"):
        lines.append("")
        counts = ""
        if tests.get("passed") is not None:
            counts = (
                f" — {tests.get('passed')} passed, {tests.get('failed')} failed, "
                f"{tests.get('skipped')} skipped"
            )
        lines.append(
            f"Suite: `{tests.get('command')}` exited `{tests.get('exit_code')}`{counts}."
        )

    red_green = checks.get("red-green") or {}
    if red_green.get("ran"):
        lines.append("")
        lines.append(
            f"**Red-green proof** — `{red_green.get('test')}` exited "
            f"`{red_green.get('before_exit')}` against the unfixed code and "
            f"`{red_green.get('after_exit')}` after the fix. The bug is reproduced by a "
            "test, so a regression will be caught."
        )

    lines.append("")
    lines.append("## Review")
    lines.append("")
    lines.extend(review_section(review))

    if verdict.get("warnings"):
        lines.append("")
        lines.append("## Known soft spots")
        lines.append("")
        lines.append("_Not blockers, but worth a reviewer's eye:_")
        lines.append("")
        for warning in verdict["warnings"]:
            lines.append(f"- ({warning['gate']}) {warning['message']}")

    if verdict.get("missing_evidence"):
        lines.append("")
        lines.append("## Unverified")
        lines.append("")
        for miss in verdict["missing_evidence"]:
            lines.append(f"- ({miss['gate']}) {miss['message']}")

    lines.append("")
    lines.append("## What a reviewer should look at")
    lines.append("")
    focus_points: list[str] = []
    for tag in risk.get("tags", []):
        evidence = risk.get("evidence", {}).get(tag, [])
        if evidence:
            focus_points.append(
                f"- **{tag}** — {', '.join(f'`{p}`' for p in evidence[:3])}"
            )
    if not totals.get("test_files"):
        focus_points.append("- No test files changed; confirm the behaviour is genuinely covered.")
    if not focus_points:
        focus_points.append(
            "- Nothing high-risk was touched. The usual: does it do what the intent says?"
        )
    lines.extend(focus_points)

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(
        "_Generated by `/dev-autopilot-skill`. Every gate above reads a recorded "
        "observation — a command's real exit code, a parsed diff — not an assertion by "
        "the agent that wrote the change. Logs are under `.dev-autopilot/logs/`._"
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", default=None)
    parser.add_argument("--verdict", default=None, help="Reuse a verdict JSON")
    parser.add_argument("--stdout", action="store_true")
    parser.add_argument("--title-only", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    state = dev_state.load_state(root)
    if not state:
        print("no run in progress; nothing to describe", file=sys.stderr)
        return 2

    run = dev_state.build_run_record(root, state)
    if args.verdict:
        verdict = json.loads(Path(args.verdict).read_text(encoding="utf-8"))
    else:
        verdict = verify_gates.evaluate(run)

    if args.title_only:
        print(title_for(state))
        return 0

    review = dev_state.load_review(root)
    body = build_body(state, verdict, review, run)

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(body, encoding="utf-8")
        print(f"PR body written to {out}")
        print(f"title: {title_for(state)}")
    if args.stdout or not args.output:
        print(body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
