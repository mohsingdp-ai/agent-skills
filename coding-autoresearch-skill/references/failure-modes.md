# Failure modes

The ways an unattended run gets stranded, or worse, reports success it has not
earned. Each entry is a real trap, several of them found by running this skill
against real repositories rather than by reasoning about it.

## Silent-success traps

These are the dangerous ones: the run says `complete` and the result is wrong.

### The contract was weakened

**Symptom:** everything green, suspiciously fast.
**Detection:** `contract.py verify` — exit 3 and every score is void.

This is the failure the whole design exists to prevent. It is worth being precise
about what "weakened" includes, because not all of it looks like cheating:

- changing a criterion's `cmd` to something narrower
- widening `scope` after discovering the change needs to touch more
- lowering a `weight`
- deleting a criterion that turned out to be hard

The last two are the tempting ones, because in the moment each has a reasonable
story. If the task genuinely changed, the honest move is a new run with a new
contract, not an edit to this one.

### Green by not running the tests

**Symptom:** the suite passes; it is also much faster than it used to be.
**Detection:** `no-new-suppressions`, `no-focus-markers` (holdout).

A `.only` on the one passing test turns a 400-test suite into a 1-test suite that
passes. The suite command still exits 0, so every visible criterion is satisfied.
This is the single most common way an agent reaches a green that means nothing.

### The reproducer never reproduced anything

**Symptom:** the bugfix run completes in one attempt with no source change.
**Detection:** baseline red requirement — you get `fix_reproducer`.

A test asserting behaviour that already works is green at baseline and green after,
and proves the fix works. It proves nothing at all.

### Tests that cannot fail

**Symptom:** a `test` run completes; coverage is up; nothing is actually verified.
**Detection:** the `mutation` criterion.

`assert result is not None` on a function that cannot return `None` passes forever.
Mutation is the only mechanical check that distinguishes a test from an assertion
that happens to be true.

### Review findings about untouched code

**Symptom:** a plausible review; the cited lines are not in the diff.
**Detection:** the `anchored` criterion.

A model asked to review a diff will happily produce findings about the file's other
900 lines. They may even be correct, and they are still not a review of this change.

## Stranding traps

Less dangerous, more annoying: the night is wasted and nothing is produced.

### The test command does not exist

**Symptom:** every criterion `crash`, exit 127.
**Detection:** three consecutive crashes → `blocked`.

Toolchain detection is a heuristic. It reads `package.json` scripts, lockfiles,
`pyproject.toml`, `go.mod`, `Cargo.toml` — and it guesses. **This is exactly what
the `review_contract` step is for.** Run the command yourself once before locking.
Thirty seconds there saves the whole run.

The `MISSING-TEST-COMMAND` placeholder is emitted rather than a fake command when
nothing is detected, and `contract.py init` exits non-zero so it cannot be locked
by accident.

### Nothing was changed between attempts

**Symptom:** `implement` three times in a row, same message.
**Detection:** `action_repeat` ≥ 3 → `blocked`.

Usually means the next step is genuinely unclear. Better to stop and say so than
to loop on an empty diff for six hours.

### Refactoring a red suite

**Symptom:** immediate `blocked` at baseline.
**Not a bug.** Behaviour that is already broken cannot be preserved, and a
behaviour-preserving change measured against a failing suite measures nothing.
Fix or quarantine the failing test first, in its own run.

### The benchmark produces no parseable number

**Symptom:** `perf` runs crash on the `benchmark` criterion.
**Fix:** declare `benchmark.pattern` in the contract before locking. The default
looks for `metric:`/`score:`/`time:`/`duration:`/`ops:`/`latency:` followed by a
number, which will not match most real benchmark output.

### Build noise read as source changes

**Symptom:** `tests-unchanged` fails on a clean tree; complexity jumps for no
reason.
**Fixed, but worth knowing about.** `__pycache__/*.pyc` matches a naive `*test*`
glob and reads as "a test file changed". Two guards: `ensure_ignored` writes the
noise list to `.git/info/exclude` before the first score, and `is_test_path` only
considers recognised source extensions.

If you see this anyway, something is writing artefacts with source extensions into
the repo during the test run. Add them to the contract's scope exclusions.

## Environment traps

### The run is on `main`

Preflight refuses. Pass `--tag <name>` and it creates `autoresearch/<name>` for
you. The loop commits on every kept attempt; that must not be `main`.

### The tree was dirty at the start

Preflight refuses. Uncommitted work would be mixed into the first attempt and then
destroyed by the first discard. Stash or commit it.

Build noise (`node_modules/`, `dist/`, `__pycache__/`, `.venv/`, …) is exempt —
preflight and the commit step use the same noise list, so what preflight tolerates
is also what never gets staged.

### `.autoresearch/` was committed

It should never be. It is added to `.git/info/exclude` automatically. If it lands
in a commit, every attempt's diff contains the previous attempt's ledger, which
corrupts both the complexity metric and the scope check.

## Judgement traps

No guard catches these. They are listed because the guards passing is not the same
as the work being good.

- **Satisfying the letter of every check with a bad change.** All three holdout
  checks can pass on a change that is poorly factored, wrongly abstracted, or
  solves the wrong problem well. The contract measures completion, not quality.
- **A contract that measures the wrong thing.** Locked at attempt zero and never
  revisited, a mis-specified criterion is pursued faithfully all night. The
  `review_contract` step is the only defence, and it is a human-attention defence.
- **Scope drawn too narrowly.** The change needed a companion edit one directory
  over; `in-scope` blocks it; the loop finds a worse in-scope solution instead. The
  guard did its job, and the outcome is still bad.

The honest summary: this design makes it hard to reach a *fake* green, and does
nothing to guarantee a *good* one. Read the diff in the morning.
