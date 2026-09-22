---
name: "OPSX: Autopilot"
description: "Autonomously execute the entire OpenSpec lifecycle (propose, apply, verify, sync, archive) unattended"
allowed-tools: Bash(openspec:*), Bash(git:*), Bash(npm:*), Bash(npx:*), Bash(yarn:*), Bash(pnpm:*), Bash(pytest:*), Bash(cargo:*), Bash(go:*), Bash(make:*)
category: "Workflow"
tags: ["workflow", "autopilot", "autonomous", "sdd"]
---

Autonomously drive an OpenSpec change from start to finish without pausing for approval between stages.

**Store selection:** If the user names a store or the work lives in one, discover registered stores via `openspec store list --json`, then append `--store <id>` to all openspec commands.

**Project check:** Confirm `openspec list --json` returns a valid `root`. If `"root": null`, prompt the user to initialize (`openspec init`) before writing.

**Input**: The argument after `/opsx:autopilot` is the change name or a description of what to build (e.g. `/opsx:autopilot add-jwt-auth` or `/opsx:autopilot Add OAuth2 login with GitHub`).

---

## Autonomous Execution Steps

### 1. Goal Resolution & Naming
- If an argument is provided, extract the goal and derive a kebab-case change name (e.g. `add-github-oauth`).
- If no argument is provided, ask the user what they want to build before proceeding.

### 2. Scaffold Change
```bash
openspec new change "<change-name>"
```

### 3. Generate Specs & Tasks (One-Shot Planning)
- Inspect dependencies: `openspec status --change "<change-name>" --json`
- Author all required planning artifacts (`proposal.md`, `specs/`, `design.md`, `tasks.md`):
  - In `specs/`, write explicit requirements with formal `SHALL`/`MUST` clauses and concrete `#### Scenario:` cases.
  - In `tasks.md`, create an atomic, ordered task checklist (`- [ ] 1.1 ...`).
- Validate artifacts:
  ```bash
  openspec validate --change "<change-name>"
  ```
  Auto-repair any schema formatting issues.

### 4. Continuous Implementation Loop (Self-Healing)
- Retrieve apply instructions:
  ```bash
  openspec instructions apply --change "<change-name>" --json
  ```
- Read all `contextFiles`.
- For each pending task in `tasks.md`:
  1. Announce current task: `Working on: <task description>`
  2. Implement code changes with surgical precision.
  3. Run relevant unit / integration tests (e.g. `npm test`, `pytest`, `cargo test`).
  4. If tests fail, diagnose and fix code (self-healing loop, up to 3 retries).
  5. Update `tasks.md`: mark task complete `- [ ]` ➔ `- [x]`.

### 5. Automated Contract Verification
- Run:
  ```bash
  openspec instructions verify --change "<change-name>" --json
  ```
- Ensure all behavioral scenarios and contract assertions pass without regressions.

### 6. Synchronize & Archive
- Sync delta specs to canonical specs:
  ```bash
  openspec sync specs --change "<change-name>"
  ```
- Archive the change:
  ```bash
  openspec archive change "<change-name>"
  ```

### 7. Executive Summary
Provide a clean final report:
- Change name & scope
- All completed tasks
- Test outcomes
- Synced specifications and archive path
