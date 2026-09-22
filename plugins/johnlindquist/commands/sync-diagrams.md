---
description: Store and synchronize digrams with codebase in ai/diagrams directory
allowed-tools: Bash(mkdir:*), Bash(find:*), Glob, Read, Write, Edit
argument-hint: [diagram-name]
---

# Diagram Synchronization (DDD Workflow)

You are operating under **Diagram Driven Development (DDD)** methodology.

**Purpose:** Maintain the `ai/diagrams` directory as the single source of truth for system understanding.

## Diagram Management Conventions

**Location:** `ai/diagrams/`

**Organization:**
- `ai/diagrams/features/` - Feature-specific diagrams
- `ai/diagrams/architecture/` - System architecture diagrams
- `ai/diagrams/journeys/` - User journey diagrams
- `ai/diagrams/tests/` - Test coverage diagrams
- `ai/diagrams/refactoring/` - Before/After improvement diagrams

**Format:** Markdown files (`.md`) containing Mermaid code blocks

**Naming Convention:**
- Use descriptive lowercase names with hyphens
- Include diagram type prefix: `sequence-`, `flow-`, `arch-`, `feature-`
- Examples:
  - `feature-user-checkout-flow.md`
  - `sequence-authentication-journey.md`
  - `arch-system-overview.md`
  - `flow-payment-processing.md`

## Your Task

### If $ARGUMENTS is provided:
Store or update the specific diagram named in $ARGUMENTS.

### If $ARGUMENTS is empty:
Perform a full sync operation:

1. **Audit Current Diagrams**
   - Read all existing diagrams in `ai/diagrams/`
   - Identify diagrams that may be outdated based on recent code changes
   - List diagrams that should exist but don't

2. **Validate Diagram Quality**
   - Ensure all diagrams follow DDD principles
   - Check for segregated technical-only diagrams (these must be upgraded to diagrams)
   - Verify impact annotations are present
   - Confirm Front-Stage/Back-Stage separation exists

3. **Suggest Updates**
   - List diagrams that need updating
   - Propose new diagrams for recent features
   - Recommend consolidation of overlapping diagrams

4. **Execute Sync**
   - Create missing diagram files
   - Update outdated diagrams
   - Remove obsolete diagrams (with confirmation)
   - Maintain consistent formatting

## Diagram File Structure

Each diagram file should follow this structure:

```markdown
# [Diagram Title]

**Type:** [Feature Diagram | Sequence Diagram | Architecture Diagram | etc.]
**Last Updated:** [YYYY-MM-DD]
**Related Files:**
- `path/to/implementation.ts`
- `path/to/component.tsx`

## Purpose

[1-2 sentence description of what user value this diagram illustrates]

## Diagram

\`\`\`mermaid
[Mermaid diagram code following DDD principles]
\`\`\`

## Key Insights

- [User impact point 1]
- [User impact point 2]
- [Technical enabler point 1]

## Change History

- **YYYY-MM-DD:** [Description of change]
```

## Quality Checklist

Before storing any diagram, verify:

- [ ] Diagram shows both Front-Stage (user experience) AND Back-Stage (implementation)
- [ ] Impact annotations explain user value of technical components
- [ ] User actions are clearly visible as entry/exit points
- [ ] Error paths and recovery options are shown
- [ ] NO custom fill colors (except `#90EE90` for highlighting changes in Before/After)
- [ ] Related code file paths are documented
- [ ] Last updated date is current
- [ ] Key insights section explains user impact

## Index File

Maintain an index at `ai/diagrams/README.md`:

```markdown
# Unified Impact Diagrams Index

This directory contains all diagrams for the project, following Diagram Driven Development (DDD) methodology.

## Architecture Overview

- [System Architecture](architecture/arch-system-overview.md) - High-level diagram showing all major systems

## User Journeys

- [User Authentication](journeys/sequence-authentication-journey.md) - Login/signup flow with security impact
- [Checkout Process](journeys/feature-user-checkout-flow.md) - Complete purchase flow with performance annotations

## Features

- [Real-time Notifications](features/feature-notification-system.md) - WebSocket implementation with UX impact
- [Search Functionality](features/feature-search-feature.md) - Search architecture with speed optimizations

## Test Coverage

- [Payment Tests](tests/feature-payment-test-coverage.md) - Test strategy connected to user security requirements

## Refactoring Plans

- [Caching Layer Addition](refactoring/feature-add-caching-layer.md) - Before/After with load time improvements

## Last Updated

[YYYY-MM-DD] - [Brief description of recent diagram changes]
```

## Workflow Integration

This command is part of the DDD workflow:

1. **Before Code Changes:** Use `/analyze-flows` to understand current state
2. **During Planning:** Create proposal diagrams showing planned changes
3. **After Implementation:** Use `/sync-diagrams` to update diagrams
4. **During Review:** Reference diagrams to explain impact

## Critical Rules

1. **Diagrams MUST stay synchronized with code** - Outdated diagrams are worse than no diagrams
2. **Every diagram MUST follow DDD principles** - No purely technical diagrams allowed
3. **Organization is critical** - Use subdirectories to prevent chaos
4. **Index MUST be maintained** - The README.md is the entry point for understanding
5. **File naming MUST be consistent** - Predictable names enable faster navigation

## Begin Sync Operation

Start by examining the `ai/diagrams/` directory (create if it doesn't exist) and execute the appropriate sync operation based on whether $ARGUMENTS was provided.
