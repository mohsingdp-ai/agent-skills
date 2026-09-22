# Failure Modes

The ways an unattended development run goes wrong. Each one either strands the run
or — far worse — lets it report success while having verified nothing.

Ordered by how expensive they are when missed.

---

## 1. The focused suite (silently passes)

**What happens.** A `.only` / `fit` / `fdescribe` marker is added — often while
debugging a single test, then never removed. The suite runs three tests instead of
nine hundred and exits **0**.

**Why it is the worst one.** It does not look like suppression. Nothing is skipped
or disabled. Every downstream gate reads a genuine green exit code, the PR says
"suite passed", and it is true — it just describes a run that proved almost nothing.

**Guard.** `focus-guard`, blocking, zero tolerance. Counted against added lines, so
a pre-existing marker is not blamed on this change but a new one always blocks.

---

## 2. Green by disabling (silently passes)

**What happens.** A test fails, and instead of fixing it the agent marks it
`test.fixme()`, `@pytest.mark.skip`, `t.Skip()`, `@Disabled`. The suite goes green.

Playwright's healer is *explicitly instructed* to do this:

> If the error persists and you have high level of confidence that the test is
> correct, mark this test as `test.fixme()` so that it is skipped during the
> execution.

Under human review, sensible. Unattended, it converts a red suite into a green one
without fixing anything — and **nobody re-reads a green suite.**

**Guard.** `suppression-budget`, default 0 added markers, blocking. Plus a
whole-tree census that warns when the repository's absolute suppression ratio
exceeds 20%, so a suite that was already hollowed out does not read as healthy.

---

## 3. The unproven bug fix (silently passes)

**What happens.** A bug is reported, code is changed, the suite is green, the PR
ships. Nothing ever demonstrated that the change fixes the reported bug, and no test
will catch it coming back.

**Why it survives review.** The suite is green, so every automated signal agrees.
But the suite was green *before* the fix too — that is how the bug reached
production in the first place.

**Guard.** `red-green-proof`, blocking for `kind: bugfix`. A test must exit non-zero
against the unfixed code and zero after. Both runs recorded, both timestamps kept.

---

## 4. The broken command that looks like a failing test (silently passes)

**What happens.** The red phase is recorded with a command that has a typo, a
missing runner, or an import error. It exits non-zero. Naive logic reads non-zero as
"the test failed" and the red-green proof is satisfied by a command that never
executed a single assertion.

**Found in this skill's own smoke test**, which is why it is guarded explicitly:
`pytest` was not installed, the command exited 1, and the proof looked satisfied.

**Guard.** `record_check.py` detects harness errors — exit 127, pytest exit codes
2/3/4/5, and output signatures like `ModuleNotFoundError`, `command not found`,
`collected 0 items`, `ERROR collecting`. A run flagged with `harness_error` cannot
serve as either half of the proof.

---

## 5. New files invisible to the gates (silently passes)

**What happens.** The agent adds a new module. `git diff` shows **nothing** for
untracked files. The change reads as smaller than it is, the new code is never
risk-scored, never scanned for suppression markers, and never sent to the reviewer.

For feature work — where "add a new file" is the normal shape — this is a hole big
enough to drive the entire change through.

**Also found in this skill's own smoke test.**

**Guard.** `diff_intel.analyze` folds in `git ls-files --others --exclude-standard`,
treating every line of a new file as an addition. Excludes `.git`, `node_modules`,
`__pycache__`, `.venv`, and the skill's own `.dev-autopilot/` state directory.

---

## 6. The rubber-stamp review (silently passes)

**What happens.** The agent reviews the change it just wrote and finds nothing. The
review record exists, `review-credible` passes, and the change ships unexamined.

**Why it happens.** The agent concluded the code was correct while writing it.
Re-reading its own reasoning reproduces the conclusion. This is structural, not a
prompting failure.

**Guard.** `review_pack.py audit` rejects an unexplained clean review on a large or
high-risk change, findings that cite files outside the diff, findings with no stated
consequence, missing dimensions, and reviews produced against a stale pack.

---

## 7. Scope drift (needs a human)

**What happens.** A small approved change quietly grows. The plan a reviewer agreed
to no longer describes the change in front of them.

**Guard.** `scope`, advisory, enforced only when a scope was declared:
`--scope 'src/api/**'`. Reports every file outside the declared globs.

---

## 8. The stale review (silently passes)

**What happens.** The review runs, then the agent fixes a blocker and changes the
code. The review record still says "credible, no high findings" — about code that no
longer exists.

**Guard.** `context_digest` in the review record is compared against the current
pack digest. A mismatch is `stale_context`, and the state machine re-issues `review`.

---

## 9. Vacuous test runs (silently passes)

**What happens.** The test command exits 0 having collected zero tests — a
mis-scoped path argument, a renamed directory, a broken glob.

**Guard.** `tests_vacuous` in `tests-pass`: exit 0 with a parsed count of zero
passing tests is a blocker, not a success. Counts that could not be parsed are
recorded as `null` rather than `0`, so "unknown" is never mistaken for "zero".

---

## 10. The loop that will not converge (strands)

**What happens.** The agent fixes a blocker, the gate fails again, the agent fixes
it again. Nothing changes. The run burns context indefinitely.

**Guard.** `NO_PROGRESS_LIMIT = 3` in `dev_state.py`. Three identical consecutive
actions escalate to `blocked` with the stuck action and its last payload, rather
than spinning.

---

## 11. Detached HEAD / working on main (strands, late)

**What happens.** Work is committed to a detached HEAD and is unreachable when the
run ends, or lands directly on `main` where it cannot become a PR.

**Guard.** `dev_preflight.py`, checked in seconds before any work begins. Detached
HEAD is an error; working on the default branch is a warning with the `git switch`
command attached.

---

## 12. Unresolvable base ref (strands)

**What happens.** A branch that was never pushed has no upstream, `origin/HEAD` is
unset, and there is nothing to diff against. Every gate reads an empty change.

**Guard.** `resolve_base` falls back in order: explicit `--base` → upstream tracking
branch → `origin/HEAD` → `origin/main` → `origin/master` → `main` → `master` → the
repository's first commit. The final fallback is what makes an unpushed branch work.
