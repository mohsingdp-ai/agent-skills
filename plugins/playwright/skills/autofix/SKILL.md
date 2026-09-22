---
name: autofix
description: Autonomous Playwright Test & Application Code Auto-Repair Loop. Finds why a test fails (trace as text, official test_debug when needed), fixes the application source code when the app is wrong, fixes the test only when the test is wrong (official healer for unclear locator/timing breaks), and re-verifies until green with zero test suppression.
allowed-tools: Read, Grep, Glob, Write, Edit, Bash, Agent
---

# Playwright Test & Application Auto-Repair (`autofix`)

A closed loop: run the failing test, find out whether the **app** or the **test** is wrong, fix that side, and re-run until green.

It uses the official Playwright Test Agents ([playwright.dev/docs/test-agents](https://playwright.dev/docs/test-agents)) where they add something, and the plain CLI where it does more:

| Need | Use |
| :--- | :--- |
| Run and verify tests | CLI `npx playwright test`. The MCP `test_run` only takes locations and projects: no `--workers`, `--repeat-each` or trace flags |
| Inspect a failure | `error-context.md` + trace as text (Step 2). If that isn't enough: MCP `test_debug`, which pauses at the error on a live page |
| Repair a stale locator / timing race you can't pin down | `playwright:healer` → official `playwright-test-healer` subagent |

The one thing autofix adds on top: **when the app is wrong, fix the app.** The official healer never touches app code; when it thinks the app is broken it marks the test `test.fixme()`. Autofix treats that as a signal, not an outcome.

---

## 🛑 The Non-Negotiable Contract

1. **Zero suppression.** No `test.skip()`, `test.fixme()`, `test.fail()`, loosened assertions, or raised timeouts in the final diff. If the healer adds a `fixme`, revert it and go to Step 4.
2. **Fix the side that is wrong.** App returns wrong data / crashes → edit app code. Test uses a stale selector or races the app → edit the test.
3. **Never change what the test expects to make it pass**, unless you can show the behaviour changed on purpose: a line in the plan in `specs/`, or the commit / PR that made the change deliberately. Cite it in the report.
   Unit tests broken by an app fix may follow the new mechanism (e.g. what they mock), never a new expected result. List them in the report.
4. **Minimal blast radius.** Touch only files needed for this defect.
5. **Machine-verified proof.** Done only when the previously failing test passes 3 runs in a row.

---

## 0. Preflight

1. Run the `playwright:init` preflight. The MCP tools are only needed for `test_debug` (Step 2) and the healer (Step 5); everything else uses the CLI.
2. Find the app source root from the config's `webServer.command` / `package.json` (do not assume `src/`).
3. **Find out how the running app picks up your edits.** Tests hit whatever server `baseURL` points at, not your files.
   - Dev server with hot reload (usually the config's `webServer`) → edits show up by themselves.
   - Prebuilt or containerized app (`E2E_BASE_URL` set, `next start`, a docker stack) → find its rebuild command in the README / CLAUDE.md / scripts. You must run it after every app edit, before Step 6.
   - Remote deploy you can't rebuild → you can still fix, but say the fix is **unverified**.
4. Record `git status --porcelain` so the report only covers files this run changed.

## 1. Reproduce

Target = `$ARGUMENTS`, else the last failures.

```bash
npx playwright test <target> --reporter=line --trace=retain-on-failure --workers=1   # no target → --last-failed
```

Run it **alone, with one worker**. A test that fails in the full suite but passes alone is **flaky**: report it, don't edit code. Typical signs: crashed browser, click timeout, or the login session dropping mid-test (a redirect to the login page in the trace's requests).

Already green → stop and say so. Nothing to fix.

Several tests failing with the same error usually share one root cause. Group them and fix the cause once.

## 2. Inspect at the point of failure

Read `error-context.md` in the test's `test-results/` folder (error + page snapshot), then query the trace as text:
  ```bash
  npx playwright trace open test-results/<test>/trace.zip
  npx playwright trace errors      # errors with stack traces
  npx playwright trace console     # browser console
  npx playwright trace requests    # network; `trace request <id>` for one body
  npx playwright trace close
  ```
  (`show-trace` opens a GUI window: for humans, not agents.)

Still unclear, and the MCP tools pass the `playwright:init` preflight → `test_debug` the test; it pauses on the error so you can read `browser_snapshot`, `browser_console_messages`, `browser_network_requests` on the live page.

Collect: the failing step, the assertion message, console errors, and any non-2xx network response.

## 3. Decide: app bug or test bug

Decide from evidence, not a prior.

| Evidence | Verdict |
| :--- | :--- |
| Uncaught console error, 4xx/5xx from own API while correctly logged in, element missing because a render/branch is wrong, valid input rejected, wrong value shown | **App bug** → Step 4 |
| Element exists with a new name/role/label that matches an intentional UI change, strict-mode multi-match, action ran before the app was ready, test setup missing (no login → 401 or a redirect to login) | **Test bug** → Step 5 |
| The broken response comes from a service outside this repo (backend, another microservice, a third-party sandbox) | **Out of scope** → stop and report the failing request, its status and body. Don't work around it here |
| Unsure | Step 5 first; if the healer adds `fixme`, it is an app bug |

## 4. Fix the app

1. Trace from the failing element / request to the component, handler, or data code that produced it.
2. Fix the root cause there. If several callers share the broken function, fix the shared function.
3. Run the project's typecheck/lint if it has one.
4. Revert any `test.fixme()` / `test.skip()` the healer added.
5. If the app is prebuilt (Preflight step 3), rebuild it now.
6. Go to Step 6.

## 5. Fix the test

- **Cause already pinned down** (missing login/setup, an expected value that changed on purpose with evidence per contract rule 3): fix it directly, under the `playwright:healer` guardrail table.
- **Locator or timing broken and the cause isn't clear**: run the `playwright:healer` skill. It spawns the official healer and reverts any skip, `fixme`, or changed expected value.
  - Healer reports "app bug suspected" → Step 4.

Then → Step 6.

## 6. Verify

Rebuild first if the app is prebuilt and anything in it changed since the last build.

```bash
npx playwright test <target> --repeat-each=3 --workers=1
```

Then check side effects of an app fix: run the whole folder the target lives in once, plus the unit tests for the files you changed.

Still failing → back to Step 2 with the new error. **Stop after 3 full rounds** and report what you found; do not keep editing blindly.

## 7. Report

1. Verdict per test: app bug, test bug, flaky, or out of scope, plus the evidence that decided it.
2. Root cause in one line.
3. Files changed by this run (`git diff --stat`, excluding what Preflight step 4 recorded).
4. Proof: the 3 green runs.
5. If stopped at the round limit: the last error and the best current guess.
