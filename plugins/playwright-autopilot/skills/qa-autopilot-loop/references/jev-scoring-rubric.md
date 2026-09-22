# Jev Calibrated Confidence Scoring Rubric

The Jev confidence score is a calibrated probability estimate (0–100 scale) that measures whether an observed anomaly is a genuine, deterministic bug versus a false alarm, test flake, or intentional behavior.

---

## 🎯 Scoring Scale

| Score Range | Classification | Action | Description |
| :--- | :--- | :--- | :--- |
| **0 – 25** | **Noise / Flake** | ❌ Discard | Non-reproducible race condition, slow network timeout, or third-party analytics script failure. |
| **26 – 50** | **Cosmetic / Nuance** | ❌ Discard | Minor alignment nuance, subjective design choice, or graceful degradation that does not block task completion. |
| **51 – 79** | **Low-Impact Edge Case** | ❌ Discard | Requires an abnormal sequence of actions with minimal user impact; unlikely to be encountered in standard production paths. |
| **80 – 90** | **Deterministic Defect** | ✅ Accept & Backlog | Fully reproducible bug: unhandled HTTP 500 error, broken form validation, button click with no response, or state desynchronization. |
| **91 – 100** | **Critical Blocker** | ✅ Accept & Backlog | Fatal unhandled client-side exception (`TypeError: Cannot read properties of undefined`), white-screen crash, or broken primary checkout/auth flow. |

---

## 🛑 Strict Gating Rule

- **Threshold: ≥ 80**
- Any issue with a score below 80 must be dropped from the backlog pipeline.
- This ensures high signal-to-noise ratio and protects engineering teams from chasing flaky test failures.
