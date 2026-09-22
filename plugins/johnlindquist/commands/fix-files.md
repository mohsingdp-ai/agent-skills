---
description: Spawn a haiku agent per file to fix issues in parallel
allowed-tools: Task, Bash, Read, Glob, Grep, AskUserQuestion
argument-hint: [file patterns or issue type]
---

# Parallel File Fix with Haiku Agents

Spawn a haiku agent for each file to fix issues in parallel.

## Arguments

- **input**: Either:
  - File patterns: `src/**/*.ts` or `src/api.ts src/utils.ts`
  - Issue type: `lint`, `types`, `tests`, `todo`, `eslint`, `tsc`
  - Empty: Will detect issues from common sources (TypeScript errors, ESLint, etc.)

## Workflow

### Phase 1: Identify Files with Issues

Based on $ARGUMENTS:

**If file patterns provided:**
```bash
# Glob the patterns
```

**If issue type provided:**

| Type | Command |
|------|---------|
| `lint` / `eslint` | `npx eslint . --format json 2>/dev/null \| jq -r '.[].filePath'` |
| `types` / `tsc` | `npx tsc --noEmit 2>&1 \| grep -oE '^[^(]+' \| sort -u` |
| `tests` | Find test files with failures |
| `todo` | `grep -rl "TODO\|FIXME" --include="*.ts" --include="*.tsx"` |

**If empty:** Try to auto-detect:
1. Check for TypeScript errors: `npx tsc --noEmit 2>&1`
2. Check for ESLint errors: `npx eslint . --format json`
3. Check git status for modified files

### Phase 2: Collect Issue Details Per File

For each identified file, gather specific issues:

```bash
# TypeScript errors for specific file
npx tsc --noEmit 2>&1 | grep "^FILE_PATH"

# ESLint errors for specific file
npx eslint FILE_PATH --format stylish

# Get file content for context
```

### Phase 3: Launch Haiku Agents in Parallel

For each file with issues, use Task tool:

```
Task(
  subagent_type: "general-purpose",
  model: "haiku",
  run_in_background: true,
  prompt: <see template below>
)
```

**Maximum parallel agents:** 10 (batch if more files)

### Phase 4: Collect Results

1. Use TaskOutput to wait for each agent
2. Collect success/failure status
3. Track which files were fixed

### Phase 5: Verify & Report

1. **Re-run checks** to verify fixes:
   ```bash
   npx tsc --noEmit  # if type issues
   npx eslint .      # if lint issues
   ```

2. **Report summary:**
   - Files processed
   - Files fixed successfully
   - Files still with issues
   - New issues introduced (if any)

## Haiku Agent Prompt Template

```
Fix the issues in this file.

**File**: {FILE_PATH}
**Issues**:
{ISSUE_DETAILS}

**Current file content**:
```
{FILE_CONTENT}
```

Instructions:
1. Read and understand the file
2. Fix ALL listed issues
3. Do NOT change unrelated code
4. Do NOT add new features
5. Preserve existing formatting style
6. Use Edit tool for changes (not Write)

When complete, report:
- Issues fixed (list each)
- Any issues that couldn't be fixed (and why)
```

## Error Handling

- **No issues found**: Report "No issues detected" and exit
- **Too many files** (>10): Batch into groups, process sequentially
- **Agent fails**: Log failure, continue with other files
- **File not found**: Skip with warning

## Examples

### Fix TypeScript Errors
```
/fix-files tsc
```

### Fix ESLint Issues
```
/fix-files eslint
```

### Fix Specific Files
```
/fix-files src/api.ts src/utils.ts src/types.ts
```

### Fix by Pattern
```
/fix-files src/components/**/*.tsx
```

### Fix TODOs
```
/fix-files todo
```

### Auto-detect Issues
```
/fix-files
```

## Begin

Parse $ARGUMENTS to determine files and issue type. Identify all files with issues. Launch a haiku agent per file (max 10 parallel). Wait for completion and verify fixes.
