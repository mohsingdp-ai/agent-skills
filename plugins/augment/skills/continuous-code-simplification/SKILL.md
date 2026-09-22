---
name: continuous-code-simplification
description: Finds functions modified in the last 30 days whose cognitive complexity exceeds 15, rewrites them with guard clauses, extracted helpers and loop decomposition, checks behavior with the existing test suite, and opens one draft PR per file with a before and after complexity table for human review. Use when the user asks to "simplify complex functions", "reduce cognitive complexity", "find overly complex code changed recently", or wants refactoring PRs proposed for review. Adapted from Augment Code's "Continuous code simplification" workflow.
---

# Continuous code simplification

Complexity grows one condition at a time. This skill scores recently changed functions for cognitive complexity, rewrites the ones over the threshold using established simplification patterns, and checks the tests still pass. It opens a draft PR per file, and a human reviewer adjusts or approves before merge so intent stays intact.

Source: https://www.augmentcode.com/workflows/coding/continuous-code-simplification (Augment Code workflow, adapted for Claude Code).

## When to run

Augment runs this nightly (cron 03:00 UTC).
In Claude Code it runs on demand. Inputs: the repo (default: the current checkout), the base branch (default: the repo's default branch), the look-back window (default: 30 days) and the complexity threshold (default: 15).
To repeat it nightly, use /loop or /schedule.

## Needs

- Complexity scores: the SonarQube MCP if connected. Otherwise a local cognitive-complexity tool for the language, such as the `sonarjs/cognitive-complexity` rule from `eslint-plugin-sonarjs` for JavaScript and TypeScript, or `complexipy` for Python.
- Git history: `git log`.
- Tests: the project's existing test command.
- GitHub: `gh` CLI (`gh pr create --draft`).
- If a tool is not connected, ask the user for that data or skip the step and say so in the report. Never invent data.

## Steps

Work through all steps without stopping to ask questions between them.

1. **Find recently modified functions.** Start from an up-to-date base branch. List files changed in the past 30 days (`git log --since="30 days ago" --name-only --pretty=format: | sort -u`). Map the changed lines in those files to the functions that contain them.
2. **Score complexity.** Compute the cognitive complexity score of each modified function.
3. **Decision — does any function score above 15?** If no, take no action and report that all files are within the threshold. If yes, continue with only the functions over the threshold.
4. **Rewrite each function over the threshold.** Apply established simplification patterns: early-return guard clauses, extracted helper functions, and loop decomposition. Keep the signature and behavior the same. Record each transformation you applied and why.
5. **Verify behavior is unchanged.** Run the existing test suite against the rewrite. **Decision — does the suite pass as it did before the rewrite?** If yes, keep the rewrite. If no, revert it and list the function in the report as not simplified. If no test covers the function, say so in the PR.
6. **Re-score** each kept rewrite to get its new complexity score.
7. **Open one draft PR per file.** For each file with at least one kept rewrite, create a branch from the base branch, commit only that file's changes, push, and open a draft PR (`gh pr create --draft`). The PR description contains:
   - a side-by-side table per function: complexity before, complexity after;
   - an explanation of each transformation applied;
   - the test command run and its result;
   - a note that the PR is flagged for human review and must not be merged automatically.

## Output

- One draft PR per simplified file, with the complexity comparison table and the transformation notes.
- A short report to the user: functions scanned, functions over the threshold, PR links, rewrites reverted because tests failed, and any step that was skipped.

## Guardrails

- Confirm with the user before pushing branches or opening PRs, unless they said to proceed without asking.
- Never merge automatically. Every PR stays a draft and is flagged for human review.
- Never open a PR for a rewrite that fails the existing test suite.
- Do not change tests, public APIs or behavior to make a rewrite pass.
