export type Tab = 'plugins' | 'mcp' | 'skills'

export type Item = {
  /** Unique within its tab: one plugin installed for several projects is several items. */
  key: string
  /** What the switch acts on: plugin id, MCP server name, or skill name. */
  id: string
  name: string
  isOn: boolean
  /** Section heading the row sits under. */
  group: string
  detail: string
  /** A skill whose plugin is off: the key of that plugin, which switching the skill turns on. */
  via?: string
  /** A plugin whose hooks module changes Claude Code itself. */
  isMod?: boolean
  /** Shown in yellow: an MCP server's health. */
  warn?: string
  /** A plugin's installs: one global (user) and/or one per project. */
  copies?: { scope: string; cwd?: string; isOn: boolean }[]
}

export type Lists = { plugins: Item[]; mcp: Item[]; skills: Item[] }

/** `${tab}:${key}` → the on/off state the person marked it to become. */
export type Pending = Record<string, boolean>

/** A saved set: for each tab, item key → on. Items it never saw are left alone. */
export type Preset = { name: string; state: Record<Tab, Record<string, boolean>> }

declare module 'claude-code' {
  interface PluginState {
    toggles: {
      tab: Tab
      filter: string
      lists: Shaped<Lists>
      note: string
      pending: Pending
      folded: string[]
      presets: Shaped<Preset[]>
      naming: boolean
      reload: boolean
    }
  }
}
