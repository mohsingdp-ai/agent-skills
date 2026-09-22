---
name: prompt-eval-regression-gate
description: Gates an LLM release candidate or model checkpoint on a prompt-evaluation suite by replaying the same scenarios, comparing accuracy, safety, latency and cost per scenario against the last shipped baseline, blocking with an incident on any critical regression, queuing near misses for ML triage, promoting the baseline only after a clean gate, and appending every run to an append-only eval history log. Use when the user says "run the eval gate on this checkpoint", "did the RC regress against production", "compare evals to baseline", "should this model release ship", or pushes a release/* or rc-* branch for an LLM feature. Adapted from Augment Code's "Prompt eval regression gate for LLM releases" workflow.
---

# Prompt eval regression gate for LLM releases

Gates every release candidate of an LLM-powered feature on a prompt-evaluation regression suite. Replays the same eval set against the candidate, compares every scenario with the last shipped baseline, and blocks the release with an incident if anything critical regressed. Clean runs promote the new baseline; near misses are queued for ML triage and every run is logged for trend dashboards.

Source: https://www.augmentcode.com/workflows/ai/prompt-eval-regression-gate (Augment Code workflow, adapted for Claude Code).

## When to run

Augment runs this on every new model checkpoint published to the model registry, and on every push to a release-candidate branch (for example `release/*` or `rc-*`).
In Claude Code it runs on demand. Inputs:
- The candidate: a checkpoint id, or an RC branch or sha (default: the current branch if it matches `release/*` or `rc-*`).
- The baseline: the last shipped version (default: the current production checkpoint or latest release tag).
- The eval suite command and config: scenarios, which ones are tagged critical, per-scenario floors, warning bands, and the aggregate release-gate threshold. Ask if they are not in the repo; do not invent floors.
- The eval-history log path, the baseline store, and the ML team channel.

## Needs

- GitHub: `gh` CLI (`gh api repos/{owner}/{repo}/statuses/<sha>` to set the release gate status on the RC commit).
- Incidents: the Linear MCP or the Atlassian (Jira) MCP.
- Release flag, if the team gates deploys with one: the LaunchDarkly MCP if connected. Latency traces: the Honeycomb MCP if connected.
- Notifications: the Slack MCP if connected.
- If a tool is not connected, ask the user for that data or skip the step and say so in the report. Never invent data.

## Steps

1. **Fetch the baseline.** Load the baseline scores and example outputs from the last shipped version (the current production checkpoint or release tag), so every comparison is apples to apples.
2. **Run the eval suite against the candidate.** Replay the full scenario set: golden prompts, adversarial probes, safety jailbreak attempts, and latency / cost benchmarks. Capture per-scenario scores for accuracy, safety, latency (p50 / p95) and cost per call.
3. **Compare candidate to baseline.** Compute deltas per scenario and per metric, plus aggregate movement on each metric. Flag any scenario that crossed its configured floor: accuracy drop, safety score drop, or latency or cost ceiling breached.
4. **Decision — any critical scenario regressed?** A critical regression is a scenario tagged critical that crosses its floor, or aggregate movement past the release-gate threshold.
   - If yes:
     - Open an incident in Linear or Jira with the failing scenarios, candidate vs baseline scores, the actual model outputs side by side, and a one-paragraph summary.
     - Block the release gate (commit status `failure`, or the team's release flag).
     - Notify the ML team channel so the fix loop can start.
     - Do not touch the baseline. Go to step 7. The next checkpoint or RC push re-enters the gate.
   - If no, continue.
5. **Flag near-miss edge cases.** Any scenario inside its warning band (close to the floor but not over it) goes into a queue for the ML team to triage asynchronously, so the next baseline is not blind to drift.
6. **Promote the baseline and allow the release.** Save the candidate scores and example outputs as the new baseline, so the next candidate is compared with this version, not the old one. Then mark the release gate green (commit status `success`, or the team's release flag) so the deploy pipeline can ship the candidate.
7. **Append to the eval-history log (every run, block or allow).** Record: run id, candidate identifier, baseline identifier, every per-scenario score and delta, the decision, the near-miss queue, and the incident link when one was opened. Trend dashboards (regression rate, recurring failure scenarios, accuracy / safety drift, MTTR on blocked releases) are built on this log.

## Output

- Blocked run: an incident with scenario deltas and side-by-side outputs, a red gate, a message to the ML team channel, and a log entry.
- Clean run: a near-miss queue (possibly empty), a promoted baseline, a green gate, and a log entry.
- A short report to the user: decision, critical regressions or near misses with deltas, incident link, gate state, and any step that was skipped.

## Guardrails

- Confirm with the user before any outward or hard-to-undo action (opening the incident, setting the gate, posting to Slack, promoting the baseline) unless they said to proceed without asking.
- Never ship a candidate with a known critical regression. The gate is mandatory: never mark it green, even on request, while the recorded comparison shows a critical regression.
- Always attach example outputs and per-scenario score deltas to the incident, so the ML team can reproduce the regression without rerunning the suite.
- Keep the eval-history log append-only. Never overwrite a prior run record, even when the same candidate is re-evaluated later.
- Update the baseline only after a clean gate, never before, so a regression cannot poison the comparison floor for the next candidate.
