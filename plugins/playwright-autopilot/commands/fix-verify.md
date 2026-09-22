---
description: Surgically fix an application bug, heal test locators, and gate verification via Playwright E2E + Chrome DevTools UI (skipping Vitest).
argument-hint: "[spec path or issue description]"
---

# /pw-autopilot:fix

Perform a targeted surgical fix and dual-gate verification on a specific defect or test failure.

## Execution Steps
1. Run target spec with `--trace=on`.
2. Check external API docs if defect touches third-party integrations (e.g. Equals Money).
3. Apply surgical edits in `src/`.
4. Heal locators without skipping tests.
5. Verify via Playwright E2E (`exit code 0`).
6. Verify live DOM and 0 console errors in Chrome DevTools. **Skip Vitest**.
7. Commit atomically. Keep pre-push locked.
