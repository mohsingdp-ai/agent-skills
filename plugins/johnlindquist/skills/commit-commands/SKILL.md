---
name: commit-commands
description: Streamlines git workflows with automated conventional committing, pushing, branch cleanup (clean_gone), and pull request creation.
allowed-tools: Bash, Read, Grep, Glob
---

# Commit Commands Skill

Automates common git lifecycle operations: crafting conventional commit messages, staging files, pushing branches, creating PRs, and pruning stale merged branches.

## Operations

### 1. Smart Commit
- Analyzes `git status` and diffs across staged and unstaged changes.
- Matches existing repository commit style and conventional commit conventions (`feat:`, `fix:`, `refactor:`, etc.).
- Omits secret files (`.env`, credentials, tokens).
- Stages modified files and commits cleanly.

### 2. Commit, Push & PR
- Runs smart commit on current changes.
- Pushes the feature branch to remote (`git push -u origin <branch>`).
- Generates PR summary from recent commits and opens a PR via `gh pr create`.

### 3. Clean Gone Branches
- Prunes local branches whose remote tracking upstream has been deleted (`git branch -vv` marked as `[gone]`).
- Safely excludes `main`, `master`, and current checked-out branch.
