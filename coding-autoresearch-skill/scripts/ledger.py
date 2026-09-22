#!/usr/bin/env python3
"""The attempt ledger — the thing a human reads in the morning.

autoresearch logs every experiment to a tab-separated ``results.tsv`` that stays
untracked, with one row per experiment and a status of keep / discard / crash.
This is the same file with the columns a coding run needs: the score replaces
``val_bpb``, and changed-lines replaces ``memory_gb`` as the cost being traded off.

Tab-separated, deliberately: descriptions contain commas.

Commands
--------
    ledger.py append --commit abc1234 --score 4 --max 5 --complexity 37 \\
                     --status keep --description "cache the resolved config"
    ledger.py rows [--root .] [--json]
    ledger.py report [--root .] [--output report.md]
    ledger.py best [--root .]
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

# Never leave __pycache__ in the repository under test: an untracked byte-cache
# directory reads as a dirty tree and would be swept away by a discard.
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

from contract import STATE_DIR, load_contract  # noqa: E402

LEDGER_FILE = "ledger.tsv"
COLUMNS = ["attempt", "commit", "score", "max_score", "complexity", "status", "description"]

STATUS_KEEP = "keep"
STATUS_DISCARD = "discard"
STATUS_CRASH = "crash"
STATUS_BASELINE = "baseline"
STATUS_COMPLETE = "complete"
STATUS_BLOCKED = "blocked"
STATUS_OVERFIT = "overfit"

VALID_STATUS = {
    STATUS_KEEP, STATUS_DISCARD, STATUS_CRASH, STATUS_BASELINE,
    STATUS_COMPLETE, STATUS_BLOCKED, STATUS_OVERFIT,
}


def ledger_path(root: Path) -> Path:
    return root / STATE_DIR / LEDGER_FILE


def ensure_ledger(root: Path) -> Path:
    path = ledger_path(root)
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            csv.writer(handle, delimiter="\t", lineterminator="\n").writerow(COLUMNS)
    return path


def read_rows(root: Path) -> list[dict[str, Any]]:
    path = ledger_path(root)
    if not path.is_file():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    parsed: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        for key in ("attempt", "score", "max_score", "complexity"):
            try:
                item[key] = int(row.get(key, "0") or 0)
            except (TypeError, ValueError):
                item[key] = 0
        parsed.append(item)
    return parsed


def next_attempt(root: Path) -> int:
    rows = read_rows(root)
    return max((r["attempt"] for r in rows), default=-1) + 1


def append(
    root: Path,
    commit: str,
    score: int,
    max_score: int,
    complexity: int,
    status: str,
    description: str,
    attempt: int | None = None,
) -> int:
    """Append one attempt. Tabs and newlines are stripped from the description."""
    if status not in VALID_STATUS:
        raise ValueError(f"invalid status {status!r}; expected one of {sorted(VALID_STATUS)}")
    ensure_ledger(root)
    number = next_attempt(root) if attempt is None else attempt
    clean = " ".join(description.replace("\t", " ").split())
    with ledger_path(root).open("a", encoding="utf-8", newline="") as handle:
        csv.writer(handle, delimiter="\t", lineterminator="\n").writerow(
            [number, commit, score, max_score, complexity, status, clean]
        )
    return number


def best_row(root: Path) -> dict[str, Any] | None:
    """The high-water mark: highest score, then lowest complexity.

    This is the simplicity criterion made mechanical — among attempts that score
    the same, the one that changed fewer lines is better, so deleting code to
    reach an equal score is a win rather than a wash.
    """
    kept = [r for r in read_rows(root) if r["status"] in {STATUS_KEEP, STATUS_BASELINE, STATUS_COMPLETE}]
    if not kept:
        return None
    return max(kept, key=lambda r: (r["score"], -r["complexity"], r["attempt"]))


def render_report(root: Path) -> str:
    """Markdown summary of the run — the morning read."""
    rows = read_rows(root)
    try:
        contract = load_contract(root)
        task = contract.get("task", "(unknown task)")
        kind = contract.get("kind", "?")
    except Exception:  # noqa: BLE001 - a report must render even without a contract
        task, kind = "(no contract found)", "?"

    if not rows:
        return f"# autoresearch run\n\n**Task:** {task} (`{kind}`)\n\nNo attempts recorded yet.\n"

    kept = [r for r in rows if r["status"] == STATUS_KEEP]
    discarded = [r for r in rows if r["status"] == STATUS_DISCARD]
    crashed = [r for r in rows if r["status"] == STATUS_CRASH]
    best = best_row(root)
    final = rows[-1]

    lines = [
        "# autoresearch run",
        "",
        f"**Task:** {task}",
        f"**Kind:** `{kind}`",
        f"**Attempts:** {len(rows)}  ·  kept {len(kept)}  ·  discarded {len(discarded)}  ·  crashed {len(crashed)}",
    ]
    if best:
        lines.append(f"**Best:** {best['score']}/{best['max_score']} at `{best['commit']}` "
                     f"({best['complexity']} changed lines)")
    lines.append(f"**Final status:** `{final['status']}`")
    lines += [
        "",
        "| # | commit | score | changed lines | status | what was tried |",
        "|---:|---|---:|---:|---|---|",
    ]
    for row in rows:
        score = f"{row['score']}/{row['max_score']}"
        desc = row["description"].replace("|", "\\|")
        lines.append(
            f"| {row['attempt']} | `{row['commit']}` | {score} | {row['complexity']} | "
            f"{row['status']} | {desc} |"
        )

    lines += ["", "## How to read this", "",
              "`keep` advanced the branch (the score improved, or matched at lower complexity).",
              "`discard` was reset away — the branch never carried it.",
              "`crash` means the check could not run at all, which is not the same as failing it.",
              "`overfit` means the visible criteria were satisfied but a holdout check caught it.",
              ""]
    return "\n".join(lines)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def _cmd_append(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    number = append(
        root, args.commit, args.score, args.max, args.complexity,
        args.status, args.description, args.attempt,
    )
    print(f"attempt {number} recorded ({args.status})")
    return 0


def _cmd_rows(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    rows = read_rows(root)
    if args.json:
        print(json.dumps(rows, indent=2))
        return 0
    if not rows:
        print("no attempts recorded")
        return 0
    print("\t".join(COLUMNS))
    for row in rows:
        print("\t".join(str(row.get(col, "")) for col in COLUMNS))
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    text = render_report(root)
    if args.output:
        out = Path(args.output)
        if not out.is_absolute():
            out = root / out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(f"report written: {out}")
    else:
        print(text)
    return 0


def _cmd_best(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    best = best_row(root)
    if not best:
        print("no kept attempts yet")
        return 1
    print(json.dumps(best, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    ap = sub.add_parser("append", help="record one attempt")
    ap.add_argument("--root", default=".")
    ap.add_argument("--commit", required=True)
    ap.add_argument("--score", type=int, required=True)
    ap.add_argument("--max", type=int, required=True)
    ap.add_argument("--complexity", type=int, default=0)
    ap.add_argument("--status", required=True, choices=sorted(VALID_STATUS))
    ap.add_argument("--description", required=True)
    ap.add_argument("--attempt", type=int, default=None)
    ap.set_defaults(func=_cmd_append)

    rows = sub.add_parser("rows", help="print the ledger")
    rows.add_argument("--root", default=".")
    rows.add_argument("--json", action="store_true")
    rows.set_defaults(func=_cmd_rows)

    report = sub.add_parser("report", help="render the markdown run report")
    report.add_argument("--root", default=".")
    report.add_argument("--output", default=None)
    report.set_defaults(func=_cmd_report)

    best = sub.add_parser("best", help="print the high-water-mark attempt")
    best.add_argument("--root", default=".")
    best.set_defaults(func=_cmd_best)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
