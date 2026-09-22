#!/usr/bin/env python3
"""Self-test: drive the loop against throwaway repositories and assert behaviour.

Every claim this skill makes about safety is a claim about what the code does
when an agent misbehaves. These tests make the misbehaviour happen on purpose —
a reproducer that reproduces nothing, a contract edited after locking, a suite
turned green by skipping the failing test — and assert the loop catches it.

Each subcommand builds a fresh git repository under a temporary directory, runs
the real scripts against it, and cleans up. Nothing touches the current repo.

    selftest.py all
    selftest.py tamper
    selftest.py holdout

Exit codes: 0 all assertions held, 1 a behaviour regressed.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable

sys.dont_write_bytecode = True

SCRIPTS = Path(__file__).resolve().parent
TEST_CMD = "python3 -m unittest discover -s tests -q"

BUGGY = 'def apply_discount(price, pct):\n    return price - price * pct / 100\n'
FIXED = 'def apply_discount(price, pct):\n    return max(0, price - price * pct / 100)\n'

BASE_TEST = """import unittest, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from calc import apply_discount

class TestBasic(unittest.TestCase):
    def test_half_off(self):
        self.assertEqual(apply_discount(100, 50), 50)
"""

REAL_REPRODUCER = """import unittest, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from calc import apply_discount

class TestFloor(unittest.TestCase):
    def test_never_negative(self):
        self.assertEqual(apply_discount(100, 150), 0)
"""

FAKE_REPRODUCER = """import unittest, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from calc import apply_discount

class TestFloor(unittest.TestCase):
    def test_already_passes(self):
        self.assertEqual(apply_discount(100, 50), 50)
"""

SKIPPED_REPRODUCER = """import unittest, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from calc import apply_discount

class TestFloor(unittest.TestCase):
    @unittest.skip("flaky, revisit later")
    def test_never_negative(self):
        self.assertEqual(apply_discount(100, 150), 0)
"""


class Failed(AssertionError):
    """A behaviour this skill promises did not hold."""


def sh(cmd: list[str], cwd: Path, check: bool = False) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)  # noqa: S603
    if check and proc.returncode != 0:
        raise Failed(f"{' '.join(cmd)} exited {proc.returncode}\n{proc.stdout}\n{proc.stderr}")
    return proc


def pipeline(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return sh([sys.executable, str(SCRIPTS / "run_pipeline.py"), "--root", str(root), *args], root)


def make_repo(tmp: Path) -> Path:
    """A minimal Python repo with a real bug and a green existing test."""
    root = tmp / "repo"
    (root / "tests").mkdir(parents=True)
    (root / "calc.py").write_text(BUGGY, encoding="utf-8")
    (root / "tests" / "test_basic.py").write_text(BASE_TEST, encoding="utf-8")
    (root / "pyproject.toml").write_text('[project]\nname = "t"\nversion = "0.1.0"\n', encoding="utf-8")
    sh(["git", "init", "-q"], root, check=True)
    sh(["git", "config", "user.email", "selftest@example.com"], root, check=True)
    sh(["git", "config", "user.name", "Selftest"], root, check=True)
    sh(["git", "add", "-A"], root, check=True)
    sh(["git", "commit", "-qm", "initial"], root, check=True)
    sh(["git", "checkout", "-q", "-b", "work"], root, check=True)
    return root


def bind_test_command(root: Path) -> None:
    """Stand in for the agent's review_contract step: point criteria at a real runner."""
    path = root / ".autoresearch" / "contract.json"
    contract = json.loads(path.read_text(encoding="utf-8"))
    contract["toolchain"]["test"] = TEST_CMD
    for crit in contract["criteria"]:
        if "MISSING-TEST-COMMAND" in crit["cmd"] or crit["cmd"].startswith("python3 -m pytest"):
            crit["cmd"] = TEST_CMD
    path.write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")


def lock(root: Path) -> subprocess.CompletedProcess[str]:
    return sh([sys.executable, str(SCRIPTS / "contract.py"), "lock", "--root", str(root)], root)


def start_bugfix(root: Path) -> None:
    pipeline(root, "--task", "apply_discount must never return a negative price", "--kind", "bugfix")
    bind_test_command(root)
    lock(root)


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise Failed(message)


# --------------------------------------------------------------------------
# the behaviours
# --------------------------------------------------------------------------


def test_lock(root: Path) -> None:
    """A contract can be built, locked, and verified."""
    start_bugfix(root)
    verify = sh([sys.executable, str(SCRIPTS / "contract.py"), "verify", "--root", str(root)], root)
    expect(verify.returncode == 0, f"verify should pass on an untouched locked contract, got {verify.returncode}")
    contract = json.loads((root / ".autoresearch" / "contract.json").read_text(encoding="utf-8"))
    expect(bool(contract.get("lock", {}).get("digest")), "locking must record a digest")


def test_tamper(root: Path) -> None:
    """Weakening a criterion after locking voids the run."""
    start_bugfix(root)
    path = root / ".autoresearch" / "contract.json"
    contract = json.loads(path.read_text(encoding="utf-8"))
    contract["criteria"][1]["cmd"] = "true"          # the classic: make a check trivially pass
    path.write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")

    verify = sh([sys.executable, str(SCRIPTS / "contract.py"), "verify", "--root", str(root)], root)
    expect(verify.returncode == 3, f"tampering must exit 3, got {verify.returncode}")
    expect("TAMPERED" in verify.stdout + verify.stderr, "the tamper message must name what happened")

    scored = sh([sys.executable, str(SCRIPTS / "score.py"), "--root", str(root), "--phase", "attempt"], root)
    expect(scored.returncode == 3, f"scoring a tampered contract must refuse, got {scored.returncode}")


def test_red_baseline(root: Path) -> None:
    """A reproducer that passes at baseline is rejected, not rewarded."""
    start_bugfix(root)
    pipeline(root, "--continue")                                   # -> write_reproducer
    (root / "tests" / "test_floor.py").write_text(FAKE_REPRODUCER, encoding="utf-8")
    out = pipeline(root, "--continue").stdout
    expect("fix_reproducer" in out, f"a non-reproducing test must be rejected; got:\n{out}")


def test_discard(root: Path) -> None:
    """A non-improving attempt is reset away and leaves nothing behind."""
    start_bugfix(root)
    pipeline(root, "--continue")
    (root / "tests" / "test_floor.py").write_text(REAL_REPRODUCER, encoding="utf-8")
    baseline = pipeline(root, "--continue").stdout
    expect("implement" in baseline, f"baseline should ask for an implementation; got:\n{baseline}")

    noise = BUGGY.replace("def apply_discount", '"""Unrelated prose."""\n\n\ndef apply_discount')
    (root / "calc.py").write_text(noise, encoding="utf-8")
    out = pipeline(root, "--continue").stdout
    expect("discard" in out, f"a change that fixes nothing must be discarded; got:\n{out}")
    expect(
        (root / "calc.py").read_text(encoding="utf-8") == BUGGY,
        "a discard must restore the tree exactly",
    )


def test_keep_and_complete(root: Path) -> None:
    """A real fix is kept and the run reaches a verified completion."""
    start_bugfix(root)
    pipeline(root, "--continue")
    (root / "tests" / "test_floor.py").write_text(REAL_REPRODUCER, encoding="utf-8")
    pipeline(root, "--continue")
    (root / "calc.py").write_text(FIXED, encoding="utf-8")
    out = pipeline(root, "--continue").stdout
    expect("complete" in out, f"a real fix must complete the run; got:\n{out}")
    rows = (root / ".autoresearch" / "ledger.tsv").read_text(encoding="utf-8")
    expect("baseline" in rows and "keep" in rows, f"the ledger must record the run; got:\n{rows}")


def test_holdout(root: Path) -> None:
    """Reaching green by skipping the failing test is caught as overfit."""
    start_bugfix(root)
    pipeline(root, "--continue")
    (root / "tests" / "test_floor.py").write_text(REAL_REPRODUCER, encoding="utf-8")
    pipeline(root, "--continue")
    # The cheat: suppress the failing test instead of fixing the code.
    (root / "tests" / "test_floor.py").write_text(SKIPPED_REPRODUCER, encoding="utf-8")
    out = pipeline(root, "--continue").stdout
    expect("fix_overfit" in out, f"skipping to green must be caught by the holdout; got:\n{out}")
    expect("no-new-suppressions" in out, f"the failing holdout check must be named; got:\n{out}")


def test_scope(root: Path) -> None:
    """A change outside the declared scope fails the scope guard."""
    pipeline(root, "--task", "floor the discount", "--kind", "bugfix", "--scope", "calc.py")
    bind_test_command(root)
    lock(root)
    (root / "elsewhere.py").write_text("SECRET = 1\n", encoding="utf-8")
    guard = sh(
        [sys.executable, str(SCRIPTS / "guards.py"), "scope", "--root", str(root), "--base", "HEAD"],
        root,
    )
    expect(guard.returncode != 0, "a file outside scope must fail the scope guard")
    expect("elsewhere.py" in guard.stdout + guard.stderr, "the guard must name the offending file")


CASES: dict[str, Callable[[Path], None]] = {
    "lock": test_lock,
    "tamper": test_tamper,
    "red-baseline": test_red_baseline,
    "discard": test_discard,
    "keep-complete": test_keep_and_complete,
    "holdout": test_holdout,
    "scope": test_scope,
}


def run_case(name: str) -> bool:
    tmp = Path(tempfile.mkdtemp(prefix=f"car-selftest-{name}-"))
    try:
        root = make_repo(tmp)
        CASES[name](root)
    except Failed as exc:
        print(f"FAIL {name}: {exc}", file=sys.stderr)
        return False
    except Exception as exc:  # noqa: BLE001 - a self-test must report, not traceback
        print(f"ERROR {name}: {type(exc).__name__}: {exc}", file=sys.stderr)
        return False
    else:
        print(f"ok   {name}")
        return True
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("case", choices=[*sorted(CASES), "all"], nargs="?", default="all")
    args = parser.parse_args(argv)

    if shutil.which("git") is None:
        print("error: git is required for the self-test", file=sys.stderr)
        return 1

    names = sorted(CASES) if args.case == "all" else [args.case]
    results = [run_case(name) for name in names]
    passed, total = sum(results), len(results)
    print(f"\n{passed}/{total} behaviours held")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
