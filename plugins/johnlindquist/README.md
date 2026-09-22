# John Lindquist Claude Code Plugin

A curated suite of **53 skills** and **11 slash commands** adapted from [John Lindquist's Claude environment](https://github.com/johnlindquist/claude).

This plugin packages advanced developer workflows, git automation, multi-agent code review, task tracking via beads (`bd`), root-cause debugging, persona-based reviews, and session memory.

---

## 🚀 Installation

### Method 1: Automatic Script
```bash
/home/mejazbese21/Work/RndProjects/AgentSkills/plugins/johnlindquist/install.sh
```

### Method 2: Claude Code CLI
```bash
# Register marketplace
claude plugin marketplace add /home/mejazbese21/Work/RndProjects/AgentSkills/plugins/johnlindquist

# Install globally
claude plugin install johnlindquist@johnlindquist

# Or project-only scope
claude plugin install johnlindquist@johnlindquist --scope project
```

---

## ⚡ Slash Commands (`commands/`)

| Command | Description |
| :--- | :--- |
| **`/code-review`** | Automated multi-agent PR review with confidence scoring (≥80 threshold) to filter false positives. |
| **`/feature-dev`** | Guided 7-phase feature development (Discovery → Exploration → Questions → Architecture → Plan → Implement → Review). |
| **`/commit`** | Intelligent conventional commit based on staged & unstaged changes matching repo style. |
| **`/commit-push-pr`** | Stages, commits, pushes upstream, and opens a pull request via `gh`. |
| **`/clean_gone`** | Safely deletes local git branches whose remotes have been merged/deleted (`[gone]`). |
| **`/fix-files`** | Diagnoses and repairs issues across specified file sets. |
| **`/fix-ide`** | Resolves IDE settings, workspace misconfigurations, and language server conflicts. |
| **`/packx`** | Packages repository context, diffs, and prompts into compact transferrable packs. |
| **`/sync-diagrams`** | Synchronizes and updates architectural diagrams with current codebase state. |
| **`/variations`** | Generates alternative architectural and algorithmic implementations for comparison. |
| **`/worktree-tasks`** | Manages and runs tasks across isolated git worktrees. |

---

## 🧠 Skills Catalog (`johnlindquist:*`)

Invoke skills directly as `johnlindquist:<skill-name>`:

### 📋 Task Tracking & Planning
| Skill | Purpose |
| :--- | :--- |
| `johnlindquist:beads` | Git-backed issue tracking with dependency awareness using the `bd` CLI. |

### 🔍 Code Quality & Architecture
| Skill | Purpose |
| :--- | :--- |
| `johnlindquist:code-review` | Multi-agent code review with confidence filtering. |
| `johnlindquist:review` | Persona-driven code reviews (Fowler, Torvalds, Carmack, Beck, DHH, Anders, etc.). |
| `johnlindquist:testgen` | Systematic test generation and coverage expansion. |
| `johnlindquist:refactor` | Code modernization and structural refactoring patterns. |
| `johnlindquist:ubs` | Bug scanning and heuristic flaw detection. |
| `johnlindquist:diagram` | Architecture diagrams & Mermaid visual specs. |
| `johnlindquist:frontend-design` | Frontend UI/UX component design patterns. |
| `johnlindquist:ts-testing` | TypeScript testing patterns and mocks. |

### 🐛 Debugging & Problem Solving
| Skill | Purpose |
| :--- | :--- |
| `johnlindquist:debug` | Root-cause analysis and bug isolation. |
| `johnlindquist:investigate` | Hypothesis-driven debug investigation. |
| `johnlindquist:stuck` | Heuristic framework for breaking out of loops and deadlocks. |

### 🤖 AI Research & Reasoning
| Skill | Purpose |
| :--- | :--- |
| `johnlindquist:gemini` | Gemini CLI research, web search, and analysis. |
| `johnlindquist:gemini-image` | Multimodal visual and image analysis with Gemini. |
| `johnlindquist:think` | Deep structured reasoning protocols. |
| `johnlindquist:council` | Multi-agent diverse perspectives and debate. |
| `johnlindquist:council-of-five` | Formal 5-perspective deliberation framework. |
| `johnlindquist:research` | Deep multi-source research workflow. |
| `johnlindquist:brainstorm` | Structured ideation and exploration. |

### 🌿 Git & Workflows
| Skill | Purpose |
| :--- | :--- |
| `johnlindquist:commit-commands` | Automated conventional commits, pushing, and branch pruning. |
| `johnlindquist:github` | GitHub issue and PR triage. |
| `johnlindquist:diff-preview` | Diff analysis and change impact forecasting. |
| `johnlindquist:worktree` | Parallel branch development via git worktree. |
| `johnlindquist:changelog` | Release notes generation from git tags. |
| `johnlindquist:workflow` | CI/CD pipeline automation and GitHub Actions. |
| `johnlindquist:workflow-devkit` | Workflow development utilities. |

### ⚙️ Development & Engineering
| Skill | Purpose |
| :--- | :--- |
| `johnlindquist:feature-dev` | 7-phase guided feature development. |
| `johnlindquist:deps` | Dependency updates and auditing. |
| `johnlindquist:perf` | Performance profiling and optimization. |
| `johnlindquist:db` | Database schema migrations and queries. |
| `johnlindquist:bundle` | Code bundling and packaging. |

### 💾 Session History & Agent Coordination
| Skill | Purpose |
| :--- | :--- |
| `johnlindquist:memory` | Persistent cross-session knowledge storage. |
| `johnlindquist:cass` | Search coding agent history across sessions. |
| `johnlindquist:cass-memory` | Playbook generation from past agent successes. |
| `johnlindquist:lessons` | Capturing and indexing project lessons learned. |
| `johnlindquist:long-agent` | Long-running session context management. |
| `johnlindquist:pipeline` | Multi-step agent orchestrator. |
| `johnlindquist:agent-mail` | Asynchronous multi-agent message coordination. |
| `johnlindquist:packx` | Repository context packaging. |
| `johnlindquist:repo` | Rapid repository context indexing. |
| `johnlindquist:deepwiki` | Repository docs and wiki extraction. |
| `johnlindquist:skill-creator` | Interactive generator for new Claude skills. |

### 🔌 Tools & Integrations
| Skill | Purpose |
| :--- | :--- |
| `johnlindquist:linear` | Linear issue management. |
| `johnlindquist:figma` | Figma designs to code. |
| `johnlindquist:chrome` | Browser automation workflows. |
| `johnlindquist:spider` | Web crawling and content extraction. |
| `johnlindquist:mcp-spy` | Real-time MCP communication monitoring. |
| `johnlindquist:tmux` | Terminal session multiplexing. |
| `johnlindquist:wezterm` | WezTerm configuration. |
| `johnlindquist:karabiner` | Karabiner Elements key mappings. |
| `johnlindquist:raycast-extension` | Raycast extension development. |
| `johnlindquist:article` | Article and technical documentation drafting. |
| `johnlindquist:design` | Design tokens and UI themes. |

---

## 🔗 Attribution

- Source Repository: [github.com/johnlindquist/claude](https://github.com/johnlindquist/claude)
- Author: [John Lindquist](https://github.com/johnlindquist)
