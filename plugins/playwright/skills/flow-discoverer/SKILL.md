---
name: flow-discoverer
description: Hybrid Static & Dynamic User Flow Discovery. Mines routes and navigation from the codebase, crawls the live UI once per persona through the official playwright-test-planner agent, writes a Mermaid flow map plus a smoke-test plan to specs/flows/, and hands the plan to playwright:generator.
allowed-tools: Read, Grep, Glob, Write, Edit, Bash, Agent
---

# Playwright Flow Discovery (`flow-discoverer`)

Maps what users can actually do in the app, per persona, and turns that map into smoke tests.

It reuses the rest of the plugin instead of crawling on its own:
- Live crawling → official **`playwright-test-planner`** subagent (browser tools from the `playwright-test` MCP server).
- Writing tests → **`playwright:generator`**.

```text
1. Static scan ──► 2. Crawl per persona ──► 3. Flow map + plan ──► 4. Generate smoke tests
   (routes, nav)      (planner agent)          (specs/flows/)          (playwright:generator)
```

---

## Personas

Personas are **project config, not plugin config.** Read them from `specs/personas.md`. If it doesn't exist, ask the user and create it:

```markdown
| Persona  | storageState file            | Login env vars                        |
| :------- | :--------------------------- | :------------------------------------ |
| personal | playwright/.auth/personal.json | PERSONAL_USER_EMAIL, PERSONAL_USER_PASSWORD |
| business | playwright/.auth/business.json | BUSINESS_USER_EMAIL, BUSINESS_USER_PASSWORD |
```

Never write real emails, passwords, or account IDs into skill files, plans, or tests. They live in env vars.

Each persona needs its own setup project + `storageState` (see `playwright:fixtures`) and a seed that runs as that persona (`seed.<persona>.spec.ts`).

---

## Phase 1: Static scan

Find the routes and entry points, so the crawl has a checklist:
- Next.js app router: `app/**/page.tsx`. Pages router: `pages/**`.
- React Router / others: `grep -rnE "path[:=]|createBrowserRouter" <src>`.
- Nav items: sidebar / header / tab components.

Limit to `$ARGUMENTS` (a route or module) when given.

## Phase 2: Crawl per persona

Run the `playwright:init` preflight, then spawn one `playwright-test-planner` per persona (they can run in parallel):

> Seed: `seed.<persona>.spec.ts`. Visit these routes: <list from Phase 1>. On each, record reachable links, tabs, buttons that open dialogs/drawers, and forms. Do not submit forms that move money, send messages, or delete data. Note any console error or 4xx/5xx. Save the result to `specs/flows/<module>.<persona>.md`.

## Phase 3: Flow map + smoke plan

Merge the persona results into `specs/flows/<module>.md`:

1. A Mermaid `flowchart TD` of routes → screens → dialogs, with edges labelled by persona where they differ.
2. A table of what each persona can and cannot see.
3. Errors seen during the crawl (these are bugs: report them, don't bake them into tests).
4. A smoke-test plan in the planner's format: one scenario per route/dialog per persona, each with steps and an expected result.

Show the file to the user for review.

## Phase 4: Generate smoke tests

After approval, run `playwright:generator` on `specs/flows/<module>.md`. Tests go under `<testDir>/flows/<module>/`.

Smoke tests assert; they don't branch. If a persona should not see a button, the test asserts `toBeHidden()`. It never wraps a step in `if (await x.isVisible())`.
