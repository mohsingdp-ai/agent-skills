---
name: codebase-health-scorecard
description: Scores each repository 0 to 100 on six agent-readiness criteria (AGENTS.md coverage, test coverage, pre-commit hooks, CI pass rate, dependency freshness, documentation coverage), compares the composite score with the last run, alerts the owner team when it regressed, and publishes a scorecard with the top 3 actions per repo. Use when the user says "run the codebase health scorecard", "score our repos for agent readiness", "check if repo health regressed", "nightly health scan", or wants a health score trend after a merge to main. Adapted from Augment Code's "Codebase health scorecard with regression alerts" workflow.
---

# Codebase health scorecard with regression alerts

Scans each repository against six health criteria: AGENTS.md quality, test coverage, pre-commit hooks, CI health, dependency freshness and documentation coverage. Scores are kept across runs, so a regression triggers an alert to the owner team. Teams use the scorecard to prioritise cleanup and to decide where agent work is safe.

Source: https://www.augmentcode.com/workflows/devops/codebase-health-scorecard (Augment Code workflow, adapted for Claude Code).

## When to run

Augment runs this on a schedule (for example nightly) and on every merge to the main branch of any connected repository.
In Claude Code it runs on demand. Inputs:
- The repositories to scan (default: the current checkout; for a workspace, every git repo in it). For a post-merge run, the merged PR number.
- Settings, with defaults: coverage target (80%), regression threshold (5 points), criterion weights (equal weights if none are configured), and the minimum score below which a repo gets the `health-warning` tag (ask if not given; skip tagging if the user has none).
- The score history log path (an append-only file that persists between runs; ask if not given) and the Slack channel or dashboard for the scorecard.
To repeat it, use /loop or /schedule.

## Needs

- GitHub: `gh` CLI (`gh run list --branch <main> --limit 30 --json conclusion`, `gh run download` for coverage artifacts, `gh repo edit --add-topic`, `gh pr comment`).
- Coverage: the latest CI coverage report, or the SonarQube MCP if connected.
- Alerts and publishing: the Slack MCP if connected. Owner team: CODEOWNERS or the repo's documented owners.
- Dependency freshness: the stack's own outdated-package command (for example `npm outdated`, `pnpm outdated`, `pip list --outdated`).
- Optional follow-up tickets: the Linear MCP if connected.
- If a tool is not connected, ask the user for that data or skip the step and say so in the report. Never invent data.

## Steps

1. **Enumerate repositories.** Take the list from the inputs above (Augment pulls it from its environment config).
2. **Run the health scan for each repository.** Score each criterion 0–100:
   - a. **AGENTS.md coverage.** Does an AGENTS.md (or equivalent, such as CLAUDE.md) exist? Does it cover the required sections: codebase overview, coding conventions, test instructions, agent-specific notes? Score by completeness.
   - b. **Test coverage.** Pull the latest coverage report from CI. Score against the configured target (default 80%).
   - c. **Pre-commit hooks.** Are pre-commit hooks configured? Do they include linting, formatting and secrets detection?
   - d. **CI pipeline health.** What is the pass rate of the main-branch CI pipeline over the past 30 runs? Flag it if below 90%.
   - e. **Dependency freshness.** How many direct dependencies have a newer major or minor version available? Score by the ratio of up-to-date packages.
   - f. **Documentation coverage.** For public APIs and exported functions, what percentage have docstrings or inline documentation?
   - If a criterion cannot be measured (for example no coverage report), mark it "not measured" with the reason instead of guessing a score.
3. **Compute the composite score** for each repository as the weighted average of the criteria. Compare it with the score from the last run in the history log.
4. **Decision — score regressed?**
   - If the composite dropped by more than the threshold (default 5 points), post a Slack alert to the repository's owner team with the delta and the specific criteria that regressed. For a post-merge run, also comment on the merged PR.
   - In all cases, append this run to the score history log and continue.
5. **Generate the scorecard report.** For each repository: the composite score, per-criterion scores, the delta against the last run, and the top 3 recommended actions to improve the lowest-scoring criteria.
6. **Publish.** Post the scorecard to the configured Slack channel or dashboard. For repositories below the minimum threshold, apply the `health-warning` tag in the repository (a GitHub topic via `gh repo edit <repo> --add-topic health-warning`).

## Output

- One history log entry per repository per run: timestamp, repo, commit sha, per-criterion scores, composite score, delta.
- The scorecard (a Markdown table plus the top 3 actions per repo), posted to Slack or the dashboard and shown to the user.
- Regression alerts and `health-warning` tags where they apply.
- A short report to the user: repos scanned, regressions found, alerts and tags applied, and any criterion or step that was skipped.

## Guardrails

- Confirm with the user before any outward or hard-to-undo action (Slack alerts, PR comments, repo topics) unless they said to proceed without asking.
- Never fail a CI run on the health score. It is advisory, not a hard gate, unless the user explicitly configured otherwise.
- Keep the score history append-only so trend charts can be built. Never edit or delete past entries.
- Always include the recommended actions. A score without guidance is noise.
