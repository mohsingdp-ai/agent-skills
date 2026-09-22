---
name: healer
description: Playwright Test Agent - Healer. Delegates to the official playwright-test-healer subagent to repair broken test code (stale locators, timing races, setup) and rejects any healing that skips the test or changes what it expects. Test-side only; use playwright:autofix when the app itself may be wrong.
allowed-tools: Read, Grep, Glob, Write, Edit, Bash, Agent
---

# Playwright Test Agent: Healer

Repairs **test code** only. It never edits the app.

The official **`playwright-test-healer`** subagent ([docs](https://playwright.dev/docs/test-agents)) does the debugging: it pauses the test at the failure and inspects the live page. This skill adds one guardrail.

## The guardrail

The official healer, when it believes the app is broken, marks the test `test.fixme()` so it is skipped. **This plugin does not allow that.** A skipped test hides a bug.

| Healer result | What this skill does |
| :--- | :--- |
| Fixed locator / wait / setup, expected values unchanged | Keep it |
| Added `test.fixme()` / `test.skip()` | Revert it. Report "app bug suspected" with the healer's comment, and suggest `/pw:autofix` |
| Changed an expected value (text, count, URL, status) | Revert it, unless the behaviour changed on purpose: a line in the plan in `specs/`, or the commit / PR that made the change. Cite it |
| Raised a timeout or added `waitForTimeout` | Revert it. Replace with a web-first assertion or `waitForResponse` |

---

## Steps

1. **Preflight.** Run the `playwright:init` preflight.
2. **Record** `git diff --stat` so you can see exactly what the healer changes.
3. **Delegate.** Spawn `playwright-test-healer` with the failing test(s) from `$ARGUMENTS` and this instruction:
   > Heal only locators, waits, and test setup. Do not change expected values. If you believe the app is broken, add `test.fixme()` with a comment and stop.
4. **Apply the guardrail** table above to the healer's diff.
5. **Verify:** `npx playwright test <file> --repeat-each=3`. All 3 must pass.
6. **Report** what was broken, what changed, and any suspected app bug.

Fallback without the agents: run with `--trace=retain-on-failure`, read `error-context.md` and the trace as text (`npx playwright trace open <zip>`, then `trace errors` / `console` / `requests`), and fix the test by hand under the same guardrail.
