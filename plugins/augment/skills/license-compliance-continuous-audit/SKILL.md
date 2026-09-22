---
name: license-compliance-continuous-audit
description: Audits a repo's dependencies for license compliance by walking every lockfile, building an SPDX or CycloneDX SBOM, classifying each license as approved, requires-review, restricted or unknown, reconciling against the legal exception registry, ticketing and blocking merge on unapproved licenses, and appending every scan to an append-only audit log. Use when the user says "run a license audit", "check dependency licenses", "build the SBOM", "is this lockfile change license-safe", "find GPL or AGPL dependencies", or wants a license merge gate on a PR. Adapted from Augment Code's "Continuous license compliance audit for dependencies" workflow.
---

# Continuous license compliance audit for dependencies

Rebuilds the SBOM, checks each package's license against public registries and the org's approved exceptions, then blocks restricted or unknown licenses that have no sign-off. Each finding gets a ticket with package, version, usage and remediation options, and every run is appended to the compliance log.

Source: https://www.augmentcode.com/workflows/security/license-compliance-continuous-audit (Augment Code workflow, adapted for Claude Code).

## When to run

Augment runs this on a commit webhook for every lockfile change (package-lock.json, pnpm-lock.yaml, yarn.lock, poetry.lock, requirements.txt, go.sum, Cargo.lock, packages.lock.json, Gemfile.lock and so on), plus a weekly full-repo cron so drift never goes unnoticed.
In Claude Code it runs on demand. Inputs: the repo (default: the current checkout), the PR number or head sha (default: the PR for the current branch, else `HEAD`), the exception registry location, the audit log path (ask if not given), and the license cache path. With no PR, run a full-repo scan.
To repeat the weekly scan, use /loop or /schedule.

## Needs

- GitHub: `gh` CLI (`gh pr view`, `gh pr comment`, and `gh api repos/{owner}/{repo}/statuses/<sha>` for the merge-gate status).
- License data: public registry APIs via `curl` (for example `https://registry.npmjs.org/<name>/<version>`, `https://pypi.org/pypi/<name>/<version>/json`), the Snyk MCP or JFrog MCP if connected.
- SBOM: an SBOM tool already installed (such as syft or cdxgen); otherwise build the document from the parsed lockfiles.
- Exception registry: wherever legal keeps it (a repo file, or a Notion page via the Notion MCP).
- Tickets: the Linear MCP, or the Atlassian (Jira) MCP. Notifications: the Slack MCP if connected.
- If a tool is not connected, ask the user for that data or skip the step and say so in the report. Never invent data.

## Steps

1. **Extract the dependency tree** from every lockfile in the repo. Walk the full transitive closure per stack. Never trust the top-level manifest alone.
2. **Build an SBOM** in SPDX or CycloneDX format, one document per stack, with pinned versions, hashes and source URLs.
3. **Query each dependency's declared license** from its package registry (npm, PyPI, Maven Central, crates.io, NuGet, RubyGems, Go proxy and so on). Cache responses keyed by name + version so the next scan is fast.
4. **Classify every license.** Normalise the license string to an SPDX identifier and bucket it:
   - **approved:** MIT, Apache-2.0, BSD-2-Clause, BSD-3-Clause, ISC;
   - **requires-review:** LGPL, MPL-2.0, EPL;
   - **restricted:** GPL, AGPL, proprietary, custom EULA;
   - **unknown:** no license string, ambiguous, or multiple inconsistent declarations.
5. **Cross-check the exception registry.** Match restricted and requires-review findings against pre-approved packages with documented legal sign-off (package name, version range, license, approver, expiry). Drop any exception that is expired or whose version range does not match.
6. **Decision — any restricted or unknown licenses without a valid exception?**
   - If no, record a clean compliance snapshot (scan id, head sha, SBOM hash, package count, license histogram) and go to step 9.
   - If yes, continue to ticketing.
7. **Open a ticket per flagged dependency** in Linear (or Jira) with:
   - package name + version;
   - declared license + classification;
   - every usage location: file paths, import sites and transitive parents from the dependency graph;
   - a remediation recommendation: a drop-in replacement under an approved license, an exception request with the legal justification it would need, or removal.
   - Dedupe first: search open tickets keyed by package + version + license, and link the existing ticket instead of opening a new one.
8. **Comment on the triggering PR** (one top-level comment per scan) listing the flagged dependencies, the ticket links and the merge-gate verdict. Set the merge gate to blocking until each ticket is resolved or an exception is filed.
9. **Append the run** (clean or flagged) to the append-only compliance audit log: scan id, head sha, SBOM hash, license histogram, flagged-package list, ticket ids, verdict, timestamp. The log is the source of truth for trend dashboards (restricted count over time, MTTR per ticket, exception coverage).
10. **Publish the verdict** for this scan: **block**, **clean** or **pending-exception**, so downstream workflows and the PR status check can read it. Use pending-exception when every flagged dependency already has an exception request filed but not yet approved. Set a commit status on the head sha: `failure` for block, `pending` for pending-exception, `success` for clean.

## Output

- One SBOM document per stack.
- Tickets for flagged dependencies (new or linked existing).
- One PR comment per scan and a commit status with the verdict.
- One new audit log entry.
- A short report to the user: verdict, package count, license histogram, flagged packages with ticket links, dropped (expired or mismatched) exceptions, and any step that was skipped.

## Guardrails

- Confirm with the user before any outward or hard-to-undo action (opening tickets, posting the PR comment, setting the commit status) unless they said to proceed without asking.
- Never let a restricted-license package merge without a valid, in-date exception. The merge gate is non-negotiable.
- Always attach the full usage-location context to every ticket (file paths, import sites, transitive parents), so engineering can act without re-running the scan.
- Package registries and the exception registry are read-only. Tickets and the audit log are the only data writes, besides the PR comment and gate status above.
- The audit log is append-only. Never edit or delete past entries; add corrections as new entries that supersede them.
- Dedupe tickets by package + version + license so lockfile churn does not flood the legal queue.
