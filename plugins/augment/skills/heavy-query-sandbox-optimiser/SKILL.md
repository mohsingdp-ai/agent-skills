---
name: heavy-query-sandbox-optimiser
description: Finds the most expensive database queries from slow-query logs, query statistics and APM traces, benchmarks rewrite candidates on a sandboxed replica, verifies they return the same rows, and opens a PR only when one is clearly faster or lighter. Use when the user asks to "find our slowest queries", "optimise heavy queries", "benchmark this query rewrite", "test an index in a sandbox", or wants a query-optimisation PR backed by a benchmark table. Adapted from Augment Code's "Heavy query sandbox optimizer" workflow.
---

# Heavy query sandbox optimizer

Reads slow-query logs and APM data, ranks expensive queries by time, bandwidth, rows scanned and lock waits, then tests safer rewrites on a production-like sandbox replica. Opens a PR only when a candidate returns the same rows and is meaningfully faster. If nothing clears the bar, the finding goes to the optimisation log.

Source: https://www.augmentcode.com/workflows/database/heavy-query-sandbox-optimiser (Augment Code workflow, adapted for Claude Code).

## When to run

Augment runs this continuously: on every new slow-query log entry, plus a periodic sweep of the APM / pg_stat_statements top-N by total time and total bytes returned.
In Claude Code it runs on demand. Inputs:
- The database (engine, read-only access to its statistics and slow log) and the repo (default: the current checkout).
- How to get a sandbox replica (a Neon or Supabase branch, or a local container restored from an anonymised snapshot).
- Top-N to keep, the "worth optimizing" cost threshold, and the improvement margin. The original leaves these configurable; use top 10 and a 20% margin unless the user says otherwise.
- Where the optimisation log lives (ask; if there is none, propose a file and confirm before creating it).

To repeat the sweep, use /loop or /schedule.

## Needs

- Query statistics: `psql` against `pg_stat_statements` (Postgres) or Performance Schema (MySQL), plus the slow-query log.
- APM traces: the Datadog, Honeycomb or Sentry MCP if connected.
- Sandbox: the Neon MCP or Supabase MCP (branching) if connected; the MongoDB, Redis, Convex or Google BigQuery MCP for those engines; otherwise a local database container.
- GitHub: `gh` CLI (`gh pr create`).
- If a tool is not connected, ask the user for that data or skip the step and say so in the report. Never invent data.

## Steps

Gather and analyse without stopping to ask questions between steps.

1. **Collect and fingerprint.** Pull candidate queries from the slow-query log, pg_stat_statements / Performance Schema and the APM trace stream. Normalise them (parameterise literals) so duplicates collapse into one fingerprint per query shape.
2. **Rank by cost.** Combine total execution time, mean time, calls per minute, rows scanned, bytes returned over the network, and lock wait time. Keep the top offenders.
3. **Decision — worth optimizing?** Skip queries that are above neither cost threshold: already cheap, run rarely, or dominated by client-side wait. If not worth it, record the finding in the optimisation log and end for that query.
4. **Pull the context** for each kept query: table schemas, current indexes, the EXPLAIN ANALYZE plan, partitioning, recent migrations, and a representative parameter set captured from production traffic. EXPLAIN ANALYZE executes the query, so run it on the sandbox, or use plain `EXPLAIN` or a captured `auto_explain` plan from production.
5. **Draft rewrite candidates.** Propose several independent strategies, for example:
   - rewrite the SQL (push predicates down, replace correlated subqueries with joins, switch IN to EXISTS, project fewer columns, paginate properly);
   - add a covering or partial index;
   - add a materialized view or a summary table;
   - batch the call site instead of issuing N queries;
   - denormalise a hot column.
6. **Provision a sandbox replica** that mirrors the production schema and a recent, anonymised data snapshot. Reset it between runs so candidates do not pollute each other.
7. **Benchmark each candidate, including the unchanged baseline.** For each one:
   - apply the migration or index in the sandbox;
   - run the query with the captured parameter set, warm and cold;
   - record execution time (p50 / p95), rows scanned, rows returned, bytes returned over the network, buffers read, index hit ratio, and any lock waits (for Postgres, `EXPLAIN (ANALYZE, BUFFERS)`);
   - confirm the result set is equivalent to the baseline (same row count, and no rows in either side `EXCEPT` the other).
8. **Decision — result-equivalent and meaningfully faster?** A candidate qualifies only if it returns the same rows AND beats the baseline by the configured margin on time and / or bandwidth, without regressing the other metrics.
   - If no candidate qualifies, write the findings to the optimisation log and end.
   - If yes, continue.
9. **Pick the best candidate.** Tie-break by lowest write-amplification, then smallest index footprint, then simplest migration.
10. **Open an optimisation pull request** containing:
    - the rewrite or migration;
    - the EXPLAIN diff (baseline vs winner);
    - the benchmark table comparing every candidate;
    - a rollout note: locking implications, expected index build time, and how to roll back.

## Output

- For a winner: a PR with the change, EXPLAIN diff, full benchmark table and rollout note.
- For no winner or a skipped query: an appended optimisation-log entry (fingerprint, cost metrics, candidates tried, results, reason).
- A short report to the user: queries ranked, queries skipped and why, winners with the time and bandwidth saved, PR links, and any step skipped.

## Guardrails

- Confirm with the user before any outward or hard-to-undo action (provisioning paid sandbox branches, opening the PR, writing the optimisation log) unless they said to proceed without asking.
- Never run candidates against production. Every benchmark goes through the sandbox replica. Production access is read-only statistics and plans.
- Always verify result equivalence before declaring a winner. A faster query that returns different rows is a regression.
- Keep the optimisation log append-only so trend dashboards (queries optimised, time saved, bandwidth saved) can be built over time.
