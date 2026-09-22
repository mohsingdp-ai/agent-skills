---
name: jev-confidence-triage
description: Calibrated decision-making and confidence scoring (0–100 scale) for test failures and UI anomalies. Evaluates determinism, impact, and flakiness, enforcing an 80-point gating threshold to eliminate false positives before filing backlog tasks.
allowed-tools: Read, Grep, Glob
---

# Jev Confidence Triage (`jev-confidence-triage`)

The **Jev Confidence Triage Skill** provides a rigorous, calibrated filter for automated test failures and crawler findings. It prevents flakiness, transient network delays, and minor stylistic discrepancies from cluttering the backlog.

---

## 🎯 Evaluation Rubric

Evaluate every candidate defect against these criteria:

1. **Determinism (40 pts):**
   - Does the failure repeat consistently upon re-execution?
   - Is it independent of machine speed, CPU throttling, or network latency?

2. **Functional Severity (30 pts):**
   - Does it block a core user workflow (e.g. login, payment, form submission)?
   - Does it cause an unhandled client crash or HTTP 500 error?

3. **Specification Alignment (20 pts):**
   - Does the observed behavior contradict documented requirements or API contracts?
   - Is it clearly unintended rather than an undocumented fallback?

4. **Blast Radius (10 pts):**
   - Does it affect all users or only a narrow edge case?

---

## 🛑 Strict Gating Threshold

- **Score ≥ 80:** Approved for backlog creation and automated surgical repair.
- **Score < 80:** Discarded immediately as noise or non-critical edge case.
