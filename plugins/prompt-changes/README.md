# prompt-changes

A Claude Code mod that shows what each prompt changed in your git repo, and lets you discard it.

- Before each prompt it takes a hidden git snapshot of the folder (new files included, ignored files never).
- The band above the prompt box shows the latest prompt whose changes are still in place.
- `/changes` opens a pane listing every prompt with its files and `+/-` counts.
- **Discard** puts the files back to before that prompt (and every later one), including changes made by
  shell commands, then opens `/rewind` so you can rewind the chat too ("Restore conversation only").
- **Undo discard** brings the files back, until the next prompt starts.
- `/rewind-discard <n>` does the same as Discard on prompt `n`.

Snapshots live under `refs/prompt-changes/` in the repo (visible in `git log --all`, not in branches) and are
removed after 7 days. New files over 10 MB are left out and never touched. Nothing is sent to the model.

## Install

```
claude plugin marketplace add /path/to/plugins/prompt-changes
claude plugin install prompt-changes@prompt-changes
```

## Check

```
sh bin/snap.test.sh        # the git snapshot/restore work, on a throwaway repo
claude plugin test .       # the hooks: prompt -> band -> Discard -> restore + /rewind
```
