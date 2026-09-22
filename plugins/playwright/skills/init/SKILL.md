---
name: init
description: Playwright Project & Agent Bootstrapper. Installs Playwright, runs the official `npx playwright init-agents --loop=claude` (planner/generator/healer subagents + playwright-test MCP server + seed test), and owns the preflight check every other playwright:* skill runs first.
allowed-tools: Read, Grep, Glob, Write, Edit, Bash
---

# Playwright Project & Agent Bootstrapper (`init`)

Sets up Playwright and the official Playwright Test Agents ([playwright.dev/docs/test-agents](https://playwright.dev/docs/test-agents)). Every other skill in this plugin depends on what this one installs.

---

## What the official init installs

`npx playwright init-agents --loop=claude` creates:

| File | What it is |
| :--- | :--- |
| `.claude/agents/playwright-test-planner.md` | Planner subagent: explores the app, saves plans to `specs/` |
| `.claude/agents/playwright-test-generator.md` | Generator subagent: turns a plan into `*.spec.ts`, checking each step live |
| `.claude/agents/playwright-test-healer.md` | Healer subagent: debugs and repairs failing tests |
| `.mcp.json` → `playwright-test` | MCP server (`npx playwright run-test-mcp-server`) giving the agents browser + test tools |
| `specs/README.md` | Folder for Markdown test plans |
| `seed.spec.ts` (inside the project's `testDir`) | Seed test: the starting page state every agent builds from |

The agent files are generated: **don't hand-edit them**, and re-run init after every Playwright upgrade so they match the installed version. `.mcp.json` is yours to edit after init (Setup steps 3–4).

---

## Preflight (other skills run this first)

1. `npx playwright --version` succeeds and a `playwright.config.*` exists.
2. `.claude/agents/playwright-test-{planner,generator,healer}.md` exist and `.mcp.json` has a `playwright-test` server.
3. `mcp__playwright-test__*` tools are available in this session.
4. Those tools test **this checkout**. Claude also loads `.mcp.json` from parent folders, so in a monorepo or git worktree the `playwright-test` server can belong to another checkout. Read the `.mcp.json` that defines it (this folder, then each parent): its `command`/`args`/`cwd` and `-c` config must resolve to this checkout, and its `env` must point at the app you mean to test.

- 1 fails → do **Setup** below.
- 2 fails → do Setup steps 3–4 (they protect `.mcp.json`).
- 3 fails (files exist, tools don't) → tell the user to restart Claude Code and approve the `playwright-test` MCP server. Until then, skills fall back to the plain `npx playwright test` CLI.
- 4 fails → don't use the `mcp__playwright-test__*` tools this session (they'd test the wrong code). Use the CLI fallback, and tell the user to start Claude from a folder whose `.mcp.json` points here, or run it with `--mcp-config <this checkout>/.mcp.json --strict-mcp-config`.

---

## Setup

1. **Install** (use the project's package manager):
   ```bash
   npm i -D @playwright/test
   npx playwright install --with-deps chromium
   ```
2. **Config.** If there is no `playwright.config.ts`, create one. If there is one, keep its `testDir` and project names and only add what's missing:
   ```typescript
   import { defineConfig, devices } from '@playwright/test';

   export default defineConfig({
     testDir: './tests',
     fullyParallel: true,
     forbidOnly: !!process.env.CI,
     retries: process.env.CI ? 2 : 0,
     reporter: [['list'], ['html', { open: 'never' }]],
     use: {
       baseURL: process.env.E2E_BASE_URL || 'http://localhost:3000',
       trace: 'retain-on-failure',
       screenshot: 'only-on-failure',
     },
     projects: [
       {
         name: 'chromium',
         // --class lets a Linux window manager rule keep headed runs from stealing focus
         use: { ...devices['Desktop Chrome'], launchOptions: { args: ['--class=playwright-chrome'] } },
       },
     ],
     webServer: process.env.E2E_BASE_URL
       ? undefined
       : { command: 'npm run dev', url: 'http://localhost:3000', reuseExistingServer: !process.env.CI },
   });
   ```
3. **Agents.** `init-agents` **overwrites `.mcp.json`**, which deletes any other MCP servers in it. So:
   ```bash
   [ -f .mcp.json ] && cp .mcp.json .mcp.json.bak
   npx playwright init-agents --loop=claude          # add --project <name> if there are several
   ```
   Then merge every server from `.mcp.json.bak` back into `.mcp.json` (keep the new `playwright-test` entry) and delete the backup. It keeps an existing seed file and overwrites the agent files, which is expected.
4. **MCP server env.** The `playwright-test` server runs the tests itself, so it needs the same env vars the tests read (base URL, login mode, etc.). Add them under the server's `env` in `.mcp.json`, e.g. `"env": { "E2E_BASE_URL": "http://localhost:3000" }`. If `playwright.config.ts` isn't in the folder Claude starts in, add `"-c", "<path>/playwright.config.ts"` to its `args`.
5. **Seed.** Fill in the generated `seed.spec.ts` so it reaches the page state every test starts from. If the app needs login, import `test` from the project's fixtures (see `playwright:fixtures`) so the seed runs signed in.
6. **Check:** `npx playwright test seed.spec.ts` passes.
7. Tell the user to restart Claude Code so the MCP server loads.
