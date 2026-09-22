---
description: Run visual regression snapshots and Axe-core accessibility audits on target routes
argument-hint: [route or component path]
---

# /pw:audit

Invoke the `playwright:visual-a11y` skill on `$ARGUMENTS` and follow it exactly.

- Reports snapshot diffs and WCAG 2.1 AA violations with fixes.
- Never updates baselines without your confirmation.
