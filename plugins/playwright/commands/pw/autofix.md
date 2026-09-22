---
description: Autonomous loop: runs Playwright test, diagnoses failure, fixes the application source code (or test), and re-verifies until green
argument-hint: [path/to/spec.ts or test title]
---

# /pw:autofix

Invoke the `playwright:autofix` skill on `$ARGUMENTS` and follow it exactly.

- No arguments → the last failed tests.
- App wrong → fix app code. Test wrong → heal the test. Never skip, `fixme`, or weaken a test.
- Done only after 3 green runs in a row. Stops after 3 repair rounds and reports.
