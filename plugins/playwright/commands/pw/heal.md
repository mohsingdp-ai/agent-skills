---
description: Repair a failing Playwright test (test code only) without skipping or masking defects
argument-hint: [path/to/failing.spec.ts]
---

# /pw:heal

Invoke the `playwright:healer` skill on `$ARGUMENTS` and follow it exactly.

- Uses the official healer agent, then reverts any skip, `fixme`, or changed expected value.
- Suspected app bug → reported; run `/pw:autofix` to fix the app.
