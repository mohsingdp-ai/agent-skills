---
description: Run Playwright tests with project filters, tracing, and Linux focus-stealing prevention
argument-hint: [optional flags, files, or filters]
---

# /pw:test

Invoke the `playwright:runner` skill on `$ARGUMENTS` and follow it exactly.

- Passes `$ARGUMENTS` straight to `npx playwright test`.
- Reports counts, each failure, and any skipped tests; suggests `/pw:autofix` for failures.
