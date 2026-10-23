# AgentSkills

A curated collection of agent skills and plugins for coding assistants, Claude Code, and agentic workflows.

## 📦 Plugins (`plugins/`)

Claude Code plugins grouping domain-specific skills with marketplace manifests, unified installation, and namespaced invocation.

| Plugin | Skills Count | Description | Location |
| :--- | :--- | :--- | :--- |
| **`addy-skills`** | **25** | Production-grade engineering lifecycle skills from Addy Osmani covering spec, plan, build, verify, review, and ship. Includes 9 slash commands (`/spec`, `/plan`, `/build`, `/test`, `/review`, `/code-simplify`, `/ship`, `/constraints`, `/webperf`) and 4 agent personas. Easily updated via `./update.sh`. | [`plugins/addy-skills/`](plugins/addy-skills/) |
| **`openspec`** | **14** | Artifact-guided spec-driven development (14 slash commands & 14 skills: autopilot, workflow, propose, explore, apply, sync, archive). Easily updated via `./update.sh`. | [`plugins/openspec/`](plugins/openspec/) |
| **`firecrawl`** | **17** | Web scraping, search, crawling, browser interaction, change monitoring, research paper retrieval, and application SDK/API integration. | [`plugins/firecrawl/`](plugins/firecrawl/) |
| **`augment`** | **62** | Skills adapted from Augment Code's public workflows (coding, QA, DevOps, observability, security, release). | [`plugins/augment/`](plugins/augment/) |
| **`johnlindquist`** | **53** | Developer workflows, beads issue tracking, persona code reviews, debugging, git automation, and 11 slash commands from John Lindquist's Claude config. | [`plugins/johnlindquist/`](plugins/johnlindquist/) |
| **`playwright`** | **9** | Built on the official Playwright Test Agents (planner, generator, healer + MCP): app-code autofix, no-suppression heal guardrail, persona flow discovery, visual/a11y audits, fixtures, runner and init, with 8 slash commands (`/pw:*`). | [`plugins/playwright/`](plugins/playwright/) |
| **`humanlayer`** | **7** | Research-design-implement flow (`rpi`), diagram & architecture visualizations (`show-me`), PR visual outlines (`visual-pr`), CLAUDE.md `<important if>` optimization, React prop narrowing, iterated loops, and control loop engineering with 6 slash commands. Easily updated via `./update.sh`. | [`plugins/humanlayer/`](plugins/humanlayer/) |
| **`playwright-autopilot`** | **4** | Autonomous QA Autopilot: live UI flow discovery, Jev calibrated confidence scoring (≥80 gate), Epic backlog generation with reproduction steps, surgical code repair & test healing, just-in-time API docs verification (Equals Money/fintech), Vitest-skipped E2E/DevTools gates, and atomic pre-push lockdown with 3 slash commands (`/pw-autopilot:*`). | [`plugins/playwright-autopilot/`](plugins/playwright-autopilot/) |

### Installing Plugins in Claude Code
```bash
# Register marketplace and install Addy Skills plugin
claude plugin marketplace add /home/mejazbese21/Work/RndProjects/AgentSkills/plugins/addy-skills
claude plugin install addy-skills@addy-skills

# Register marketplace and install OpenSpec plugin
claude plugin marketplace add /home/mejazbese21/Work/RndProjects/AgentSkills/plugins/openspec
claude plugin install openspec@openspec

# Register marketplace and install Firecrawl plugin
claude plugin marketplace add /home/mejazbese21/Work/RndProjects/AgentSkills/plugins/firecrawl
claude plugin install firecrawl@firecrawl

# Register marketplace and install Augment plugin
claude plugin marketplace add /home/mejazbese21/Work/RndProjects/AgentSkills/plugins/augment
claude plugin install augment@augment

# Register marketplace and install John Lindquist plugin
claude plugin marketplace add /home/mejazbese21/Work/RndProjects/AgentSkills/plugins/johnlindquist
claude plugin install johnlindquist@johnlindquist

# Register marketplace and install Playwright plugin
claude plugin marketplace add /home/mejazbese21/Work/RndProjects/AgentSkills/plugins/playwright
claude plugin install playwright@playwright

# Register marketplace and install HumanLayer plugin
claude plugin marketplace add /home/mejazbese21/Work/RndProjects/AgentSkills/plugins/humanlayer
claude plugin install humanlayer@humanlayer

# Register marketplace and install Playwright Autopilot plugin
claude plugin marketplace add /home/mejazbese21/Work/RndProjects/AgentSkills/plugins/playwright-autopilot
claude plugin install playwright-autopilot@playwright-autopilot
```

---

## 🎯 Standalone Skills

Specialized standalone agent skills with dedicated evaluation harnesses and installation scripts.

| Skill | Description | Location |
| :--- | :--- | :--- |
| **`coding-autoresearch-skill`** | Autonomous research loop with a locked objective, keep-or-reset attempts, and held-out test checks. | [`coding-autoresearch-skill/`](coding-autoresearch-skill/) |
| **`dev-autopilot-skill`** | End-to-end development autopilot for feature implementation, verification, and regression prevention. | [`dev-autopilot-skill/`](dev-autopilot-skill/) |

---

## 📁 Repository Layout

```text
AgentSkills/
├── plugins/
│   ├── addy-skills/               # 25 Addy Osmani engineering skills, 9 slash commands & 4 agents (with ./update.sh)
│   │   ├── .claude-plugin/        # plugin.json & marketplace.json
│   │   ├── skills/                # 25 core skill definitions (SKILL.md)
│   │   ├── commands/              # 9 slash commands (/spec, /plan, /build, /test, etc.)
│   │   ├── agents/                # 4 agent personas (reviewer, security, tester, webperf)
│   │   ├── hooks/                 # Lifecycle hooks
│   │   ├── README.md
│   │   ├── update.sh              # 1-command upstream updater
│   │   └── install.sh
│   ├── openspec/                  # 14 OpenSpec skills & slash commands (with ./update.sh)
│   │   ├── .claude-plugin/        # plugin.json & marketplace.json
│   │   ├── skills/                # Individual skill definitions (SKILL.md)
│   │   ├── commands/opsx/         # Slash commands (/opsx:*)
│   │   ├── README.md
│   │   ├── update.sh              # 1-command upstream updater
│   │   └── install.sh
│   ├── firecrawl/                 # 17 Firecrawl skills (CLI & build)
│   │   ├── .claude-plugin/        # plugin.json & marketplace.json
│   │   ├── skills/                # Individual skill definitions (SKILL.md)
│   │   ├── README.md
│   │   └── install.sh
│   ├── augment/                   # 62 Augment Code workflow skills
│   │   ├── .claude-plugin/
│   │   ├── skills/
│   │   └── README.md
│   ├── johnlindquist/             # 53 John Lindquist skills & 11 slash commands
│   │   ├── .claude-plugin/        # plugin.json & marketplace.json
│   │   ├── skills/                # 53 skill definitions (SKILL.md)
│   │   ├── commands/              # 11 slash commands (/code-review, /feature-dev, /commit, etc.)
│   │   ├── README.md
│   │   └── install.sh
│   ├── playwright/                # 9 Playwright skills on the official Test Agents & 8 slash commands (/pw:*)
│   │   ├── .claude-plugin/        # plugin.json & marketplace.json
│   │   ├── skills/                # Planner, Generator, Healer, Fixtures, Runner, Visual-A11y, Init
│   │   ├── commands/pw/           # /pw:plan, /pw:generate, /pw:heal, /pw:test, /pw:audit, /pw:init
│   │   ├── README.md
│   │   └── install.sh
│   ├── humanlayer/                # 6 HumanLayer skills & 6 slash commands (/show-me, /visual-pr, etc.) (with ./update.sh)
│   │   ├── .claude-plugin/        # plugin.json & marketplace.json
│   │   ├── skills/                # 6 skill definitions (SKILL.md)
│   │   ├── commands/              # 6 slash commands (/show-me, /visual-pr, /improve-claude-md, etc.)
│   │   ├── README.md
│   │   ├── update.sh              # 1-command upstream updater
│   │   └── install.sh
│   └── playwright-autopilot/      # Autonomous QA Autopilot (Jev confidence, surgical repair, DevTools gate, 3 commands)
│       ├── .claude-plugin/        # plugin.json & marketplace.json
│       ├── skills/                # qa-autopilot-loop, jev-confidence-triage, devtools-ui-verify, contract-docs-verify
│       ├── commands/              # /pw-autopilot:loop, /pw-autopilot:discover-backlog, /pw-autopilot:fix-verify
│       ├── README.md
│       └── install.sh
├── coding-autoresearch-skill/     # Standalone autoresearch skill
├── dev-autopilot-skill/           # Standalone autopilot skill
└── readme.md
```
