---
description: Bootstrap Playwright in the current project and initialize official Playwright Test Agents
---

# /pw:init

Invoke the `playwright:init` skill and follow it exactly.

- Installs Playwright if missing, runs `npx playwright init-agents --loop=claude`, and fills in the seed test.
- Re-run after every Playwright upgrade so the generated agents match.
- Restart Claude Code afterwards so the `playwright-test` MCP server loads.
