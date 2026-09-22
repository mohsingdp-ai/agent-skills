# addy-skills

This is the `addy-skills` plugin (packaged from [`addyosmani/agent-skills`](https://github.com/addyosmani/agent-skills)) — a collection of production-grade engineering skills for AI coding agents.

> **Scope:** This plugin configures engineering workflow skills and slash commands in Claude Code under the `addy-skills` namespace (`addy-skills:<skill-name>`).

## Project Structure

```
skills/           → Core skills (SKILL.md per directory)
agents/           → Reusable agent personas (code-reviewer, test-engineer, security-auditor, web-performance-auditor)
hooks/            → Session lifecycle hooks
.claude/commands/ → Slash commands (/spec, /plan, /build, /test, /review, /code-simplify, /ship, /constraints, /webperf)
references/       → Supplementary checklists (testing, performance, security, accessibility, observability)
evals/            → Skill eval cases + framework (see evals/README.md)
docs/             → Setup guides for different tools
```

## Skills by Phase

**Define:** interview-me, idea-refine, spec-driven-development, constraint-driven-development
**Plan:** planning-and-task-breakdown
**Build:** incremental-implementation, test-driven-development, context-engineering, source-driven-development, doubt-driven-development, frontend-ui-engineering, api-and-interface-design
**Verify:** browser-testing-with-devtools, debugging-and-error-recovery
**Review:** code-review-and-quality, code-simplification, security-and-hardening, performance-optimization
**Ship:** git-workflow-and-versioning, ci-cd-and-automation, deprecation-and-migration, documentation-and-adrs, observability-and-instrumentation, shipping-and-launch

## Conventions

- Every skill lives in `skills/<name>/SKILL.md`
- YAML frontmatter with `name` and `description` fields
- Description starts with what the skill does (third person), followed by trigger conditions ("Use when...")
- Every skill has: Overview, When to Use, Process, Common Rationalizations, Red Flags, Verification
- Shared references are in the root `references/` directory; the emerging convention for self-contained, distributable skills keeps a skill's own references inside `skills/<name>/references/`
- Supporting files only created when content exceeds 100 lines

## Invocation

- In Claude Code: `addy-skills:<skill-name>` (e.g. `addy-skills:code-review-and-quality`, `addy-skills:test-driven-development`)
- Slash commands: `/spec`, `/constraints`, `/plan`, `/build`, `/test`, `/review`, `/code-simplify`, `/ship`, `/webperf`
