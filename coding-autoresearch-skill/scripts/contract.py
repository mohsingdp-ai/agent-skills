#!/usr/bin/env python3
"""Task contract: the objective function a coding run is scored against.

This is the analogue of autoresearch's ``prepare.py`` — the file the agent may
NOT edit. In autoresearch the metric (``val_bpb``) pre-exists and is computed by
a read-only harness. A general coding task has no such metric, so the contract
manufactures one *before* implementation starts and then locks it with a
SHA-256 digest over its canonical form.

The lock is the whole point. An agent that can rewrite its own success criteria
mid-run will always reach green, and the green means nothing. ``verify`` recomputes
the digest and fails loudly when the objective moved.

Commands
--------
    contract.py init  --task "..." --kind bugfix [--scope GLOB ...] [--root .]
    contract.py lock  [--root .]
    contract.py verify [--root .]
    contract.py show  [--root .] [--json]
    contract.py kinds

Exit codes: 0 ok, 1 error, 3 lock mismatch (objective was tampered with).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Never leave __pycache__ in the repository under test: an untracked byte-cache
# directory reads as a dirty tree and would be swept away by a discard.
sys.dont_write_bytecode = True
STATE_DIR = ".autoresearch"
CONTRACT_FILE = "contract.json"

#: Criteria whose ``expect`` is ``"fail"`` are asserted against the *untouched*
#: tree during the baseline attempt. This is how the red-green proof and
#: autoresearch's "first run establishes the baseline" become the same rule.
EXPECT_FAIL = "fail"
EXPECT_PASS = "pass"


class ContractError(RuntimeError):
    """Raised when a contract cannot be built, read, or verified."""


# --------------------------------------------------------------------------
# Toolchain detection — so ``init`` emits runnable commands, not placeholders
# --------------------------------------------------------------------------


def detect_toolchain(root: Path) -> dict[str, str]:
    """Infer the project's test/lint/typecheck commands from its manifests.

    Returns a mapping with at least a ``test`` key. Values are real shell
    commands for the detected ecosystem; an ecosystem we cannot identify yields
    an empty mapping so the caller can ask the agent to fill it in rather than
    baking in a command that does not exist.
    """
    tools: dict[str, str] = {}

    pkg = root / "package.json"
    if pkg.is_file():
        runner = _js_runner(root)
        data = _read_json(pkg)
        scripts = data.get("scripts", {}) if isinstance(data, dict) else {}
        dev = _all_js_deps(data)

        if "test" in scripts:
            tools["test"] = f"{runner} test"
        elif "vitest" in dev:
            tools["test"] = f"{runner} exec vitest run"
        elif "jest" in dev:
            tools["test"] = f"{runner} exec jest"

        if "lint" in scripts:
            tools["lint"] = f"{runner} lint"
        elif "eslint" in dev:
            tools["lint"] = f"{runner} exec eslint ."

        if "typecheck" in scripts:
            tools["typecheck"] = f"{runner} typecheck"
        elif (root / "tsconfig.json").is_file() or any(root.glob("tsconfig*.json")):
            tools["typecheck"] = f"{runner} exec tsc --noEmit"

        if "@playwright/test" in dev or any(root.glob("playwright.config.*")):
            tools["e2e"] = f"{runner} exec playwright test"
        if "build" in scripts:
            tools["build"] = f"{runner} build"
        return tools

    if (root / "pyproject.toml").is_file() or (root / "setup.py").is_file() or (root / "tox.ini").is_file():
        tools["test"] = "python3 -m pytest -q"
        if (root / "ruff.toml").is_file() or _file_contains(root / "pyproject.toml", "ruff"):
            tools["lint"] = "ruff check ."
        if _file_contains(root / "pyproject.toml", "mypy"):
            tools["typecheck"] = "mypy ."
        return tools

    if (root / "go.mod").is_file():
        return {"test": "go test ./...", "lint": "go vet ./...", "build": "go build ./..."}

    if (root / "Cargo.toml").is_file():
        return {"test": "cargo test", "lint": "cargo clippy -- -D warnings", "build": "cargo build"}

    if (root / "pom.xml").is_file():
        return {"test": "mvn -q test"}

    if (root / "build.gradle").is_file() or (root / "build.gradle.kts").is_file():
        return {"test": "./gradlew test"}

    return tools


def _js_runner(root: Path) -> str:
    """Pick the package manager the repo actually uses, from its lockfile."""
    if (root / "pnpm-lock.yaml").is_file():
        return "pnpm"
    if (root / "yarn.lock").is_file():
        return "yarn"
    if (root / "bun.lockb").is_file():
        return "bun"
    return "npm run" if (root / "package-lock.json").is_file() else "npm run"


def _all_js_deps(data: Any) -> set[str]:
    if not isinstance(data, dict):
        return set()
    names: set[str] = set()
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        section = data.get(key)
        if isinstance(section, dict):
            names.update(section)
    return names


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _file_contains(path: Path, needle: str) -> bool:
    try:
        return needle in path.read_text(encoding="utf-8")
    except OSError:
        return False


# --------------------------------------------------------------------------
# Kind profiles — what "done" means differs per task type
# --------------------------------------------------------------------------


class Profile:
    """A per-task-kind template for the contract's shape.

    ``baseline_red`` marks kinds where the baseline attempt must *fail* a named
    criterion before any code is written — the proof that the task addresses a
    real, currently-broken thing rather than something already working.
    """

    def __init__(
        self,
        kind: str,
        summary: str,
        baseline_red: bool,
        criteria: list[dict[str, Any]],
        holdout: list[dict[str, Any]],
        complexity_direction: str = "lower",
        default_scope: list[str] | None = None,
        guidance: str = "",
        objective: str = "criteria",
    ) -> None:
        self.kind = kind
        self.summary = summary
        self.baseline_red = baseline_red
        self.criteria = criteria
        self.holdout = holdout
        self.complexity_direction = complexity_direction
        self.default_scope = default_scope or []
        self.guidance = guidance
        self.objective = objective


def _c(cid: str, text: str, cmd: str, weight: int = 1, expect: str = EXPECT_PASS) -> dict[str, Any]:
    """Build one criterion. ``cmd`` may contain ``{test}``/``{lint}`` tokens."""
    return {"id": cid, "text": text, "cmd": cmd, "weight": weight, "expect": expect}


#: Holdout criteria shared by every kind that produces code. These are the
#: checks an agent optimizing the visible score would happily violate: they are
#: hidden from the loop and asserted only at completion.
_CODE_HOLDOUT = [
    {"id": "no-focus-markers", "text": "No .only/fit/fdescribe/test.only added", "cmd": "python3 {guards} focus --root {root} --base {base}"},
    {"id": "no-new-suppressions", "text": "No tests newly skipped or fixme'd", "cmd": "python3 {guards} suppression --root {root} --base {base}"},
    {"id": "in-scope", "text": "No files changed outside declared scope", "cmd": "python3 {guards} scope --root {root} --base {base}"},
]

_DOC_HOLDOUT = [
    {"id": "in-scope", "text": "No files changed outside declared scope", "cmd": "python3 {guards} scope --root {root} --base {base}"},
]

PROFILES: dict[str, Profile] = {
    "bugfix": Profile(
        kind="bugfix",
        summary="A reported defect. Proven fixed only by a test that was red first.",
        baseline_red=True,
        criteria=[
            _c("reproducer", "The reproducing test passes", "{test}", weight=3, expect=EXPECT_FAIL),
            _c("suite", "The full test suite passes", "{test}", weight=2),
        ],
        holdout=_CODE_HOLDOUT,
        guidance=(
            "Write the smallest failing test FIRST and let the baseline attempt prove it red. "
            "A reproducer that is green at baseline does not reproduce the reported bug — "
            "rewrite it before touching any source."
        ),
    ),
    "debug": Profile(
        kind="debug",
        summary="Root-cause analysis. The deliverable is an explanation plus a reproducer.",
        baseline_red=True,
        criteria=[
            _c("reproducer", "A test reproduces the reported behaviour", "{test}", weight=3, expect=EXPECT_FAIL),
            _c("findings", "findings.md names the root cause with file:line evidence", "python3 {guards} findings --root {root}", weight=2),
        ],
        holdout=_CODE_HOLDOUT,
        guidance=(
            "Root cause means the line that produces the wrong value, not the line that reports it. "
            "Stop at the reproducer plus the written cause; do not fix unless the task asked for a fix."
        ),
    ),
    "feature": Profile(
        kind="feature",
        summary="New behaviour. Acceptance criteria become executable tests.",
        baseline_red=True,
        criteria=[
            _c("acceptance", "Acceptance tests for the new behaviour pass", "{test}", weight=3, expect=EXPECT_FAIL),
            _c("suite", "The full test suite passes", "{test}", weight=2),
        ],
        holdout=_CODE_HOLDOUT,
        guidance=(
            "Turn each acceptance criterion into one named test before implementing. "
            "The baseline must be red: a feature whose tests already pass was not missing."
        ),
    ),
    "missing": Profile(
        kind="missing",
        summary="Functionality assumed present but absent (a stub, a TODO, a NotImplemented).",
        baseline_red=True,
        criteria=[
            _c("implemented", "Tests exercising the previously-absent path pass", "{test}", weight=3, expect=EXPECT_FAIL),
            _c("suite", "The full test suite passes", "{test}", weight=2),
        ],
        holdout=_CODE_HOLDOUT,
        guidance="Find every caller of the stub first — the absent behaviour usually has more than one expected shape.",
    ),
    "refactor": Profile(
        kind="refactor",
        summary="Behaviour-preserving change. Score is complexity; tests must not move.",
        baseline_red=False,
        criteria=[
            _c("suite", "The full test suite still passes", "{test}", weight=3),
            _c("tests-unchanged", "No test file was modified", "python3 {guards} tests-unchanged --root {root} --base {base}", weight=2),
        ],
        holdout=_CODE_HOLDOUT,
        complexity_direction="lower",
        objective="complexity",
        guidance=(
            "This is the purest autoresearch analogue: the criteria only gate correctness, "
            "so the complexity tiebreak IS the objective. Deleting code for an equal score is a win. "
            "Changing a test to make a refactor pass is changing the metric — forbidden."
        ),
    ),
    "perf": Profile(
        kind="perf",
        summary="Optimization against a measured benchmark. Closest kin to val_bpb.",
        baseline_red=True,
        criteria=[
            _c("suite", "The full test suite still passes", "{test}", weight=3),
            _c("benchmark", "The benchmark improves on the baseline measurement", "python3 {guards} benchmark --root {root}", weight=2, expect=EXPECT_FAIL),
        ],
        holdout=_CODE_HOLDOUT,
        guidance=(
            "Measure before optimizing; the baseline attempt records the number to beat. "
            "An optimization with no benchmark is a guess. Report the delta, not an adjective."
        ),
    ),
    "test": Profile(
        kind="test",
        summary="New tests or fixtures. Graded on whether they can actually fail.",
        baseline_red=True,
        criteria=[
            _c("new-tests-pass", "The new tests pass against current code", "{test}", weight=2),
            _c("mutation", "The new tests fail when the code under test is mutated", "python3 {guards} mutation --root {root} --base {base}", weight=3, expect=EXPECT_FAIL),
        ],
        holdout=_DOC_HOLDOUT,
        guidance=(
            "A test that passes no matter what the code does is worse than no test — it buys false "
            "confidence. The mutation check is the real criterion; passing is the easy half."
        ),
    ),
    "docs": Profile(
        kind="docs",
        summary="Documentation. Graded on coverage and on examples that actually run.",
        baseline_red=False,
        criteria=[
            _c("examples-run", "Every documented example executes successfully", "python3 {guards} examples --root {root}", weight=3),
            _c("suite", "The test suite still passes", "{test}", weight=1),
        ],
        holdout=_DOC_HOLDOUT,
        guidance="Document what the code does, verified by running it — not what the names suggest it does.",
    ),
    "review": Profile(
        kind="review",
        summary="Code review. The deliverable is findings, each anchored to evidence.",
        baseline_red=True,
        criteria=[
            _c("findings", "findings.md exists with file:line anchored findings", "python3 {guards} findings --root {root}", weight=3, expect=EXPECT_FAIL),
            _c("anchored", "Every finding cites a line inside the reviewed diff", "python3 {guards} review-anchors --root {root} --base {base}", weight=2),
        ],
        holdout=_DOC_HOLDOUT,
        guidance=(
            "Review as an adversary of the change, not its author. A finding without a named consequence "
            "is a style opinion; drop it. An unexplained clean review on a large diff is not a result."
        ),
    ),
    "research": Profile(
        kind="research",
        summary="Investigation. No code change required; the deliverable is a written answer.",
        baseline_red=True,
        criteria=[
            _c("answers", "findings.md answers every posed question", "python3 {guards} findings --root {root}", weight=3, expect=EXPECT_FAIL),
            _c("sourced", "Every claim cites a file:line or a URL", "python3 {guards} sources --root {root}", weight=2),
        ],
        holdout=_DOC_HOLDOUT,
        guidance=(
            "An uncited claim is a guess wearing a suit. Prefer reading the source over reading about it; "
            "when the answer is 'the codebase does not do this', say so plainly and show where you looked."
        ),
    ),
    "integration": Profile(
        kind="integration",
        summary="Wiring two systems together. Graded end to end, not per unit.",
        baseline_red=True,
        criteria=[
            _c("e2e", "The end-to-end path across the boundary passes", "{e2e}", weight=3, expect=EXPECT_FAIL),
            _c("suite", "The full test suite passes", "{test}", weight=2),
        ],
        holdout=_CODE_HOLDOUT,
        guidance=(
            "Unit tests on both sides of a boundary can pass while the boundary itself is broken. "
            "The criterion must cross the seam. Record whether the far side is real or stubbed."
        ),
    ),
}

KIND_ALIASES = {
    "bug": "bugfix",
    "fix": "bugfix",
    "rca": "debug",
    "root-cause": "debug",
    "feat": "feature",
    "performance": "perf",
    "optimize": "perf",
    "optimization": "perf",
    "fixture": "test",
    "tests": "test",
    "doc": "docs",
    "documentation": "docs",
    "code-review": "review",
    "investigate": "research",
    "integrate": "integration",
}


def resolve_kind(kind: str) -> Profile:
    """Map a user-supplied kind (or alias) to its profile."""
    key = kind.strip().lower()
    key = KIND_ALIASES.get(key, key)
    if key not in PROFILES:
        valid = ", ".join(sorted(PROFILES))
        raise ContractError(f"unknown kind {kind!r}; valid kinds: {valid}")
    return PROFILES[key]


# --------------------------------------------------------------------------
# Contract construction, locking, verification
# --------------------------------------------------------------------------


def state_dir(root: Path) -> Path:
    return root / STATE_DIR


def contract_path(root: Path) -> Path:
    return state_dir(root) / CONTRACT_FILE


def canonical_digest(contract: dict[str, Any]) -> str:
    """SHA-256 over the contract's canonical JSON, excluding the lock itself.

    Sorting keys and using compact separators makes the digest insensitive to
    formatting so a reformat is not mistaken for tampering, while any change to
    a criterion, command, weight, or scope entry changes it.
    """
    payload = {k: v for k, v in contract.items() if k != "lock"}
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _git(root: Path, *args: str) -> str:
    proc = subprocess.run(  # noqa: S603
        ["git", *args], cwd=root, capture_output=True, text=True, check=False
    )
    return proc.stdout.strip() if proc.returncode == 0 else ""


def build_contract(
    root: Path,
    task: str,
    kind: str,
    scope: list[str] | None = None,
    attempt_seconds: int = 600,
    max_attempts: int = 60,
    no_progress_limit: int = 5,
) -> dict[str, Any]:
    """Assemble an unlocked contract for ``task`` from its kind profile."""
    profile = resolve_kind(kind)
    tools = detect_toolchain(root)
    base = _git(root, "rev-parse", "HEAD") or "HEAD"

    # Guard commands are bound to an absolute path: criteria run with the target
    # repo as cwd, and the skill is normally installed outside that repo, so a
    # relative "scripts/guards.py" would only resolve by accident.
    guards = str(Path(__file__).resolve().parent / "guards.py")

    def bind(cmd: str) -> str:
        return (
            cmd.replace("{test}", tools.get("test", "MISSING-TEST-COMMAND"))
            .replace("{lint}", tools.get("lint", "true"))
            .replace("{e2e}", tools.get("e2e", tools.get("test", "MISSING-TEST-COMMAND")))
            .replace("{guards}", guards)
            .replace("{root}", ".")
            .replace("{base}", base)
        )

    criteria = [{**c, "cmd": bind(c["cmd"])} for c in profile.criteria]
    holdout = [{**h, "cmd": bind(h["cmd"]), "weight": h.get("weight", 1), "expect": EXPECT_PASS} for h in profile.holdout]

    contract: dict[str, Any] = {
        "version": 1,
        "task": task,
        "kind": profile.kind,
        "summary": profile.summary,
        "guidance": profile.guidance,
        "created": _now(),
        "base_ref": base,
        "scope": scope or profile.default_scope,
        "toolchain": tools,
        "budget": {
            "attempt_seconds": attempt_seconds,
            "max_attempts": max_attempts,
            "no_progress_limit": no_progress_limit,
        },
        "baseline_must_be_red": profile.baseline_red,
        "objective": profile.objective,
        "complexity": {
            "direction": profile.complexity_direction,
            "metric": "changed_lines",
        },
        "criteria": criteria,
        "holdout": holdout,
    }
    return contract


def load_contract(root: Path) -> dict[str, Any]:
    path = contract_path(root)
    if not path.is_file():
        raise ContractError(f"no contract at {path}; run 'contract.py init' first")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ContractError(f"contract at {path} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ContractError(f"contract at {path} must be a JSON object")
    return data


def save_contract(root: Path, contract: dict[str, Any]) -> Path:
    path = contract_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(contract, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def lock_contract(root: Path) -> dict[str, Any]:
    """Freeze the contract by recording its digest. Idempotent re-lock is refused."""
    contract = load_contract(root)
    if contract.get("lock"):
        existing = contract["lock"].get("digest")
        recomputed = canonical_digest(contract)
        if existing == recomputed:
            return contract
        raise ContractError(
            "contract is already locked and its content changed since locking.\n"
            "Re-locking would erase the objective this run is being scored against.\n"
            "If the task genuinely changed, start a new run in a new state directory."
        )
    contract["lock"] = {
        "algorithm": "sha256",
        "digest": canonical_digest(contract),
        "locked_at": _now(),
    }
    save_contract(root, contract)
    return contract


def verify_contract(root: Path) -> tuple[bool, str]:
    """Return (ok, message). ``ok`` is False when the objective moved."""
    contract = load_contract(root)
    lock = contract.get("lock")
    if not lock:
        return False, "contract is not locked; run 'contract.py lock' before the first attempt"
    recorded = lock.get("digest", "")
    actual = canonical_digest(contract)
    if recorded != actual:
        return False, (
            "CONTRACT TAMPERED — the objective changed after it was locked.\n"
            f"  locked digest: {recorded}\n"
            f"  actual digest: {actual}\n"
            "Every result scored against the modified contract is void. Restore the "
            "original contract from git or start a fresh run."
        )
    return True, f"contract intact (sha256 {recorded[:12]})"


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def _cmd_init(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    path = contract_path(root)
    if path.is_file() and not args.force:
        print(f"error: contract already exists at {path} (use --force to overwrite)", file=sys.stderr)
        return 1
    contract = build_contract(
        root,
        task=args.task,
        kind=args.kind,
        scope=args.scope,
        attempt_seconds=args.attempt_seconds,
        max_attempts=args.max_attempts,
        no_progress_limit=args.no_progress_limit,
    )
    save_contract(root, contract)
    missing = [c["id"] for c in contract["criteria"] if "MISSING-TEST-COMMAND" in c["cmd"]]
    print(f"contract written: {path}")
    print(f"  kind: {contract['kind']} — {contract['summary']}")
    print(f"  criteria: {len(contract['criteria'])} visible, {len(contract['holdout'])} holdout")
    print(f"  baseline must be red: {contract['baseline_must_be_red']}")
    if contract["toolchain"]:
        print(f"  detected: {', '.join(f'{k}={v}' for k, v in contract['toolchain'].items())}")
    if missing:
        print(
            f"\nACTION REQUIRED: no test command detected. Edit the 'cmd' of {', '.join(missing)} "
            "in the contract to a real command, THEN lock.",
            file=sys.stderr,
        )
        return 1
    print("\nnext: review the criteria, then run 'contract.py lock' to freeze them")
    return 0


def _cmd_lock(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    contract = lock_contract(root)
    print(f"contract locked: sha256 {contract['lock']['digest'][:12]}")
    print("the objective is now immutable for this run")
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    ok, message = verify_contract(root)
    print(message, file=sys.stderr if not ok else sys.stdout)
    return 0 if ok else 3


def _cmd_show(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    contract = load_contract(root)
    if args.json:
        print(json.dumps(contract, indent=2, ensure_ascii=False))
        return 0
    print(f"task: {contract['task']}")
    print(f"kind: {contract['kind']}")
    print(f"scope: {', '.join(contract['scope']) or '(whole repo)'}")
    print(f"locked: {'yes' if contract.get('lock') else 'NO'}")
    print("\nvisible criteria (drive the loop):")
    for crit in contract["criteria"]:
        marker = "must FAIL at baseline" if crit.get("expect") == EXPECT_FAIL else ""
        print(f"  [{crit['weight']}] {crit['id']}: {crit['text']} {marker}".rstrip())
        print(f"        $ {crit['cmd']}")
    print("\nholdout criteria (scored only at completion):")
    for crit in contract["holdout"]:
        print(f"  {crit['id']}: {crit['text']}")
    return 0


def _cmd_kinds(_args: argparse.Namespace) -> int:
    for name in sorted(PROFILES):
        profile = PROFILES[name]
        red = " [baseline must be red]" if profile.baseline_red else ""
        print(f"{name:<12} {profile.summary}{red}")
    aliases = ", ".join(f"{a}->{t}" for a, t in sorted(KIND_ALIASES.items()))
    print(f"\naliases: {aliases}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="scaffold a contract for a task")
    init.add_argument("--task", required=True, help="plain-language task statement")
    init.add_argument("--kind", required=True, help="task kind (see 'kinds')")
    init.add_argument("--scope", action="append", default=[], help="glob the change may touch (repeatable)")
    init.add_argument("--root", default=".")
    init.add_argument("--attempt-seconds", type=int, default=600)
    init.add_argument("--max-attempts", type=int, default=60)
    init.add_argument("--no-progress-limit", type=int, default=5)
    init.add_argument("--force", action="store_true")
    init.set_defaults(func=_cmd_init)

    lock = sub.add_parser("lock", help="freeze the contract with a digest")
    lock.add_argument("--root", default=".")
    lock.set_defaults(func=_cmd_lock)

    verify = sub.add_parser("verify", help="check the contract was not modified")
    verify.add_argument("--root", default=".")
    verify.set_defaults(func=_cmd_verify)

    show = sub.add_parser("show", help="print the contract")
    show.add_argument("--root", default=".")
    show.add_argument("--json", action="store_true")
    show.set_defaults(func=_cmd_show)

    kinds = sub.add_parser("kinds", help="list task kinds")
    kinds.set_defaults(func=_cmd_kinds)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except ContractError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
