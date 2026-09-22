# What was ported from autoresearch, and what was changed

Source: <https://github.com/karpathy/autoresearch> — in particular `program.md`,
which is the instruction file the agent is handed.

This document exists so that a later maintainer can tell which decisions are
inherited (and should not be casually overridden) from which are ours (and are
therefore fair game).

## What autoresearch actually is

An agent is given a small ML training repo and told to improve a model overnight.
It edits `train.py`, runs a 5-minute training job, reads one number out of the
log, and keeps or reverts the change. Roughly 12 experiments an hour, ~100 over a
night's sleep. The human wakes to a log.

The design is unusually disciplined, and four properties do the work:

1. **The metric pre-exists and is untouchable.** `evaluate_bpb` lives in
   `prepare.py`, which the agent is forbidden to modify. The agent cannot make
   the number better by making the ruler shorter.
2. **The budget is fixed.** Exactly 5 minutes, wall clock, per experiment. Every
   result is comparable and the night's throughput is predictable.
3. **Git is the accept/reject mechanism.** Improve and the branch advances; fail
   and `git reset`. A bad idea costs five minutes and nothing else.
4. **The agent is forbidden to stop and ask.** "The human might be asleep."

## Ported unchanged

| Property | Where it lives here |
|---|---|
| Read-only objective | `contract.py` — SHA-256 lock, verified before every score |
| Fixed per-attempt budget | `budget.attempt_seconds`, enforced by subprocess timeout |
| Keep on improvement, `git reset` otherwise | `run_pipeline._is_improvement` + `gitops.reset_to` |
| Untracked TSV ledger, keep/discard/crash | `ledger.py`, `.autoresearch/ledger.tsv` |
| First run establishes the baseline | the `baseline` phase, mandatory |
| Crash ≠ failure; read the log, fix if dumb, skip if fundamental | `score.py` `HARNESS_EXITS`, `fix_harness` action |
| Simplicity criterion | complexity tiebreak in `_is_improvement` |
| Redirect output to a log, never flood context | every criterion writes `.autoresearch/logs/<phase>-<id>.log` |
| Never pause to ask the human | no action ever asks for permission |

The logging detail is easy to dismiss as housekeeping. `program.md` is explicit —
*"redirect everything — do NOT use tee or let output flood your context"* — and it
is load-bearing: a test suite's stdout will bury the loop's own state in the
agent's context within a handful of iterations.

## Changed deliberately

### 1. The metric has to be manufactured

The single largest difference. autoresearch's whole premise is a pre-existing
`val_bpb`; a coding task has nothing of the sort. So the loop's first phase builds
a contract and locks it. Everything else here is downstream of that one problem.

The lock matters more than it looks. Without it, the agent both defines and
pursues the objective, which is not a loop — it is a wish.

### 2. Scores are vectors, not one float

`val_bpb` is a single continuous number, so "improved" is unambiguous. A coding
objective is a set of checks. The score is the summed weight of satisfied
criteria, with complexity as the tiebreak — which recovers a total order and
keeps the keep/discard rule intact.

### 3. Complexity is absolute, not diff size

An early version measured "changed lines against base". That was wrong, and
wrong in a way worth recording: diff size starts at zero and can only grow, so
every refactor scored as a regression and no simplification could ever be kept.

autoresearch's rule — *"removing something and getting equal results is a great
outcome"* — is a claim about the code, not the patch. So complexity is total
source lines in scope. Delete four lines with the tests still green and the score
goes down, which is a keep.

### 4. There is a holdout

autoresearch needs none: you cannot cheat `val_bpb` by editing `train.py`. A
coding contract is cheatable in about four keystrokes — skip the test, add
`.only`, weaken the assertion.

So criteria are split. The visible set drives the loop; the holdout set is scored
only once the visible set is green. Failing it yields `overfit`, not `complete`.

This is the one place the design is genuinely *better* than its source, and also
the one place it is genuinely leaky: revealing which holdout check failed partly
spends it. Two reveals, then the run blocks for a human. Not solved — bounded.

### 5. The loop terminates

`program.md` says **NEVER STOP**, and is right to: research has no completion
condition. Coding tasks do. So "never stop" is narrowed to *never stop to ask*,
and two terminal states are added:

- `complete` — visible criteria green and holdout clean
- `blocked` — attempt cap, repeated stagnation, broken harness, tampered
  contract, or a holdout that keeps catching the loop

Running out of ideas is explicitly **not** a stopping condition, exactly as in the
source: read more, combine near-misses, try the radical change.

### 6. Two objectives, two stop conditions

Most kinds are criteria-driven: they finish when the checks go green. `refactor`
is complexity-driven — its checks are green from the start, so it finishes by
*converging*, when no further simplification can be found. Treating stagnation as
failure there would report success as a blockage.

### 7. Baseline-must-be-red unifies two rules

autoresearch's "the first run establishes the baseline" and the red-green proof
of test-driven bug fixing turn out to be the same instruction. A bug fix whose
reproducer is green at baseline has not reproduced the bug, and a baseline that
does not demonstrate the problem cannot measure its resolution.

## Not ported

- **A fixed idea of throughput.** 5 minutes per experiment gives autoresearch ~100
  runs a night. Coding attempts vary by orders of magnitude; the cap is a kill
  switch, not a schedule.
- **`--rewind`.** `program.md` allows rewinding the branch "very very sparingly
  (if ever)". Omitted: with a vector score and a holdout, the failure modes that
  would motivate a rewind are already caught more precisely.
- **Overnight parallelism.** autoresearch suggests one branch per GPU
  (`autoresearch/mar5-gpu0`). Nothing here prevents several tags in several
  worktrees, but no support is provided for merging their results.
