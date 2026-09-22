# OpenSpec Plugin for Claude Code

A complete Claude Code plugin packaging **OpenSpec** — the artifact-guided, spec-driven development framework by [Fission AI](https://github.com/Fission-AI/openspec).

This plugin provides **14 slash commands** (`/opsx:*`) and **14 skills** (`openspec:*`), enabling Claude Code to structure changes with verifiable requirements, delta specifications, implementation tasks, and automated sync-back.

---

## 🔄 Easy 1-Command Updates from Upstream

Whenever a new version of `@fission-ai/openspec` is released on npm, update this entire plugin with a single command:

```bash
cd /home/mejazbese21/Work/RndProjects/AgentSkills/plugins/openspec
./update.sh
```

**What `./update.sh` does automatically:**
1. Checks the latest `@fission-ai/openspec` version published to npm.
2. Uses `npx @fission-ai/openspec@latest` to generate clean, up-to-date templates for Claude Code.
3. Synchronizes all skills in `skills/` and slash commands in `commands/opsx/`.
4. Updates version metadata in `.claude-plugin/plugin.json`.
5. Automatically notifies Claude Code to reload the plugin.

---

## Installation

### Method 1: Automatic Script
```bash
/home/mejazbese21/Work/RndProjects/AgentSkills/plugins/openspec/install.sh
```

### Method 2: Claude Code CLI
```bash
# Register marketplace
claude plugin marketplace add /home/mejazbese21/Work/RndProjects/AgentSkills/plugins/openspec

# Install plugin
claude plugin install openspec@openspec

# Or project-only scope
claude plugin install openspec@openspec --scope project
```

Verify the installation:
```bash
claude plugin list
```

---

## ⚡ Slash Commands (`/opsx:*`)

Available directly in your Claude Code prompt:

| Command | Purpose |
| :--- | :--- |
| **`/opsx:autopilot`** | Fully autonomous, unattended SDD execution (scaffold ➔ propose ➔ apply loop ➔ verify ➔ sync ➔ archive). |
| **`/opsx:workflow`** | Master guide for end-to-end change lifecycle, tracks (Core vs Expanded), and decision matrices. |
| **`/opsx:explore`** | Explore an idea, scope tradeoffs, investigate feasibility before proposing. |
| **`/opsx:propose`** | Propose a new change: creates proposal, delta specs, design, and tasks in one step. |
| **`/opsx:new`** | Initialize a new empty change directory structure. |
| **`/opsx:continue`** | Resume work on an active change proposal or incomplete artifacts. |
| **`/opsx:apply`** | Execute implementation: follows `tasks.md` step-by-step and writes code. |
| **`/opsx:verify`** | Verify that implemented code adheres strictly to the change requirements. |
| **`/opsx:ff`** | Fast-forward simple changes with minimal artifact friction. |
| **`/opsx:sync`** | Sync approved delta specifications into the canonical `openspec/specs/`. |
| **`/opsx:archive`** | Move a completed change from `changes/` to `changes/archive/`. |
| **`/opsx:bulk-archive`**| Bulk archive multiple changes that have already been merged or completed. |
| **`/opsx:update`** | Update an existing change proposal based on new feedback or constraints. |
| **`/opsx:onboard`** | Onboard a new repository or developer to the project's OpenSpec practices. |

---

## 🧠 Skills Catalog (`openspec:*`)

Invoke any skill directly as `openspec:<name>`:

| Skill | Description |
| :--- | :--- |
| `openspec:autopilot` | End-to-end unattended SDD lifecycle runner with self-healing task loop. |
| `openspec:workflow` | Master workflow decision engine, lifecycle tracks, and state transitions. |
| `openspec:propose` | Complete one-shot change proposal creation. |
| `openspec:explore` | Design exploration and scope discovery. |
| `openspec:apply` | Task-by-task implementation execution. |
| `openspec:verify` | Contract and spec compliance verification. |
| `openspec:sync` | Syncing delta specs into main specs. |
| `openspec:archive` | Archiving completed changes. |
| `openspec:new` | Scaffold new change directory. |
| `openspec:continue`| Resume incomplete change workflows. |
| `openspec:update` | Update change artifacts against new requirements. |
| `openspec:ff` | Fast-forward small changes. |
| `openspec:bulk-archive` | Archive multiple changes in bulk. |
| `openspec:onboard` | OpenSpec team onboarding workflow. |

---

## 📖 OpenSpec Change Lifecycle

```text
1. Explore       -> /opsx:explore (investigate approach, styling, dependencies)
   │
2. Propose       -> /opsx:propose "my-feature" (writes proposal.md, spec.md, design.md, tasks.md)
   │ [Review & Approve]
3. Apply         -> /opsx:apply (implements tasks.md into source code)
   │
4. Verify        -> /opsx:verify (confirms code satisfies all requirements)
   │
5. Sync          -> /opsx:sync (merges spec.md deltas into openspec/specs/)
   │
6. Archive       -> /opsx:archive (moves change to openspec/changes/archive/)
```

---

## References

- [OpenSpec GitHub Repository](https://github.com/Fission-AI/openspec)
- [OpenSpec Documentation](https://github.com/Fission-AI/openspec/tree/main/docs)
- [npm Package `@fission-ai/openspec`](https://www.npmjs.com/package/@fission-ai/openspec)
