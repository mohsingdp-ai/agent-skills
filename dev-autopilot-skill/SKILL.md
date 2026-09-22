---
name: dev-autopilot-skill
description: >-
  Drive a feature, change or bug fix from plain-language intent to a PR a human can
  trust — plan, implement, test, self-review, then gate. Replaces the human
  checkpoints in spec-driven planning, browser test generation and deep code review
  with machine gates that read evidence rather than the agent's opinion of its own
  work: a red-green proof that a bug fix reproduced the bug before it was fixed, a
  focus-marker guard that catches .only silently narrowing a suite to nothing, a
  suppression budget that stops tests being skipped to reach green, scope-drift
  detection, and a review-credibility audit that rejects an agent rubber-stamping
  its own change. Use when asked to implement a feature, fix a bug, ship a change
  end to end, self-verify work before opening a PR, check whether a change is
  PR-ready, generate a PR description with an evidence trail, audit skipped or
  focused tests, or make an agent own development from intent to pull request.
license: MIT
activation: /dev-autopilot-skill
provenance:
  maintainer: Mohsin Ejaz
  version: 1.0.0
  created: 2026-08-08
  source_references:
    - https://www.augmentcode.com/workflows/coding/deep-code-reviewer
    - https://playwright.dev/docs/test-agents
    - https://github.com/Fission-AI/OpenSpec/blob/main/docs/workflows.md
metadata:
  author: Mohsin Ejaz
  version: 1.0.0
  created: 2026-08-08
  last_reviewed: 2026-08-08
  review_interval_days: 90
  composes_with:
    - openspec-autopilot-skill
    - playwright-test-autopilot-skill
    - github-pr-triage-skill
  dependencies:
    - url: https://www.augmentcode.com/workflows/coding/deep-code-reviewer
      name: Augment deep code reviewer workflow
      type: docs
    - url: https://playwright.dev/docs/test-agents
      name: Playwright Test Agents
      type: docs
    - url: https://github.com/Fission-AI/OpenSpec/blob/main/docs/workflows.md
      name: OpenSpec workflows
      type: docs
---
# /dev-autopilot-skill — Intent to PR, Self-Verified

You take a plain-language intent — a new feature, a change to an existing one, or a
bug — and drive it to a pull request that a human can trust without re-doing your
work. Plan, implement, test, review your own change adversarially, and stop at a
verdict that is computed, not claimed.

## Trigger

```
/dev-autopilot-skill add rate limiting to the public API
/dev-autopilot-skill fix the login redirect dropping the return URL
/dev-autopilot-skill --continue                    # resume an interrupted run
/dev-autopilot-skill status                        # where is everything
/dev-autopilot-skill verify                        # gate the current diff, no build
/dev-autopilot-skill --scope 'src/api/**' add pagination to /orders
```

Also activates on: "implement X and open a PR", "fix this bug end to end",
"is this PR-ready", "self-verify before I review it", "check what tests got skipped".

## The one rule everything rests on

**A gate is green only when something ran and left evidence. Silence is never
success.**

An agent reviewing a change it wrote is the weakest link in autonomous
development. It concluded the code was correct while writing it, so re-reading its
own reasoning reproduces the same conclusion. Ask it "is this ready?" and you get
back a restatement of its intentions, not an assessment of its output.

So no gate here ever reads something you assert. Each one reads a machine-produced
observation — a command's real exit code captured by `record_check.py`, a parsed
diff, an audited review record. A gate with nothing to read reports `skip`, and a
skipped required gate makes `pr_ready` **unreachable**. You cannot talk your way to
green; you can only run things.

The three sources this skill is built on are all human-in-the-loop by design.
Augment's reviewer posts severity-tagged comments *for a person*. Playwright's
healer is told to `test.fixme()` when it gives up, which is sensible under review
and a trapdoor without one. OpenSpec's `verify` "surfaces warnings but doesn't
block archiving". Take the human out of all three and you get an agent grading its
own homework. The gates are what replaces that human.

## Step 0 — Preflight, always

```bash
python3 scripts/dev_preflight.py --root .
```

Exit 0 ready, 2 fixable (each finding carries its command), 1 hard stop. It catches
the expensive-because-late failures: detached HEAD, no resolvable base ref, no test
command, working directly on `main`.

It also reports which sibling skills are installed. **Their absence is never an
error** — the loop runs standalone. See "Composition" below.

## The loop

Ask what to do, do exactly that, ask again:

```bash
python3 scripts/run_pipeline.py --intent "fix the login redirect" --kind bugfix
python3 scripts/run_pipeline.py --continue
```

`run_pipeline.py` does everything code can do — preflight, diff analysis, running
and recording checks, building the review pack, evaluating gates, writing the PR
body — and stops with `status: needs_agent` the moment it hits something needing
judgement. Sequencing lives in code, so you run one command instead of re-deriving
an eight-step order and eventually getting it wrong.

State lives on disk under `.dev-autopilot/`, so an interrupted or compacted run
resumes exactly where it stopped. Never infer state from memory — ask again.

| `action` | What you do |
|---|---|
| `fix_preflight` | Fix each finding in `payload.findings`; each carries its `fix` |
| `plan` | Write the plan to `payload.write_to` — or delegate (see Composition) |
| `write_regression_test` | **Bug fixes only.** Write a test that fails against today's code |
| `implement` | Write the code |
| `collect_evidence` | The pipeline runs these itself; if handed to you, run the listed commands |
| `review` | Deep-review the change against the built pack (see below) |
| `fix_blockers` | Fix each blocker in `payload.blockers`, then re-enter the loop |
| `open_pr` | `.dev-autopilot/PR.md` is written — open the PR |
| `done` | Stop, report what shipped |
| `blocked` | Stop and escalate `payload.reason` verbatim. Do not improvise |

Three identical actions in a row means the loop is not converging; it escalates to
`blocked` rather than spinning.

## The gates

| Gate | Required | Fails when |
|---|---|---|
| `diff-present` | ● | The change is empty or the diff is unreadable |
| `focus-guard` | ● | Any `.only` / `fit` / `fdescribe` was added |
| `suppression-budget` | ● | Added skips/fixmes exceed budget (default **0**) |
| `tests-pass` | ● | Suite red, vacuous (0 tests), or the harness never ran |
| `red-green-proof` | ● | Bug fix without a test that was red before the fix |
| `changed-code-tested` | ● | Source changed and no test did |
| `review-credible` | ● | No credible review, or unresolved high findings |
| `static-checks` | ○ | Lint / types / build failing |
| `scope` | ○ | Files changed outside the declared scope |

Verdicts: `pr_ready` (all required gates pass with evidence) · `needs_evidence` (a
required gate has nothing to read) · `blocked` (a gate failed).

```bash
python3 scripts/dev_state.py status --root .        # the full gate table
```

## Recording evidence

Only `record_check.py` produces evidence, because it executes the command and
captures the real exit code:

```bash
python3 scripts/record_check.py --check tests --auto
python3 scripts/record_check.py --check lint --command 'ruff check .'
python3 scripts/record_check.py --check typecheck --none --reason 'no type checker'
```

`--none` records an explicit "this project has no such check" — absence of a tool
is a real observation, unlike absence of a run.

**Never hand-edit `.dev-autopilot/run.json` to make a gate pass.** That is the one
action that breaks the entire contract, and the logs under `.dev-autopilot/logs/`
make it visible in review anyway.

## Bug fixes: the red-green proof

The gate people skip, and the reason "fixed" bugs come back.

A green suite *after* a fix proves nothing — it was green *before* the fix too,
which is exactly how the bug shipped. The only proof that a fix addresses the
reported bug is a test that fails without it.

```bash
# 1. Write the smallest test that reproduces the bug. Fix NOTHING yet.
python3 scripts/record_check.py --check red-green --phase before \
    --test 'test_never_negative' --command 'pytest -q tests/test_x.py::test_never_negative'
#    -> must exit NON-ZERO. If it passes, the test does not reproduce the bug.

# 2. Now apply the fix.
python3 scripts/record_check.py --check red-green --phase after \
    --command 'pytest -q tests/test_x.py::test_never_negative'
#    -> must exit ZERO.
```

A non-zero exit from a *broken* command (missing runner, typo'd path, collection
error) is detected and rejected — it is not a failing test, and accepting it would
let a typo stand in for the whole proof.

## The deep review

Run it only once the change is stable and green, so you review what will actually
ship.

```bash
python3 scripts/review_pack.py build --root . --intent "<intent>" --kind <kind> \
    --output .dev-autopilot/pack.json
```

The pack carries the diff, full text of changed files and their siblings, the
repository's own conventions (`AGENTS.md`, `CLAUDE.md`, `.augment/rules/*`), and
prior review notes so you do not repeat feedback.

Review against all five dimensions, then write findings to
`.dev-autopilot/review-raw.json`:

```json
{
  "reviewer": "claude-opus-5",
  "context_digest": "<pack digest>",
  "dimensions_covered": ["correctness","security","data-safety","error-handling","intent-fidelity"],
  "findings": [
    {"file":"src/billing/charge.py","line":88,"severity":"high",
     "title":"Refund races overwrite each other",
     "why":"Two concurrent refunds both read the pre-refund balance and each write it back, so the second silently overwrites the first and money is lost.",
     "suggestion":"Take a row lock, or make the update conditional on the balance read."}
  ]
}
```

```bash
python3 scripts/review_pack.py audit --pack .dev-autopilot/pack.json \
    --findings .dev-autopilot/review-raw.json --output .dev-autopilot/review.json
```

**Review as an adversary of the change, not its author.** Skip style nitpicks
entirely when substantive issues exist — they bury the findings that matter. Every
finding needs a file, a line in the diff, a severity, and a `why` that names the
failure it causes rather than the rule it breaks.

The audit rejects a review that cites files outside the diff, omits a dimension, was
produced against a stale pack, or carries findings with no stated consequence. It
also rejects an **unexplained clean review on a large or high-risk change** — the
signature of an agent confirming its own work. If you genuinely find nothing there,
attest per dimension what you examined and why it is sound.

See `references/deep-review-protocol.md` for the full dimension guide.

## Composition

This skill is the conductor. It delegates rather than reimplements, and degrades
gracefully when a sibling is absent.

| Phase | Delegates to | Standalone fallback |
|---|---|---|
| Plan | `openspec-autopilot-skill` (when `openspec/` exists) | `.dev-autopilot/plan.md` |
| Browser tests | `playwright-test-autopilot-skill` (when `playwright.config.*` exists) | Unit tests only |
| Post-PR review | `github-pr-triage-skill` (once the PR is open) | Human review |

Preflight reports which are installed. When `plan` returns a `delegate_command`,
run it instead of writing the plan yourself, then `dev_state.py mark --plan-written`.

The boundary is deliberate: this skill owns everything **before** the PR exists;
`github-pr-triage-skill` owns everything **after**.

## Opening the PR

```bash
python3 scripts/pr_body.py --root . --output .dev-autopilot/PR.md
gh pr create --title "$(python3 scripts/pr_body.py --root . --title-only)" \
             --body-file .dev-autopilot/PR.md
python3 scripts/dev_state.py mark --root . --pr-opened --pr-url <url>
```

The body is an evidence trail, not a summary — the reviewer can read the diff. It
publishes the unflattering parts too: warnings, waived findings, anything left
unverified. An agent that hides its soft spots teaches reviewers to stop reading
its PRs, and then the loop has automated nothing.

## Overrides

| Flag | Effect | When it is legitimate |
|---|---|---|
| `--max-new-suppression N` | Raise the skip budget | A genuinely correct skip, explained in the PR body |
| `--no-review` | Drop the review gate | Mechanical changes only (generated code, formatting) |
| `--kind chore` | Skip red-green and test co-movement | Config, docs, dependency bumps |
| `--scope 'glob' ...` | Enforce a file boundary | Any change with an agreed blast radius |

Raise a threshold deliberately and say why. Never raise one just to make a run
pass — that is the failure the gate exists to catch, performed by hand.

## Reference files

| File | Contents |
|---|---|
| `references/self-verification-contract.md` | Why evidence outranks assertion; the full gate semantics |
| `references/deep-review-protocol.md` | The five dimensions, severity rubric, credibility audit |
| `references/state-machine.md` | Every action, its payload, and the transitions |
| `references/failure-modes.md` | The traps that strand or silently pass an unattended run |
| `references/toolchain-matrix.md` | Runner/linter detection, suppression markers per language |
