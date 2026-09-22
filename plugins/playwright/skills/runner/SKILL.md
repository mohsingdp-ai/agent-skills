---
name: runner
description: Playwright Test Runner. Executes tests with filters, projects, sharding, traces, and Linux focus-stealing prevention, then summarizes failures and routes them to playwright:autofix.
allowed-tools: Read, Bash
---

# Playwright Test Runner

Runs tests and reports results. It never edits code; failures go to `playwright:autofix`.

Use the project names from `playwright.config.*` (check with `npx playwright test --list`). Don't assume `chromium`.

---

## Commands

| Goal | Command |
| :--- | :--- |
| Everything, headless | `npx playwright test` |
| One file / folder | `npx playwright test tests/auth/` |
| By title or tag | `npx playwright test -g "@smoke"` |
| One project | `npx playwright test --project=<name>` |
| Only last failures | `npx playwright test --last-failed` |
| Only tests touched by git changes | `npx playwright test --only-changed` |
| Flakiness check | `npx playwright test <file> --repeat-each=3` |
| Keep traces of failures | `npx playwright test --trace=retain-on-failure` |
| Read a trace as text (agents) | `npx playwright trace open <zip>` then `trace errors` / `console` / `requests` |
| Open a trace in the viewer (humans) | `npx playwright show-trace test-results/<test>/trace.zip` |
| CI sharding | `npx playwright test --shard=1/3` |

The MCP `test_run` / `test_list` tools only take file locations and project names, so use the CLI for anything with flags.

## Headed runs on Linux without stealing focus

- Hidden: `xvfb-run npx playwright test --headed`
- Visible but no focus steal: the config passes `--class=playwright-chrome` to Chrome; add a window-manager rule for that class (for Hyprland: `windowrule = nofocus, class:playwright-chrome`).

## Report

1. Passed / failed / flaky / skipped counts.
2. Each failure: file:line, test title, first line of the error.
3. Any `test.skip` / `test.fixme` in the run, called out explicitly. Skips hide bugs.
4. Next step: `/pw:autofix <file>` for each failing file.
