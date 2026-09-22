# Loop semantics

Everything the orchestrator decides, and why. Read this when the loop does
something you did not expect — the answer is usually that the rule is stricter
than it looks, on purpose.

## Phases

```
init → contract → await_baseline → loop ⇄ holdout → done
```

| Phase | What happens |
|---|---|
| `init` | preflight; the repo either can host a run or cannot |
| `contract` | criteria drafted from the kind profile; you review and lock |
| `await_baseline` | for red-baseline kinds: write the reproducer, nothing else |
| `loop` | commit → score → keep or reset → next instruction |
| `holdout` | visible criteria all green; score the checks the loop never saw |
| `done` | `complete` or `blocked`; the report is written |

State is `.autoresearch/run.json`. It is the source of truth. After a context
compaction, do not reconstruct where you were — run `--continue` and be told.

## Scoring

Each criterion runs as a real subprocess with the attempt budget as its timeout.
Three outcomes:

| Status | Meaning |
|---|---|
| `pass` | exited 0 |
| `fail` | ran, exited non-zero |
| `crash` | could not run — exit 126/127, or timed out |

`score` is the summed `weight` of passing criteria; `max_score` is the total.

**The score means the same thing in every phase.** An earlier version scored
baseline criteria under inverted semantics (a required-red check "passed" by
failing), which made the baseline score incomparable with attempt scores — the
loop reported "3 → 0" for a change that had improved nothing and regressed
nothing. Whether a criterion was correctly red at baseline is now tracked
separately in `demonstrated`, and contributes nothing to the score.

### `demonstrated`

Only meaningful at baseline, only for criteria marked `expect: fail`:

| Value | Meaning |
|---|---|
| `true` | red at baseline as required — the problem is real and present |
| `false` | green when it had to be red — proves nothing; you get `fix_reproducer` |
| `null` | not a baseline red-check |

### Complexity

Total lines across tracked source files, filtered by scope when the contract
declares one. Absolute, not diff size — see `autoresearch-mapping.md` §3 for why
the diff-size version was wrong.

Only files with a recognised source extension count, so committing a fixture or a
lockfile does not read as a complexity regression.

## Keep or discard

```
higher score                          → keep
equal score AND lower complexity      → keep   (the simplicity win)
otherwise                             → discard, git reset --hard to the last kept sha
```

Kept attempts advance the branch, so the branch is a record of monotonic
improvement and the final commit is the best result rather than the last one.

Discards are hard-reset and `git clean`ed, with `.autoresearch/` preserved. The
work is genuinely gone. That is the trade autoresearch makes and it is what makes
a bad idea cheap: nothing accumulates, so nothing has to be untangled later.

## Objectives

| Objective | Kinds | Finishes when |
|---|---|---|
| `criteria` | all except `refactor` | every visible criterion is green |
| `complexity` | `refactor` | no further improvement is found (convergence) |

A complexity-driven run has `score == max_score` from attempt zero, so "all green"
is not a stop condition for it. Treating its stagnation as failure would report
success as a blockage.

## Stagnation

`no_progress` counts consecutive discards.

| Threshold | What happens |
|---|---|
| `no_progress_limit` (default 5) | action `research` — stop varying the same idea |
| `2 ×` the limit | `blocked`, or `complete` for a converged complexity run |

The `research` escalation is not decoration. Attempts 6 through 10 being smaller
versions of attempts 1 through 5 is the characteristic way an unattended loop
burns a night. The instruction is deliberately specific: read the code paths you
have not read, look for a prior solution in this repo, come back with a different
approach.

## Crashes

A crash is not a failed criterion, and the distinction is load-bearing: a typo'd
command that exits 127 would otherwise stand in for a real failing check, and the
loop would start "fixing" code to satisfy a command that never ran.

On crash: the attempt is reset, logged as `crash`, and you get `fix_harness` —
fix the command or the environment, not the code. Three consecutive crashes of the
same criterion blocks the run, because at that point the harness is broken and no
amount of code will fix it.

`program.md`'s rule applies verbatim: something dumb and easy (a typo, a missing
import) — fix it and re-run. Fundamentally broken — log it and move on.

## The holdout

Scored only when every visible criterion is green.

| Check | Catches |
|---|---|
| `no-focus-markers` | `.only` / `fit` / `fdescribe` narrowing the suite to the passing test |
| `no-new-suppressions` | tests skipped or `fixme`'d to reach green |
| `in-scope` | changes outside the declared blast radius |

A failure yields `overfit`: the visible criteria were satisfied by a route the
contract meant to exclude.

**The leak, stated plainly.** Telling the loop which holdout check failed partly
spends the holdout — it is now information the loop can optimise against. Two
reveals are permitted; the third blocks for a human. This bounds the damage rather
than eliminating it, and it is the weakest joint in the design. Nothing here
prevents an agent from satisfying the *letter* of all three holdout checks while
still writing a bad change; they catch mechanical cheating, not bad judgement.

## Terminal states

**`complete`** — every visible criterion green *and* every holdout check clean.
The report is written to `.autoresearch/report.md`.

**`blocked`** — one of:

| Reason | Meaning |
|---|---|
| preflight hard finding | not a repo, detached HEAD, no commits |
| baseline not green (behaviour-preserving kinds) | cannot preserve what is already broken |
| attempt cap reached | `max_attempts`, default 60 |
| stagnation past `2 × no_progress_limit` | out of ideas, having already widened once |
| same criterion crashed 3× | the harness is broken |
| contract digest mismatch | the objective moved; every number is void |
| holdout caught the run 3× | the holdout is no longer independent |
| three `implement` actions with no file change | nothing is happening |

Escalate a `blocked` reason **verbatim**. Do not improvise a fix for a state the
loop has declared out of its own reach — that is how an unattended run turns a
clean stop into a mess someone has to unpick in the morning.

## What never happens

- The loop never asks whether to continue.
- The loop never edits the contract.
- The loop never reports `complete` without the holdout having run.
- A crash is never counted as a failing criterion.
- A discard never leaves anything behind.
