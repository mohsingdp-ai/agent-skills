# The eleven kinds

`--kind` decides what "done" means. It is the highest-leverage thing you type,
because it selects the criteria the run is scored against and those are locked a
moment later.

Pick by **what the deliverable is**, not by what the work feels like. "Investigate
why checkout is slow" is `debug` if the deliverable is an explanation and `perf`
if it is a faster endpoint.

`python3 scripts/contract.py kinds` prints this list with aliases
(`bug`→`bugfix`, `rca`→`debug`, `fixture`→`test`, `optimize`→`perf`, …).

---

## Code-producing kinds

### `bugfix` — a reported defect

| | |
|---|---|
| Visible | `reproducer` (3), `suite` (2) |
| Baseline | **must be red** — the reproducer has to fail before anything is fixed |
| Holdout | focus markers, suppressions, scope |

The baseline is the whole point. A green suite *after* a fix proves nothing: it
was green before the fix too, which is precisely how the bug shipped. Only a test
that fails without the fix proves the fix addresses the reported bug.

If your reproducer passes at baseline you get `fix_reproducer`, not credit.

### `feature` — new behaviour

| | |
|---|---|
| Visible | `acceptance` (3), `suite` (2) |
| Baseline | must be red |
| Holdout | focus markers, suppressions, scope |

Turn each acceptance criterion into one named test *before* implementing. If the
acceptance tests pass at baseline, the feature was not missing — re-read the
request, because you have misunderstood what was asked for.

### `missing` — functionality assumed present but absent

A stub, a `TODO`, a `NotImplementedError`. Same shape as `feature`; the
distinction is that callers already exist. Find every one of them first: absent
behaviour usually has more than one expected shape, and satisfying the first
caller you find is how you end up satisfying only that one.

### `refactor` — behaviour-preserving change

| | |
|---|---|
| Visible | `suite` (3), `tests-unchanged` (2) |
| Baseline | must be **green** — you cannot preserve behaviour that is already broken |
| Objective | **complexity**, not criteria |
| Holdout | focus markers, suppressions, scope |

The purest analogue of autoresearch. The criteria only gate correctness, so they
are satisfied from attempt zero and the number actually being minimised is total
source lines in scope. Deleting code with the score unchanged is a *keep*.

Two consequences worth internalising:

- **The run ends by converging, not by going green.** When no further
  simplification is found, that is success.
- **Editing a test to make a refactor pass is editing the metric.**
  `tests-unchanged` fails the attempt, and it is a visible criterion, so you will
  not even reach the holdout.

### `perf` — optimization against a benchmark

| | |
|---|---|
| Visible | `suite` (3), `benchmark` (2, must be red at baseline) |
| Baseline | records the number to beat |
| Holdout | focus markers, suppressions, scope |

The closest kin to `val_bpb`. Declare the benchmark in the contract before
locking:

```json
"benchmark": {
  "cmd": "python3 bench/orders.py",
  "direction": "lower",
  "pattern": "^latency_ms:\\s*([0-9.]+)"
}
```

The guard runs `cmd`, parses the first capture group as a float, and compares it
with `.autoresearch/benchmark_baseline.json`. Without a `pattern` it looks for a
line like `metric: 12.34` (also `score`, `time`, `duration`, `ops`, `latency`).

The baseline measurement deliberately reports **failure**: recording a number is
not improving on it, and free credit for having measured something would let the
loop finish before optimizing anything.

An optimization with no benchmark is a guess. Report the delta, not an adjective.

### `integration` — wiring two systems together

| | |
|---|---|
| Visible | `e2e` (3, red at baseline), `suite` (2) |
| Holdout | focus markers, suppressions, scope |

Unit tests on both sides of a boundary can pass while the boundary itself is
broken; that is the characteristic failure of integration work. The criterion must
cross the seam. Record in the contract whether the far side is real or stubbed —
a green e2e against a stub is a different claim from a green e2e against the
actual service, and six months later nobody will remember which one this was.

---

## Test and documentation kinds

### `test` — new tests or fixtures

| | |
|---|---|
| Visible | `new-tests-pass` (2), `mutation` (3, red at baseline) |
| Holdout | scope |

Graded on whether the tests can *fail*, not on whether they pass. The mutation
guard applies one small textual change to the source (`true`→`false`, `==`→`!=`,
`<=`→`>`, …), runs the suite, restores the file, and requires at least one
mutation to be killed.

At baseline this is red for a genuinely useful reason: before the tests exist,
mutating the code does not turn the suite red, and that gap is exactly the task.

Restrict what gets mutated when the default (changed non-test files) is too broad:

```json
"mutation": {"targets": ["src/pricing/**/*.py"]}
```

A test that passes no matter what the code does is worse than no test. It buys
false confidence, and false confidence is what stops anybody looking again.

### `docs` — documentation

| | |
|---|---|
| Visible | `examples-run` (3), `suite` (1) |
| Baseline | green is fine — docs tasks are not always about absence |
| Holdout | scope |

Every fenced ` ```bash `, ` ```sh `, or ` ```python ` block in the matched files is
executed. Mark a block `no-run` on the fence line to exempt it — sparingly, since
an unexecuted example is an unverified claim.

Narrow the search with `"docs": {"paths": ["docs/**/*.md"]}` in the contract.

Document what the code does, verified by running it — not what the names suggest.

---

## Deliverable-is-prose kinds

These three write to `.autoresearch/findings.md`. They produce no code, and the
baseline is red because the deliverable does not exist yet — which also catches a
stale `findings.md` left behind by a previous run getting free credit.

### `debug` — root-cause analysis

| | |
|---|---|
| Visible | `reproducer` (3, red at baseline), `findings` (2) |

Root cause means the line that produces the wrong value, not the line that reports
it. Stop at the reproducer plus the written cause; do not fix unless fixing was
asked for — a `debug` run that quietly turns into a `bugfix` run is scored against
the wrong contract.

### `review` — code review

| | |
|---|---|
| Visible | `findings` (3, red at baseline), `anchored` (2) |

`anchored` requires every cited `path:line` to land inside the reviewed diff, which
kills the most common failure of automated review: confident findings about code
the change never touched.

Review as an adversary of the change, not its author. A finding without a named
consequence is a style opinion — drop it, because it buries the ones that matter.

### `research` — investigation

| | |
|---|---|
| Visible | `answers` (3, red at baseline), `sourced` (2) |

`sourced` requires every `##` section to contain at least one `file:line` or URL.
An uncited claim is a guess wearing a suit.

Prefer reading the source over reading about it. When the answer is "this codebase
does not do that", say so plainly and show where you looked — a confident wrong
answer costs more than an honest empty one.

---

## Choosing when it is ambiguous

| The ask | Kind | Why |
|---|---|---|
| "why is this slow" | `debug` | deliverable is an explanation |
| "make this faster" | `perf` | deliverable is a number that moved |
| "clean this up" | `refactor` | behaviour must not change |
| "this function is missing a case" | `bugfix` | a case that should work does not |
| "we never implemented X" | `missing` | it was never there to break |
| "is this PR OK" | `review` | deliverable is findings |
| "add tests for X" | `test` | graded by mutation, not coverage |

When two fit, pick the one whose criteria you would actually want enforced. That
is the question the contract is really asking.
