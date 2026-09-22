---
name: "OPSX: Workflow"
description: "Master orchestrator and status dashboard: inspect active changes, progress, lifecycle stage, and recommended next actions"
allowed-tools: Bash(openspec:*)
category: "Workflow"
tags: ["workflow", "orchestrator", "status", "lifecycle", "dashboard"]
---

# OpenSpec Workflow Orchestrator & Live Status

Use this command to discover:
- Which OpenSpec change is active in this workspace
- Where your work is currently located in the lifecycle
- Progress: completed vs remaining tasks and artifact statuses
- The immediate recommended next step

---

## 1. Live Workspace Status (Run First)

Always inspect the current project state:

```bash
openspec list --json
```

1. **If `"root": null`:**
   - Report that no OpenSpec root exists in this repository.
   - Suggest: `/opsx:onboard` or `openspec init`.

2. **If no active changes exist (`"changes": []`):**
   - Report: "No active changes found. Ready to start a new change."
   - Recommend: `/opsx:explore` (if researching) or `/opsx:propose "<name>"` (to start planning).

3. **If active change(s) exist:**
   For each active change (or the one named in the argument / context), inspect detailed state:
   ```bash
   openspec status --change "<name>" --json
   openspec instructions apply --change "<name>" --json
   ```

   **Display the Live Status Dashboard:**
   ```
   ============================================================
   📊 OPENSPEC ORCHESTRATOR DASHBOARD
   ============================================================
   📁 Active Change:     <change-name>
   📍 Change Directory:  openspec/changes/<change-name>/
   📑 Schema:            <schemaName> (e.g. spec-driven)
   
   📦 Artifacts Status:
     • Proposal:         [done | missing | in-progress]
     • Delta Specs:      [done | missing | in-progress]
     • Technical Design: [done | missing | in-progress]
     • Tasks Checklist:  [done | missing | in-progress]

   ⚡ Implementation Progress:
     • Tasks:            N / M completed (X%)
     • Remaining Tasks:  <count> pending

   🎯 Current Lifecycle Phase:
     [ ] Planning (authoring specs & tasks)
     [X] Implementation (executing code in tasks.md)
     [ ] Verification (running verify & tests)
     [ ] Finalization (sync specs & archive)

   👉 Recommended Next Action:
     Run `/opsx:apply <name>` to continue implementing pending tasks,
     OR run `/opsx:verify` if implementation is done.
   ============================================================
   ```

---

## 2. The OpenSpec Lifecycle Tracks

### Track 1: The Core Track (Fast & Standard)
1. **Explore**: `/opsx:explore` — Investigate ideas and codebase before proposing.
2. **Propose**: `/opsx:propose "<name>"` — Generate all 4 artifacts in one step (`proposal.md`, `spec.md`, `design.md`, `tasks.md`).
3. **Implement**: `/opsx:apply` — Execute tasks in code and check off checklist items.
4. **Finalize**: `/opsx:archive` — Sync delta specs into main specs and move change to archive.

### Track 2: The Expanded Track (Step-by-Step Control)
1. **Scaffold**: `/opsx:new "<name>"` — Create change directory.
2. **Author**: `/opsx:continue` — Generate artifacts one-by-one with human checkpoints (or `/opsx:ff` to fast-forward).
3. **Implement**: `/opsx:apply` — Write code.
4. **Audit**: `/opsx:verify` — Check completeness, correctness, and coherence.
5. **Sync**: `/opsx:sync` — Explicitly merge delta specs into repository specs.
6. **Archive**: `/opsx:archive` — Move change to `openspec/changes/archive/`.

### Track 3: The Autopilot Track (Fully Autonomous)
1. **Autopilot**: `/opsx:autopilot "<goal>"` — Autonomous unattended SDD loop with self-healing tests.

---

## 3. Decision Trees

### `/opsx:ff` vs `/opsx:continue`
- **Use `/opsx:ff`**: If requirements are clear upfront, time pressure is high, or scope is narrow.
- **Use `/opsx:continue`**: If exploring a complex architecture, novel pattern, or wanting a human review gate between proposal and design.

### When to Update vs Start New Change
- **Update Existing (`/opsx:update`)**: Same intent, refined execution, learned code constraints during implementation, or narrowing scope for MVP.
- **Start New Change (`/opsx:propose`)**: Intent fundamentally changed, scope exploded to unrelated subsystems, or original change can be shipped standalone.
