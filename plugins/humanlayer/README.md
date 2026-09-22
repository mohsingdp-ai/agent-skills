# HumanLayer Claude Code Plugin

A curated suite of **6 skills** and **6 slash commands** from [HumanLayer](https://humanlayer.dev) ([humanlayer/skills](https://github.com/humanlayer/skills)).

This plugin packages diagram & visual architecture generators, PR visual outlines, intelligent `CLAUDE.md` optimizers using `<important if>` blocks, React prop type narrowing, iterated agentic loops, and control loop engineering for autonomous coding agents.

---

## 🚀 Installation

### Method 1: Automatic Installer
```bash
/home/mejazbese21/Work/RndProjects/AgentSkills/plugins/humanlayer/install.sh
```

### Method 2: Claude Code CLI
```bash
# Register marketplace
claude plugin marketplace add /home/mejazbese21/Work/RndProjects/AgentSkills/plugins/humanlayer

# Install unified bundle (all 6 skills + slash commands)
claude plugin install humanlayer@humanlayer

# Or install in project-only scope
claude plugin install humanlayer@humanlayer --scope project
```

### Method 3: Standalone Plugins
Each skill can also be installed individually from the `humanlayer` marketplace:
```bash
claude plugin install show-me@humanlayer
claude plugin install visual-pr@humanlayer
claude plugin install improve-claude-md@humanlayer
claude plugin install narrow-react-prop-types@humanlayer
claude plugin install build-iterated-agentic-loop@humanlayer
claude plugin install design-control-loop@humanlayer
```

---

## ⚡ Slash Commands (`commands/`)

| Command | Description |
| :--- | :--- |
| **`/show-me`** | Explains the current topic, codebase architecture, or feature using concise Mermaid diagrams, code-shape sketches, and focused HTML artifacts. |
| **`/visual-pr`** | Creates or updates a pull request with a structured visual outline, data-flow diagrams, and clear summaries for reviewers. |
| **`/improve-claude-md`** | Audits and rewrites `CLAUDE.md` using `<important if>` conditional blocks to prevent context bloat and instruction degradation. |
| **`/narrow-react-prop-types`** | Analyzes React component prop contracts and narrows types to match live production code paths rather than test/mock artifacts. |
| **`/build-iterated-agentic-loop`** | Builds a repo-local skill and an iterated autonomous coding-agent workflow (sensor, loop, prompt, and memory tracking). |
| **`/design-control-loop`** | Conducts a guided interview to design a closed control loop (sensor, controller, actuator, disturbances) for the codebase and creates runnable components. |

---

## 🛠 Skills Reference (`skills/`)

### 1. `humanlayer:show-me`
Explains complex codebases, architectures, and concepts visually:
- Generates ASCII art, Mermaid diagrams, or interactive HTML files.
- Automatically handles deep architectural explanations without cluttering terminal output.

### 2. `humanlayer:visual-pr`
Transforms standard Git PR descriptions into visually appealing, high-signal briefs:
- Generates architecture flowcharts and before/after comparisons.
- Interacts with GitHub CLI (`gh pr create` / `gh pr edit`).

### 3. `humanlayer:improve-claude-md`
Optimizes agent instruction files:
- Introduces `<important if="...">` conditional syntax.
- Distinguishes always-on project constraints from situational task guidelines.

### 4. `humanlayer:narrow-react-prop-types`
Eliminates loose prop types across React codebases:
- Traces real call-sites across production code.
- Eliminates unused optional properties and over-permissive union types.

### 5. `humanlayer:build-iterated-agentic-loop`
Generates full end-to-end agentic feedback loops:
- Creates GitHub Actions workflows, agent runner scripts, prompt templates, and memory files.
- Provides test-driven verification cycles for autonomous agent execution.

### 6. `humanlayer:design-control-loop`
Applies classical control theory to autonomous agent systems:
- Models system state via sensors, controllers, actuators, and disturbance rejection.
- Scaffolds modular TypeScript components and scheduled execution loops.

---

## 🔄 Updating

To sync latest updates from upstream `humanlayer/skills`:
```bash
/home/mejazbese21/Work/RndProjects/AgentSkills/plugins/humanlayer/update.sh
```
