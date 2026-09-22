---
description: Crawl application with Playwright, calculate Jev Calibrated Confidence Scores (0-100), and file validated defects (>=80) into backlog under Epic with reproduction steps.
argument-hint: "[BASE_URL] [EPIC_NAME]"
---

# /pw-autopilot:discover

Crawl the application, detect live runtime/UI defects, score with Jev confidence, and backlog verified defects.

## Execution Steps
1. Crawl entry URL and routes using `playwright:flow-discoverer`.
2. Evaluate each defect against Jev Confidence scoring rubric (0–100 scale). Discard any issue with score < 80.
3. For each accepted defect (≥ 80), file a backlog issue under the specified Epic:
   - Include Jev score and calibration rationale.
   - Include deterministic steps to reproduce (1..N).
   - Include expected vs. actual outcomes and diagnostic traces.
