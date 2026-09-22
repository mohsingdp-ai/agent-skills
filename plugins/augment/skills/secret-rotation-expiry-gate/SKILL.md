---
name: secret-rotation-expiry-gate
description: Sweeps HashiCorp Vault, AWS Secrets Manager, 1Password Connect and environment-variable references for secrets within 7 days of expiry, generates replacements through the vault's rotation policy, keeps the old version live, validates the new value in staging with smoke tests, reverts and pages security on failure, and promotes to production only after human approval, recording every run in an append-only audit trail. Use when the user says "check for expiring secrets", "rotate secrets before they expire", "run the secret expiry sweep", "rotate this certificate safely", or wants a staged, audited credential rotation. Adapted from Augment Code's "Proactive secret rotation with expiry gate" workflow.
---

# Proactive secret rotation with expiry gate

Tracks secret expiry across the configured vaults, rotates credentials before they lapse, validates each new value in staging, and keeps an audit trail of every rotation. Nothing reaches production without human approval. Failed staging checks are reverted and security on-call is paged.

Source: https://www.augmentcode.com/workflows/security/secret-rotation-expiry-gate (Augment Code workflow, adapted for Claude Code).

## When to run

Augment runs this as a weekly cron sweep across all configured vaults, plus on demand when any monitored secret is within 7 days of its expiry timestamp.
In Claude Code it runs on demand. Inputs: the vaults to sweep (HashiCorp Vault, AWS Secrets Manager, 1Password Connect, environment-variable references; default: all configured), the staging and production environments, the IaC / config-as-code pipeline, the SIEM or audit trail destination, and the maintenance windows for shared secrets.
To repeat it, use /loop or /schedule.

## Needs

- AWS Secrets Manager: the AWS MCP server if connected, or the `aws secretsmanager` CLI.
- HashiCorp Vault: the `vault` CLI if installed. 1Password Connect: the `op` CLI if installed.
- Environment-variable references: the IaC and config files in the repo.
- Certificates: `openssl` to read `notAfter` and to generate fallback certs or keys.
- IaC pipeline: `gh` CLI (`gh pr create`, `gh workflow run`, `gh run watch`) or the team's pipeline tool.
- Smoke tests: the Playwright MCP if connected for login flows, and service health checks; the Datadog MCP if connected for auth error rates.
- Paging: the PagerDuty MCP if connected. Notifications: the Slack MCP if connected.
- Audit trail: the SIEM or append-only log the user names.
- If a tool is not connected, ask the user for that data or skip the step and say so in the report. Never invent data.

## Steps

Gather and analyse without stopping to ask, up to the approval gate in step 8.

1. **Enumerate secrets.** List every secret across the configured vaults and pull its expiry metadata: TTL, lease end, certificate `notAfter`, or manual expiry tag.
   - No expiry metadata: infer one from the vault's rotation policy.
   - No policy either: flag the secret in the audit trail and skip it this run.
2. **Decision — is any secret within 7 days of expiry?**
   - If no, record a clean sweep to the SIEM trail (timestamp, secrets checked, next expiry date) and end.
   - If yes, continue with the at-risk set.
3. **Generate a replacement** for each at-risk secret.
   - Prefer the vault's built-in rotation: Vault dynamic secret, AWS Secrets Manager rotation Lambda, 1Password rotation hook.
   - Fall back to an OpenSSL-generated cert or a crypto-random key for static credentials.
   - Never write the new value to disk outside the vault. Pipe it straight into the vault; never print it in terminal output or this conversation.
4. **Write to the vault.** Store the new value, tag the previous version "deprecated" with the rotation timestamp, and keep the previous version live so dependents can still resolve it during cut-over.
5. **Deploy to staging.** Push the updated secret reference to a staging environment that mirrors the production dependency graph. Use the existing IaC / config-as-code pipeline. Never hand-edit production-adjacent config.
6. **Run smoke tests against staging.** For every dependent service that uses the secret:
   - open a connection through it and verify auth succeeds with the new value;
   - confirm the previous version is still accepted, so a stale dependent does not break during the rollout window.
7. **Decision — did the smoke tests pass (all dependents authenticated)?**
   - If no, revert the staging reference to the previous version, page security on-call with the failure log, append the reverted run to the audit trail, and end without touching production.
   - If yes, continue.
8. **Pause for human approval** before production rollout. Show the approver the diff, the staging smoke-test report, and the maintenance-window check for every service that shares this secret. If a secret fans out to multiple dependent services and no maintenance window is available, pause for human scheduling.
9. **Promote and notify.** After approval, promote the new secret reference to production through the same IaC pipeline. Then notify stakeholders on Slack (security channel, dependent-service owners) with the rotation summary, timestamp and next expiration date. Append the successful promotion to the audit trail.

## Output

- One append-only audit trail entry per run: a clean sweep, a successful promotion, or a failed-then-reverted run, plus flagged secrets that have no expiry or policy.
- For rotations: an approval packet (diff, staging smoke-test report, maintenance-window check), a production promotion through IaC, and a Slack rotation summary.
- For failures: a staging revert and a security on-call page with the failure log.
- A short report to the user: secrets checked, at-risk set, outcome per secret, next expiry date, and any step that was skipped. No secret values.

## Guardrails

- Confirm with the user before any outward or hard-to-undo action (writing to a vault, deploying to staging, paging, posting to Slack) unless they said to proceed without asking.
- Never auto-promote to production. The human approval gate before rollout is mandatory, even for low-risk secrets, and "proceed without asking" does not skip it.
- Never write a generated secret value anywhere outside the vault: no logs, no terminal output, no ticket bodies, no Slack posts, no PR descriptions.
- Always keep the previous version live until staging confirms the new value works end to end. Rotation is a cut-over, not a hard swap.
- Always coordinate rotation with the maintenance window for any secret that fans out to multiple dependent services. If no window is available, pause for human scheduling.
- Always record every rotation event (clean sweep, successful promotion, failed-then-reverted run) in the append-only audit trail, so SOC 2 evidence and trend analysis (MTTR for rotation, near-expiry rate) can be built later.
