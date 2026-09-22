---
name: openspec-autopilot
description: Fully autonomous, unattended OpenSpec lifecycle execution. Automatically scaffolds a change, generates all required specifications (proposal, delta specs, design, tasks), validates schema integrity, executes all implementation tasks sequentially with self-healing test loops, verifies adherence, synchronizes delta specs into canonical specs, and archives the completed change.
allowed-tools: Bash(openspec:*), Bash(git:*), Bash(npm:*), Bash(npx:*), Bash(yarn:*), Bash(pnpm:*), Bash(pytest:*), Bash(cargo:*), Bash(go:*), Bash(make:*)
license: MIT
compatibility: Requires openspec CLI.
metadata:
  author: openspec
  version: "1.0"
  generatedBy: "1.13.1"
---

# OpenSpec Autopilot Skill

Execute the entire OpenSpec Spec-Driven Development (SDD) lifecycle end-to-end without requiring manual human-in-the-loop approvals between stages.

---

## 🚀 Overview

OpenSpec Autopilot unifies the rigor of Spec-Driven Development with the velocity of autonomous coding agents. Instead of stopping for human feedback at every milestone (`explore` ➔ wait ➔ `propose` ➔ wait ➔ `apply` ➔ wait ➔ `verify` ➔ wait ➔ `sync` ➔ `archive`), Autopilot drives the entire sequence deterministically from initial prompt to verified, archived change.

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        AUTONOMOUS OPENSPEC LOOP                        │
│                                                                        │
│   [Goal] ──► 1. Scaffold & Plan (proposal, specs, design, tasks)       │
│                     │                                                  │
│                     ▼                                                  │
│              2. Validate Schema (openspec validate)                    │
│                     │                                                  │
│                     ▼                                                  │
│              3. Autonomous Apply (implement ➔ test ➔ tick - [x])       │
│                     │                                                  │
│                     ▼                                                  │
│              4. Verify Contract Compliance (all scenarios & tests)     │
│                     │                                                  │
│                     ▼                                                  │
│              5. Sync & Archive (merge deltas ➔ archive change)         │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 🎯 When to Use

- **Unattended / Long-Running Tasks:** Implement features or refactors while you step away.
- **Well-Defined Objectives:** Features, bug fixes, API endpoints, or migrations with clear acceptance criteria.
- **CI/CD & Headless Agent Runners:** Automated maintenance, PR generation, or issue remediation workflows.
- **Disciplined Autonomy:** When you need the quality and audit trail of specs, designs, and task checklists without the manual overhead.

---

## 🛠️ The 5-Phase Autopilot Pipeline

### Phase 1: Target Definition & Change Scaffolding

1. **Infer or Derive Change Name:**
   - If a name is provided (e.g. `add-jwt-auth`), sanitize to kebab-case.
   - If a description is provided (e.g. "Add JWT token refresh endpoint"), derive a succinct kebab-case identifier (`add-jwt-token-refresh`).

2. **Verify OpenSpec Root:**
   ```bash
   openspec list --json
   ```
   If `"root": null`, prompt to initialize (`openspec init`) before writing.

3. **Scaffold the Change Directory:**
   ```bash
   openspec new change "<change-name>"
   ```

---

### Phase 2: Autonomous Spec & Task Authoring

Generate all planning artifacts required by the active schema in strict dependency order:

1. **Inspect Artifact Dependencies:**
   ```bash
   openspec status --change "<change-name>" --json
   ```
   Read `artifacts` and `applyRequires` to identify the sequence (typically `proposal` ➔ `specs` ➔ `design` ➔ `tasks`).

2. **Generate Each Artifact:**
   For each required artifact:
   ```bash
   openspec instructions <artifact-id> --change "<change-name>" --json
   ```
   - **`proposal.md`**: Problem statement, why now, proposed changes, scope, capabilities.
   - **`specs/<capability>/spec.md`**: Strict delta specifications with `ADDED`, `MODIFIED`, or `REMOVED` requirements, formal `SHALL`/`MUST` behavioral statements, and Gherkin-style verification scenarios (`#### Scenario: ...`).
   - **`design.md`**: Architecture, data structures, interfaces, failure modes, trade-offs.
   - **`tasks.md`**: Granular, atomic checklist of executable implementation items (`- [ ] 1.1 ...`).

3. **Validate Planning Integrity:**
   ```bash
   openspec validate --change "<change-name>"
   ```
   If any validation lints fail, auto-correct artifact frontmatter or headings immediately until clean.

---

### Phase 3: Autonomous Implementation Loop (Self-Healing)

Execute the tasks sequentially without stopping:

1. **Fetch Dynamic Instructions:**
   ```bash
   openspec instructions apply --change "<change-name>" --json
   ```
   Read all `contextFiles` (`proposal.md`, `specs/`, `design.md`, `tasks.md`).

2. **Sequential Task Execution Loop:**
   For each incomplete task in `tasks.md` (`- [ ]`):
   - Announce: `▶ Working on task: <task-description>`.
   - Write or modify the required source files with minimal, surgical changes.
   - Run the relevant test suite or build check (e.g. `npm test`, `pytest`, `cargo test`, `go test`).
   - **Self-Healing Sub-Loop:**
     - If tests fail, inspect stderr/stdout, identify root cause, and apply fixes.
     - Retry up to 3 times.
     - Never silently delete or weaken spec assertions to make tests pass.
   - Once tests pass, update `tasks.md` immediately: `- [ ]` ➔ `- [x]`.

---

### Phase 4: Autonomous Contract Verification

Confirm that the implemented code adheres to the delta specifications:

1. **Scenario Auditing:**
   Check each `#### Scenario:` defined in `specs/`:
   - Verify that automated unit/integration tests directly cover the scenario conditions.
   - Run full project test and lint suites to ensure zero regressions.

2. **Run Verify Command:**
   ```bash
   openspec instructions verify --change "<change-name>" --json
   ```
   Ensure all verify criteria (completeness, correctness, coherence) are satisfied.

---

### Phase 5: Autonomous Sync & Archive

Finalize the change to preserve knowledge and keep the repository clean:

1. **Sync Canonical Specifications:**
   Merge approved delta specs into the canonical repository specs:
   ```bash
   openspec sync specs --change "<change-name>"
   ```
   Or update canonical `openspec/specs/<capability>/spec.md` directly if using standard layout.

2. **Archive the Change:**
   ```bash
   openspec archive change "<change-name>"
   ```
   The change is moved from `openspec/changes/<change-name>/` to `openspec/changes/archive/...`.

3. **Executive Summary Output:**
   Present a clear report:
   - Change Name & Scope
   - Total Tasks Implemented (`N/N complete ✓`)
   - Test Results & Verification Status
   - Delta Specs Synchronized
   - Archive Location
