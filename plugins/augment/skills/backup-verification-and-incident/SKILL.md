---
name: backup-verification-and-incident
description: Verifies every backup expected in a backup window (existence, size, checksum, tool status, sampled restore test), diagnoses and classifies each failure, correlates it with application logs, retries only known-transient failures, and opens a fully documented incident and pages on-call for the rest. Use when the user says "check last night's backups", "verify the backup window", "did any backups fail", "run a restore test", or wants a backup failure turned into an incident with log evidence. Adapted from Augment Code's "Backup verification with auto-incident" workflow.
---

# Backup verification with auto-incident

Checks every backup that should have run in a window, verifies the artefacts, and samples restore tests. Each failure is classified by cause and correlated with application logs. Known-transient failures are retried; everything else becomes an incident with evidence, timeline and runbook context, and the on-call engineer is paged.

Source: https://www.augmentcode.com/workflows/observability/backup-verification-and-incident (Augment Code workflow, adapted for Claude Code).

## When to run

Augment runs this at the end of each scheduled backup window (daily, hourly, or whatever cadence is configured) and on every backup-completion event from the backup tool.
In Claude Code it runs on demand. Inputs: the backup window (default: the most recent completed window), where the schedule and asset inventory live, the restore sample size (configurable; default: one artefact per asset type), and the scratch environment for restores.
To repeat it, use /loop or /schedule.

## Needs

- Backup tool and storage: its CLI or API (for example the `aws` CLI for AWS Backup, RDS snapshots or S3).
- Restore target: a scratch environment the user names. Never production.
- Application logs: the Sentry MCP or Honeycomb MCP if connected, or the cloud log tool (for example `aws logs`). Recent deploys: `gh run list` or the deploy tool.
- Incidents and paging: the PagerDuty MCP, Linear MCP or Atlassian (Jira) MCP if connected, whichever the team uses.
- Status board and messages: the Slack MCP if connected, or the board the user names.
- Run record: the append-only file or table the user names.
- If a tool is not connected, ask the user for that data or skip the step and say so in the report. Never invent data.

## Steps

Gather and analyse without stopping to ask between steps.

1. **Enumerate expected backups.** List every backup that was expected to run during the window. Pull the list from the schedule and the asset inventory: databases, services, volumes, object stores.
2. **Verify each artefact.** For every expected backup, check that:
   - the artefact exists;
   - its size is in the expected range;
   - its checksum matches;
   - the backup tool reported success.
3. **Run a sampled restore test.** Pick the configured subset of artefacts and restore them to the scratch environment to confirm they are not silently corrupted.
4. **Decision — are all backups healthy (files and checksums valid, restores good)?**
   - If yes, record the run as healthy on the backup status board, append it to the run record, and end.
   - If no, continue.
5. **Diagnose each failure individually.** Classify the root cause into one bucket: not enough disk space, network timeout, target server down, permission denied, expired credentials, corrupted artefact, missing dependency, quota exceeded, or unknown.
6. **Correlate with application logs.** For each failed backup, pull the logs from the source service and any adjacent services for the same time range. Surface anything that looks related: errors, restarts, deploys, traffic spikes, lock waits.
7. **Compose an incident report** that includes:
   - which backups failed;
   - the diagnosed cause for each;
   - the relevant log excerpts;
   - a timeline;
   - what was attempted automatically.
8. **Decision — is the failure auto-recoverable?** Only known-transient causes qualify: network timeout, momentary lock wait, brief quota exhaustion.
   - If yes, retry the backup, re-verify it (steps 2–3 for that asset), and update the run record. If the retry does not come back healthy, treat it as not recoverable and continue.
   - If no, continue.
9. **Open an incident** in the on-call system (PagerDuty, Linear or Jira, whichever is configured) with the report attached. Include the affected assets, the diagnosed cause, the correlated log excerpts, and the runbook link if one exists.
10. **Page the on-call engineer** with a one-paragraph summary plus the link to the full incident.

## Output

- One appended run record entry: window, assets checked, result per asset (healthy, retried-and-healthy, or incident), diagnosed cause, action taken, incident link.
- The backup status board updated for the run.
- For unrecoverable failures: an incident with the full report, and an on-call page with a one-paragraph summary and link.
- A short report to the user: counts per result, causes found, incident and page links, and any step that was skipped.

## Guardrails

- Confirm with the user before any outward or hard-to-undo action (retrying backups, restoring, opening the incident, paging, posting to Slack) unless they said to proceed without asking.
- Never silently swallow a failure. Every failed backup must end up either retried-and-healthy or as an incident.
- Always attach the correlated log excerpts to the incident. The on-call engineer should not have to dig for them.
- Keep the run record append-only, so trend dashboards (failure rate, MTTR, recurring causes) can be built later. Never edit or delete past entries.
- Restore tests go only to the scratch environment. Never restore over a live system.
