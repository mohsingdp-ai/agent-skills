---
name: canary-slo-auto-rollback
description: Gates a Kubernetes canary deployment on live SLO metrics by comparing canary latency, error rate and saturation against a 7-day stable baseline, advancing the 10/25/50/100% traffic ramp while healthy, pausing on network partitions, and rolling back with a PagerDuty incident after two consecutive breached windows. Use when the user says "watch this canary", "gate the rollout on SLOs", "should this canary advance or roll back", "run canary analysis for workload X", or shares an Argo Rollouts, Flagger or canary Deployment revision. Adapted from Augment Code's "Canary deployment SLO breach auto-rollback" workflow.
---

# Canary deployment SLO breach auto-rollback

Watches a canary deployment and compares its p50/p95/p99 latency, error rate and saturation with stable traffic. Healthy canaries keep ramping. Sustained SLO breaches halt the rollout, roll back, open an incident and write an audit entry. Missing baselines or weak traffic fail safely to manual review.

Source: https://www.augmentcode.com/workflows/devops/canary-slo-auto-rollback (Augment Code workflow, adapted for Claude Code).

## When to run

Augment runs this on a new canary deployment event from the Kubernetes control plane (Argo Rollouts, Flagger, or a native Deployment with a canary track), keyed on the workload name and the canary revision.
In Claude Code it runs on demand. Inputs: the workload name, canary revision, namespace and cluster context, rollout type (Argo Rollouts, Flagger or native), the baseline minimum N requests per route, the per-route minimum sample size (default about 1k requests per route, or the threshold the baseline used), and the audit log path (default `.claude/logs/canary-audit.jsonl`).
Each 5-minute window is one pass. To repeat the sampling loop, use `/loop 5m` (or the Monitor tool); do not block the session on long sleeps.

## Needs

- Kubernetes: `kubectl` (`kubectl rollout status`, `kubectl rollout undo`), plus the Argo Rollouts kubectl plugin for Argo (`kubectl argo rollouts get rollout`, `pause`, `promote`, `abort`).
- Metrics and baselines: the Datadog MCP if connected, and Prometheus through the Grafana MCP if connected.
- If the ramp is driven by Harness or a LaunchDarkly flag instead of the rollout controller: the Harness MCP or LaunchDarkly MCP if connected, to hold, advance or roll back.
- Incidents: the PagerDuty MCP if connected. Operator page and notifications: the Slack MCP if connected.
- If a tool is not connected, ask the user for that data or skip the step and say so in the report. Never invent data.

## Steps

Gather and analyse without stopping to ask questions. Stop only at the manual approval gate and for the confirmations in Guardrails.

1. **Pull baseline SLOs.** From Datadog and from Prometheus through Grafana, get p50, p95 and p99 latency, error rate and saturation over the last 7 days of stable traffic on the same service. Cache the baseline keyed by workload + route + method.
2. **Decision — baseline available?** Sufficient stable history means at least 24h of clean traffic and at least N requests per route.
   - If no, fail safe to the manual approval gate (step 3) before any traffic shift.
   - If yes, go to sampling (step 4).
3. **Manual approval gate.** Page the release operator on Slack. Show the workload, the missing-baseline reason, and the proposed ramp ladder. The operator must explicitly approve before the canary receives traffic. Without a baseline, never auto-advance: every later ramp step also needs the operator's approval.
4. **Sample canary metrics** over a 5-minute window: p50/p95/p99 latency, error rate (5xx + application errors), and saturation (CPU, memory, in-flight requests). In the same step, probe the canary pods for reachability from the SLO scraper.
5. **Decision — network healthy?** All scrape probes returned within timeout, and there is no partition between the SLO collectors and the canary.
   - If no, pause the rollout: hold the current traffic split and do not roll back. Alert release-ops on Slack and stop. A partitioned reading is not a real SLO breach.
   - If yes, continue.
6. **Decision — significant traffic?** The canary received at least the per-route minimum sample size for a meaningful comparison (configurable; default about 1k requests per route, or the same threshold the baseline used).
   - If no, extend the observation window: wait one more 5-minute cycle and resample (step 4).
   - If yes, continue.
7. **Compare canary vs baseline.** Score each metric against the baseline window: `error_rate_canary / error_rate_baseline`, `p99_canary / p99_baseline`, and saturation deltas. Record the verdict for this window in the canary audit log.
8. **Decision — breached for 2 consecutive windows?** A breach is error rate > 2x baseline OR p99 latency > 1.5x baseline, sustained across the previous and the current 5-minute window.
   - If yes, halt the traffic ramp, execute the automated rollback (`kubectl rollout undo`, or abort the Argo Rollout), open a PagerDuty incident with the breach evidence and audit trail to page on-call, log the action, and stop.
   - If no, continue to the ramp evaluation.
9. **Decision — at 100% traffic?** The canary is receiving full production traffic and has just cleared the final healthy window.
   - If yes, promote the canary to stable, post a Slack notification with the rollout summary, append the success entry to the audit log, and stop.
   - If no, continue.
10. **Advance the ramp** one step on the 10% → 25% → 50% → 100% ladder, within a 30–60 minute total budget. Then loop back to sampling (step 4) for the next window.

## Output

- An append-only audit log keyed by workload + revision, with every window verdict, the final outcome, and the rollback or promotion action.
- One of four outcomes: promoted with a Slack rollout summary; rolled back with a PagerDuty incident; paused with a Slack alert (network partition); or waiting at the manual approval gate.
- A short report to the user: workload, revision, current traffic step, per-window ratios, outcome, and any step that was skipped.

## Guardrails

- Confirm with the user before any traffic shift, rollback, promotion, page or Slack message unless they said to proceed without asking.
- Never roll back on a single bad window. Require two consecutive breaches to filter transient noise.
- Never roll back on a network-partition reading. Pause and alert instead, because the data is unreliable.
- Always gate on a baseline. A missing baseline means human approval, never auto-advance.
- Always write every window verdict, the final outcome, and the rollback or promotion action to the append-only audit log keyed by workload + revision, so trends and post-mortems can be built later.
- Never expose raw scrape credentials or PagerDuty routing keys in Slack messages or the audit log.
