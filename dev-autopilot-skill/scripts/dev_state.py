#!/usr/bin/env python3
"""Answer one question: what is the next action?

The agent asks, performs exactly the action it is given, and asks again. It
never plans several steps ahead, because state lives on disk rather than in the
agent's context — so a run that is interrupted, compacted, or resumed tomorrow
picks up precisely where it stopped instead of restarting or, worse, redoing
work it cannot remember doing.

The split of labour follows what each side can actually do. Python owns
sequencing, gates and evidence, because those must be identical on every run.
The agent owns the four things that need judgement — writing the plan, writing
the regression test, implementing, and reviewing — because no script can do
them. Every handoff carries the full payload the agent needs, so the agent
never has to reconstruct context to act.

Actions:
    fix_preflight           environment problems; each finding carries its fix
    plan                    write the plan / spec for this change
    write_regression_test   bug fixes only: a test that fails against today's code
    implement               write the code
    collect_evidence        run the recorded checks (deterministic; pipeline does it)
    review                  run the deep review against the built pack
    fix_blockers            gates failed; fix each and re-enter
    open_pr                 everything green — generate the PR body and open it
    done                    finished
    blocked                 escalate; do not improvise

Usage:
    python3 dev_state.py next --root . --json
    python3 dev_state.py start --root . --intent "fix login redirect" --kind bugfix
    python3 dev_state.py mark --root . --plan-written
    python3 dev_state.py status --root .
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import dev_preflight  # noqa: E402
import diff_intel  # noqa: E402
import record_check  # noqa: E402
import verify_gates  # noqa: E402

SCHEMA_VERSION = "1.0"
STATE_DIR = ".dev-autopilot"

#: Stop rather than spin. Three consecutive identical actions means the agent
#: is not making progress and a human needs to look.
NO_PROGRESS_LIMIT = 3

STOPWORDS = {
    "a", "an", "the", "to", "for", "of", "in", "on", "and", "or", "please",
    "we", "i", "our", "my", "this", "that", "it", "should", "would", "can",
    "make", "let", "us", "need", "needs", "want", "wants", "fix", "add",
}

BUGFIX_HINTS = re.compile(
    r"\b(bug|fix|broken|regression|crash|error|fails?|failing|incorrect|wrong|"
    r"defect|issue|hotfix|patch)\b",
    re.IGNORECASE,
)
REFACTOR_HINTS = re.compile(
    r"\b(refactor|rename|restructure|cleanup|clean up|tidy|extract|inline|"
    r"reorganis|reorganiz|simplify)\b",
    re.IGNORECASE,
)
CHORE_HINTS = re.compile(
    r"\b(bump|upgrade|dependency|dependencies|docs|documentation|readme|"
    r"changelog|lint config|ci config|formatting)\b",
    re.IGNORECASE,
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def slugify(intent: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", intent.lower())
    kept = [w for w in words if w not in STOPWORDS] or words
    slug = "-".join(kept[:6]).strip("-")
    return re.sub(r"-{2,}", "-", slug)[:60] or "change"


def infer_kind(intent: str) -> str:
    """Guess the kind of work from the intent.

    The stakes are asymmetric, so the tie-break is deliberate: calling a
    feature a bugfix costs one extra regression test, while calling a bugfix a
    feature skips the red-green proof entirely. Bug wins ties.
    """
    if BUGFIX_HINTS.search(intent):
        return "bugfix"
    if REFACTOR_HINTS.search(intent):
        return "refactor"
    if CHORE_HINTS.search(intent):
        return "chore"
    return "feature"


def state_path(root: Path) -> Path:
    target = root / STATE_DIR
    target.mkdir(parents=True, exist_ok=True)
    return target / "state.json"


def load_state(root: Path) -> dict[str, Any]:
    path = state_path(root)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_state(root: Path, state: dict[str, Any]) -> None:
    state_path(root).write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def plan_paths(root: Path, state: dict[str, Any]) -> dict[str, Any]:
    """Where the plan lives, which depends on whether OpenSpec is in play."""
    name = state.get("slug") or "change"
    openspec_change = root / "openspec" / "changes" / name
    if (root / "openspec").is_dir():
        return {
            "mode": "openspec",
            "dir": str(openspec_change),
            "exists": openspec_change.is_dir()
            and (openspec_change / "tasks.md").is_file(),
            "primary": str(openspec_change / "proposal.md"),
        }
    local = root / STATE_DIR / "plan.md"
    return {
        "mode": "local",
        "dir": str(root / STATE_DIR),
        "exists": local.is_file() and len(local.read_text(encoding="utf-8").strip()) > 80,
        "primary": str(local),
    }


def load_review(root: Path) -> dict[str, Any] | None:
    path = root / STATE_DIR / "review.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def load_diff(root: Path, base: str | None) -> dict[str, Any]:
    try:
        return diff_intel.analyze(root, base=base)
    except diff_intel.GitError as exc:
        return {"error": str(exc)}


def build_run_record(root: Path, state: dict[str, Any]) -> dict[str, Any]:
    """Assemble everything the gates read, from disk."""
    run = record_check.load_run(root)
    run["intent"] = state.get("intent")
    run["kind"] = state.get("kind", "feature")
    run["scope"] = state.get("scope") or []
    run["diff"] = load_diff(root, state.get("base"))
    review = load_review(root)
    if review:
        run["review"] = review
    return run


def action(name: str, why: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"action": name, "why": why, "payload": payload or {}}


def decide(root: Path, state: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    """The whole state machine, in evaluation order."""
    if not state.get("intent"):
        return action(
            "blocked",
            "No run has been started, so there is no intent to work toward.",
            {"reason": "Run: python3 scripts/dev_state.py start --intent '<what to build or fix>'"},
        )

    # 1. Environment.
    preflight = dev_preflight.run_all(root, state.get("base"))
    if not preflight["ready"]:
        return action(
            "fix_preflight",
            "The environment cannot support an unattended run yet.",
            {
                "findings": [f for f in preflight["findings"] if f["severity"] == "error"],
                "all_findings": preflight["findings"],
            },
        )

    kind = state.get("kind", "feature")
    plan = plan_paths(root, state)

    # 2. Plan before code.
    if not plan["exists"] and not state.get("plan_written"):
        siblings = preflight["siblings"]
        openspec_ready = (
            plan["mode"] == "openspec"
            and siblings.get("openspec-autopilot-skill", {}).get("installed")
        )
        return action(
            "plan",
            "Nothing is written down yet. A change with no plan has nothing to verify "
            "the implementation against, and scope drift becomes undetectable.",
            {
                "intent": state["intent"],
                "kind": kind,
                "slug": state.get("slug"),
                "plan_mode": plan["mode"],
                "write_to": plan["primary"],
                "delegate_to": "openspec-autopilot-skill" if openspec_ready else None,
                "delegate_command": (
                    f"/openspec-autopilot-skill {state['intent']}" if openspec_ready else None
                ),
                "must_contain": [
                    "what changes and why",
                    "the files or modules in scope",
                    "how the change will be verified",
                    "what is explicitly out of scope",
                ],
            },
        )

    diff = load_diff(root, state.get("base"))
    if diff.get("error"):
        return action(
            "blocked",
            "The diff cannot be read, so no gate can run.",
            {"reason": diff["error"]},
        )
    has_changes = diff.get("totals", {}).get("files", 0) > 0
    checks = record_check.load_run(root).get("checks", {})

    # 3. Bug fixes: prove the bug exists before fixing it.
    if kind == "bugfix":
        red_green = checks.get("red-green") or {}
        if red_green.get("before_exit") is None:
            return action(
                "write_regression_test",
                "This is a bug fix and no failing test has been recorded. A suite that is "
                "green after the fix proves nothing — it was green before the fix too, "
                "which is exactly how the bug shipped.",
                {
                    "intent": state["intent"],
                    "instruction": (
                        "Write the smallest test that reproduces the reported bug against "
                        "the CURRENT (unfixed) code. Do not fix anything yet. Then record "
                        "the red phase with the command below — it must exit non-zero."
                    ),
                    "record_command": (
                        "python3 scripts/record_check.py --check red-green --phase before "
                        "--test '<test id>' --command '<command that runs just that test>'"
                    ),
                },
            )
        if red_green.get("before_harness_error"):
            return action(
                "write_regression_test",
                (
                    "The recorded red phase did not actually run a test: "
                    f"{red_green['before_harness_error']}. A non-zero exit from a broken "
                    "command is not a reproduction of the bug."
                ),
                {
                    "instruction": (
                        "Fix the command so it genuinely executes the regression test, "
                        "then re-record the before phase."
                    ),
                    "command_used": red_green.get("command"),
                    "harness_error": red_green["before_harness_error"],
                    "log": red_green.get("before_log"),
                },
            )
        if red_green.get("before_exit") == 0:
            return action(
                "write_regression_test",
                "The recorded regression test passed against the unfixed code, so it does "
                "not reproduce the bug and cannot prove the fix.",
                {
                    "instruction": (
                        "Rewrite the test so it fails without the fix. If it cannot be made "
                        "to fail, the bug is not where the plan says it is — re-investigate."
                    ),
                    "previous_exit": red_green.get("before_exit"),
                    "test": red_green.get("test"),
                },
            )

    # 4. Implementation.
    source_changed = diff.get("totals", {}).get("source_files", 0) > 0
    if not has_changes or (not source_changed and kind in ("feature", "bugfix")):
        return action(
            "implement",
            "The plan exists but the code does not reflect it yet.",
            {
                "intent": state["intent"],
                "kind": kind,
                "plan": plan["primary"],
                "scope": state.get("scope") or [],
                "changed_so_far": diff.get("totals", {}),
            },
        )

    # 5. Evidence. Deterministic — the pipeline runs these, no agent needed.
    missing_checks = [
        name for name in ("tests", "lint", "typecheck")
        if not (isinstance(checks.get(name), dict) and checks[name].get("ran"))
    ]
    if "tests" in missing_checks:
        toolchain = preflight["toolchain"]
        return action(
            "collect_evidence",
            "The suite has not been run against this change, so nothing is verified.",
            {
                "missing": missing_checks,
                "commands": [
                    "python3 scripts/record_check.py --check tests --auto",
                    *(
                        [f"python3 scripts/record_check.py --check lint --command "
                         f"'{toolchain['lint']['command']}'"]
                        if toolchain.get("lint")
                        else ["python3 scripts/record_check.py --check lint --none "
                              "--reason 'no linter configured'"]
                    ),
                    *(
                        [f"python3 scripts/record_check.py --check typecheck --command "
                         f"'{toolchain['typecheck']['command']}'"]
                        if toolchain.get("typecheck")
                        else ["python3 scripts/record_check.py --check typecheck --none "
                              "--reason 'no type checker configured'"]
                    ),
                ],
                "detected_test_command": toolchain.get("test_command"),
            },
        )

    # 6. Bug fixes: the green half of the proof.
    if kind == "bugfix":
        red_green = checks.get("red-green") or {}
        if red_green.get("after_exit") is None:
            return action(
                "collect_evidence",
                "The regression test was red before the fix; now prove it is green after it.",
                {
                    "commands": [
                        "python3 scripts/record_check.py --check red-green --phase after "
                        f"--command '{red_green.get('command', '<same command as the before phase>')}'"
                    ],
                    "test": red_green.get("test"),
                },
            )

    # 7. Review — only once the change is stable and green.
    review = load_review(root)
    pack_file = root / STATE_DIR / "pack.json"
    stale_pack = False
    if review and pack_file.is_file():
        try:
            pack = json.loads(pack_file.read_text(encoding="utf-8"))
            stale_pack = bool(review.get("pack_digest")) and review["pack_digest"] != pack.get("digest")
        except json.JSONDecodeError:
            stale_pack = True

    if review is None or stale_pack:
        return action(
            "review",
            (
                "The change has never been read critically."
                if review is None
                else "The code changed after the last review, so that review no longer describes it."
            ),
            {
                "build_pack": (
                    "python3 scripts/review_pack.py build --root . "
                    f"--intent {json.dumps(state['intent'])} --kind {kind} "
                    f"--output {STATE_DIR}/pack.json"
                ),
                "audit_command": (
                    f"python3 scripts/review_pack.py audit --pack {STATE_DIR}/pack.json "
                    f"--findings {STATE_DIR}/review-raw.json --output {STATE_DIR}/review.json"
                ),
                "write_findings_to": f"{STATE_DIR}/review-raw.json",
                "dimensions": list(verify_gates_dimensions()),
                "guidance": (
                    "Review with fresh eyes, as an adversary of the change rather than its "
                    "author. Cite file and line for every finding, state the failure it "
                    "causes, and give it a severity. If you find nothing on a large or "
                    "risky change you must attest per dimension what you examined — an "
                    "unexplained clean review is rejected as no review."
                ),
            },
        )

    # 8. Gates.
    run = build_run_record(root, state)
    verdict = verify_gates.evaluate(run, cfg)

    if verdict["blockers"]:
        return action(
            "fix_blockers",
            "Gates failed. Each blocker names what breaks and how to fix it.",
            {"blockers": verdict["blockers"], "verdict": verdict["verdict"]},
        )
    if verdict["missing_evidence"]:
        return action(
            "collect_evidence",
            "Some required gate has no observation to read, and a gate never passes on silence.",
            {"missing": verdict["missing_evidence"]},
        )

    if state.get("pr_opened"):
        return action(
            "done",
            "The change is PR-ready and the PR is open.",
            {"verdict": verdict["verdict"], "pr": state.get("pr_url")},
        )

    return action(
        "open_pr",
        "Every required gate passed with evidence.",
        {
            "verdict": verdict["verdict"],
            "summary": verdict["summary"],
            "pr_body_command": (
                f"python3 scripts/pr_body.py --root . --output {STATE_DIR}/PR.md"
            ),
        },
    )


def verify_gates_dimensions() -> tuple[str, ...]:
    """Import lazily so review_pack stays optional at import time."""
    try:
        import review_pack  # noqa: PLC0415

        return review_pack.REQUIRED_DIMENSIONS
    except ImportError:  # pragma: no cover
        return ("correctness", "security", "data-safety", "error-handling", "intent-fidelity")


def track_progress(root: Path, state: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    """Detect a stuck loop and convert it into an escalation."""
    last = state.get("last_action")
    repeats = state.get("repeat_count", 0)
    if result["action"] == last and result["action"] not in ("done", "blocked"):
        repeats += 1
    else:
        repeats = 0
    state["last_action"] = result["action"]
    state["repeat_count"] = repeats
    state["updated"] = now_iso()
    save_state(root, state)

    if repeats >= NO_PROGRESS_LIMIT:
        return action(
            "blocked",
            f"'{result['action']}' has been returned {repeats + 1} times without the "
            "state changing. The loop is not converging and a human should look.",
            {
                "reason": result["why"],
                "stuck_on": result["action"],
                "last_payload": result["payload"],
            },
        )
    return result


def cmd_start(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    state = load_state(root)
    intent = args.intent.strip()
    kind = args.kind or infer_kind(intent)
    state.update(
        {
            "schema_version": SCHEMA_VERSION,
            "intent": intent,
            "kind": kind,
            "slug": args.slug or slugify(intent),
            "base": args.base,
            "scope": args.scope or [],
            "ticket": args.ticket,
            "started": state.get("started") or now_iso(),
            "updated": now_iso(),
            "plan_written": False,
            "pr_opened": False,
        }
    )
    save_state(root, state)
    print(
        f"started: {state['slug']}  kind={kind}"
        + (f"  (inferred)" if not args.kind else "")
        + f"\nintent: {intent}"
    )
    if kind == "bugfix":
        print(
            "\nkind=bugfix, so a red-green proof is required: a test that fails against "
            "the current code before any fix is written."
        )
    return 0


def cmd_next(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    state = load_state(root)
    cfg: dict[str, Any] = {}
    if args.max_new_suppression is not None:
        cfg["max_new_suppression"] = args.max_new_suppression
    if args.no_review:
        cfg["require_review"] = False

    result = decide(root, state, cfg)
    if state.get("intent"):
        result = track_progress(root, state, result)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"action: {result['action']}\nwhy: {result['why']}")
        if result["payload"]:
            print("payload:")
            print(json.dumps(result["payload"], indent=2))
    return 0


def cmd_mark(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    state = load_state(root)
    if not state:
        print("no run in progress; run 'start' first", file=sys.stderr)
        return 2
    changed = []
    if args.plan_written:
        state["plan_written"] = True
        changed.append("plan_written")
    if args.pr_opened:
        state["pr_opened"] = True
        changed.append("pr_opened")
    if args.pr_url:
        state["pr_url"] = args.pr_url
        changed.append("pr_url")
    if args.scope:
        state["scope"] = args.scope
        changed.append("scope")
    if args.kind:
        state["kind"] = args.kind
        changed.append("kind")
    state["updated"] = now_iso()
    save_state(root, state)
    print(f"marked: {', '.join(changed) if changed else 'nothing'}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    state = load_state(root)
    if not state:
        print("no run in progress")
        return 0
    run = build_run_record(root, state)
    verdict = verify_gates.evaluate(run)
    if args.json:
        print(json.dumps({"state": state, "verdict": verdict}, indent=2))
    else:
        print(f"intent : {state.get('intent')}")
        print(f"kind   : {state.get('kind')}   slug: {state.get('slug')}")
        print(f"started: {state.get('started')}   updated: {state.get('updated')}")
        print("")
        print(verify_gates.render_text(verdict))
    return 0


def cmd_reset(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    target = root / STATE_DIR
    if not target.is_dir():
        print("nothing to reset")
        return 0
    removed = []
    for name in ("state.json", "run.json", "review.json", "review-raw.json", "pack.json"):
        path = target / name
        if path.exists():
            path.unlink()
            removed.append(name)
    print(f"reset: removed {', '.join(removed) if removed else 'nothing'} (logs kept)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)

    def with_root(sub_parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        """Accept --root on every subcommand.

        Putting it only on the top-level parser forces `dev_state.py --root .
        next`, which reads backwards and is the kind of thing an agent gets
        wrong once per session forever.
        """
        sub_parser.add_argument("--root", default=".")
        return sub_parser

    start = with_root(sub.add_parser("start", help="Begin a run"))
    start.add_argument("--intent", required=True)
    start.add_argument("--kind", choices=verify_gates.KINDS, default=None)
    start.add_argument("--slug", default=None)
    start.add_argument("--base", default=None)
    start.add_argument("--ticket", default=None)
    start.add_argument("--scope", nargs="*", default=None, help="Glob patterns")
    start.set_defaults(func=cmd_start)

    nxt = with_root(sub.add_parser("next", help="Ask for the next action"))
    nxt.add_argument("--json", action="store_true")
    nxt.add_argument("--max-new-suppression", type=int, default=None)
    nxt.add_argument("--no-review", action="store_true")
    nxt.set_defaults(func=cmd_next)

    mark = with_root(sub.add_parser("mark", help="Record a milestone"))
    mark.add_argument("--plan-written", action="store_true")
    mark.add_argument("--pr-opened", action="store_true")
    mark.add_argument("--pr-url", default=None)
    mark.add_argument("--scope", nargs="*", default=None)
    mark.add_argument("--kind", choices=verify_gates.KINDS, default=None)
    mark.set_defaults(func=cmd_mark)

    status = with_root(sub.add_parser("status", help="Where is everything"))
    status.add_argument("--json", action="store_true")
    status.set_defaults(func=cmd_status)

    reset = with_root(sub.add_parser("reset", help="Clear run state (keeps logs)"))
    reset.set_defaults(func=cmd_reset)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
