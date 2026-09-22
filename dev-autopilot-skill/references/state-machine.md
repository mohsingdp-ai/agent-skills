# State Machine

`dev_state.py` answers exactly one question — *what is the next action?* — and the
agent performs exactly that, then asks again.

State lives on disk under `.dev-autopilot/`, never in the agent's context. A run
that is interrupted, compacted, or resumed the next day picks up precisely where it
stopped rather than restarting or redoing work it cannot remember doing.

```bash
python3 scripts/dev_state.py next --root . --json
```

## Division of labour

The split is forced by capability, not preference:

| Owner | Responsibility | Why |
|---|---|---|
| Python | Sequencing, gates, evidence | Must be identical on every run; a model re-deriving order eventually gets it wrong |
| Agent | Plan, regression test, implement, review | No script can do these |

`run_pipeline.py` performs every deterministic step itself and returns
`needs_agent` at the four handoffs, each carrying the full payload.

## Evaluation order

The machine evaluates in this order and returns the **first** action that applies.
Order is the design: it enforces plan-before-code and red-before-fix, which no
amount of prose instruction reliably achieves.

```
 1. no intent recorded                      -> blocked
 2. preflight not ready                     -> fix_preflight
 3. no plan                                 -> plan
 4. diff unreadable                         -> blocked
 5. bugfix & no red phase                   -> write_regression_test
 6. bugfix & red phase was a harness error  -> write_regression_test
 7. bugfix & red phase exited 0             -> write_regression_test
 8. no source changes                       -> implement
 9. no test run recorded                    -> collect_evidence
10. bugfix & no green phase                 -> collect_evidence
11. no review, or review is stale           -> review
12. gates failed                            -> fix_blockers
13. required gate has no evidence           -> collect_evidence
14. PR already opened                       -> done
15. everything green                        -> open_pr
```

## Actions and payloads

### `fix_preflight`
```json
{"findings": [{"code":"detached_head","severity":"error","message":"...","fix":"git switch -c ..."}]}
```
Fix each error-severity finding. Warnings do not block.

### `plan`
```json
{"intent":"...", "kind":"bugfix", "plan_mode":"local|openspec",
 "write_to":"<path>", "delegate_to":"openspec-autopilot-skill|null",
 "delegate_command":"/openspec-autopilot-skill <intent>",
 "must_contain":["what changes and why","the files or modules in scope",
                 "how the change will be verified","what is explicitly out of scope"]}
```
When `delegate_command` is present, run it instead of writing the plan yourself,
then `dev_state.py mark --plan-written`.

The plan is considered written when the file exists with >80 characters of content,
or `--plan-written` was marked.

### `write_regression_test`
Bug fixes only. Write the smallest test that reproduces the bug **against the
current, unfixed code**. Fix nothing yet. Then record the red phase — it must exit
non-zero, and must not be a harness error.

### `implement`
```json
{"intent":"...", "kind":"...", "plan":"<path>", "scope":[...], "changed_so_far":{...}}
```

### `collect_evidence`
```json
{"missing":["tests","lint"], "commands":["python3 scripts/record_check.py --check tests --auto", ...]}
```
`run_pipeline.py` executes these itself. When invoked through `dev_state.py`
directly, run them yourself.

### `review`
```json
{"build_pack":"<command>", "audit_command":"<command>",
 "write_findings_to":".dev-autopilot/review-raw.json",
 "dimensions":["correctness","security","data-safety","error-handling","intent-fidelity"],
 "guidance":"..."}
```

### `fix_blockers`
```json
{"blockers":[{"gate":"focus-guard","code":"focus_marker_added","severity":"blocker",
              "message":"...","fix":"..."}], "verdict":"blocked"}
```
Every blocker carries a `fix`. An autonomous agent has no human to ask, so a finding
without a remedy is a dead end.

### `open_pr` / `done` / `blocked`
`blocked` carries `payload.reason`. Escalate it verbatim — do not improvise a
workaround.

## Loop protection

`NO_PROGRESS_LIMIT = 3`. Three identical consecutive actions convert to `blocked`
with the stuck action and its last payload. A loop that is not converging should
cost three cycles, not a context window.

Progress tracking is persisted in `state.json` (`last_action`, `repeat_count`), so
it survives interruption along with everything else.

## Commands

```bash
dev_state.py start  --root . --intent "..." [--kind K] [--scope 'glob' ...] [--base REF] [--ticket ID]
dev_state.py next   --root . [--json] [--max-new-suppression N] [--no-review]
dev_state.py mark   --root . [--plan-written] [--pr-opened] [--pr-url URL] [--scope ...] [--kind K]
dev_state.py status --root . [--json]
dev_state.py reset  --root .          # clears run state, keeps logs
```

## Kind inference

`start` infers `kind` from the intent when not given:

| Kind | Triggered by |
|---|---|
| `bugfix` | bug, fix, broken, regression, crash, error, fails, incorrect, wrong, defect, issue, hotfix, patch |
| `refactor` | refactor, rename, restructure, cleanup, tidy, extract, inline, simplify |
| `chore` | bump, upgrade, dependency, docs, readme, changelog, lint config, ci config, formatting |
| `feature` | anything else |

**Bugfix wins ties**, deliberately. Calling a feature a bugfix costs one extra
regression test; calling a bugfix a feature skips the red-green proof entirely. The
asymmetry decides the tie-break.

Override with `--kind` whenever the inference is wrong.

## Files under `.dev-autopilot/`

| File | Written by | Contents |
|---|---|---|
| `state.json` | `dev_state.py` | Intent, kind, slug, scope, progress counters |
| `run.json` | `record_check.py` | Every recorded check and its real exit code |
| `plan.md` | agent | The plan (standalone mode) |
| `pack.json` | `review_pack.py build` | Reviewer context pack |
| `review-raw.json` | agent | Raw review findings |
| `review.json` | `review_pack.py audit` | Audited, credibility-checked review |
| `PR.md` | `pr_body.py` | The PR description |
| `logs/*.log` | `record_check.py` | Full output of every command executed |

Add `.dev-autopilot/` to `.gitignore` — it is run state, not source.
