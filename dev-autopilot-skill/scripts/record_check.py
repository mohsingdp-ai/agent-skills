#!/usr/bin/env python3
"""Run a check and write down what actually happened.

Every gate in ``verify_gates.py`` reads an observation, and this is the only
thing that produces one. That is the point. If the agent could write "tests
passed" into the run record directly, the gates would be grading a claim rather
than a result, and the whole verification loop would be theatre.

So this script executes the command, captures the real exit code and the real
output, parses the counts out of it, and appends the record. The agent chooses
*which* command to run; it does not get to choose what the command returned.

It also handles the two cases that are easy to get wrong:

**Absence as evidence.** A project with no type checker should not leave the
static-checks gate permanently starved of evidence. ``--none`` records an
explicit, dated "this project has no such check", which is a real observation
and passes the gate.

**Red-green proof.** A bug fix needs a test that failed *before* the fix. That
is two runs at two points in time, so it is recorded in two phases and the
gate compares them. Running the test once, after the fix, proves nothing.

Usage:
    python3 record_check.py --check tests --command "pytest -q"
    python3 record_check.py --check tests --auto
    python3 record_check.py --check lint --none --reason "no linter configured"
    python3 record_check.py --check red-green --phase before --test "test_bug_42" \\
        --command "pytest -q tests/test_bug.py::test_bug_42"
    python3 record_check.py --check red-green --phase after --command "..."
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"
STATE_DIR = ".dev-autopilot"
RUN_FILE = "run.json"
LOG_DIR = "logs"

CHECKS = ("tests", "lint", "typecheck", "build", "red-green")

MAX_LOG_BYTES = 200_000
MAX_TAIL_CHARS = 4_000

#: (name, marker file, command) — first match wins when --auto is used.
AUTO_TEST_COMMANDS: tuple[tuple[str, str, str], ...] = (
    ("pytest", "pyproject.toml", "python3 -m pytest -q"),
    ("pytest", "pytest.ini", "python3 -m pytest -q"),
    ("pytest", "setup.cfg", "python3 -m pytest -q"),
    ("go", "go.mod", "go test ./..."),
    ("cargo", "Cargo.toml", "cargo test"),
    ("gradle", "build.gradle", "./gradlew test"),
    ("gradle", "build.gradle.kts", "./gradlew test"),
    ("maven", "pom.xml", "mvn -q test"),
    ("composer", "composer.json", "./vendor/bin/phpunit"),
    ("bundler", "Gemfile", "bundle exec rspec"),
)

#: Count parsers, tried in order. Each returns (passed, failed, skipped) or None.
COUNT_PATTERNS: tuple[tuple[str, str], ...] = (
    # pytest: "5 passed, 1 failed, 2 skipped in 0.4s"
    ("pytest", r"(?:(?P<failed>\d+) failed)?[,\s]*(?:(?P<passed>\d+) passed)?"
               r"[,\s]*(?:(?P<skipped>\d+) skipped)?[^\n]*in [\d.]+s"),
    # jest / vitest: "Tests:  1 failed, 12 passed, 13 total"
    ("jest", r"Tests?:\s+(?:(?P<failed>\d+) failed,\s*)?(?:(?P<skipped>\d+) skipped,\s*)?"
             r"(?:(?P<passed>\d+) passed)"),
    # playwright: "12 passed (3.2s)" / "2 failed"
    ("playwright", r"(?:(?P<failed>\d+) failed)?\s*(?:(?P<skipped>\d+) skipped)?\s*"
                   r"(?:(?P<passed>\d+) passed)\s*\("),
    # mocha: "12 passing" / "1 failing" / "2 pending"
    ("mocha", r"(?P<passed>\d+) passing(?:[\s\S]{0,80}?(?P<skipped>\d+) pending)?"
              r"(?:[\s\S]{0,80}?(?P<failed>\d+) failing)?"),
    # go test: counted separately below
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def state_dir(root: Path) -> Path:
    target = root / STATE_DIR
    target.mkdir(parents=True, exist_ok=True)
    (target / LOG_DIR).mkdir(exist_ok=True)
    return target


def load_run(root: Path) -> dict[str, Any]:
    path = state_dir(root) / RUN_FILE
    if not path.exists():
        return {"schema_version": SCHEMA_VERSION, "checks": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"schema_version": SCHEMA_VERSION, "checks": {}}
    data.setdefault("checks", {})
    return data


def save_run(root: Path, run: dict[str, Any]) -> Path:
    path = state_dir(root) / RUN_FILE
    path.write_text(json.dumps(run, indent=2) + "\n", encoding="utf-8")
    return path


def detect_test_command(root: Path) -> tuple[str, str] | None:
    """Guess the project's test command from its manifests."""
    package_json = root / "package.json"
    if package_json.is_file():
        try:
            manifest = json.loads(package_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            manifest = {}
        scripts = manifest.get("scripts") or {}
        if "test" in scripts:
            runner = "npm"
            if (root / "pnpm-lock.yaml").is_file():
                runner = "pnpm"
            elif (root / "yarn.lock").is_file():
                runner = "yarn"
            elif (root / "bun.lockb").is_file():
                runner = "bun"
            command = f"{runner} test" if runner != "npm" else "npm test --silent"
            return ("node", command)

    for name, marker, command in AUTO_TEST_COMMANDS:
        if (root / marker).is_file():
            return (name, command)
    if (root / "tests").is_dir() or (root / "test").is_dir():
        return ("pytest", "python3 -m pytest -q")
    return None


def parse_counts(output: str) -> dict[str, int | None]:
    """Extract passed/failed/skipped counts from runner output.

    Best-effort by design: a missing count is reported as ``None``, never as
    zero. Zero is a claim; ``None`` is an admission, and the gates distinguish
    a vacuous run from an unparsed one.
    """
    tail = output[-8000:] if len(output) > 8000 else output

    go_pass = len(re.findall(r"^--- PASS:", tail, re.MULTILINE))
    go_fail = len(re.findall(r"^--- FAIL:", tail, re.MULTILINE))
    go_skip = len(re.findall(r"^--- SKIP:", tail, re.MULTILINE))
    if go_pass or go_fail or go_skip:
        return {"passed": go_pass, "failed": go_fail, "skipped": go_skip, "parser": "go"}

    cargo = re.search(
        r"test result: \w+\. (?P<passed>\d+) passed; (?P<failed>\d+) failed;"
        r" (?P<ignored>\d+) ignored",
        tail,
    )
    if cargo:
        return {
            "passed": int(cargo.group("passed")),
            "failed": int(cargo.group("failed")),
            "skipped": int(cargo.group("ignored")),
            "parser": "cargo",
        }

    for name, pattern in COUNT_PATTERNS:
        for match in re.finditer(pattern, tail):
            groups = match.groupdict()
            if not any(groups.values()):
                continue
            return {
                "passed": int(groups["passed"]) if groups.get("passed") else 0,
                "failed": int(groups["failed"]) if groups.get("failed") else 0,
                "skipped": int(groups["skipped"]) if groups.get("skipped") else 0,
                "parser": name,
            }
    return {"passed": None, "failed": None, "skipped": None, "parser": None}


#: Output signatures meaning "the test harness never ran the tests".
#: This distinction is load-bearing. A non-zero exit is taken as proof that a
#: test failed — but a typo'd command, a missing runner, or a collection error
#: also exits non-zero while proving nothing at all. Without this check, a bug
#: fix could satisfy its red-green proof with a command that never executed a
#: single assertion, which is precisely the failure the proof exists to prevent.
HARNESS_ERROR_MARKERS: tuple[tuple[str, str], ...] = (
    ("ModuleNotFoundError", "a module could not be imported"),
    ("No module named", "a module could not be imported"),
    ("ImportError", "an import failed"),
    ("command not found", "the command does not exist"),
    ("is not recognized as an internal or external command", "the command does not exist"),
    ("MODULE_NOT_FOUND", "a module could not be resolved"),
    ("Cannot find module", "a module could not be resolved"),
    ("no tests ran", "no tests were collected"),
    ("No tests found", "no tests were collected"),
    ("collected 0 items", "no tests were collected"),
    ("ERROR collecting", "collection failed before any test ran"),
    ("Permission denied", "the command could not be executed"),
)

#: pytest reserves these for usage errors and empty collections, never failures.
PYTEST_NON_FAILURE_EXITS = {2: "interrupted", 3: "internal error", 4: "usage error", 5: "no tests collected"}


def detect_harness_error(output: str, exit_code: int, command: str) -> str | None:
    """Return why the run proves nothing, or None if it genuinely ran tests."""
    if exit_code == 127:
        return "the command was not found (exit 127)"
    if exit_code == 124:
        return "the command timed out before finishing"
    if "pytest" in command and exit_code in PYTEST_NON_FAILURE_EXITS:
        return f"pytest exited {exit_code} ({PYTEST_NON_FAILURE_EXITS[exit_code]}), not a test failure"
    lowered = output.lower()
    for marker, reason in HARNESS_ERROR_MARKERS:
        if marker.lower() in lowered:
            return reason
    return None


def run_command(root: Path, command: str, timeout: int) -> dict[str, Any]:
    """Execute a command and capture its true result."""
    env = {**os.environ, "CI": "1", "NO_COLOR": "1", "FORCE_COLOR": "0"}
    started = time.monotonic()
    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        exit_code = proc.returncode
        output = (proc.stdout or "") + (proc.stderr or "")
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        exit_code = 124
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        output = stdout + stderr
        timed_out = True

    duration = round(time.monotonic() - started, 2)
    return {
        "command": command,
        "exit_code": exit_code,
        "duration_s": duration,
        "timed_out": timed_out,
        "output": output,
    }


def write_log(root: Path, check: str, output: str) -> str:
    """Persist full output so a verdict can be re-audited later."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    path = state_dir(root) / LOG_DIR / f"{check}-{stamp}.log"
    data = output.encode("utf-8", errors="replace")[:MAX_LOG_BYTES]
    path.write_bytes(data)
    return str(path.relative_to(root))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--root", default=".")
    parser.add_argument("--check", required=True, choices=CHECKS)
    parser.add_argument("--command", default=None, help="Command to execute")
    parser.add_argument("--auto", action="store_true", help="Detect the test command")
    parser.add_argument(
        "--none",
        dest="declare_none",
        action="store_true",
        help="Record that this project has no such check (absence is evidence)",
    )
    parser.add_argument("--reason", default=None, help="Why --none applies")
    parser.add_argument("--phase", choices=("before", "after"), default=None)
    parser.add_argument("--test", default=None, help="Test id for red-green proof")
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    run = load_run(root)
    checks = run["checks"]

    if args.declare_none:
        if args.check == "red-green":
            print("red-green proof cannot be declared absent; it is the proof.", file=sys.stderr)
            return 2
        record = {
            "ran": True,
            "kind": "declared-absent",
            "command": None,
            "exit_code": 0,
            "reason": args.reason or "project has no such check configured",
            "at": now_iso(),
        }
        checks[args.check] = record
        save_run(root, run)
        print(f"recorded {args.check}: declared absent ({record['reason']})")
        return 0

    command = args.command
    if not command and args.auto and args.check == "tests":
        detected = detect_test_command(root)
        if not detected:
            print(
                "could not detect a test command; pass --command explicitly",
                file=sys.stderr,
            )
            return 2
        _, command = detected
        print(f"detected test command: {command}")
    if not command:
        print("--command is required (or --auto for tests)", file=sys.stderr)
        return 2

    result = run_command(root, command, args.timeout)
    log_path = write_log(root, args.check, result["output"])
    counts = parse_counts(result["output"]) if args.check in ("tests", "red-green") else {}
    tail = result["output"][-MAX_TAIL_CHARS:]

    harness_error = detect_harness_error(result["output"], result["exit_code"], command)

    if args.check == "red-green":
        if not args.phase:
            print("--phase before|after is required for red-green", file=sys.stderr)
            return 2
        record = checks.get("red-green")
        if not isinstance(record, dict):
            record = {"ran": False}
        record["ran"] = True
        record["command"] = command
        record["test"] = args.test or record.get("test")
        record[f"{args.phase}_exit"] = result["exit_code"]
        record[f"{args.phase}_at"] = now_iso()
        record[f"{args.phase}_log"] = log_path
        record[f"{args.phase}_tail"] = tail
        record[f"{args.phase}_harness_error"] = harness_error
        checks["red-green"] = record
        save_run(root, run)

        before = record.get("before_exit")
        after = record.get("after_exit")
        if harness_error:
            print(
                f"WARNING: this run proves nothing — {harness_error}. A non-zero exit "
                "from a broken command is not a failing test.",
                file=sys.stderr,
            )
        elif args.phase == "before" and result["exit_code"] == 0:
            print(
                "WARNING: the test passed against the unfixed code. It does not "
                "reproduce the bug, so it cannot prove the fix.",
                file=sys.stderr,
            )
        print(
            f"recorded red-green [{args.phase}]: exit={result['exit_code']} "
            f"(before={before}, after={after}) log={log_path}"
        )
        return 0

    record = {
        "ran": True,
        "kind": "executed",
        "command": command,
        "exit_code": result["exit_code"],
        "duration_s": result["duration_s"],
        "timed_out": result["timed_out"],
        "at": now_iso(),
        "log": log_path,
        "tail": tail,
        "harness_error": harness_error,
        **{k: v for k, v in counts.items() if k != "parser"},
    }
    if counts.get("parser"):
        record["parser"] = counts["parser"]
    checks[args.check] = record
    save_run(root, run)
    if harness_error:
        print(f"WARNING: {harness_error} — this run did not verify anything.", file=sys.stderr)

    if args.json:
        print(json.dumps({k: v for k, v in record.items() if k != "tail"}, indent=2))
    else:
        state = "PASS" if result["exit_code"] == 0 else f"FAIL(exit {result['exit_code']})"
        detail = ""
        if counts.get("passed") is not None:
            detail = (
                f"  passed={counts['passed']} failed={counts['failed']} "
                f"skipped={counts['skipped']}"
            )
        print(f"recorded {args.check}: {state}{detail}  [{result['duration_s']}s]  log={log_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
