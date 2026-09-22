---
name: planner
description: Playwright Test Agent - Planner. Delegates to the official playwright-test-planner subagent to explore a feature live and save a reviewable Markdown test plan to specs/, then gates it on human review before generation.
allowed-tools: Read, Grep, Glob, Bash, Agent
---

# Playwright Test Agent: Planner

Produces a Markdown test plan in `specs/` for a feature or user flow, before any test code is written.

The exploring and writing is done by the official **`playwright-test-planner`** subagent ([docs](https://playwright.dev/docs/test-agents)). This skill adds the context it needs and the review gate after it.

---

## Steps

1. **Preflight.** Run the `playwright:init` preflight. Fallback if the agents are unavailable: explore with Read/Grep and write the plan by hand, same format, same folder.
2. **Gather context** for the planner prompt:
   - The feature or route from `$ARGUMENTS`.
   - The seed file path (the generated `seed.spec.ts` in `testDir`).
   - Any PRD, user story, or existing plan in `specs/` for this feature.
   - Personas / roles that see different UI, if the app has them.
3. **Delegate.** Spawn `playwright-test-planner` with:
   > Plan tests for: <feature>. Seed: <seed path>. Personas: <list or "one">. Cover happy path, validation errors, edge cases, and error states. Save the plan to `specs/<feature>.md`.
4. **Check the saved plan.** Every scenario must have: a starting state, numbered steps, and an expected result. Fix gaps before review.
5. **Human review gate.** Show the user the plan and wait for approval. Do not hand off to `playwright:generator` until they approve.
