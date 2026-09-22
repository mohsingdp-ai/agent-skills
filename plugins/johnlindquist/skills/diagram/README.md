# Diagrams Skill (Diagram Driven Development)

A comprehensive skill for maintaining Unified Impact Diagrams that connect user value to technical implementation following Diagram Driven Development (DDD) methodology.

## Overview

This skill helps you maintain the `ai/diagrams` directory as the single source of truth for system understanding. Unlike traditional technical diagrams, DDD diagrams always show:
- **Front-Stage**: What users see and experience
- **Back-Stage**: How we deliver that experience
- **Impact Annotations**: Why each technical component matters to users
- **Error Paths**: What happens when things go wrong
- **User Value**: Clear connection from code to user benefit

## Philosophy

**Traditional diagrams answer "What does the code do?"**
**DDD diagrams answer "Why does it matter to users?"**

Every technical decision should trace back to user value, and diagrams make that connection explicit.

## Skill Structure

```
diagrams/
├── SKILL.md                      # Main skill definition
├── README.md                     # This file
└── references/
    ├── DDD_PRINCIPLES.md         # Core methodology (READ FIRST)
    ├── CREATE.md                 # Creating new diagrams
    ├── UPDATE.md                 # Updating existing diagrams
    ├── AUDIT.md                  # Auditing quality and coverage
    ├── ORGANIZE.md               # Directory structure and naming
    └── MERMAID_GUIDE.md          # Mermaid syntax patterns
```

## Core Capabilities

### 1. Create Diagrams
Generate new diagrams for features, architectures, user journeys, test coverage, and refactoring plans.

**Supported Types:**
- Feature diagrams (feature-*.md)
- Sequence diagrams (sequence-*.md)
- Architecture diagrams (arch-*.md)
- Flow diagrams (flow-*.md)
- Test coverage diagrams (test-*.md)
- Refactoring Before/After (in refactoring/)

### 2. Update Diagrams
Keep diagrams synchronized with code changes, ensuring they remain accurate and useful.

### 3. Audit Diagrams
- **Quality Audit**: Check if diagrams follow DDD principles
- **Coverage Audit**: Identify features without diagrams
- **Synchronization Audit**: Find outdated diagrams
- **Organization Audit**: Ensure proper structure and naming

### 4. Organize Diagrams
Maintain clean directory structure with consistent naming conventions.

### 5. Index Management
Keep README.md updated as the entry point for understanding the system.

## Directory Structure

```
ai/diagrams/
├── README.md                    # Index (always up-to-date)
├── features/                    # Feature-specific flows
│   └── feature-*.md
├── architecture/                # System-level diagrams
│   └── arch-*.md
├── journeys/                    # User journey sequences
│   └── sequence-*.md
├── tests/                       # Test coverage
│   └── test-*.md
└── refactoring/                 # Before/After improvements
    └── feature-*.md
```

## Quick Start

### Creating Your First Diagram

1. **Understand the user need**
   - What problem does this solve?
   - What value does it deliver?

2. **Choose diagram type**
   - Feature flow → `features/feature-{name}.md`
   - User journey → `journeys/sequence-{name}.md`
   - System architecture → `architecture/arch-{name}.md`

3. **Read DDD_PRINCIPLES.md** (REQUIRED)
   ```
   references/DDD_PRINCIPLES.md
   ```

4. **Read CREATE.md for patterns**
   ```
   references/CREATE.md
   ```

5. **Create using template**
   - Both Front-Stage and Back-Stage
   - Impact annotations on all Back-Stage components
   - Error paths with recovery options
   - User as entry/exit point

6. **Update README.md index**

## Usage Examples

### Example 1: New Feature Diagram

**User Request**: "Create a diagram for the new payment processing feature"

**Agent Workflow**:
1. Reads `references/DDD_PRINCIPLES.md` and `references/CREATE.md`
2. Analyzes payment feature code
3. Creates `features/feature-checkout-payment-flow.md`:
   - Shows user clicking "Pay Now" (Front-Stage)
   - Shows payment gateway, validation, order creation (Back-Stage)
   - Adds impact annotations (🛡️ Secure, 💾 Guarantees save, ⚡ Fast)
   - Shows error paths (payment fails → retry options)
4. Updates `ai/diagrams/README.md` index

### Example 2: Update After Code Change

**User Request**: "We added caching to the search feature, update the diagram"

**Agent Workflow**:
1. Reads `references/UPDATE.md`
2. Finds `features/feature-search-functionality.md`
3. Adds cache layer to diagram with impact annotation (⚡ 80% faster)
4. Updates "Last Updated" date
5. Adds change history entry

### Example 3: Audit Diagrams

**User Request**: "Audit our diagrams for quality and coverage"

**Agent Workflow**:
1. Reads `references/AUDIT.md` and `references/DDD_PRINCIPLES.md`
2. Scans all diagrams in `ai/diagrams/`
3. Checks each against DDD quality checklist
4. Identifies features without diagrams
5. Compares diagram dates with git history
6. Creates comprehensive audit report with recommendations

### Example 4: Before/After Refactoring

**User Request**: "We're adding a caching layer to improve performance. Document the change."

**Agent Workflow**:
1. Reads `references/CREATE.md` (refactoring section)
2. Creates `refactoring/feature-add-caching-layer.md`
3. Shows "Before" diagram (current slow flow)
4. Shows "After" diagram (with cache, highlighted in #90EE90)
5. Annotates performance improvements (2s → 50ms)
6. Explains user benefit (instant search results)

## DDD Core Principles (Brief)

Every diagram MUST include:

✅ **Both Stages**
- Front-Stage (user experience)
- Back-Stage (technical implementation)

✅ **Impact Annotations**
- ⚡ Speed/Performance
- 💾 Storage/Persistence
- 🛡️ Security/Safety
- ✅ Validation/Success
- ⏱️ Responsiveness
- 🔄 Recovery/Retry
- 📊 Data Accuracy
- 🎯 Feature Enablement

✅ **User-Centric**
- User as entry/exit point
- User actions are visible
- User outcomes are clear

✅ **Error Handling**
- Error paths shown
- Recovery options included
- Fallback behavior documented

❌ **Prohibited**
- Purely technical diagrams without user context
- Missing impact annotations
- Only happy path (no errors)
- Custom colors (except #90EE90 for changes)

For complete principles, read `references/DDD_PRINCIPLES.md`.

## Reference Files

### DDD_PRINCIPLES.md (START HERE)
**Purpose**: Core methodology and philosophy
**Read when**: Before creating any diagram
**Contains**: Front-Stage/Back-Stage, impact annotations, error paths, quality checklist

### CREATE.md
**Purpose**: Creating new diagrams
**Read when**: Making a new diagram
**Contains**: Templates, patterns, examples, validation checklist

### UPDATE.md
**Purpose**: Updating existing diagrams
**Read when**: Code changes affect diagrams
**Contains**: Update patterns, synchronization strategies, metadata updates

### AUDIT.md
**Purpose**: Auditing diagram quality
**Read when**: Need to assess diagram health
**Contains**: Quality checks, coverage analysis, synchronization audits, reports

### ORGANIZE.md
**Purpose**: Directory structure and naming
**Read when**: Organizing or reorganizing diagrams
**Contains**: Naming conventions, directory rules, index structure, migration

### MERMAID_GUIDE.md
**Purpose**: Mermaid syntax reference
**Read when**: Need help with Mermaid syntax
**Contains**: Flowchart patterns, sequence diagrams, styling, common mistakes

## Workflow Integration

### Development Workflow

```
1. Planning Phase
   ├─ Review existing diagrams
   └─ Create proposal diagrams for new features

2. Implementation Phase
   ├─ Reference diagrams during coding
   └─ Ensure code matches diagram intent

3. Completion Phase
   ├─ Update diagrams to reflect implementation
   └─ Add change history entries

4. Review Phase
   ├─ Use diagrams to explain changes
   └─ Verify diagrams match code
```

### Collaboration Workflow

```
1. Onboarding
   └─ New developers read diagrams to understand system

2. Architecture Reviews
   └─ Use diagrams to discuss system design

3. Code Reviews
   └─ Reference diagrams to explain impact

4. Documentation
   └─ Diagrams serve as living documentation
```

## Quality Standards

### Minimum Requirements

Every diagram must have:
- [ ] Proper file structure (Type, Last Updated, Related Files, Purpose, Diagram, Key Insights, Change History)
- [ ] Front-Stage showing user experience
- [ ] Back-Stage showing implementation
- [ ] Impact annotations on Back-Stage components
- [ ] At least one error path with recovery
- [ ] Valid Mermaid syntax
- [ ] Entry in README.md index

### Excellent Diagram Characteristics

- Clear user journey from start to finish
- Every technical component has meaningful impact annotation
- Multiple error paths with recovery options shown
- Performance metrics quantified where possible
- Related code files documented
- Change history tracks evolution
- Key insights explain user value clearly

## Common Workflows

### Workflow 1: New Project Setup

```bash
# 1. Create directory structure
mkdir -p ai/diagrams/{features,architecture,journeys,tests,refactoring}

# 2. Create README.md index
# (Use ORGANIZE.md template)

# 3. Create system architecture diagram
# (Use CREATE.md patterns)

# 4. Document key user journeys
# (Use sequence diagram patterns)
```

### Workflow 2: Feature Addition

```
1. Create feature diagram before coding
2. Use diagram to guide implementation
3. Update diagram if implementation differs
4. Add to README.md index
5. Reference in pull request
```

### Workflow 3: Refactoring

```
1. Create Before diagram (current state)
2. Create After diagram (proposed state)
3. Highlight changes in #90EE90
4. Document user impact of changes
5. Use in architecture review
6. Update after implementation
```

### Workflow 4: Monthly Audit

```
1. Run quality audit (check DDD compliance)
2. Run coverage audit (find missing diagrams)
3. Run sync audit (find outdated diagrams)
4. Create prioritized fix list
5. Schedule updates for high-priority items
```

## Best Practices

1. **Keep synchronized** - Update diagrams immediately after code changes
2. **User-first thinking** - Always start with user need
3. **Show errors** - Don't just show happy paths
4. **Quantify impact** - Use metrics in annotations (2s → 50ms)
5. **Maintain index** - README.md is the entry point
6. **Validate quality** - Run through DDD checklist before saving
7. **Document changes** - Change history helps future understanding
8. **Load references** - Always read relevant reference files first
9. **Test Mermaid** - Validate syntax before committing
10. **Regular audits** - Monthly audits keep diagrams healthy

## Integration with Other Skills

### With chrome-devtools
Use diagrams to plan testing flows:
- Create sequence diagram of user journey
- Use chrome-devtools to test each step
- Verify error paths actually work
- Update diagram with actual timings

### With github
Link diagrams in issues and PRs:
- Reference diagrams to explain features
- Include diagram links in issue descriptions
- Use in PR descriptions to show impact
- Create issues from diagram audit findings

### With review
Reference diagrams during code reviews:
- Show how code connects to user value
- Explain architectural decisions
- Discuss error handling strategies
- Validate implementation matches design

## Troubleshooting

### "I don't know what user value this provides"

**Solution**: Ask these questions:
- What problem does this solve?
- What happens if we don't have this?
- How does this improve the user experience?
- What metrics improve (speed, reliability, security)?

If you can't answer these, reconsider if the feature is necessary.

### "The diagram is too complex"

**Solutions**:
- Split into multiple diagrams (overview + details)
- Use subgraphs to organize complexity
- Create separate sequence diagrams for detailed flows
- Focus on one aspect per diagram

### "Code changed but I don't know which diagrams"

**Solution**:
```bash
# Find diagrams referencing changed files
grep -r "path/to/changed/file" ai/diagrams/

# Check diagram dates vs git history
git log --since="diagram-date" path/to/file
```

### "Mermaid won't render"

**Solutions**:
- Copy code to [Mermaid Live Editor](https://mermaid.live)
- Check for common syntax errors (see MERMAID_GUIDE.md)
- Validate bracket matching
- Check arrow syntax
- Ensure graph direction is specified

## Metrics to Track

Monitor diagram health over time:
- Total number of diagrams
- Percentage meeting DDD standards
- Feature coverage percentage
- Average diagram age
- Time from code change to diagram update
- Number of broken links
- Audit findings trend

## Resources

- **DDD Command**: `/sync-diagrams` - Original command this skill is based on
- **Mermaid Live**: https://mermaid.live - Test diagrams
- **Mermaid Docs**: https://mermaid.js.org - Full documentation
- **Review Skill**: Use for reviewing diagram quality

## Version

Skill created based on `/sync-diagrams` command (January 2025)

## Summary

This skill helps maintain high-quality, user-centric diagrams that bridge the gap between technical implementation and user value. By following DDD principles, your diagrams become powerful tools for:
- Understanding system behavior
- Communicating with stakeholders
- Onboarding new team members
- Making architectural decisions
- Connecting code changes to user impact

**Remember**: Outdated diagrams are worse than no diagrams. Keep them synchronized, keep them user-focused, and keep them valuable.
