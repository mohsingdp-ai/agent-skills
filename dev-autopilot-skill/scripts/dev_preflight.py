#!/usr/bin/env python3
"""Check the environment before an unattended run spends an hour failing.

Everything here is cheap and everything here has stranded a real run. The
expensive failures in autonomous development are not clever — they are a
detached HEAD, an unresolvable base ref, or a test command that does not exist,
discovered forty minutes in.

It also reports which **sibling skills** are installed. This skill composes
rather than reimplements: when ``openspec-autopilot-skill`` is present the
planning phase delegates to it, and when ``playwright-test-autopilot-skill`` is
present the browser-verification phase delegates to that. Neither is required —
their absence degrades the loop to plain-file planning and unit tests, which is
still a complete loop — so both are reported as capabilities, never as errors.

Exit codes:
    0  ready to run unattended
    2  fixable — every finding carries the command that fixes it
    1  hard stop — the run cannot proceed

Usage:
    python3 dev_preflight.py --root . --json
    python3 dev_preflight.py --root . --base origin/main
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import diff_intel  # noqa: E402

SCHEMA_VERSION = "1.0"

SIBLING_SKILLS = {
    "openspec-autopilot-skill": "spec-driven planning (propose → tasks → archive)",
    "playwright-test-autopilot-skill": "browser verification (plan → generate → heal)",
    "github-pr-triage-skill": "post-PR review triage once the PR is opened",
}

SKILL_SEARCH_PATHS = (
    "~/.claude/skills",
    "~/.agents/skills",
    "~/.copilot/skills",
    "~/.gemini/skills",
    "~/.config/opencode/skills",
    ".claude/skills",
    ".agents/skills",
)

LINT_MARKERS: tuple[tuple[str, str, str], ...] = (
    ("ruff", "ruff.toml", "ruff check ."),
    ("ruff", ".ruff.toml", "ruff check ."),
    ("eslint", ".eslintrc.json", "npx eslint ."),
    ("eslint", ".eslintrc.js", "npx eslint ."),
    ("eslint", "eslint.config.js", "npx eslint ."),
    ("eslint", "eslint.config.mjs", "npx eslint ."),
    ("golangci", ".golangci.yml", "golangci-lint run"),
    ("rubocop", ".rubocop.yml", "bundle exec rubocop"),
    ("clippy", "Cargo.toml", "cargo clippy -- -D warnings"),
)

TYPECHECK_MARKERS: tuple[tuple[str, str, str], ...] = (
    ("tsc", "tsconfig.json", "npx tsc --noEmit"),
    ("mypy", "mypy.ini", "mypy ."),
    ("pyright", "pyrightconfig.json", "npx pyright"),
)


def finding(code: str, severity: str, message: str, fix: str) -> dict[str, str]:
    return {"code": code, "severity": severity, "message": message, "fix": fix}


def git_ok(root: Path, *args: str) -> tuple[bool, str]:
    try:
        proc = subprocess.run(
            ["git", *args], cwd=str(root), capture_output=True, text=True, timeout=60
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False, ""
    return proc.returncode == 0, proc.stdout.strip()


def check_git(root: Path, base: str | None) -> tuple[list[dict[str, str]], dict[str, Any]]:
    """Repository state: is this a repo, where is HEAD, what do we diff against."""
    findings: list[dict[str, str]] = []
    info: dict[str, Any] = {}

    if not shutil.which("git"):
        findings.append(
            finding(
                "no_git", "error",
                "git is not on PATH; every gate in this skill reads the diff.",
                "Install git.",
            )
        )
        return findings, info

    inside, _ = git_ok(root, "rev-parse", "--is-inside-work-tree")
    if not inside:
        findings.append(
            finding(
                "not_a_repo", "error",
                f"{root} is not a git repository, so there is no diff to verify.",
                f"Run: git init {root}   (or run from inside the project)",
            )
        )
        return findings, info

    ok, branch = git_ok(root, "rev-parse", "--abbrev-ref", "HEAD")
    info["branch"] = branch if ok else None
    if branch == "HEAD":
        findings.append(
            finding(
                "detached_head", "error",
                "HEAD is detached. Commits made here are unreachable once the run ends, "
                "so the change cannot become a PR.",
                "Run: git switch -c <branch-name>",
            )
        )

    ok, default_branch = git_ok(root, "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD")
    info["default_branch"] = default_branch.split("/")[-1] if ok and default_branch else None

    if branch and branch == (info["default_branch"] or "main"):
        findings.append(
            finding(
                "on_default_branch", "warning",
                f"Working directly on '{branch}'. A PR needs a branch of its own.",
                f"Run: git switch -c <feature-branch>",
            )
        )

    try:
        resolved = diff_intel.resolve_base(root, base)
        info["base"] = resolved
        info["merge_base"] = diff_intel.merge_base(root, resolved)
    except diff_intel.GitError as exc:
        info["base"] = None
        findings.append(
            finding(
                "no_base_ref", "error",
                f"No base ref to diff against: {exc}. Without one, nothing can tell "
                "which lines this change introduced.",
                "Pass --base <ref> explicitly, or run: git fetch origin",
            )
        )

    ok, status = git_ok(root, "status", "--porcelain")
    info["dirty_files"] = len([ln for ln in status.splitlines() if ln.strip()]) if ok else None

    ok, remotes = git_ok(root, "remote")
    info["remotes"] = remotes.split() if ok and remotes else []
    if not info["remotes"]:
        findings.append(
            finding(
                "no_remote", "warning",
                "No git remote configured, so the loop can reach PR-ready but cannot open a PR.",
                "Run: git remote add origin <url>",
            )
        )
    return findings, info


def check_toolchain(root: Path) -> tuple[list[dict[str, str]], dict[str, Any]]:
    """What can this project actually run?"""
    findings: list[dict[str, str]] = []
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import record_check  # noqa: E402  (local import keeps preflight importable standalone)

    detected = record_check.detect_test_command(root)
    info: dict[str, Any] = {
        "test_runner": detected[0] if detected else None,
        "test_command": detected[1] if detected else None,
    }
    if not detected:
        findings.append(
            finding(
                "no_test_command", "error",
                "No test command could be detected. The tests-pass gate is required, and "
                "it cannot pass without a suite to run.",
                "Add a test script to package.json / pyproject.toml, or pass the command "
                "explicitly: record_check.py --check tests --command '<cmd>'",
            )
        )

    for name, marker, command in LINT_MARKERS:
        if (root / marker).is_file():
            info["lint"] = {"tool": name, "command": command}
            break
    else:
        info["lint"] = None

    for name, marker, command in TYPECHECK_MARKERS:
        if (root / marker).is_file():
            info["typecheck"] = {"tool": name, "command": command}
            break
    else:
        info["typecheck"] = None

    info["package_manager"] = None
    for lock, manager in (
        ("pnpm-lock.yaml", "pnpm"), ("yarn.lock", "yarn"),
        ("bun.lockb", "bun"), ("package-lock.json", "npm"),
    ):
        if (root / lock).is_file():
            info["package_manager"] = manager
            break

    info["gh_cli"] = bool(shutil.which("gh"))
    info["glab_cli"] = bool(shutil.which("glab"))
    if not info["gh_cli"] and not info["glab_cli"]:
        findings.append(
            finding(
                "no_forge_cli", "warning",
                "Neither gh nor glab is installed, so the run stops at PR-ready and the "
                "PR must be opened by hand.",
                "Install GitHub CLI (gh) or GitLab CLI (glab).",
            )
        )
    return findings, info


def check_siblings(root: Path) -> dict[str, Any]:
    """Report which composable skills are available.

    Never a finding. This skill runs standalone; siblings only make phases
    richer.
    """
    found: dict[str, Any] = {}
    for name, purpose in SIBLING_SKILLS.items():
        location = None
        for base in SKILL_SEARCH_PATHS:
            candidate = (
                Path(base).expanduser() if base.startswith("~") else root / base
            ) / name
            if candidate.exists():
                location = str(candidate)
                break
        found[name] = {"installed": location is not None, "path": location, "purpose": purpose}
    return found


def check_project_signals(root: Path) -> dict[str, Any]:
    """Cheap signals that change how the loop behaves."""
    return {
        "has_openspec": (root / "openspec").is_dir(),
        "has_playwright_config": any(
            (root / name).is_file()
            for name in ("playwright.config.ts", "playwright.config.js", "playwright.config.mjs")
        ),
        "has_specs_dir": (root / "specs").is_dir(),
        "conventions": [
            name for name in ("AGENTS.md", "CLAUDE.md", "CONTRIBUTING.md", "CONVENTIONS.md")
            if (root / name).is_file()
        ] + (["`.augment/rules`"] if (root / ".augment" / "rules").is_dir() else []),
        "state_dir_exists": (root / ".dev-autopilot").is_dir(),
    }


def run_all(root: Path, base: str | None = None) -> dict[str, Any]:
    findings: list[dict[str, str]] = []

    git_findings, git_info = check_git(root, base)
    findings.extend(git_findings)

    if any(f["code"] in ("no_git", "not_a_repo") for f in findings):
        tool_info: dict[str, Any] = {}
    else:
        tool_findings, tool_info = check_toolchain(root)
        findings.extend(tool_findings)

    findings.sort(key=lambda f: (0 if f["severity"] == "error" else 1, f["code"]))
    errors = [f for f in findings if f["severity"] == "error"]

    return {
        "schema_version": SCHEMA_VERSION,
        "root": str(root),
        "ready": not errors,
        "findings": findings,
        "errors": len(errors),
        "warnings": len(findings) - len(errors),
        "git": git_info,
        "toolchain": tool_info,
        "siblings": check_siblings(root),
        "project": check_project_signals(root),
    }


def render(report: dict[str, Any]) -> str:
    lines: list[str] = []
    state = "READY" if report["ready"] else "NOT READY"
    lines.append(f"preflight: {state}  ({report['errors']} errors, {report['warnings']} warnings)")
    git_info = report.get("git", {})
    lines.append(
        f"  repo     branch={git_info.get('branch')} base={git_info.get('base')} "
        f"dirty={git_info.get('dirty_files')}"
    )
    tools = report.get("toolchain", {})
    lint = (tools.get("lint") or {}).get("tool")
    types = (tools.get("typecheck") or {}).get("tool")
    lines.append(
        f"  tools    tests={tools.get('test_command')} lint={lint} typecheck={types}"
    )
    siblings = [n for n, v in report.get("siblings", {}).items() if v["installed"]]
    lines.append(f"  siblings {', '.join(siblings) if siblings else 'none (standalone mode)'}")
    if report["findings"]:
        lines.append("")
        for item in report["findings"]:
            lines.append(f"  [{item['severity']}] {item['code']}: {item['message']}")
            lines.append(f"      fix: {item['fix']}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--root", default=".")
    parser.add_argument("--base", default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    root = Path(args.root).resolve()
    report = run_all(root, args.base)

    text = json.dumps(report, indent=2)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    if args.json:
        print(text)
    else:
        print(render(report))

    if not report["ready"]:
        hard = any(f["code"] in ("no_git", "not_a_repo") for f in report["findings"])
        return 1 if hard else 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
