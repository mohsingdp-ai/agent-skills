---
name: coding-autoresearch-skill
description: >-
  Run any coding task as an autoresearch loop — inspect, research, plan,
  implement, test, verify, evaluate, iterate — stopping only when the result is
  verified or genuinely blocked. Ports Karpathy's autoresearch to software: the
  objective is SHA-256 locked before implementation starts so the agent cannot
  weaken its own success criteria to reach green, every attempt is committed and
  scored by running real commands then kept or git reset away, and held-out checks
  the loop never sees catch a contract satisfied by cheating. Handles bug fixing,
  debugging, root-cause analysis, features, missing functionality, refactoring,
  performance optimization, test and fixture creation, documentation, code review,
  research, and integration — each with its own definition of done. Use when asked
  to work autonomously or unattended, fix a bug end to end, run an agent loop
  overnight, iterate until tests pass, prove a fix actually fixes something,
  simplify code without breaking it, resume an interrupted run, or log what was tried.
license: MIT
activation: /coding-autoresearch-skill
provenance:
  maintainer: Mohsin Ejaz
  version: 1.0.0
  created: 2026-08-10
  source_references:
    - https://github.com/karpathy/autoresearch
    - https://github.com/karpathy/autoresearch/blob/master/program.md
metadata:
  author: Mohsin Ejaz
  version: 1.0.0
  created: 2026-08-10
  last_reviewed: 2026-08-10
  review_interval_days: 90
  composes_with:
    - dev-autopilot-skill
    - openspec-autopilot-skill
    - playwright-test-autopilot-skill
  dependencies:
    - url: https://github.com/karpathy/autoresearch
      name: Karpathy autoresearch
      type: docs
---
# /coding-autoresearch-skill — Any Coding Task as an Overnight Loop

You take one coding task and drive it to a verified result without asking
permission along the way. Somebody may be asleep. Keep working.

## Trigger

```
/coding-autoresearch-skill fix the login redirect dropping the return URL
/coding-autoresearch-skill --kind refactor simplify the pricing module
/coding-autoresearch-skill --kind perf the /orders endpoint is too slow
/coding-autoresearch-skill --kind research how does auth token refresh work here
/coding-autoresearch-skill --continue          # resume an interrupted run
/coding-autoresearch-skill --status            # where is it
/coding-autoresearch-skill --report            # what happened overnight
```

Also activates on: "work on this autonomously", "iterate until the tests pass",
"run this overnight", "prove the fix actually fixes it", "what did you try".

## The idea this is built on

Karpathy's autoresearch lets an agent run ML experiments unattended overnight. It
works because of one property that is easy to miss: **the metric already exists,
and it lives in a file the agent is forbidden to edit.** `val_bpb` is computed by
`prepare.py`, `prepare.py` is read-only, and so a bad idea is cheap and a good
result cannot be faked.

A general coding task has no `val_bpb`. That is the entire difficulty, and
everything below follows from solving it.

| autoresearch | here |
|---|---|
| `val_bpb`, one scalar, lower is better | contract score — criteria weight satisfied, complexity as tiebreak |
| `prepare.py` is read-only | `contract.json` is SHA-256 locked; tampering voids the run |
| `train.py` is the only editable file | declared scope globs |
| fixed 5-minute budget per experiment | per-attempt wall-clock cap, hard kill |
| `results.tsv`, untracked, keep/discard/crash | `.autoresearch/ledger.tsv`, same shape |
| improved → commit; worse → `git reset` | identical |
| first run establishes the baseline | baseline mandatory — and for a bug fix it must be **red**, which makes the baseline rule and the red-green proof the same rule |
| NEVER STOP | never stop to *ask*; stop only when verified or blocked |

## The one rule

**The objective is written down and locked before any implementation begins.**

An agent that can edit its own success criteria will always reach green, and the
green will mean nothing. So the contract is hashed the moment it is agreed, and
every score re-verifies the hash first. Change a criterion afterwards and the run
does not fail politely — it is declared void, because every number collected
against a moving objective is worthless.

You cannot argue your way to a score here. You can only run things.

## Run it

One command. It tells you what to do; you do exactly that; you ask again.

```bash
python3 scripts/run_pipeline.py --task "fix the login redirect" --kind bugfix
python3 scripts/run_pipeline.py --continue
```

State lives in `.autoresearch/`, so a compacted or interrupted run resumes
exactly where it stopped. **Never infer the state from memory — ask again.**

| `action` | What you do |
|---|---|
| `fix_preflight` | Fix each finding; each carries the command that fixes it |
| `review_contract` | Read the drafted criteria, correct any wrong command or scope, then `contract.py lock` |
| `write_reproducer` | Write the failing test / absent deliverable. **Touch no source yet** |
| `fix_reproducer` | Your reproducer passed at baseline. It proves nothing. Rewrite it |
| `implement` | Make **one** focused change |
| `fix_harness` | A check could not run. Fix the command, not the code |
| `research` | You are stuck. Stop varying the same idea; go read something |
| `fix_overfit` | A holdout check caught you. Fix the cause, not the check |
| `done` | Stop. Report what shipped |
| `blocked` | Stop. Escalate the reason verbatim. Do not improvise |

## The eleven kinds

`--kind` selects what "done" means. Getting this right matters more than anything
else you type.

| kind | done means | baseline must be red |
|---|---|---|
| `bugfix` | a test that was red before the fix is green after | yes |
| `debug` | a reproducer plus a written root cause with file:line | yes |
| `feature` | acceptance criteria, as tests, pass | yes |
| `missing` | the previously-absent path is exercised and passes | yes |
| `refactor` | tests unchanged and still green, **and the code got smaller** | no — must be green |
| `perf` | the benchmark beats the baseline measurement | yes |
| `test` | the new tests **fail when the code is mutated** | yes |
| `docs` | every documented example actually executes | no |
| `review` | findings anchored to lines inside the diff | yes |
| `research` | every question answered, every claim cited | yes |
| `integration` | the end-to-end path across the seam passes | yes |

`python3 scripts/contract.py kinds` lists these with their aliases.

Two of these are worth dwelling on:

**`refactor` is the purest analogue.** Its criteria only gate correctness, so they
are green from attempt zero and the number actually being minimised is the size of
the code in scope. Deleting code for an equal score is a *keep*. Editing a test to
make a refactor pass is editing the metric, and `tests-unchanged` will catch it.

**`test` is graded by mutation, not by passing.** A test that passes no matter
what the code does is worse than no test: it buys false confidence. The guard
mutates the source and requires the suite to notice.

## The loop

```
LOOP:
  1. make ONE change
  2. python3 scripts/run_pipeline.py --continue
  3. it commits, scores, and keeps or resets — then tells you the next thing
```

One idea per attempt. An attempt that changes three things teaches you nothing
about which one worked, and the ledger becomes unreadable.

**Keep or discard** is decided for you: a higher score always wins; an equal score
wins only by costing fewer lines. That is autoresearch's simplicity criterion made
mechanical — *"removing something and getting equal results is a great outcome."*

**Crashes are not failures.** A check that could not run (missing binary, timeout)
is recorded as `crash`, not as a failed criterion, and the fix is to the command
or the environment. Changing the code to chase a crash is how a night gets wasted.

**Stagnation escalates rather than spinning.** N attempts with no movement returns
`research` — go read the code paths you have not read, look for a prior solution
in the repo, come back with a genuinely different approach. N more and the run
stops as `blocked` rather than burning the remaining hours.

## The holdout

autoresearch has no holdout, and does not need one: `val_bpb` cannot be gamed by
editing `train.py`. A coding contract can be, trivially — skip the failing test,
add `.only`, edit the assertion.

So the contract has two halves. The **visible** criteria drive the loop. The
**holdout** criteria are scored only when the visible ones are all green:

- no `.only` / `fit` / `fdescribe` added
- no net-new skipped or `fixme`'d tests
- nothing changed outside declared scope

Fail one and the verdict is `overfit`, not `complete` — the score was reached by
a route the contract was meant to exclude. Fix the cause, not the check.

**Honest limit:** telling you *which* holdout check failed partly spends it. That
is allowed twice; past that the loop is optimizing against the holdout too and it
has stopped being independent, so the run blocks for a human. This is a real
weakness of the design, not a solved problem.

## Never stop to ask

Once the loop begins, do not pause to ask whether to continue. Do not ask "should
I keep going?" or "is this a good stopping point?". The person who started this may
be asleep and expects to find work done.

Unlike autoresearch, this loop does have completion conditions, because coding
tasks finish and research does not:

- **complete** — every visible criterion satisfied *and* every holdout check clean
- **blocked** — the attempt cap, repeated stagnation, a broken harness, a tampered
  contract, or a holdout that keeps catching you

Those are the only two ways to stop. Running out of ideas is not one of them: read
the code you have not read, combine two near-misses, try the more radical change.

## The morning report

```bash
python3 scripts/ledger.py report
```

Tab-separated, one row per attempt, untracked — the same shape as autoresearch's
`results.tsv`, because the point is the same: someone reads it over coffee and can
see what was tried, what survived, and what it cost.

```
attempt  commit   score  max  complexity  status    description
0        9a6dea8  0      5    10          baseline  baseline for bugfix
1        9fd450c  0      5    20          discard   no gain
2        fa3bb85  5      5    17          keep      score 0 -> 5
```

Publish the unflattering rows. A loop that hides its discards teaches the reader
to stop reading its reports, and then it has automated nothing.

## Reference files

| File | Contents |
|---|---|
| `references/kind-profiles.md` | All eleven kinds: criteria, guards, when to pick which |
| `references/loop-semantics.md` | Scoring, keep/discard, phases, every action and transition |
| `references/failure-modes.md` | The traps that strand or silently pass an unattended run |
| `references/autoresearch-mapping.md` | What was ported, what was changed, and why |
