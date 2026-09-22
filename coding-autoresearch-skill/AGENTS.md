# coding-autoresearch-skill

Run any coding task as an autonomous loop that stops only when the result is
verified or genuinely blocked. A port of Karpathy's
[autoresearch](https://github.com/karpathy/autoresearch) to software work.

## When this applies

Activate when asked to:

- work on something autonomously, unattended, or overnight
- fix a bug end to end, or prove that a fix actually fixes something
- iterate until the tests pass
- refactor without changing behaviour, or make something measurably faster
- write tests, documentation, a code review, or a research answer
- resume an interrupted run, or report what was tried

Do **not** use it for a one-line edit with an obvious answer. The contract step
costs more than the task.

## The rule everything rests on

The objective is written down and SHA-256 locked **before** implementation starts.
An agent that can edit its own success criteria will always reach green, and the
green will mean nothing. Every score re-verifies the hash; change a criterion
afterwards and the run is void, not merely failed.

You cannot argue your way to a score. You can only run things.

## How to run it

One command, repeatedly. It tells you the next thing to do.

```bash
python3 scripts/run_pipeline.py --task "fix the login redirect" --kind bugfix
python3 scripts/run_pipeline.py --continue
```

Pick `--kind` from: `bugfix`, `debug`, `feature`, `missing`, `refactor`, `perf`,
`test`, `docs`, `review`, `research`, `integration`.
(`python3 scripts/contract.py kinds` lists them with aliases.)

Useful additions:

- `--scope 'src/auth/**'` — repeatable; bounds the blast radius
- `--tag nightly` — creates and switches to `autoresearch/nightly`
- `--status` / `--report` — where things are; what happened

State lives in `.autoresearch/`. After a context compaction, **do not reconstruct
where you were** — run `--continue` and be told.

## Actions

| Action | Do this |
|---|---|
| `fix_preflight` | Fix each finding; each carries the command that fixes it |
| `review_contract` | Read the criteria. Run each command once yourself. Then `python3 scripts/contract.py lock` |
| `write_reproducer` | Write the failing test or absent deliverable. Touch no source |
| `fix_reproducer` | It passed at baseline, so it proves nothing. Rewrite it |
| `implement` | Make **one** focused change |
| `fix_harness` | A check could not run. Fix the command, not the code |
| `research` | Stuck. Go read code you have not read; come back with a different approach |
| `fix_overfit` | A holdout check caught you. Fix the cause, not the check |
| `done` | Stop; report what shipped |
| `blocked` | Stop; escalate the reason verbatim. Do not improvise |

## Non-negotiables

1. **Never pause to ask whether to continue.** Whoever started this may be asleep.
2. **One idea per attempt.** Three changes at once teach you nothing about which
   one worked.
3. **Never edit the contract after locking.** If the task genuinely changed, start
   a new run.
4. **Never reach green by disabling a check.** `.only`, `skip`, `fixme`, and
   weakened assertions are all caught by the holdout, and each one wastes an
   attempt you could have spent on the actual problem.
5. **A crash is not a failure.** If a check could not run, fix the command or the
   environment — do not change code to chase it.
6. **Running out of ideas is not a stopping condition.** Read more, combine
   near-misses, try the radical change.

## Stopping

Only two ways:

- **`complete`** — every visible criterion green *and* every holdout check clean
- **`blocked`** — attempt cap, repeated stagnation, broken harness, tampered
  contract, or a holdout that keeps catching the loop

## The morning report

```bash
python3 scripts/ledger.py report
```

One row per attempt: score, complexity, keep/discard/crash, and what was tried.
Publish the unflattering rows — a loop that hides its discards teaches the reader
to stop reading its reports.

## Full details

See `SKILL.md`, and:

- `references/kind-profiles.md` — all eleven kinds and how to choose
- `references/loop-semantics.md` — scoring, keep/discard, every transition
- `references/failure-modes.md` — the traps, including the ones no guard catches
- `references/autoresearch-mapping.md` — what was ported and what was changed
