# dev-autopilot-skill

Drive a feature, change or bug fix from plain-language intent to a pull request that
is already self-verified — plan, implement, test, adversarially review, then gate.

Full instructions: [`SKILL.md`](./SKILL.md).

## When to use this

Activate when the task is any of:

- implement a feature, or change an existing one, end to end
- fix a bug and prove the fix holds
- "is this PR-ready?" / "self-verify this before I look at it"
- generate a PR description carrying an evidence trail
- audit which tests were skipped, disabled, or focused
- make an agent own development from intent through to a pull request

Do **not** use it to review a pull request that already exists — that is
`github-pr-triage-skill`. This skill owns everything *before* the PR; that one owns
everything *after*.

## The rule that defines this skill

**A gate is green only when something ran and left evidence. Silence is never
success.**

An agent that wrote a change is the worst judge of it: it concluded the code was
correct while writing it, so re-reading its own reasoning reproduces that
conclusion. No gate here reads anything you assert. Each reads a machine-produced
observation — a real exit code, a parsed diff, an audited review. A gate with
nothing to read reports `skip`, and a skipped required gate makes `pr_ready`
unreachable.

Never hand-edit `.dev-autopilot/run.json` to make a gate pass.

## Usage

```bash
# Preflight — seconds, catches the expensive-because-late failures
python3 scripts/dev_preflight.py --root .

# The loop: one command, resumable, stops when it needs judgement
python3 scripts/run_pipeline.py --intent "fix the login redirect" --kind bugfix
python3 scripts/run_pipeline.py --continue

# Where is everything
python3 scripts/dev_state.py status --root .
```

The pipeline returns `status: needs_agent` at four handoffs — `plan`,
`write_regression_test`, `implement`, `review` — each with the full payload. Do
exactly the action returned, then run `--continue`.

## Required gates

| Gate | Fails when |
|---|---|
| `diff-present` | Change is empty or the diff is unreadable |
| `focus-guard` | Any `.only` / `fit` / `fdescribe` added — a focused suite exits 0 having run almost nothing |
| `suppression-budget` | Added skips/fixmes over budget (default 0) |
| `tests-pass` | Suite red, vacuous, or the harness never ran tests |
| `red-green-proof` | Bug fix with no test that was red before the fix |
| `changed-code-tested` | Source changed and no test did |
| `review-credible` | No credible review, or unresolved high findings |

Advisory: `static-checks`, `scope`.

## Bug fixes need a red-green proof

A green suite after a fix proves nothing — it was green before the fix too, which is
how the bug shipped. Record both phases:

```bash
# 1. Write the failing test. Fix NOTHING yet. Must exit non-zero.
python3 scripts/record_check.py --check red-green --phase before \
    --test 'test_x' --command 'pytest -q tests/test_x.py::test_x'

# 2. Apply the fix. Must exit zero.
python3 scripts/record_check.py --check red-green --phase after \
    --command 'pytest -q tests/test_x.py::test_x'
```

A non-zero exit from a *broken* command is detected and rejected — it is not a
failing test.

## Reviewing your own change

Run it only once the change is stable and green. Build the pack, review against all
five dimensions (correctness, security, data-safety, error-handling,
intent-fidelity), write findings with file, line, severity and a `why` that names
the failure caused — then audit.

The audit rejects an unexplained clean review on a large or high-risk change,
because "I found nothing" from the agent that wrote the code is the single most
likely way self-review fails.

## Composition

| Phase | Delegates to when installed | Standalone fallback |
|---|---|---|
| Plan | `openspec-autopilot-skill` | `.dev-autopilot/plan.md` |
| Browser tests | `playwright-test-autopilot-skill` | Unit tests only |
| Post-PR review | `github-pr-triage-skill` | Human review |

Sibling absence is never an error. `dev_preflight.py` reports what is available.

## Notes

- State lives in `.dev-autopilot/` — add it to `.gitignore`
- An interrupted run resumes; ask the state machine, never infer from memory
- Three identical actions in a row escalates to `blocked` rather than spinning
- Python 3.9+, git. No third-party dependencies.
