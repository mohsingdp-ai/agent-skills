# augment

Claude Code plugin with 62 skills adapted from [Augment Code's public workflows](https://www.augmentcode.com/workflows).
Each skill keeps the workflow's steps, decisions and guardrails, translated to Claude Code tools (`gh`, connected MCPs, subagents, `/loop` for recurring work). Skills ask before posting, pushing or merging.

## Install

```bash
claude plugin marketplace add /path/to/AgentSkills/plugins/augment
claude plugin install augment@augment            # add --scope project for one repo only
```

Invoke a skill as `augment:<name>`, for example `augment:pr-author`.

Always-on cost is about 13.4k tokens per session (skill names and descriptions). Disable with `claude plugin disable augment@augment`.

## Skills

### AI evals

| Skill | Workflow |
|---|---|
| `augment:prompt-eval-regression-gate` | Prompt eval regression gate for LLM releases |
| `augment:synthetic-eval-dataset-from-prod` | Synthetic evaluation dataset generation from production logs |

### Coding

| Skill | Workflow |
|---|---|
| `augment:api-contract-drift-detector` | API contract drift detector with auto-versioning |
| `augment:architecture-review-before-implementation` | Architecture review before implementation |
| `augment:backlog-scrub-and-kickoff` | Linear backlog scrub and agent kickoff |
| `augment:continuous-code-simplification` | Continuous code simplification |
| `augment:deep-code-reviewer` | Automated deep review on every PR |
| `augment:docs-update-on-pr-merge` | Documentation auto-update on PR merge |
| `augment:feature-flag-cleanup` | Feature flag cleanup |
| `augment:figma-to-code` | Figma design to production code |
| `augment:legacy-code-migration` | Legacy code migration, module by module |
| `augment:meeting-notes-to-pr` | Meeting notes to PR |
| `augment:pair-reviewer` | Risk-triaged interactive pair review |
| `augment:pr-author` | Ticket or task to a merged PR |
| `augment:pr-auto-maintenance` | PR auto-maintenance agent |
| `augment:pr-review-triage` | Pull request review triage |
| `augment:pr-spec-adherence-check` | PR spec-adherence checker |
| `augment:project-builder` | Design doc to shipped feature |
| `augment:slack-feedback-to-pr` | Slack feedback to merged PR |
| `augment:spec-intake-to-rfc-ticket-breakdown` | Spec intake to RFC, ADR, and ticket breakdown |
| `augment:technical-debt-scanner` | Technical debt scanner |

### Data

| Skill | Workflow |
|---|---|
| `augment:backlog-prioritization` | AI-assisted backlog prioritization |
| `augment:cosmos-analyst` | Measure an AI agent's impact on your team |
| `augment:weekly-product-digest` | Weekly product digest from Slack, Linear and GitHub |

### Database

| Skill | Workflow |
|---|---|
| `augment:heavy-query-sandbox-optimiser` | Heavy query sandbox optimizer |
| `augment:safe-schema-migration-pipeline` | Safe schema migration pipeline |

### DevOps

| Skill | Workflow |
|---|---|
| `augment:backlog-dispatcher` | Scheduled backlog triage and agent kickoff |
| `augment:canary-slo-auto-rollback` | Canary deployment SLO breach auto-rollback |
| `augment:ci-build-failure-autofix` | CI build failure auto-fix |
| `augment:codebase-health-scorecard` | Codebase health scorecard with regression alerts |
| `augment:epic-decomposition-agent-orchestration` | Epic decomposition and parallel agent orchestration |
| `augment:personal-assistant` | Your persistent task tracker and agent dispatcher |
| `augment:safe-dependency-update` | Safe dependency update with regression loop |
| `augment:sop-policy-self-update` | SOP and policy self-update pipeline |

### Network

| Skill | Workflow |
|---|---|
| `augment:network-health-and-intrusion` | Network health and intrusion watch |

### Observability

| Skill | Workflow |
|---|---|
| `augment:backup-verification-and-incident` | Backup verification with auto-incident |
| `augment:incident-investigator` | Alert to root-cause analysis in Slack |
| `augment:incident-root-cause-correlation` | Incident root-cause correlation for on-call |
| `augment:monitoring-alert-investigation` | Monitoring alert auto-investigation |
| `augment:runbook-auto-execution` | Runbook auto-execution on incidents |

### QA

| Skill | Workflow |
|---|---|
| `augment:accessibility-audit-pr` | Accessibility audit on PR |
| `augment:e2e-playwright-pr-verification` | E2E Playwright verification on every PR |
| `augment:flaky-test-auto-quarantine` | Flaky test auto-quarantine and root-cause hunter |
| `augment:performance-regression-gate` | Performance regression gate |
| `augment:risk-based-test-plan-generator` | Risk-based test plan generator |
| `augment:spec-to-gherkin-tests` | PM spec to Gherkin to executable tests |
| `augment:test-coverage-gap-auto-pr` | Unit-test coverage gap analysis and draft PR |

### Release

| Skill | Workflow |
|---|---|
| `augment:documentation-readiness-gate-before-ga` | Documentation readiness gate before GA |
| `augment:release-candidate-readiness-review` | Release candidate readiness review |
| `augment:release-notes-multi-audience` | Multi-audience release notes from a Git tag |

### Security

| Skill | Workflow |
|---|---|
| `augment:auditor-evidence-response` | Auditor evidence response |
| `augment:continuous-privacy-compliance` | Continuous privacy compliance |
| `augment:license-compliance-continuous-audit` | Continuous license compliance audit for dependencies |
| `augment:owasp-vulnerability-scanner` | OWASP vulnerability scanner |
| `augment:secret-rotation-expiry-gate` | Proactive secret rotation with expiry gate |
| `augment:threat-model-from-prd` | Threat model from PRD or RFC |

### Support

| Skill | Workflow |
|---|---|
| `augment:ask-channel-kb-answer-drafting` | Ask-channel KB answer drafting |
| `augment:customer-escalation-to-product-fix` | Customer escalation to product fix workflow |
| `augment:docs-gap-from-support-ticket` | Doc gap auto-fix from support tickets |
| `augment:email-triage-and-response` | Email triage and automated response |
| `augment:multi-channel-ticket-dedup-sync` | Multi-channel support ticket sync with AI-driven deduplication |
| `augment:ticket-dispatcher` | Intelligent ticket dispatcher |

## Updating

Edit `skills/<name>/SKILL.md`, bump `version` in `.claude-plugin/plugin.json`, then run `claude plugin marketplace update augment` and `claude plugin update augment@augment`.

The original workflows belong to Augment Code; each skill links to its source page.
