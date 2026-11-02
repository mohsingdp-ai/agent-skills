# toggles

A Claude Code mod: `/toggles` opens a pane beside the chat to switch plugins, MCP servers and skills on or off.

- **Tabs:** Plugins, MCP, Skills (`p` / `m` / `s`), `r` reloads plugins and the lists, `f` starts typing a filter (Enter finishes).
- **Keys in the list:** ↑↓ move, → opens a group, ← closes it (or jumps to its header), Space marks a row or a whole group (✱), Enter opens/closes a group. Groups with something on start open, the rest closed.
- **Mark, then apply:** `a` applies all marks, `u` drops them.
- **Plugins:** one row per plugin. On enables the global install, or installs it for all projects. Off disables every enabled copy. After a change, `r` reloads plugins.
- **MCP servers:** each shows its tool count or health (needs login, failed, not set up). Off adds a `mcp__<server>` deny rule to your user settings, so Claude can't use its tools; the server itself still starts.
- **Skills:** grouped by source (your skills, this project, each plugin). The group header switches the whole group. Off sets the skill to `"off"` under `skillOverrides` in your user settings, which hides it from Claude and from `/`. Skills of a switched-off plugin are listed too: picking one turns the plugin on with only the picked skills on.

Deny rules go in your user settings file, so they apply in every project. The file is never written if it can't be read as JSON.

## Install

```
claude plugin marketplace add /path/to/plugins/toggles
claude plugin install toggles@toggles
```
