# The Self-Verification Contract

## The problem this exists to solve

Autonomous development has one structural weakness, and it is not code generation.
It is that **the agent which wrote a change is the worst available judge of it.**

When an agent writes code it simultaneously constructs a belief that the code is
correct — that belief is what caused it to stop writing. Asking the same agent "is
this ready?" re-runs the reasoning that produced the belief, and reproduces it. The
answer is not an assessment of the output; it is a restatement of the intention.

This is not a prompting problem. No instruction to "be critical" survives the fact
that the reviewer and the author share a context, a set of assumptions, and a
conclusion. You cannot fix it with adjectives.

## The rule

> A gate is green only when something ran and left evidence. Silence is never
> success.

Every gate is a pure function of a machine-produced observation:

- an exit code captured by `record_check.py`, which executed the command itself
- a diff parsed by `diff_intel.py` from git
- a review record that passed `review_pack.py audit`

A gate with no observation to read does not pass and does not fail. It reports
`skip`, and a skipped **required** gate sets `evidence_complete: false`, which makes
`pr_ready` unreachable by construction.

The consequence is the point: an agent cannot reach a green verdict by asserting
things went well. The only path to green runs through commands that actually ran.

## Three verdicts

| Verdict | Meaning | Exit code |
|---|---|---|
| `pr_ready` | Every required gate passed **with evidence** | 0 |
| `needs_evidence` | Nothing failed, but a required gate had nothing to read | 3 |
| `blocked` | A gate failed | 1 |

`needs_evidence` is deliberately distinct from `blocked`. "I have not checked" and
"I checked and it is broken" call for different next actions, and collapsing them
into one status is how "unverified" gets quietly reported as "fine".

## Why each required gate exists

### `diff-present`
An empty diff with a confident report is the purest form of the failure this skill
guards against. Also catches the wrong `--base`, where a real change reads as empty.

### `focus-guard`
`.only`, `fit`, `fdescribe` narrow a run to the focused tests **and still exit 0**.
Every green signal downstream is then meaningless — the suite reported success while
running almost nothing. Count is irrelevant; one is a blocker.

This is the most dangerous marker in unattended work because it does not look like
suppression. Nothing is skipped, nothing is disabled; the run simply covers three
tests instead of nine hundred and says "passed".

### `suppression-budget`
Playwright's healer is explicitly instructed to `test.fixme()` a test it cannot fix.
Under human review that is a reasonable give-up. Unattended it is a trapdoor: the
healer can drive the suite green by switching tests off, and **a silently green
suite is worse than a red one, because nobody looks at it again.**

Counted against **added lines only**. Inheriting a skipped test is not a sin; adding
one to reach green is. Default budget is 0 — raise it deliberately, never to make a
run pass.

### `tests-pass`
Three distinct failures, not one:
- the suite ran and was red
- the suite exited 0 having run **zero** tests (mis-scoped selector, collection error)
- the command never ran tests at all (missing runner, typo, import error)

The third matters most. A broken command exits non-zero, which naive logic reads as
"a test failed". `record_check.py` detects harness errors explicitly so a typo
cannot masquerade as a test result.

### `red-green-proof`
Required for `kind: bugfix`. A green suite after a fix proves nothing: it was green
before the fix as well, which is precisely how the bug reached production.

The only proof that a fix addresses the reported bug is a test that **fails without
it**. Two runs, two points in time, both recorded. A single run after the fix is not
a weaker version of this proof — it is not a proof at all.

Rejected: a "red" phase that was actually a harness error; a regression test that
passed against the unfixed code; a test still failing after the fix.

### `changed-code-tested`
Source moved and no test did. Either the new behaviour is untested, or an existing
test should have needed updating and did not — both mean the suite is not watching
this change. Non-code changes (docs, config) pass automatically.

### `review-credible`
Delegates to `review_pack.py audit`. See `deep-review-protocol.md`. The gate treats
a non-credible review exactly like no review at all, because that is what it is.

## Optional gates

`static-checks` and `scope` are advisory: they contribute warnings, never blockers.
`scope` only enforces when a scope was actually declared.

## What breaks the contract

**Hand-editing `.dev-autopilot/run.json` to make a gate pass.** This is the single
action that invalidates everything above. The gates become a formality and the
verdict becomes a claim again.

It is also visible: `.dev-autopilot/logs/` holds the real output of every recorded
command, and the PR body cites exit codes a reviewer can re-run. The contract is
enforced by transparency rather than by permissions, which is the right trade for a
tool a developer runs on their own machine.
