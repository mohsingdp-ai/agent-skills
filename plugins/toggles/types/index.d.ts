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


/** One line of the list widget, ready to draw. */
export type Line = {
  key: string
  kind: 'gap' | 'head' | 'row'
  /** Heads: whether the group shows its rows. */
  open?: boolean
  glyph: string
  color?: string
  dim?: boolean
  name: string
  detail: string
  warn?: string
  isMod?: boolean
  isMarked?: boolean
}

/** What the hooks module hands the list widget. */
export type ListProps = {
  lines: Line[]
  /** Shown when there are no lines. */
  empty: string
  height: number
  width: number
  /** Changes when the tab or filter changes: the widget goes back to the top. */
  view: string
  wheel: number
  /** The filter text, and whether keys now type into it (after f, until Enter). */
  filter: string
  typing: boolean
}

export type ListState = { cursor: string; off: number; view: string; wheel: number }

/** What the list widget posts to the hooks module. */
export type ListMessage =
  | { t: 'mark'; key: string }
  | { t: 'fold'; key: string; open: boolean }
  | { t: 'key'; key: string }
  | { t: 'filter'; value: string }
  | { t: 'typing'; on: boolean }

declare module 'claude-code' {
  interface PluginState {
    toggles: {
      tab: Tab
      filter: string
      lists: Shaped<Lists>
      note: string
      pending: Pending
      /** tab → the one open group ('' none); absent, the first group with something on. */
      open: Record<string, string>
      reload: boolean
      /** Sum of wheel ticks over the pane; the list widget scrolls by the change. */
      wheel: number
      typing: boolean
    }
  }
}
