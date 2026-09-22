# Eval — dev-autopilot-skill

## What is being measured

The skill's value is not that it runs tests and calls a reviewer — any script can do
that. It is that **an unattended run cannot report success without evidence, and
cannot be argued into it.** So the loss function targets the gate engine: given a
run record, does it reach the right verdict, refuse to go green on silence, and
explain every blocker well enough that an agent can act without a human?

The scored surface is `run_pipeline.py --input ... --output ...` (audit mode), which
is deterministic and side-effect free: no git, no subprocesses, no network, no repo
mutation. That is deliberate — it lets the evals score the interesting part (the
gate logic) without needing a repository in a particular state, and it means a
failing eval always points at logic rather than at the environment.

Note the exit-code contract: audit mode exits **0 whenever the audit ran**, even
when the verdict is `blocked`. Correctly refusing a bad change is a successful
audit. `audit_ok` reports whether the audit ran; `pr_ready` reports whether the
change may ship.

## Criteria

1. **valid-json** — the audit writes parseable JSON. Everything downstream branches
   on this file.

2. **verdict-schema** — every required top-level key is present, so a caller can
   branch without defensive parsing.

3. **findings-actionable** — every blocker and every missing-evidence entry carries
   `gate`, `code`, `severity`, `message` and `fix`. An autonomous agent has no human
   to ask, so a finding without a remedy is a dead end.

4. **deterministic-order** — blockers and missing-evidence entries are sorted by
   `(code, gate)`. Unstable ordering makes the regression gate flap and hides real
   diffs behind reshuffling.

5. **no-green-without-evidence** — the load-bearing one. `pr_ready` is true **only
   if** `evidence_complete` is true and no required gate is `skip`. This encodes the
   skill's entire contract as a check: if this criterion can be made to pass while a
   required gate reported `skip`, the self-verification guarantee is void.

6. **blocker-explains-consequence** (judge) — each blocker names what actually
   breaks and when, not merely that a rule was violated. "A focused suite exits 0
   while running only the focused tests, so every green signal downstream of it is
   meaningless" is useful; "focus marker found" is not. An agent fixes what it
   understands.

## Golden cases

| Case | Split | What it pins |
|---|---|---|
| `case-1-focus-marker` | val | A `.only` added → `focus_marker_added`. The silently-green trap: exit 0 having run almost nothing. |
| `case-2-clean-feature` | val | Everything green with full evidence → **`pr_ready`**. Guards against a gate engine that blocks everything, which would pass criteria 1–5 while being useless. |
| `case-3-bugfix-no-red-proof` | val | `kind: bugfix`, suite green, no red-green record → **`needs_evidence`**, not `blocked` and emphatically not `pr_ready`. Pins the distinction between "checked and broken" and "never checked". |
| `case-4-rubber-stamp-review` | **test** | Holdout. 605-line diff across auth and money, suite green, review credible=false → `review_not_credible`. |
| `case-5-suppression-and-vacuous` | val | Three independent blockers at once: skips over budget, a suite that exited 0 having run zero tests, and files changed outside the declared scope. Pins that gates are independent rather than short-circuiting at the first failure. |

`case-4` is the holdout: skipped by default, never promoted, scored only with
`--include-holdout`. It is the one case an optimization loop never sees, and it
tests the property most likely to be over-fitted — the credibility bar for a review
of a large, risky change.

`case-2` earns its place by being the only case that must come back **green**. A
gate engine that refuses everything satisfies every other criterion here; this is
what stops that.

```json
{
  "skill": "dev-autopilot-skill",
  "run": "python3 scripts/run_pipeline.py --input {input} --output {output}",
  "criteria": [
    {
      "id": "valid-json",
      "text": "The audit output is parseable JSON",
      "type": "command",
      "cmd": "python3 -c \"import json,sys; json.load(open(sys.argv[1]))\" {output}"
    },
    {
      "id": "verdict-schema",
      "text": "Output carries audit_ok, verdict, pr_ready, evidence_complete, summary, gates, blockers, missing_evidence and warnings",
      "type": "command",
      "cmd": "python3 -c \"import json,sys; d=json.load(open(sys.argv[1])); sys.exit(0 if {'audit_ok','verdict','pr_ready','evidence_complete','summary','gates','blockers','missing_evidence','warnings'} <= set(d) else 1)\" {output}"
    },
    {
      "id": "findings-actionable",
      "text": "Every blocker and missing-evidence entry has gate, code, severity, message and a fix",
      "type": "command",
      "cmd": "python3 -c \"import json,sys; d=json.load(open(sys.argv[1])); items=d['blockers']+d['missing_evidence']; sys.exit(0 if all({'gate','code','severity','message','fix'} <= set(x) and str(x.get('fix','')).strip() for x in items) else 1)\" {output}"
    },
    {
      "id": "deterministic-order",
      "text": "Blockers and missing-evidence entries are sorted by (code, gate)",
      "type": "command",
      "cmd": "python3 -c \"import json,sys; d=json.load(open(sys.argv[1])); k=lambda xs:[(x['code'],x['gate']) for x in xs]; sys.exit(0 if all(k(xs)==sorted(k(xs)) for xs in (d['blockers'],d['missing_evidence'])) else 1)\" {output}"
    },
    {
      "id": "no-green-without-evidence",
      "text": "pr_ready is true only when evidence_complete is true and no required gate was skipped",
      "type": "command",
      "cmd": "python3 -c \"import json,sys; d=json.load(open(sys.argv[1])); skipped=[g for g in d['gates'] if g.get('required') and g.get('status')=='skip']; sys.exit(0 if (not d['pr_ready']) or (d['evidence_complete'] and not skipped) else 1)\" {output}"
    },
    {
      "id": "blocker-explains-consequence",
      "text": "Each blocker message names the failure it causes and when, not merely that a rule was broken",
      "type": "llm-judge"
    }
  ],
  "judge": {
    "model": "claude-sonnet-5",
    "temperature": 0,
    "canary": "canary/bad_output.json"
  },
  "golden": [
    {"id": "case-1-focus-marker", "input": "golden/case-1-focus-marker/input.json", "expected": "golden/case-1-focus-marker/expected.json", "split": "val"},
    {"id": "case-2-clean-feature", "input": "golden/case-2-clean-feature/input.json", "expected": "golden/case-2-clean-feature/expected.json", "split": "val"},
    {"id": "case-3-bugfix-no-red-proof", "input": "golden/case-3-bugfix-no-red-proof/input.json", "expected": "golden/case-3-bugfix-no-red-proof/expected.json", "split": "val"},
    {"id": "case-4-rubber-stamp-review", "input": "golden/case-4-rubber-stamp-review/input.json", "expected": null, "split": "test", "expected_status": "pending-first-green"},
    {"id": "case-5-suppression-and-vacuous", "input": "golden/case-5-suppression-and-vacuous/input.json", "expected": "golden/case-5-suppression-and-vacuous/expected.json", "split": "val"}
  ]
}
```

## The canary

`canary/bad_output.json` is a well-formed verdict whose blocker messages are
contentless — "Invalid.", "Bad value." It satisfies every `command` criterion (valid
JSON, correct schema, sorted, has a `fix` string) and must **fail**
`blocker-explains-consequence`. A judge run where the canary passes is invalid and
its scores are discarded — that is what stops a judge that has drifted into
approving anything from silently certifying the suite.

## Running

```bash
python3 scripts/run_evals.py --validate          # spec is well-formed
python3 scripts/run_evals.py --rollout           # score val cases
python3 scripts/run_evals.py --rollout --judge   # include the judged criterion
python3 scripts/run_evals.py --rollout --include-holdout   # release scoring only
```
