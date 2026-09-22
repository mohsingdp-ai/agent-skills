#!/usr/bin/env python3
"""One entry point, two modes, because two very different callers need this.

**Live mode** (``--intent`` / ``--continue``) drives the loop as far as code
alone can take it: preflight, diff analysis, running and recording the checks,
building the review pack, evaluating the gates, writing the PR body. It stops
the moment it reaches something that genuinely needs judgement — plan, write
the failing test, implement, review — and returns ``needs_agent`` with the full
payload rather than faking the step. Sequencing lives here rather than in the
SKILL.md prose, so the agent runs one command instead of re-deriving an eight
step order every run and eventually getting it wrong.

**Audit mode** (``--input``) is deterministic and side-effect free: it reads a
run record and reports the verdict. No git, no subprocesses, no network, no
mutation. That is what the bundled evals score, and it is why they can score
the interesting part — the gate logic — without needing a repository in a
particular state.

Note the exit-code contract in audit mode: it exits **0 whenever the audit
ran**, even when the verdict is ``blocked``. Correctly refusing a bad change is
a successful audit. ``audit_ok`` reports whether the audit ran; ``pr_ready``
reports whether the change may ship.

Usage:
    python3 run_pipeline.py --intent "fix the login redirect" --kind bugfix
    python3 run_pipeline.py --continue
    python3 run_pipeline.py --input evals/golden/case-1/input.json --output out.json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import dev_preflight  # noqa: E402
import dev_state  # noqa: E402
import diff_intel  # noqa: E402
import pr_body  # noqa: E402
import record_check  # noqa: E402
import review_pack  # noqa: E402
import verify_gates  # noqa: E402

SCHEMA_VERSION = "1.0"
STATE_DIR = ".dev-autopilot"

#: Actions the pipeline performs itself. Everything else stops for the agent.
AUTOMATABLE = {"collect_evidence"}

MAX_STEPS = 12


def audit(input_path: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    """Score a run record with no side effects at all."""
    try:
        run = json.loads(input_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "schema_version": SCHEMA_VERSION,
            "audit_ok": False,
            "error": f"cannot read run record: {exc}",
            "verdict": "blocked",
            "pr_ready": False,
            "gates": [],
            "blockers": [],
            "missing_evidence": [],
            "warnings": [],
        }

    overrides = {**cfg, **(run.get("config") or {})}
    verdict = verify_gates.evaluate(run, overrides)
    return {
        "schema_version": SCHEMA_VERSION,
        "audit_ok": True,
        "intent": run.get("intent"),
        "kind": verdict["kind"],
        "verdict": verdict["verdict"],
        "pr_ready": verdict["pr_ready"],
        "evidence_complete": verdict["evidence_complete"],
        "summary": verdict["summary"],
        "gates": verdict["gates"],
        "blockers": verdict["blockers"],
        "missing_evidence": verdict["missing_evidence"],
        "warnings": verdict["warnings"],
    }


def run_recorded_checks(root: Path, payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Execute the evidence commands the state machine asked for."""
    transcript: list[dict[str, Any]] = []
    for command in payload.get("commands", []):
        parts = command.split()
        if not parts or "record_check.py" not in command:
            continue
        # Re-point the script path at this installation.
        script = str(Path(__file__).resolve().parent / "record_check.py")
        rebuilt = command.replace("scripts/record_check.py", script)
        proc = subprocess.run(
            rebuilt, shell=True, cwd=str(root), capture_output=True, text=True, timeout=3600
        )
        transcript.append(
            {
                "step": "record_check",
                "command": rebuilt,
                "exit_code": proc.returncode,
                "stdout": (proc.stdout or "").strip()[-800:],
                "stderr": (proc.stderr or "").strip()[-800:],
            }
        )
    return transcript


def ensure_pack(root: Path, state: dict[str, Any]) -> dict[str, Any]:
    """Build the reviewer context pack so the agent's review step is one call."""
    try:
        diff_report = diff_intel.analyze(root, base=state.get("base"))
    except diff_intel.GitError as exc:
        return {"step": "build_pack", "ok": False, "error": str(exc)}

    pack = review_pack.build_pack(
        root,
        diff_report,
        state.get("intent"),
        state.get("kind", "feature"),
        state.get("ticket"),
    )
    out = root / STATE_DIR / "pack.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(pack, indent=2) + "\n", encoding="utf-8")
    return {
        "step": "build_pack",
        "ok": True,
        "path": str(out),
        "digest": pack["digest"],
        "files": pack["diff_summary"]["files"],
        "risk": pack["diff_summary"]["risk_level"],
    }


def live(
    root: Path,
    intent: str | None,
    kind: str | None,
    base: str | None,
    scope: list[str] | None,
    ticket: str | None,
    cfg: dict[str, Any],
    max_steps: int = MAX_STEPS,
) -> dict[str, Any]:
    """Drive the loop until it needs a person or an agent."""
    transcript: list[dict[str, Any]] = []

    state = dev_state.load_state(root)
    if intent:
        state.update(
            {
                "schema_version": SCHEMA_VERSION,
                "intent": intent,
                "kind": kind or dev_state.infer_kind(intent),
                "slug": state.get("slug") or dev_state.slugify(intent),
                "base": base or state.get("base"),
                "scope": scope if scope is not None else state.get("scope", []),
                "ticket": ticket or state.get("ticket"),
                "started": state.get("started") or dev_state.now_iso(),
                "plan_written": state.get("plan_written", False),
                "pr_opened": state.get("pr_opened", False),
            }
        )
        dev_state.save_state(root, state)
        transcript.append(
            {"step": "start", "slug": state["slug"], "kind": state["kind"], "intent": intent}
        )
    elif not state.get("intent"):
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "blocked",
            "reason": "No run in progress and no --intent given.",
            "transcript": transcript,
        }

    preflight = dev_preflight.run_all(root, state.get("base"))
    transcript.append(
        {
            "step": "preflight",
            "ready": preflight["ready"],
            "errors": preflight["errors"],
            "warnings": preflight["warnings"],
            "siblings": [n for n, v in preflight["siblings"].items() if v["installed"]],
        }
    )

    for _ in range(max_steps):
        result = dev_state.decide(root, state, cfg)
        result = dev_state.track_progress(root, state, result)
        action = result["action"]

        if action in ("done", "blocked"):
            transcript.append({"step": action, "why": result["why"]})
            return {
                "schema_version": SCHEMA_VERSION,
                "status": action,
                "action": action,
                "why": result["why"],
                "payload": result["payload"],
                "transcript": transcript,
            }

        if action == "collect_evidence":
            steps = run_recorded_checks(root, result["payload"])
            transcript.extend(steps)
            if not steps:
                # Nothing runnable — the agent must supply the command.
                return needs_agent(result, transcript, state)
            continue

        if action == "review":
            transcript.append(ensure_pack(root, state))
            return needs_agent(result, transcript, state)

        if action == "open_pr":
            run = dev_state.build_run_record(root, state)
            verdict = verify_gates.evaluate(run, cfg)
            body = pr_body.build_body(state, verdict, dev_state.load_review(root), run)
            out = root / STATE_DIR / "PR.md"
            out.write_text(body, encoding="utf-8")
            transcript.append(
                {"step": "pr_body", "path": str(out), "title": pr_body.title_for(state)}
            )
            return {
                "schema_version": SCHEMA_VERSION,
                "status": "pr_ready",
                "action": "open_pr",
                "why": result["why"],
                "verdict": verdict["verdict"],
                "summary": verdict["summary"],
                "pr_title": pr_body.title_for(state),
                "pr_body_path": str(out),
                "payload": result["payload"],
                "transcript": transcript,
            }

        return needs_agent(result, transcript, state)

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "blocked",
        "reason": f"Pipeline did not converge within {max_steps} steps.",
        "transcript": transcript,
    }


def needs_agent(
    result: dict[str, Any], transcript: list[dict[str, Any]], state: dict[str, Any]
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "needs_agent",
        "action": result["action"],
        "why": result["why"],
        "payload": result["payload"],
        "intent": state.get("intent"),
        "kind": state.get("kind"),
        "transcript": transcript,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--root", default=".")
    parser.add_argument("--intent", default=None, help="Start or restate the run")
    parser.add_argument("--continue", dest="cont", action="store_true", help="Resume")
    parser.add_argument("--kind", choices=verify_gates.KINDS, default=None)
    parser.add_argument("--base", default=None)
    parser.add_argument("--ticket", default=None)
    parser.add_argument("--scope", nargs="*", default=None)
    parser.add_argument("--input", default=None, help="Audit mode: a run-record JSON")
    parser.add_argument("--output", default=None)
    parser.add_argument("--max-new-suppression", type=int, default=None)
    parser.add_argument("--no-review", action="store_true")
    parser.add_argument("--max-steps", type=int, default=MAX_STEPS)
    args = parser.parse_args()

    cfg: dict[str, Any] = {}
    if args.max_new_suppression is not None:
        cfg["max_new_suppression"] = args.max_new_suppression
    if args.no_review:
        cfg["require_review"] = False

    if args.input:
        result = audit(Path(args.input), cfg)
    else:
        if not args.intent and not args.cont:
            parser.error("give --intent, --continue, or --input")
        result = live(
            Path(args.root).resolve(),
            args.intent,
            args.kind,
            args.base,
            args.scope,
            args.ticket,
            cfg,
            args.max_steps,
        )

    text = json.dumps(result, indent=2)
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
    if not args.output or args.input is None:
        print(text)

    if args.input:
        return 0 if result.get("audit_ok") else 1
    return 0 if result.get("status") in ("pr_ready", "needs_agent", "done") else 1


if __name__ == "__main__":
    sys.exit(main())
