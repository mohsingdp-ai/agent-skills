---
name: generator
description: Playwright Test Agent - Generator. Delegates to the official playwright-test-generator subagent to turn an approved specs/ plan into executable Playwright tests (one scenario per file), reviews the output against locator/assertion rules, and runs it.
allowed-tools: Read, Grep, Glob, Write, Edit, Bash, Agent
---

# Playwright Test Agent: Generator

Turns an approved plan from `specs/` into `*.spec.ts` files.

The official **`playwright-test-generator`** subagent ([docs](https://playwright.dev/docs/test-agents)) does the writing. It performs each step live in a browser before writing it down, so selectors are real. This skill feeds it scenarios and checks what comes back.

---

## Steps

1. **Preflight.** Run the `playwright:init` preflight.
2. **Pick scenarios.** Read the plan (`$ARGUMENTS`, or the newest file in `specs/`). The plan should be user-approved; if unsure, ask.
3. **Delegate, one scenario per call.** For each scenario spawn `playwright-test-generator` with:
   - `test-suite`: the top-level plan heading
   - `test-name`: the scenario title
   - `test-file`: `<testDir>/<feature>/<scenario-slug>.spec.ts`
   - `seed-file`: the seed path from the plan
   - `body`: the scenario steps and expected results

   Independent scenarios can run as parallel subagents.
4. **Review each file** against these rules. Fix violations by hand:
   - Locators: `getByRole` → `getByLabel` → `getByPlaceholder` → `getByText` → `getByTestId`. No CSS chains, no XPath.
   - Assertions: web-first only (`await expect(locator).toBeVisible()`), never `expect(await locator.isVisible())`.
   - No `waitForTimeout`, no `networkidle`.
   - No `if (await x.isVisible())` branches. A test asserts; it doesn't guess.
   - Each test stands alone. Login comes from fixtures/`storageState`, not a repeated UI login.
5. **Run:** `npx playwright test <new files>`.
   - Pass → report.
   - Fail → hand off to `playwright:autofix` (it decides app bug vs test bug and uses the healer when the test is at fault).

Fallback without the agents: write the tests by hand following the rules in step 4, then run step 5.
