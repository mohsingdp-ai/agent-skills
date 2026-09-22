# Deep Review Protocol

Adapted from Augment's automated deep-review workflow, with one substantive change:
that workflow posts severity-tagged comments **for a human to read**. Here there is
no human at that point, so the review has to survive an audit instead.

## The four steps

### 1. Gather context

```bash
python3 scripts/review_pack.py build --root . --intent "<intent>" --kind <kind> \
    --output .dev-autopilot/pack.json
```

The pack contains:

| Section | Why it is there |
|---|---|
| `diff_summary` | Size and risk level — sets the credibility bar |
| `changed_files` | The authoritative list; findings must cite one of these |
| `file_contents` | Full text of changed files **and their directory siblings** |
| `conventions` | `AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`, `.augment/rules/*`, `.cursor/rules/*` |
| `prior_notes` | Earlier review records, so feedback is not repeated |

Siblings are included because the defect a diff-only review misses most often is
**the caller that was not updated**. It is not in the diff, which is exactly why
nobody looks at it.

### 2. Check prior notes

Repeating feedback already given is the fastest way to make a reviewer ignorable.
`prior_notes` carries the last ten review records; skip anything already raised
unless the code changed underneath it.

### 3. Review against every dimension

| Dimension | Look for |
|---|---|
| `correctness` | Logic errors, off-by-one, inverted conditions, unhandled branches, wrong state transitions |
| `security` | Injection, authz/authn gaps, secrets in code, unsafe deserialization, SSRF, path traversal, missing validation at a trust boundary |
| `data-safety` | Destructive or irreversible operations, migrations with no back-out, races, lost updates, unbounded queries, N+1, missing transactions |
| `error-handling` | Swallowed exceptions, unchecked returns, partial failure leaving inconsistent state, missing timeout/retry, error paths that never execute |
| `intent-fidelity` | Does the change do what the intent asked — no more, no less? |

**Skip style nitpicks entirely when substantive issues exist.** A review that leads
with import ordering while a race condition sits three lines below has buried the
finding that mattered. Augment's workflow makes the same call, and it is right.

`intent-fidelity` deserves particular attention in autonomous work, because it is
the dimension the author-agent is least able to check. Scope creep does not feel
like a defect from the inside; it feels like thoroughness.

### 4. Write findings and audit them

```json
{
  "reviewer": "claude-opus-5",
  "context_digest": "<pack digest — proves the review matches this code>",
  "dimensions_covered": ["correctness","security","data-safety","error-handling","intent-fidelity"],
  "findings": [
    {
      "file": "src/billing/charge.py",
      "line": 88,
      "severity": "high",
      "title": "Concurrent refunds overwrite each other",
      "why": "Both refunds read the pre-refund balance and each writes it back, so the second silently overwrites the first and money is lost.",
      "suggestion": "Take a row lock, or make the UPDATE conditional on the balance that was read."
    }
  ]
}
```

```bash
python3 scripts/review_pack.py audit --pack .dev-autopilot/pack.json \
    --findings .dev-autopilot/review-raw.json --output .dev-autopilot/review.json
```

## Severity rubric

| Severity | Bar | Effect |
|---|---|---|
| `high` | Causes data loss, a security hole, or incorrect behaviour on a realistic path | **Blocks** until fixed or explicitly waived with a reason |
| `medium` | Wrong under conditions that will occur but are not the main path | Reported, does not block |
| `low` | Real but low-consequence; maintainability, edge cases unlikely in practice | Reported, does not block |

A `high` finding can be waived — set `"waived": true` **and** `"waiver_reason"`. A
silent waiver is rejected, because it is indistinguishable from ignoring the
finding.

## What the audit rejects

| Code | Rejected because |
|---|---|
| `unexplained_clean_review` | No findings on a large (≥400 lines) or high-risk change, with no substantive attestation |
| `findings_off_diff` | Cites files not in `changed_files` — the review was not reading this diff |
| `findings_malformed` | Missing file, bad severity, or a `why` under 40 characters |
| `dimensions_missing` | A required dimension was not covered |
| `dimensions_unaccounted` | No `dimensions_covered` at all — a glance is indistinguishable from a review |
| `stale_context` | `context_digest` does not match the pack — the code moved after the review |
| `waiver_without_reason` | A finding waived with no reason given |

## The rubber-stamp check

`unexplained_clean_review` is the one that matters, and it is worth being explicit
about what it assumes.

When an agent reviews a change it wrote, the most likely output is not a wrong
finding. It is **no finding**. So on a change that is large or touches something
risky, "I found nothing" is treated as a claim that needs support rather than a
result.

To pass with zero findings on such a change, supply a `clean_attestation` of at
least 200 characters naming, per dimension, what you examined and why it is sound.
Not "reviewed thoroughly, no issues" — that is the assertion the gate exists to
reject. Something closer to:

> Correctness: the only branch added is the `pct > 100` clamp; the existing paths
> are unchanged and the two boundary values are covered by tests. Security: no new
> input crosses a trust boundary; the function is called only from the pricing
> service, which already validates. Data-safety: pure function, no I/O, no shared
> state. Error-handling: no new failure modes; the clamp cannot raise.
> Intent-fidelity: the plan asked only for the lower-bound clamp, and only that was
> added — the symmetric negative-pct case is filed as a separate low finding.

On a small, low-risk change zero findings is accepted without attestation. Demanding
ceremony proportional to nothing is how gates get disabled.

## Timing

Review **after** the change is stable and green, never during implementation. A
review of code that is about to change is wasted, and the `stale_context` check will
reject it anyway once the code moves.
