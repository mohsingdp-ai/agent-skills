---
name: qa-autopilot-loop
description: Autonomous Playwright & Chrome DevTools QA Autopilot. Orchestrates an end-to-end loop: crawls live UI to discover bugs, scores defects with Jev Calibrated Confidence (≥80 threshold), backlogs tasks under an Epic with reproduction steps, applies surgical source code fixes, heals locators without skipping tests, verifies via Playwright E2E and Chrome DevTools UI gates (skipping Vitest), and makes atomic commits under pre-push lockdown.
allowed-tools: Read, Grep, Glob, Write, Edit, Bash
---

# Autonomous QA Autopilot Loop (`qa-autopilot-loop`)

The **QA Autopilot Loop** is a closed-loop autonomous quality assurance system that combines exploratory UI crawling, calibrated confidence decision-making, deterministic backlog management, and surgical code repair.

---

## 🛑 The Non-Negotiable Contract

1. **Jev Confidence Filter (≥ 80):** Never file or work on unverified flakes or transient timing glitches. Every issue must be scored on a calibrated 0–100 scale; anything < 80 is discarded.
2. **Surgical Scope:** Minimal blast radius. Touch only the lines in `src/` directly responsible for the defect. No unsolicited refactoring, linting reformatting, or style restructuring.
3. **Zero Test Suppression:** Strictly forbidden to use `test.skip()` or `test.fixme()`. If application behavior is broken, fix the application. If locators legitimately moved, heal the locator.
4. **Skip Vitest:** Do not run unit tests (`vitest` / `jest`). Verification relies exclusively on Playwright E2E and Chrome DevTools live runtime inspection.
5. **Pre-Push Lockdown:** Never run `git push` while the loop is running. Commits remain local and atomic until the entire suite is verified green with exit code `0`.

---

## 🔁 The 5-Phase Autonomous Lifecycle

```text
1. Discover & Crawl ──► 2. Jev Triage (≥80) ──► 3. Backlog Under Epic ──► 4. Surgical Fix & Heal ──► 5. Dual Verification Gate
   (Playwright)           (0-100 Confidence)       (Steps to Reproduce)      (src/ & JIT Docs)        (Playwright + DevTools)
```

### Phase 1: Live Discovery via Playwright
- Crawl primary routes, navigation trees, tabs, forms, and buttons.
- Trap unhandled browser exceptions (`page.on('console')`), failed network calls (4xx/5xx), and broken UI states.

### Phase 2: Jev Calibrated Confidence Scoring
Score every detected anomaly using `{SKILLBASE}/references/jev-scoring-rubric.md`:
- `0–25`: Flake, latency, transient race condition -> **Discard**
- `26–50`: Cosmetic nuance or acceptable fallback -> **Discard**
- `51–79`: Edge-case with low business impact -> **Discard**
- `80–90`: Deterministic functional bug / 500 error -> **Accept**
- `91–100`: Fatal crash or broken core user journey -> **Accept**

### Phase 3: Backlog Task Creation Under Epic
For each accepted defect (Score ≥ 80), file a structured issue using `{SKILLBASE}/references/reproduction-steps-template.md`:
- Tag with `[Epic: {EPIC_NAME}]`.
- Document exact URL, persona, sequential reproduction steps (1..N), expected vs. actual outcome, and trace locator.

### Phase 4: Surgical Autopilot Fix & Test Healing
1. Execute failing scenario with tracing: `npx playwright test {spec_path} --trace=on`.
2. **Just-In-Time Contract Verification:** If the defect touches external services (e.g. Equals Money API, payments, cards, webhooks):
   - Consult official docs (`https://docs.equalsmoney.com`) or OpenAPI specs before writing code.
   - Do not guess payload keys, currency formats, or headers.
3. Apply surgical edits to `src/`.
4. Heal selectors in test specs if UI shifted; never skip tests.

### Phase 5: Dual Verification Gate & Atomic Commits
1. **Playwright E2E:** Re-run test spec to verify exit code `0`.
2. **Chrome DevTools UI Inspection:** Use `{SKILLBASE}/references/devtools-verification-guide.md` to check live DOM, confirm 0 console errors, and verify at least 2 edge cases.
3. **Skip Vitest:** Do not run unit tests.
4. **Atomic Commit:** Stage only the modified files and commit:
   `git commit -m "fix({scope}): {concise description} (refs #{ISSUE_NUMBER})"`
5. **Lockdown:** Hold `git push` until the entire loop terminates with 0 failures.
