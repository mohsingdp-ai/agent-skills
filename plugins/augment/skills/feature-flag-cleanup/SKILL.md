---
name: feature-flag-cleanup
description: Finds feature flags that have been at 100% rollout for more than 14 days or are past their removal date, removes each flag's check and dead code path while keeping the enabled branch, updates tests, and opens one cleanup PR per flag assigned to the owning team. Use when the user says "clean up stale feature flags", "remove fully rolled out flags", "find dead LaunchDarkly flags", or "open cleanup PRs for old flags". Adapted from Augment Code's "Feature flag cleanup" workflow.
---

# Feature flag cleanup

Feature flags pile up quickly. This skill scans the flag service (LaunchDarkly, Statsig, Unleash or a homegrown system) for flags past their removal date or fully rolled out for too long. For each stale flag, it traces usages, removes the guard and the dead branch, updates tests, and opens a cleanup PR.

Source: https://www.augmentcode.com/workflows/coding/feature-flag-cleanup (Augment Code workflow, adapted for Claude Code).

## When to run

Augment runs this weekly (Monday 08:00 UTC).
In Claude Code it runs on demand. Inputs: the flag service or the path to the homegrown flag config, the repo (default: the current checkout), and optionally a single flag name to clean up.
To repeat it, use /loop or /schedule.

## Needs

- Flag service: the LaunchDarkly MCP if connected (flag list, rollout percentage, time at 100%, removal date, owner). Statsig, Unleash or homegrown flags: their MCP or CLI if connected, or the flag config in the repo, or an export from the user.
- GitHub: `gh` CLI (`gh pr create --title --body --assignee --reviewer`).
- Code search: `grep`/`rg` across the repo, including tests, config and docs.
- Owner lookup: the flag service's owner field; the Linear MCP if connected to find the owning team.
- If a tool is not connected, ask the user for that data or skip the step and say so in the report. Never invent data.

## Steps

1. **Scan the flag service.** List flags and find stale ones. A flag is stale when either:
   - it has been at 100% rollout for more than 14 days, or
   - its scheduled removal date has passed.
2. **Decision — stale flags found?**
   - If no, report "No stale flags, nothing to clean up" and stop.
   - If yes, do steps 3–7 for each stale flag, one flag at a time, each on its own branch.
3. **Trace usages.** Find every code path that references the flag: the flag key string, any constants or wrappers around it, tests, config and docs.
4. **Remove the guard and the dead branch.** Remove the flag check and the dead code path. Keep the 'enabled' branch logic inline. Remove imports, helpers and constants that become unused.
5. **Update tests.** Update or delete the unit tests affected by the removal (for example, tests that only covered the disabled path). Run the affected tests.
6. **Confirm no references remain.** Search the repo again for the flag name and key. Every remaining hit must be removed or explained in the PR.
7. **Open the cleanup PR.**
   - Title: `cleanup: remove <flag-name> flag`.
   - Body: a summary of files changed, and a confirmation that no references to the flag remain (with the search used).
   - Assign the PR to the team listed as flag owner. GitHub assigns only people, so request review from the team (`--reviewer <org>/<team>`) and add `--assignee` when the flag names a person.

## Output

- One cleanup PR per stale flag, titled `cleanup: remove <flag-name> flag`, with a files-changed summary and a no-references-remain confirmation, assigned to the owning team.
- A short report to the user: flags scanned, stale flags found and why (14+ days at 100%, or removal date passed), PR links, owners, and any flag skipped with the reason.

## Guardrails

- Confirm with the user before pushing branches or opening PRs, unless they said to proceed without asking.
- Keep the 'enabled' behavior exactly. If a flag is at 100% but the code path is unclear (for example the flag is inverted or used as a kill switch), skip it and report it rather than guess.
- Do not archive or delete the flag in the flag service; this skill only changes code.
- If the owning team is not recorded, leave the PR unassigned and say so in the report.
