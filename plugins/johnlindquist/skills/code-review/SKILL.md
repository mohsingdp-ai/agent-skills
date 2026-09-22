---
name: code-review
description: Automated multi-agent code review for pull requests with confidence-based scoring to filter false positives and ensure actionable feedback.
allowed-tools: Bash, Read, Grep, Glob
---

# Code Review Skill

Automated pull request code review using multiple specialized agents with confidence-based scoring (threshold ≥80) to eliminate false positives and post only actionable, high-signal feedback.

## Workflow

1. **Eligibility Check**:
   - Check if PR is closed, draft, trivial, or already reviewed. Skip if so.
2. **Context Gathering**:
   - Locate root and path-specific `CLAUDE.md` files and team guidelines.
   - Summarize the PR diff and core changes.
3. **Multi-Agent Review**:
   - Agent 1 & 2: Audit for `CLAUDE.md` and style guideline adherence.
   - Agent 3: Scan diff for bugs, logic errors, and security issues.
   - Agent 4: Inspect git blame and historical context for regression risks.
   - Agent 5: Check inline comments and interface contracts.
4. **Confidence Scoring**:
   - Score each finding on a 0–100 scale:
     - 0: False positive or pre-existing issue.
     - 25: Unverified or stylistic nitpick not in guidelines.
     - 50: Minor issue or low-impact nitpick.
     - 75: Likely bug or direct guideline breach.
     - 100: Confirmed bug with concrete proof.
   - Filter out any issue scored < 80.
5. **Post Feedback**:
   - If high-confidence issues exist, format and post concise, link-rich review comments via `gh pr comment`.
