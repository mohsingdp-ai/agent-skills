#!/usr/bin/env python3
"""Assemble the deep-review context pack, then audit the review it produced.

Two subcommands, two halves of the same problem.

``build`` does what a human reviewer does before reading a line of code: pull
the diff, the files it touches, the repository's own conventions
(``AGENTS.md``, ``CLAUDE.md``, ``.augment/rules/*.md``, ``.cursor/rules/*``),
and any prior review notes so the same feedback is not given twice. The pack is
one JSON document the reviewer reads instead of going fishing for context
mid-review.

``audit`` is the half that matters for autonomy. When an agent reviews a change
it wrote itself, the likeliest outcome is not a bad finding — it is *no*
finding. The agent already concluded the code was correct when it wrote it, and
re-reading its own reasoning reproduces the same conclusion. A review that says
"looks good" is indistinguishable, in a JSON file, from a review that never
happened.

So the audit refuses to take "clean" at face value. On a large or high-risk
diff, a review with no findings must carry a per-dimension attestation naming
what was examined; findings must cite files that are actually in the diff; and
every required review dimension must be accounted for. A review that fails the
audit is reported as not credible, and ``verify_gates.py`` treats that exactly
like no review at all.

Usage:
    python3 review_pack.py build --root . --diff .dev-autopilot/diff.json \\
        --output .dev-autopilot/pack.json
    python3 review_pack.py audit --pack .dev-autopilot/pack.json \\
        --findings review.json --output .dev-autopilot/review.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import diff_intel  # noqa: E402

SCHEMA_VERSION = "1.0"

#: The dimensions a deep review must account for. Style nitpicks are
#: deliberately absent: when substantive bugs exist, style noise buries them.
REQUIRED_DIMENSIONS = (
    "correctness",
    "security",
    "data-safety",
    "error-handling",
    "intent-fidelity",
)

DIMENSION_PROMPTS = {
    "correctness": "Logic errors, off-by-one, wrong operator, inverted condition, "
                   "unhandled branch, incorrect state transition.",
    "security": "Injection, authz/authn gaps, secrets in code, unsafe deserialization, "
                "SSRF, path traversal, missing input validation on a trust boundary.",
    "data-safety": "Destructive or irreversible operations, migrations without a back-out, "
                   "race conditions, lost updates, unbounded queries, N+1, missing transaction.",
    "error-handling": "Swallowed exceptions, unchecked returns, partial failure leaving "
                      "inconsistent state, missing timeout/retry, error paths that never run.",
    "intent-fidelity": "Does the change actually do what the intent or ticket asked, "
                       "no more and no less?",
}

#: Files whose content is the repository's own review policy.
CONVENTION_SOURCES = (
    "AGENTS.md",
    "CLAUDE.md",
    "CONTRIBUTING.md",
    "CONVENTIONS.md",
    ".augment/rules",
    ".cursor/rules",
    ".github/copilot-instructions.md",
    ".windsurf/rules",
)

SEVERITIES = ("high", "medium", "low")

MAX_FILE_BYTES = 60_000
MAX_CONVENTION_BYTES = 20_000


def read_text(path: Path, limit: int) -> str | None:
    """Read a text file, truncating at ``limit`` bytes."""
    try:
        data = path.read_bytes()
    except (OSError, ValueError):
        return None
    truncated = len(data) > limit
    text = data[:limit].decode("utf-8", errors="replace")
    if truncated:
        text += f"\n\n... [truncated at {limit} bytes]"
    return text


def gather_conventions(root: Path) -> list[dict[str, Any]]:
    """Collect the repository's own review rules.

    A reviewer that does not know the house style reports the house style as a
    defect, which is noise, and misses the rules that actually matter.
    """
    found: list[dict[str, Any]] = []
    for source in CONVENTION_SOURCES:
        target = root / source
        if target.is_file():
            content = read_text(target, MAX_CONVENTION_BYTES)
            if content:
                found.append({"path": source, "content": content})
        elif target.is_dir():
            for child in sorted(target.rglob("*.md"))[:12]:
                content = read_text(child, MAX_CONVENTION_BYTES)
                if content:
                    found.append(
                        {"path": str(child.relative_to(root)), "content": content}
                    )
    return found


def gather_prior_notes(root: Path) -> list[dict[str, Any]]:
    """Load previous review records so feedback is not repeated.

    Augment's reviewer scans existing PR comments for the same reason: the
    fastest way to make a reviewer ignorable is to have it say the same thing
    on every push.
    """
    notes_dir = root / ".dev-autopilot" / "reviews"
    if not notes_dir.is_dir():
        return []
    notes: list[dict[str, Any]] = []
    for record in sorted(notes_dir.glob("*.json"))[-10:]:
        try:
            payload = json.loads(record.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for finding in payload.get("findings", [])[:50]:
            notes.append(
                {
                    "source": record.name,
                    "file": finding.get("file"),
                    "line": finding.get("line"),
                    "title": finding.get("title"),
                    "severity": finding.get("severity"),
                }
            )
    return notes


def related_files(root: Path, changed: list[str], limit: int = 25) -> list[dict[str, Any]]:
    """Include the full text of changed source files, plus their siblings.

    A diff alone hides the thing reviews most often miss: the caller that was
    not updated. Sibling files in the same directory are cheap context and
    frequently contain it.
    """
    seen: dict[str, dict[str, Any]] = {}

    for rel in changed:
        path = root / rel
        if not path.is_file():
            continue
        content = read_text(path, MAX_FILE_BYTES)
        if content is not None:
            seen[rel] = {"path": rel, "role": "changed", "content": content}

    if len(seen) < limit:
        directories = {str(Path(rel).parent) for rel in changed}
        for directory in sorted(directories):
            folder = root / directory
            if not folder.is_dir():
                continue
            for sibling in sorted(folder.iterdir()):
                if len(seen) >= limit:
                    break
                if not sibling.is_file():
                    continue
                rel = str(sibling.relative_to(root))
                if rel in seen or sibling.suffix.lower() not in diff_intel.LANGS:
                    continue
                content = read_text(sibling, MAX_FILE_BYTES // 3)
                if content is not None:
                    seen[rel] = {"path": rel, "role": "sibling", "content": content}

    return [seen[key] for key in sorted(seen)]


def build_pack(
    root: Path,
    diff_report: dict[str, Any],
    intent: str | None,
    kind: str,
    ticket: str | None,
) -> dict[str, Any]:
    """Assemble everything a reviewer needs, in one document."""
    changed = [
        f["path"] for f in diff_report.get("files", []) if f.get("status") != "D"
    ]
    risk = diff_report.get("risk", {})
    totals = diff_report.get("totals", {})

    pack: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "intent": intent,
        "kind": kind,
        "ticket": ticket,
        "diff_summary": {
            "base": diff_report.get("base"),
            "branch": diff_report.get("branch"),
            "files": totals.get("files"),
            "added": totals.get("added"),
            "deleted": totals.get("deleted"),
            "risk_level": risk.get("level"),
            "risk_tags": risk.get("tags", []),
            "risk_evidence": risk.get("evidence", {}),
        },
        "changed_files": [
            {
                "path": f["path"],
                "status": f.get("status"),
                "added": f.get("added"),
                "deleted": f.get("deleted"),
                "is_test": f.get("is_test"),
            }
            for f in diff_report.get("files", [])
        ],
        "dimensions": [
            {"id": name, "focus": DIMENSION_PROMPTS[name]} for name in REQUIRED_DIMENSIONS
        ],
        "conventions": gather_conventions(root),
        "prior_notes": gather_prior_notes(root),
        "file_contents": related_files(root, changed),
        "instructions": (
            "Review this change against every dimension listed. Report only "
            "substantive findings: correctness, security, data-safety and concurrency, "
            "error handling, and whether the change does what the intent asked. Skip "
            "style nitpicks entirely when substantive issues exist. Every finding must "
            "cite a file and line from changed_files, state why it matters (the failure "
            "it causes, not the rule it breaks), and carry a severity of high, medium "
            "or low. If you genuinely find nothing, you must still attest per dimension "
            "what you examined and why it is sound — an unexplained clean review is "
            "rejected on a large or high-risk change."
        ),
    }
    pack["digest"] = hashlib.sha256(
        json.dumps(pack["changed_files"], sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]
    return pack


# --------------------------------------------------------------------------
# Audit
# --------------------------------------------------------------------------

LINE_RE = re.compile(r"^\d+$")


def audit_review(
    pack: dict[str, Any],
    review: dict[str, Any],
    large_diff_lines: int = 400,
    min_why_chars: int = 40,
) -> dict[str, Any]:
    """Decide whether a review is credible enough to gate a PR on.

    Credibility is not about whether the findings are correct — nothing here
    can know that. It is about whether the review shows evidence of having
    read the change: real file references, accounted-for dimensions, and a
    justified conclusion when that conclusion is "clean".
    """
    problems: list[dict[str, Any]] = []
    summary = pack.get("diff_summary", {})
    changed_paths = {f["path"] for f in pack.get("changed_files", [])}
    diff_size = (summary.get("added") or 0) + (summary.get("deleted") or 0)
    high_risk = summary.get("risk_level") == "high"
    is_substantial = diff_size >= large_diff_lines or high_risk

    findings = review.get("findings")
    if not isinstance(findings, list):
        findings = []
        problems.append(
            {
                "code": "findings_missing",
                "message": "The review record has no 'findings' list, so it reports nothing at all.",
            }
        )

    # Pack identity — a review of a different diff is not a review of this one.
    if review.get("context_digest") and pack.get("digest"):
        if review["context_digest"] != pack["digest"]:
            problems.append(
                {
                    "code": "stale_context",
                    "message": (
                        f"The review was produced against pack {review['context_digest']}, "
                        f"but the current change is {pack['digest']}. The code moved after "
                        "the review, so the review no longer describes it."
                    ),
                }
            )

    # Dimension coverage.
    covered = review.get("dimensions_covered")
    if not isinstance(covered, list) or not covered:
        problems.append(
            {
                "code": "dimensions_unaccounted",
                "message": (
                    "The review does not say which dimensions it examined, so there is no "
                    "way to tell a thorough review from a glance."
                ),
            }
        )
    else:
        missing = [d for d in REQUIRED_DIMENSIONS if d not in covered]
        if missing:
            problems.append(
                {
                    "code": "dimensions_missing",
                    "message": (
                        f"Dimensions not covered: {', '.join(missing)}. Each is a class of "
                        "defect that survives a review that never looked for it."
                    ),
                }
            )

    # Findings must be well-formed and point into the diff.
    malformed: list[str] = []
    off_diff: list[str] = []
    by_severity: dict[str, int] = {s: 0 for s in SEVERITIES}
    normalized: list[dict[str, Any]] = []

    for index, finding in enumerate(findings):
        if not isinstance(finding, dict):
            malformed.append(f"#{index}: not an object")
            continue
        label = finding.get("title") or f"#{index}"
        severity = str(finding.get("severity", "")).lower()
        if severity not in SEVERITIES:
            malformed.append(f"{label}: severity {finding.get('severity')!r} not high/medium/low")
            continue
        file_ref = finding.get("file")
        if not file_ref:
            malformed.append(f"{label}: no file reference")
            continue
        if changed_paths and file_ref not in changed_paths:
            off_diff.append(f"{label} -> {file_ref}")
        why = str(finding.get("why") or finding.get("rationale") or "")
        if len(why.strip()) < min_why_chars:
            malformed.append(
                f"{label}: 'why' is {len(why.strip())} chars; a finding without a stated "
                "consequence cannot be triaged or fixed"
            )
            continue
        by_severity[severity] += 1
        normalized.append(
            {
                "file": file_ref,
                "line": finding.get("line"),
                "severity": severity,
                "title": finding.get("title"),
                "why": why,
                "suggestion": finding.get("suggestion"),
                "resolved": bool(finding.get("resolved")),
                "waived": bool(finding.get("waived")),
                "waiver_reason": finding.get("waiver_reason"),
            }
        )

    if malformed:
        problems.append(
            {
                "code": "findings_malformed",
                "message": f"{len(malformed)} finding(s) are unusable: " + "; ".join(malformed[:5]),
            }
        )
    if off_diff:
        problems.append(
            {
                "code": "findings_off_diff",
                "message": (
                    f"{len(off_diff)} finding(s) cite files that are not in this change "
                    f"({'; '.join(off_diff[:3])}). A review that points outside the diff "
                    "was not reading the diff."
                ),
            }
        )

    # The rubber-stamp check.
    attestation = str(review.get("clean_attestation") or "").strip()
    if not normalized and is_substantial:
        reason_bits = []
        if diff_size >= large_diff_lines:
            reason_bits.append(f"{diff_size} changed lines")
        if high_risk:
            reason_bits.append(f"high-risk areas ({', '.join(summary.get('risk_tags', []))})")
        if len(attestation) < 200:
            problems.append(
                {
                    "code": "unexplained_clean_review",
                    "message": (
                        f"The review found nothing on a change touching {' and '.join(reason_bits)}, "
                        "and gave no substantive attestation of what it examined. An agent "
                        "reviewing code it wrote itself reaches 'looks correct' by default, so "
                        "an unexplained clean review is treated as no review."
                    ),
                }
            )

    unresolved_high = [
        f for f in normalized
        if f["severity"] == "high" and not f["resolved"] and not f["waived"]
    ]
    waived_without_reason = [
        f for f in normalized if f["waived"] and not (f.get("waiver_reason") or "").strip()
    ]
    if waived_without_reason:
        problems.append(
            {
                "code": "waiver_without_reason",
                "message": (
                    f"{len(waived_without_reason)} finding(s) are waived with no reason. "
                    "A silent waiver is indistinguishable from ignoring the finding."
                ),
            }
        )

    problems.sort(key=lambda p: p["code"])
    credible = not problems

    return {
        "schema_version": SCHEMA_VERSION,
        "audited": True,
        "credible": credible,
        "reason": problems[0]["message"] if problems else None,
        "reviewer": review.get("reviewer"),
        "pack_digest": pack.get("digest"),
        "total_findings": len(normalized),
        "by_severity": by_severity,
        "unresolved_high": [
            {"file": f["file"], "line": f["line"], "title": f["title"]}
            for f in unresolved_high
        ],
        "findings": normalized,
        "problems": problems,
        "diff_size": diff_size,
        "risk_level": summary.get("risk_level"),
    }


def cmd_build(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    if args.diff:
        diff_report = json.loads(Path(args.diff).read_text(encoding="utf-8"))
    else:
        try:
            diff_report = diff_intel.analyze(root, base=args.base)
        except diff_intel.GitError as exc:
            print(f"cannot read the diff: {exc}", file=sys.stderr)
            return 1

    pack = build_pack(root, diff_report, args.intent, args.kind, args.ticket)
    text = json.dumps(pack, indent=2)
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
        print(
            f"pack written to {out}  "
            f"({pack['diff_summary']['files']} files, risk={pack['diff_summary']['risk_level']}, "
            f"digest={pack['digest']})"
        )
    else:
        print(text)
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    pack = json.loads(Path(args.pack).read_text(encoding="utf-8"))
    review = json.loads(Path(args.findings).read_text(encoding="utf-8"))
    result = audit_review(pack, review, large_diff_lines=args.large_diff_lines)

    text = json.dumps(result, indent=2)
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")

    if args.json or not args.output:
        print(text)
    else:
        state = "CREDIBLE" if result["credible"] else "NOT CREDIBLE"
        print(f"review: {state}  ({result['total_findings']} findings)")
        for problem in result["problems"]:
            print(f"  - [{problem['code']}] {problem['message']}")

    if args.exit_zero:
        return 0
    return 0 if result["credible"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="Assemble the reviewer context pack")
    build.add_argument("--root", default=".")
    build.add_argument("--base", default=None)
    build.add_argument("--diff", default=None, help="Reuse a diff_intel.py report")
    build.add_argument("--intent", default=None)
    build.add_argument(
        "--kind", default="feature",
        choices=["feature", "bugfix", "refactor", "chore"],
    )
    build.add_argument("--ticket", default=None)
    build.add_argument("--output", default=None)
    build.set_defaults(func=cmd_build)

    audit = sub.add_parser("audit", help="Judge whether a review is credible")
    audit.add_argument("--pack", required=True)
    audit.add_argument("--findings", required=True, help="The reviewer's output JSON")
    audit.add_argument("--output", default=None)
    audit.add_argument("--large-diff-lines", type=int, default=400)
    audit.add_argument("--json", action="store_true")
    audit.add_argument("--exit-zero", action="store_true")
    audit.set_defaults(func=cmd_audit)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
