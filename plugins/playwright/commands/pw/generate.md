---
description: Generate Playwright tests from an approved specs/ plan using the official generator agent
argument-hint: [path/to/specs/plan.md]
---

# /pw:generate

Invoke the `playwright:generator` skill on `$ARGUMENTS` and follow it exactly.

- One scenario per test file, checked live in the browser.
- Runs the new tests; failures go to `/pw:autofix`.
