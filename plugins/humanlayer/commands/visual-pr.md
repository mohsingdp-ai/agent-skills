---
description: Create or update a pull request with a concise visual outline for reviewers
---

# /visual-pr

Create or update a pull request with a concise visual outline, diagrams, and before/after comparisons that help reviewers understand the change quickly.

## Instructions
1. Invoke and follow the guidelines in the `visual-pr` skill.
2. Inspect the current diff and commits against the target base branch (`main` or default).
3. Draft a PR description with structured sections, visual mermaid diagrams (data flow, sequence, or component relationships), and bulleted change notes.
4. If requested or confirmed by the user, push and create/update the pull request using `gh pr create` or `gh pr edit`.
