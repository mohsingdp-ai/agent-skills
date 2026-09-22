# Playwright Autopilot Claude Code Plugin

An autonomous **Playwright & Chrome DevTools QA Autopilot** plugin for Claude Code and AI coding agents.

This plugin orchestrates closed-loop quality assurance: exploratory UI flow crawling, calibrated Jev confidence decision-making, deterministic backlog ticket generation under Epics, surgical application code repair in `src/`, automated locator healing, just-in-time API documentation verification (e.g. Equals Money / fintech rails), Vitest-skipped E2E/DevTools verification gates, and atomic pre-push lockdown.

---

## 🚀 Installation

### Method 1: Automated Script
```bash
/home/mejazbese21/Work/RndProjects/AgentSkills/plugins/playwright-autopilot/install.sh
```

### Method 2: Claude Code CLI
```bash
# Register marketplace
claude plugin marketplace add /home/mejazbese21/Work/RndProjects/AgentSkills/plugins/playwright-autopilot

# Install globally
claude plugin install playwright-autopilot@playwright-autopilot

# Or project-only scope
claude plugin install playwright-autopilot@playwright-autopilot --scope project
```

---

## ⚡ Slash Commands (`commands/`)

| Command | Description |
| :--- | :--- |
| **`/pw-autopilot:loop`** | Executes the full autonomous iterative repair cycle across all failing specs/backlog issues until 0 failures remain. |
| **`/pw-autopilot:discover-backlog`** | Crawls live UI, evaluates issues with Jev Calibrated Confidence (0–100, ≥80 gate), and creates backlog tickets with deterministic steps to reproduce under an Epic. |
| **`/pw-autopilot:fix-verify`** | Performs targeted surgical code repair in `src/`, heals test locators, and gates verification via Playwright E2E and Chrome DevTools live DOM/console checks. |

---

## 🛠 Skills Reference (`skills/`)

### 1. `playwright-autopilot:qa-autopilot-loop`
The master orchestrator. Coordinates the 5-phase loop:
1. **Live Discovery:** Crawls UI with Playwright, traps unhandled exceptions and HTTP 4xx/5xx errors.
2. **Jev Confidence Filter:** Scores each defect (0–100); strictly discards anything < 80.
3. **Backlog Logging:** Formats issues under an Epic with steps to reproduce and diagnostics.
4. **Surgical Repair & Healing:** Patches application code in `src/` with minimal blast radius; checks external docs (Equals Money) just-in-time; heals selectors with zero test suppression.
5. **Dual Verification Gate:** Runs Playwright E2E (`code 0`) and Chrome DevTools runtime checks while skipping Vitest.

### 2. `playwright-autopilot:jev-confidence-triage`
A calibrated decision-making model for test failures:
- Evaluates determinism (40 pts), functional severity (30 pts), spec alignment (20 pts), and blast radius (10 pts).
- Discards flakes, slow animations, and minor nuances before they reach the backlog.

### 3. `playwright-autopilot:devtools-ui-verify`
Live browser DOM and runtime hygiene auditor:
- Checks live DOM state, accessibility attributes, and loading states.
- Asserts zero unhandled exceptions and zero `console.error` calls.
- Enforces the **Skip Vitest** rule.
- Exercises at least 2 interaction edge cases (empty inputs, rapid double-clicks, state resets).

### 4. `playwright-autopilot:contract-docs-verify`
Just-in-Time external API & documentation contract verifier:
- Prevents hallucinated API keys, endpoints, or payload schemas when working with third-party providers (e.g. Equals Money API, card tokenization, webhook HMAC signatures).
- Mandates checking live specs before writing fixes.

---

## 🛑 Non-Negotiable Contract & Guardrails

- **Surgical Changes Only:** Modify only the lines causing the bug. No unsolicited refactoring.
- **Zero Test Suppression:** `test.skip()` and `test.fixme()` are strictly prohibited.
- **Skip Vitest:** Do not run unit tests (`vitest` / `jest`); rely on functional Playwright and DevTools inspection.
- **Atomic Commits:** One commit per bug fix referencing the issue number.
- **Pre-Push Lockdown:** `git push` is blocked until all test suites are completely green.
