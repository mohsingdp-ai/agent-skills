---
description: Implement each task in a separate git worktree with an opus subagent then sequentially merge and commit them back into main
allowed-tools: Task, Bash, Read, Glob, Grep, AskUserQuestion
argument-hint: [task1] [task2] [task3] ...
---

# Parallel Worktree Task Implementation

Implement multiple tasks in parallel using git worktrees and opus subagents, then merge them sequentially into main.

## Arguments

- **tasks**: A list of tasks to implement, separated by `|` or provided as numbered items
  - Example: `add login button | fix header styling | update API endpoint`
  - Example: `1. add tests 2. refactor auth 3. add logging`

## Workflow

### Phase 1: Setup & Validation

1. **Parse the tasks** from $ARGUMENTS
   - Split by `|` or numbered list format
   - Trim whitespace from each task
   - If no tasks provided, ask user with AskUserQuestion

2. **Validate git state**
   ```bash
   git status --porcelain
   git branch --show-current
   ```
   - Ensure working directory is clean (warn if not)
   - Note the current branch (should be main/master)

3. **Get repo info**
   ```bash
   basename $(git rev-parse --show-toplevel)
   git rev-parse --show-toplevel
   ```

### Phase 2: Create Worktrees & Launch Agents

For each task, create a worktree and launch an opus subagent:

1. **Create branch name** from task (kebab-case, prefix with `task/`)
   - Example: "add login button" → `task/add-login-button`

2. **Create worktree**
   ```bash
   git worktree add -b task/BRANCH_NAME ../REPO-BRANCH_NAME main
   ```

3. **Launch opus subagent** using the Task tool with `model: "opus"`:
   - Set `run_in_background: true` to run in parallel
   - Provide the worktree path and task description
   - Include instructions to:
     - Work in the worktree directory
     - Implement the task fully
     - Run any relevant tests
     - Commit changes with a descriptive message
     - Report completion status

### Phase 3: Monitor & Collect Results

1. **Wait for all agents** using TaskOutput with `block: true`
2. **Collect results** from each agent
3. **Report any failures** before proceeding

### Phase 4: Sequential Merge

For each completed task (in order):

1. **Return to main repo**
   ```bash
   cd ORIGINAL_REPO_PATH
   git checkout main
   ```

2. **Merge the branch**
   ```bash
   git merge --no-ff task/BRANCH_NAME -m "feat: TASK_DESCRIPTION"
   ```

3. **Handle merge conflicts** if any:
   - Report conflict to user
   - Ask how to proceed (resolve manually, skip, abort)

4. **Remove worktree**
   ```bash
   git worktree remove ../REPO-BRANCH_NAME
   git branch -d task/BRANCH_NAME
   ```

### Phase 5: Cleanup & Report

1. **Prune stale worktrees**
   ```bash
   git worktree prune
   ```

2. **Show final git log**
   ```bash
   git log --oneline -n NUMBER_OF_TASKS
   ```

3. **Report summary**:
   - Tasks completed successfully
   - Tasks that failed (if any)
   - Final commit hashes

## Subagent Prompt Template

When launching each opus subagent, use this prompt structure:

```
You are implementing a specific task in a git worktree.

**Task**: {TASK_DESCRIPTION}
**Working Directory**: {WORKTREE_PATH}

Instructions:
1. Change to the worktree directory: cd {WORKTREE_PATH}
2. Understand the codebase context relevant to this task
3. Implement the task completely
4. Run relevant tests if they exist
5. Commit your changes with message: "feat: {TASK_DESCRIPTION}"
6. Report what you implemented and any issues encountered

Do NOT:
- Push to remote
- Merge branches
- Modify files outside the worktree

When complete, summarize:
- Files changed
- Tests run (pass/fail)
- Commit hash
```

## Error Handling

- **Dirty working directory**: Warn user, ask to continue or abort
- **Branch already exists**: Add numeric suffix (task/name-2)
- **Merge conflict**: Pause, report details, ask user for resolution
- **Agent failure**: Report error, continue with remaining tasks, note failure in summary

## Example Usage

```
/worktree-tasks add user avatar upload | fix password validation | update email templates
```

This will:
1. Create 3 worktrees: `task/add-user-avatar-upload`, `task/fix-password-validation`, `task/update-email-templates`
2. Launch 3 opus agents in parallel
3. Merge each back to main sequentially
4. Clean up worktrees

## Begin

Parse $ARGUMENTS to extract tasks. Validate the git state. Then create worktrees and launch opus subagents in parallel. Wait for completion, then merge sequentially back to main.
