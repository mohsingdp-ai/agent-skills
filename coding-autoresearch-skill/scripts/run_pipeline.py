#!/usr/bin/env python3
"""The loop. One command in, one instruction out.

Sequencing lives here rather than in prose, so the agent runs a single command
instead of re-deriving an eight-step order every iteration and eventually getting
it wrong. Everything code can decide, this decides: preflight, baseline, scoring,
keep-vs-discard, the git reset, the ledger row, stagnation, and the stop
condition. It halts with ``needs_agent`` only where judgement is genuinely
required — writing the test, writing the code, reading a stack trace.

    run_pipeline.py --task "fix the login redirect" --kind bugfix
    run_pipeline.py --continue
    run_pipeline.py --status
    run_pipeline.py --report

State lives on disk in ``.autoresearch/run.json``, so an interrupted or
context-compacted run resumes exactly where it stopped. Never infer the state
from memory — ask again.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Never leave __pycache__ in the repository under test: an untracked byte-cache
# directory reads as a dirty tree and would be swept away by a discard.
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

import gitops  # noqa: E402
import ledger  # noqa: E402
import score as scoring  # noqa: E402
from contract import (  # noqa: E402
    EXPECT_FAIL,
    STATE_DIR,
    ContractError,
    build_contract,
    contract_path,
    load_contract,
    save_contract,
    verify_contract,
)

RUN_FILE = "run.json"

# Terminal statuses.
RUNNING = "running"
COMPLETE = "complete"
BLOCKED = "blocked"

# Actions handed back to the agent.
A_FIX_PREFLIGHT = "fix_preflight"
A_REVIEW_CONTRACT = "review_contract"
A_WRITE_REPRODUCER = "write_reproducer"
A_FIX_REPRODUCER = "fix_reproducer"
A_FIX_BASELINE = "fix_baseline"
A_IMPLEMENT = "implement"
A_FIX_HARNESS = "fix_harness"
A_RESEARCH = "research"
A_FIX_OVERFIT = "fix_overfit"
A_DONE = "done"
A_BLOCKED = "blocked"

#: How many times the same action may repeat with no score movement before the
#: loop stops calling it progress. autoresearch says "if you can't get things to
#: work after more than a few attempts, give up"; this is that, counted.
ACTION_REPEAT_LIMIT = 3

#: Revealing a holdout failure to the loop partly spends the holdout. Allow it
#: twice, then stop: past that the loop is optimizing against the holdout too and
#: the check has stopped being independent.
OVERFIT_LIMIT = 2

#: Consecutive crashes of the same criterion before the run is called blocked.
CRASH_LIMIT = 3


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def run_path(root: Path) -> Path:
    return root / STATE_DIR / RUN_FILE


def load_run(root: Path) -> dict[str, Any]:
    path = run_path(root)
    if not path.is_file():
        raise ContractError("no run in progress — start one with --task and --kind")
    return json.loads(path.read_text(encoding="utf-8"))


def save_run(root: Path, state: dict[str, Any]) -> None:
    path = run_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    state["updated"] = _now()
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def respond(
    root: Path,
    state: dict[str, Any],
    status: str,
    action: str,
    message: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Persist the decision and shape the reply."""
    if action == state.get("last_action"):
        state["action_repeat"] = int(state.get("action_repeat", 0)) + 1
    else:
        state["action_repeat"] = 1
    state["last_action"] = action
    state["status"] = status
    save_run(root, state)
    return {
        "status": status,
        "action": action,
        "message": message,
        "attempt": state.get("attempt", 0),
        "best_score": state.get("best_score"),
        "max_score": state.get("max_score"),
        "payload": payload or {},
    }


# --------------------------------------------------------------------------
# start
# --------------------------------------------------------------------------


def start(
    root: Path,
    task: str,
    kind: str,
    scope: list[str],
    tag: str | None,
    attempt_seconds: int,
    max_attempts: int,
    no_progress_limit: int,
) -> dict[str, Any]:
    findings = gitops.preflight(root)
    hard = [f for f in findings if f["severity"] == "hard"]
    fixable = [f for f in findings if f["severity"] != "hard"]

    state: dict[str, Any] = {
        "task": task,
        "kind": kind,
        "started": _now(),
        "phase": "init",
        "attempt": 0,
        "keep_sha": None,
        "best_score": None,
        "best_complexity": None,
        "max_score": None,
        "no_progress": 0,
        "overfits": 0,
        "crashes": 0,
        "last_crash": None,
        "last_action": None,
        "action_repeat": 0,
        "status": RUNNING,
    }

    if hard:
        save_run(root, state)
        return respond(root, state, BLOCKED, A_BLOCKED,
                       "the repository cannot host a run", {"findings": hard})
    if fixable:
        # A protected branch is fixable by us; the rest the agent must resolve.
        protected = [f for f in fixable if f["id"] == "protected-branch"]
        others = [f for f in fixable if f["id"] != "protected-branch"]
        if others:
            save_run(root, state)
            return respond(root, state, RUNNING, A_FIX_PREFLIGHT,
                           "resolve these before the loop can start", {"findings": others})
        if protected and tag:
            gitops.start_branch(root, tag)
        elif protected:
            save_run(root, state)
            return respond(root, state, RUNNING, A_FIX_PREFLIGHT,
                           "on a protected branch; re-run with --tag <name> to branch automatically",
                           {"findings": protected})
    elif tag:
        gitops.start_branch(root, tag)

    gitops.ensure_ignored(root)
    contract = build_contract(
        root, task=task, kind=kind, scope=scope,
        attempt_seconds=attempt_seconds, max_attempts=max_attempts,
        no_progress_limit=no_progress_limit,
    )
    save_contract(root, contract)
    state["max_score"] = sum(int(c.get("weight", 1)) for c in contract["criteria"])
    state["phase"] = "contract"
    save_run(root, state)

    unresolved = [c["id"] for c in contract["criteria"] if "MISSING-" in c["cmd"]]
    return respond(
        root, state, RUNNING, A_REVIEW_CONTRACT,
        "a contract was drafted from the task kind — read it, correct any command or scope, "
        "then lock it. Nothing is scored until it is locked, and it cannot be changed after.",
        {
            "contract": str(contract_path(root)),
            "kind": contract["kind"],
            "guidance": contract["guidance"],
            "criteria": [{"id": c["id"], "text": c["text"], "cmd": c["cmd"],
                          "weight": c["weight"], "expect": c.get("expect", "pass")}
                         for c in contract["criteria"]],
            "unresolved_commands": unresolved,
            "lock_command": "python3 scripts/contract.py lock",
        },
    )


# --------------------------------------------------------------------------
# continue
# --------------------------------------------------------------------------


def advance(root: Path) -> dict[str, Any]:  # noqa: PLR0911, PLR0912 - a state machine
    state = load_run(root)
    if state.get("status") in {COMPLETE, BLOCKED}:
        return respond(root, state, state["status"],
                       A_DONE if state["status"] == COMPLETE else A_BLOCKED,
                       state.get("reason", "this run has already finished"),
                       {"report": "python3 scripts/ledger.py report"})

    gitops.ensure_ignored(root)
    intact, message = verify_contract(root)
    if not intact:
        if "not locked" in message:
            return respond(root, state, RUNNING, A_REVIEW_CONTRACT,
                           "the contract is not locked yet",
                           {"lock_command": "python3 scripts/contract.py lock"})
        state["reason"] = message
        return respond(root, state, BLOCKED, A_BLOCKED, message, {})

    contract = load_contract(root)
    state["max_score"] = sum(int(c.get("weight", 1)) for c in contract["criteria"])

    if state["phase"] in {"init", "contract"}:
        return _enter_baseline(root, state, contract)
    if state["phase"] == "await_baseline":
        return _run_baseline(root, state, contract)
    if state["phase"] == "loop":
        return _run_attempt(root, state, contract)
    if state["phase"] == "holdout":
        return _run_holdout(root, state, contract)

    state["reason"] = f"unknown phase {state['phase']!r}"
    return respond(root, state, BLOCKED, A_BLOCKED, state["reason"], {})


def _enter_baseline(root: Path, state: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    state["phase"] = "await_baseline"
    if not contract["baseline_must_be_red"]:
        return _run_baseline(root, state, contract)

    red = [c for c in contract["criteria"] if c.get("expect") == EXPECT_FAIL]
    return respond(
        root, state, RUNNING, A_WRITE_REPRODUCER,
        "write the thing that proves the task is real, and nothing else. "
        "Do not touch the source yet — the baseline exists to show the problem is present.",
        {
            "must_fail_at_baseline": [{"id": c["id"], "text": c["text"], "cmd": c["cmd"]} for c in red],
            "guidance": contract["guidance"],
            "then": "python3 scripts/run_pipeline.py --continue",
        },
    )


def _run_baseline(root: Path, state: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    try:
        verdict = scoring.score_tree(root, scoring.PHASE_BASELINE)
    except ContractError as exc:
        state["reason"] = str(exc)
        return respond(root, state, BLOCKED, A_BLOCKED, state["reason"], {})
    scoring.write_verdict(root, verdict)

    if verdict["crashed"]:
        crashed = [c for c in verdict["criteria"] if c["status"] == scoring.CRASH]
        return respond(
            root, state, RUNNING, A_FIX_HARNESS,
            "a criterion could not run at the baseline — fix the command, not the code",
            {"crashed": crashed, "logs": [c["log"] for c in crashed]},
        )

    # A criterion required to be red at baseline that came back green means the
    # reproducer does not reproduce anything: the strongest signal available that
    # the task, as specified, is already satisfied.
    false_red = [c for c in verdict["criteria"] if c["demonstrated"] is False]
    if false_red:
        return respond(
            root, state, RUNNING, A_FIX_REPRODUCER,
            "the check that had to fail at baseline passed instead — it does not reproduce the "
            "reported problem, so nothing it later proves would mean anything",
            {"passed_but_should_fail": [{"id": c["id"], "text": c["text"], "log": c["log"]} for c in false_red]},
        )

    if not contract["baseline_must_be_red"] and not verdict["complete"]:
        failing = [c["id"] for c in verdict["criteria"] if c["status"] != scoring.PASS]
        state["reason"] = (
            f"the baseline is not green ({', '.join(failing)}). This kind of task is "
            "behaviour-preserving, and behaviour that is already broken cannot be preserved. "
            "Fix or quarantine the failing check first, then start a fresh run."
        )
        return respond(root, state, BLOCKED, A_BLOCKED, state["reason"],
                       {"failing": failing})

    # Commit whatever the baseline needed (a reproducer, usually) so the discard
    # target is a real commit rather than a moving tree.
    try:
        sha = gitops.commit_attempt(root, f"autoresearch baseline: {contract['task'][:60]}")
    except gitops.NothingToCommit:
        # Expected for behaviour-preserving kinds: the baseline is the untouched tree.
        sha = gitops.short_head(root)

    ledger.append(
        root, commit=sha, score=verdict["score"], max_score=verdict["max_score"],
        complexity=verdict["complexity"], status=ledger.STATUS_BASELINE,
        description=f"baseline for {contract['kind']}: {contract['task'][:80]}",
        attempt=0,
    )

    state.update({
        "phase": "loop",
        "attempt": 0,
        "keep_sha": sha,
        "best_score": verdict["score"],
        "best_complexity": verdict["complexity"],
        "no_progress": 0,
    })

    # A criteria-driven task whose criteria are already satisfied at baseline has
    # nothing to do. Saying so is more useful than looping to prove it.
    if verdict["complete"] and contract.get("objective", "criteria") == "criteria":
        state["phase"] = "holdout"
        return _run_holdout(root, state, contract)

    if contract.get("objective") == "complexity":
        return respond(
            root, state, RUNNING, A_IMPLEMENT,
            f"baseline: correctness is already satisfied ({verdict['score']}/{verdict['max_score']}) "
            f"and the codebase is {verdict['complexity']} lines in scope. That number is the "
            "objective — make it smaller without moving the score or touching a test.",
            _implement_payload(contract, verdict, state),
        )

    return respond(
        root, state, RUNNING, A_IMPLEMENT,
        f"baseline established at {verdict['score']}/{verdict['max_score']}. Now make one focused "
        "change that satisfies an unsatisfied criterion. One idea per attempt — an attempt that "
        "changes three things teaches you nothing about which one worked.",
        _implement_payload(contract, verdict, state),
    )


def _implement_payload(contract: dict[str, Any], verdict: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    unsatisfied = [
        {"id": c["id"], "text": c["text"], "log": c["log"], "note": c["note"]}
        for c in verdict["criteria"] if c["status"] != scoring.PASS
    ]
    return {
        "unsatisfied": unsatisfied,
        "scope": contract["scope"],
        "guidance": contract["guidance"],
        "attempt_seconds": contract["budget"]["attempt_seconds"],
        "best_score": state.get("best_score"),
        "max_score": verdict["max_score"],
        "then": "python3 scripts/run_pipeline.py --continue",
    }


def _run_attempt(root: Path, state: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    budget = contract["budget"]
    if state["attempt"] >= int(budget["max_attempts"]):
        state["reason"] = (
            f"reached the attempt cap ({budget['max_attempts']}) at "
            f"{state['best_score']}/{state['max_score']}"
        )
        return respond(root, state, BLOCKED, A_BLOCKED, state["reason"], {})

    keep_sha = state["keep_sha"]
    try:
        sha = gitops.commit_attempt(root, f"autoresearch attempt {state['attempt'] + 1}")
    except gitops.NothingToCommit:
        last = scoring.read_verdict(root) or {"criteria": [], "max_score": state["max_score"]}
        if int(state.get("action_repeat", 0)) >= ACTION_REPEAT_LIMIT:
            state["reason"] = (
                "asked for an implementation three times and the tree never changed. "
                "Either the next step is not clear or it is not possible from here."
            )
            return respond(root, state, BLOCKED, A_BLOCKED, state["reason"], {})
        return respond(
            root, state, RUNNING, A_IMPLEMENT,
            "nothing changed since the last attempt — edit the code before continuing",
            _implement_payload(contract, last, state),
        )

    state["attempt"] += 1
    try:
        verdict = scoring.score_tree(root, scoring.PHASE_ATTEMPT)
    except ContractError as exc:
        state["reason"] = str(exc)
        return respond(root, state, BLOCKED, A_BLOCKED, state["reason"], {})
    scoring.write_verdict(root, verdict)

    if verdict["crashed"]:
        crashed = [c for c in verdict["criteria"] if c["status"] == scoring.CRASH]
        ids = ",".join(c["id"] for c in crashed)
        state["crashes"] = state["crashes"] + 1 if state.get("last_crash") == ids else 1
        state["last_crash"] = ids
        ledger.append(
            root, commit=sha, score=verdict["score"], max_score=verdict["max_score"],
            complexity=verdict["complexity"], status=ledger.STATUS_CRASH,
            description=f"crash in {ids}", attempt=state["attempt"],
        )
        gitops.reset_to(root, keep_sha)
        if state["crashes"] >= CRASH_LIMIT:
            state["reason"] = f"{ids} crashed {state['crashes']} times in a row — the harness itself is broken"
            return respond(root, state, BLOCKED, A_BLOCKED, state["reason"], {"crashed": crashed})
        return respond(
            root, state, RUNNING, A_FIX_HARNESS,
            "the check could not run, which is not the same as failing it. Read the log, "
            "fix the command or the environment, and do not change the code to chase it.",
            {"crashed": crashed, "logs": [c["log"] for c in crashed],
             "reverted_to": keep_sha},
        )
    state["crashes"] = 0
    state["last_crash"] = None

    improved, why = _is_improvement(verdict, state)
    description = _describe(verdict, why)

    if improved:
        ledger.append(
            root, commit=sha, score=verdict["score"], max_score=verdict["max_score"],
            complexity=verdict["complexity"], status=ledger.STATUS_KEEP,
            description=description, attempt=state["attempt"],
        )
        state["keep_sha"] = sha
        state["best_score"] = verdict["score"]
        state["best_complexity"] = verdict["complexity"]
        state["no_progress"] = 0
    else:
        ledger.append(
            root, commit=sha, score=verdict["score"], max_score=verdict["max_score"],
            complexity=verdict["complexity"], status=ledger.STATUS_DISCARD,
            description=description, attempt=state["attempt"],
        )
        gitops.reset_to(root, keep_sha)
        state["no_progress"] += 1

    # A criteria-driven task is done the moment every criterion is green. A
    # complexity-driven one is green from attempt zero, so its stop condition is
    # convergence instead — handled by the stagnation branch below.
    criteria_driven = contract.get("objective", "criteria") == "criteria"
    if improved and verdict["complete"] and criteria_driven:
        state["phase"] = "holdout"
        return _run_holdout(root, state, contract)

    limit = int(budget["no_progress_limit"])
    if state["no_progress"] >= limit * 2:
        # Running out of simplifications is success, not blockage: a complexity-driven
        # task has no green light to reach, so convergence IS the stop condition.
        if contract.get("objective") == "complexity" and state["best_score"] == state["max_score"]:
            state["phase"] = "holdout"
            return _run_holdout(root, state, contract)
        state["reason"] = (
            f"{state['no_progress']} attempts without improvement, including a widened search. "
            f"Stuck at {state['best_score']}/{state['max_score']}."
        )
        return respond(root, state, BLOCKED, A_BLOCKED, state["reason"],
                       {"report": "python3 scripts/ledger.py report"})
    if state["no_progress"] >= limit:
        return respond(
            root, state, RUNNING, A_RESEARCH,
            f"{state['no_progress']} attempts with no movement — stop trying variations of the same "
            "idea. Read the code paths you have not read, look for a prior implementation of "
            "something similar in this repo, and come back with a different approach rather than "
            "a smaller version of the last one.",
            {
                "ledger": "python3 scripts/ledger.py rows",
                "unsatisfied": [c["id"] for c in verdict["criteria"] if c["status"] != scoring.PASS],
                "tried": [r["description"] for r in ledger.read_rows(root)[-limit:]],
            },
        )

    verb = "kept" if improved else "discarded"
    return respond(
        root, state, RUNNING, A_IMPLEMENT,
        f"attempt {state['attempt']} {verb} ({why}). Best is "
        f"{state['best_score']}/{state['max_score']}.",
        _implement_payload(contract, verdict, state),
    )


def _is_improvement(verdict: dict[str, Any], state: dict[str, Any]) -> tuple[bool, str]:
    """Keep or discard, with the simplicity criterion as the tiebreak.

    A higher score always wins. An equal score wins only by costing fewer changed
    lines — so deleting code to reach the same result is a keep, which is exactly
    autoresearch's "removing something and getting equal results is a great outcome".
    """
    best = state.get("best_score")
    best_complexity = state.get("best_complexity")
    if best is None:
        return True, "first scored attempt"
    if verdict["score"] > best:
        return True, f"score {best} -> {verdict['score']}"
    if verdict["score"] < best:
        return False, f"score regressed {best} -> {verdict['score']}"
    if best_complexity is not None and verdict["complexity"] < best_complexity:
        return True, f"same score, simpler ({best_complexity} -> {verdict['complexity']} lines)"
    return False, f"no gain (score {verdict['score']}, {verdict['complexity']} lines)"


def _describe(verdict: dict[str, Any], why: str) -> str:
    passed = [c["id"] for c in verdict["criteria"] if c["status"] == scoring.PASS]
    return f"{why}; satisfied: {','.join(passed) or 'none'}"


def _run_holdout(root: Path, state: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    """Score the checks the loop never saw. This is where gaming gets caught."""
    if not contract.get("holdout"):
        return _finish(root, state, contract, "no holdout criteria declared")

    try:
        verdict = scoring.score_tree(root, scoring.PHASE_HOLDOUT)
    except ContractError as exc:
        state["reason"] = str(exc)
        return respond(root, state, BLOCKED, A_BLOCKED, state["reason"], {})
    scoring.write_verdict(root, verdict)

    failed = [c for c in verdict["criteria"] if c["status"] != scoring.PASS]
    if not failed:
        return _finish(root, state, contract, "holdout clean")

    state["overfits"] = int(state.get("overfits", 0)) + 1
    ledger.append(
        root, commit=gitops.short_head(root), score=state["best_score"],
        max_score=state["max_score"], complexity=state.get("best_complexity", 0),
        status=ledger.STATUS_OVERFIT,
        description=f"holdout caught: {','.join(c['id'] for c in failed)}",
        attempt=state["attempt"],
    )

    if state["overfits"] > OVERFIT_LIMIT:
        state["reason"] = (
            f"the holdout caught this run {state['overfits']} times. Past this point the loop is "
            "optimizing against the holdout too, so it is no longer an independent check. "
            "A human needs to look at the diff."
        )
        return respond(root, state, BLOCKED, A_BLOCKED, state["reason"],
                       {"failed_holdout": [c["id"] for c in failed],
                        "report": "python3 scripts/ledger.py report"})

    state["phase"] = "loop"
    return respond(
        root, state, RUNNING, A_FIX_OVERFIT,
        "every visible criterion passed but a holdout check failed — the score was reached by a "
        "route the contract was meant to exclude. Fix the cause, not the check.",
        {
            "failed_holdout": [{"id": c["id"], "text": c["text"], "note": c["note"], "log": c["log"]}
                               for c in failed],
            "holdout_budget_left": OVERFIT_LIMIT - state["overfits"] + 1,
            "then": "python3 scripts/run_pipeline.py --continue",
        },
    )


def _finish(root: Path, state: dict[str, Any], contract: dict[str, Any], note: str) -> dict[str, Any]:
    sha = gitops.short_head(root)
    ledger.append(
        root, commit=sha, score=state["best_score"], max_score=state["max_score"],
        complexity=state.get("best_complexity", 0), status=ledger.STATUS_COMPLETE,
        description=f"verified complete ({note})", attempt=state["attempt"],
    )
    state["phase"] = "done"
    state["reason"] = (
        f"verified complete: {state['best_score']}/{state['max_score']} on the visible criteria "
        f"and every holdout check passed, over {state['attempt']} attempt(s)."
    )
    report = root / STATE_DIR / "report.md"
    report.write_text(ledger.render_report(root), encoding="utf-8")
    return respond(root, state, COMPLETE, A_DONE, state["reason"], {
        "commit": sha,
        "branch": gitops.current_branch(root),
        "report": str(report),
        "task": contract["task"],
    })


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def render(reply: dict[str, Any]) -> str:
    lines = [
        f"status: {reply['status']}    action: {reply['action']}    attempt: {reply['attempt']}",
    ]
    if reply.get("best_score") is not None:
        lines[0] += f"    score: {reply['best_score']}/{reply.get('max_score')}"
    lines += ["", reply["message"], ""]
    payload = reply.get("payload") or {}
    for key, value in payload.items():
        if isinstance(value, list):
            if not value:
                continue
            lines.append(f"{key}:")
            for item in value:
                if isinstance(item, dict):
                    head = item.get("id") or item.get("problem") or next(iter(item.values()), "")
                    rest = item.get("text") or item.get("note") or item.get("fix") or ""
                    lines.append(f"  - {head}: {rest}".rstrip(": "))
                    if item.get("log"):
                        lines.append(f"      log: {item['log']}")
                    if item.get("cmd"):
                        lines.append(f"      $ {item['cmd']}")
                else:
                    lines.append(f"  - {item}")
        elif value not in (None, "", {}):
            lines.append(f"{key}: {value}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", default=".")
    parser.add_argument("--task", help="plain-language task statement (starts a run)")
    parser.add_argument("--kind", help="task kind; see 'contract.py kinds'")
    parser.add_argument("--scope", action="append", default=[], help="glob the change may touch")
    parser.add_argument("--tag", help="run tag; creates branch autoresearch/<tag>")
    parser.add_argument("--attempt-seconds", type=int, default=600)
    parser.add_argument("--max-attempts", type=int, default=60)
    parser.add_argument("--no-progress-limit", type=int, default=5)
    parser.add_argument("--continue", dest="cont", action="store_true", help="advance the loop")
    parser.add_argument("--status", action="store_true", help="print the current state")
    parser.add_argument("--report", action="store_true", help="render the run report")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()

    try:
        if args.report:
            print(ledger.render_report(root))
            return 0
        if args.status:
            state = load_run(root)
            print(json.dumps(state, indent=2) if args.json else render({
                "status": state.get("status", RUNNING),
                "action": state.get("last_action") or "(none)",
                "attempt": state.get("attempt", 0),
                "best_score": state.get("best_score"),
                "max_score": state.get("max_score"),
                "message": state.get("reason", f"phase: {state.get('phase')}"),
                "payload": {"task": state.get("task"), "kind": state.get("kind"),
                            "branch": gitops.current_branch(root)},
            }))
            return 0
        if args.task:
            if not args.kind:
                print("error: --kind is required with --task", file=sys.stderr)
                return 1
            reply = start(root, args.task, args.kind, args.scope, args.tag,
                          args.attempt_seconds, args.max_attempts, args.no_progress_limit)
        elif args.cont:
            reply = advance(root)
        else:
            parser.print_help()
            return 1
    except (ContractError, gitops.GitError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(reply, indent=2, ensure_ascii=False) if args.json else render(reply))
    if reply["status"] == BLOCKED:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
