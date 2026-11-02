import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { Item, Line, ListMessage, Lists, Pending, Tab } from '../types'

const PANE = 'toggles'
const tab = atom({ plugin: 'toggles', key: 'tab' } as const, 'plugins' as Tab)
const filter = atom({ plugin: 'toggles', key: 'filter' } as const, '')
const note = atom({ plugin: 'toggles', key: 'note' } as const, '')
const pending = atom({ plugin: 'toggles', key: 'pending' } as const, {} as Pending)
const opened = atom({ plugin: 'toggles', key: 'open' } as const, {} as Record<string, string>)
const reload = atom({ plugin: 'toggles', key: 'reload' } as const, false)
const wheel = atom({ plugin: 'toggles', key: 'wheel' } as const, 0)
const typing = atom({ plugin: 'toggles', key: 'typing' } as const, false)
const lists = atom({ plugin: 'toggles', key: 'lists' } as const, { plugins: [], mcp: [], skills: [] } as Lists, {
  shape: 'lists-4',
})

type $ = EngineInterface
const TABS: Tab[] = ['plugins', 'mcp', 'skills']

// ---- settings: MCP servers and skills are switched off by deny rules ----

async function configDir($: $) {
  return (await $.env.get('CLAUDE_CONFIG_DIR')) ?? `${await $.env.get('HOME')}/.claude`
}

async function readSettings($: $): Promise<Record<string, any>> {
  const path = `${await configDir($)}/settings.json`
  if (!(await $.fs.exists(path))) return {}
  return JSON.parse(await $.fs.read(path)) // throws on bad JSON: never overwrite a file we can't parse
}

async function denyRules($: $): Promise<Set<string>> {
  const s = await readSettings($).catch(() => ({}) as Record<string, any>)
  return new Set<string>(s.permissions?.deny ?? [])
}

/**
 * One read and one write for every change: MCP deny rules [rule, isDenied]
 * and skill overrides [skill name, isOff] (Claude's own per-skill switch).
 */
async function writeSettings(
  $: $,
  rules: [string, boolean][],
  offs: [string, boolean][],
  flags: [string, boolean][] = [],
) {
  const s = await readSettings($)
  if (flags.length > 0) {
    const ep: Record<string, boolean> = (s.enabledPlugins ??= {})
    for (const [id, on] of flags) ep[id] = on
  }
  if (rules.length > 0) {
    const deny: string[] = ((s.permissions ??= {}).deny ??= [])
    for (const [rule, isDenied] of rules) {
      const at = deny.indexOf(rule)
      if (isDenied && at < 0) deny.push(rule)
      if (!isDenied && at >= 0) deny.splice(at, 1)
    }
  }
  if (offs.length > 0) {
    const o: Record<string, string> = (s.skillOverrides ??= {})
    for (const [name, isOff] of offs) {
      if (isOff) o[name] = 'off'
      else delete o[name]
    }
  }
  await $.fs.write(`${await configDir($)}/settings.json`, JSON.stringify(s, null, 2) + '\n')
}

// ---- loading ----

async function dirs($: $, path: string): Promise<string[]> {
  const all = await $.fs.list(path).catch(() => [])
  const found: string[] = []
  for (const f of all) {
    if ((f.kind === 'dir' || f.isLink) && (await $.fs.exists(`${path}/${f.name}/SKILL.md`))) found.push(f.name)
  }
  return found
}

const byName = (a: Item, b: Item) => a.name.localeCompare(b.name)
// Tool names spell a server name with every other character as "_".
const toolSpelling = (s: string) => s.replace(/[^A-Za-z0-9_-]/g, '_')

/** A plugin's skill names: its manifest's `skills` paths, else every skills/<name>/SKILL.md. */
async function pluginSkills($: $, root: string): Promise<string[]> {
  const manifest = await $.fs.read(`${root}/.claude-plugin/plugin.json`).then(JSON.parse).catch(() => ({}))
  if (!Array.isArray(manifest.skills)) return dirs($, `${root}/skills`)
  const found: string[] = []
  for (const path of manifest.skills as string[]) {
    const dir = `${root}/${String(path).replace(/^\.\//, '').replace(/\/$/, '')}`
    if (await $.fs.exists(`${dir}/SKILL.md`)) found.push(dir.split('/').at(-1) ?? dir)
  }
  return found
}

async function loadPlugins($: $) {
  const ran = await $.process.run(['claude', 'plugin', 'list', '--json'], { timeoutMs: 60_000 })
  const raw: any[] = ran.exitCode === 0 ? JSON.parse(ran.stdout.slice(ran.stdout.indexOf('['))) : []
  // One row per plugin: its per-project installs fold into it.
  const byId = new Map<string, any[]>()
  for (const p of raw) byId.set(p.id, [...(byId.get(p.id) ?? []), p])
  const plugins: Item[] = []
  const skillDirs: [string, string[], string?][] = [] // [plugin name, skill names, plugin key when it is off]
  for (const [id, all] of byId) {
    const name = id.split('@')[0] ?? id
    const root = all.map(p => p.readFromFolder ?? p.installPath).find(Boolean)
    const isOn = all.some(p => p.enabled)
    const hooks = root ? await $.fs.read(`${root}/hooks/hooks.json`).catch(() => '') : ''
    const isGlobal = all.some(p => !p.projectPath)
    const names = root ? await pluginSkills($, root) : []
    const n = names.length
    const projects = all.filter(p => p.projectPath).length
    const where = isGlobal ? 'global' : `${projects} project${projects === 1 ? '' : 's'}`
    plugins.push({
      key: id,
      id,
      name,
      isOn,
      group: isOn ? 'On' : 'Off',
      detail: `${n} skill${n === 1 ? '' : 's'} · ${where}`,
      isMod: hooks.includes('"modules"'),
      copies: all.map(p => ({ scope: p.scope, cwd: p.projectPath, isOn: !!p.enabled })),
    })
    skillDirs.push(isOn ? [name, names] : [name, names, id])
  }
  return { plugins: plugins.sort(byName), skillDirs }
}

type Step = { argv: string[]; cwd?: string } | { flag: boolean }

// The plugin CLI only knows these scopes. Synced, skills-folder and other
// plugins are switched by their enabledPlugins entry in the user settings.
const CLI_SCOPES = ['user', 'project', 'local']
const isCliManaged = (id: string, scope: string) =>
  CLI_SCOPES.includes(scope) && !/@(synced|skills-dir|builtin|inline)$/.test(id)

/** On: enable the global install, or install it globally. Off: disable each enabled copy. */
function pluginSteps(i: Item, to: boolean): Step[] {
  const copies = i.copies ?? []
  const step = (verb: string, scope: string, cwd?: string): Step =>
    isCliManaged(i.id, scope) ? { argv: ['claude', 'plugin', verb, i.id, '--scope', scope], cwd } : { flag: to }
  if (!to) return copies.filter(c => c.isOn).map(c => step('disable', c.scope, c.cwd))
  const global = copies.find(c => c.cwd === undefined)
  return [global ? step('enable', global.scope) : { argv: ['claude', 'plugin', 'install', i.id, '--scope', 'user'] }]
}

async function loadSkills($: $, cwd: string, offs: Record<string, unknown>, skillDirs: [string, string[], string?][]) {
  const items: Item[] = []
  const add = (id: string, group: string) =>
    items.push({ key: id, id, name: id, isOn: offs[id] !== 'off', group, detail: '' })
  for (const n of await dirs($, `${await configDir($)}/skills`)) add(n, 'Your skills')
  for (const n of await dirs($, `${cwd}/.claude/skills`)) add(n, 'This project')
  for (const [plugin, names, via] of skillDirs) {
    for (const n of names) {
      const id = `${plugin}:${n}`
      if (via === undefined) add(id, plugin)
      else items.push({ key: id, id, name: id, isOn: false, group: plugin, detail: '', via })
    }
  }
  for (const [name, v] of Object.entries(offs)) {
    if (v === 'off' && !items.some(i => i.id === name)) add(name, 'Other')
  }
  return items.sort(byName)
}

/** health: tool spelling → { pretty name, status text } from `claude mcp list`. */
function loadMcp(tools: string[], deny: Set<string>, health: Map<string, [string, string]>) {
  const count = new Map<string, number>()
  for (const t of tools) {
    const m = /^mcp__(.+?)__/.exec(t)
    if (m?.[1]) count.set(m[1], (count.get(m[1]) ?? 0) + 1)
  }
  const names = new Set([...count.keys(), ...health.keys()])
  for (const r of deny) if (r.startsWith('mcp__') && !r.slice(5).includes('__')) names.add(r.slice(5))
  return [...names]
    .map(id => {
      const isOn = !deny.has(`mcp__${id}`)
      const [pretty, status = ''] = health.get(id) ?? [id]
      const n = count.get(id) ?? 0
      const warn = !isOn
        ? undefined
        : /auth/i.test(status)
          ? 'needs login'
          : /fail/i.test(status)
            ? 'failed'
            : /not configured/i.test(status)
              ? 'not set up'
              : undefined
      const detail = !isOn ? 'blocked' : n > 0 ? `${n} tools` : warn ? '' : status ? 'connected' : '…'
      return { key: id, id, name: pretty, isOn, group: isOn ? 'On' : 'Off', detail, warn } as Item
    })
    .sort(byName)
}

async function mcpHealth($: $): Promise<Map<string, [string, string]>> {
  const out = new Map<string, [string, string]>()
  const r = await $.process.run(['claude', 'mcp', 'list'], { timeoutMs: 90_000 }).catch(() => undefined)
  for (const line of r?.stdout.split('\n') ?? []) {
    const m = /^(.+?): .* - . (.+)$/.exec(line.trim())
    if (m?.[1] && m[2]) out.set(toolSpelling(m[1]), [m[1], m[2]])
  }
  return out
}

let loading = 0
async function refresh($: $) {
  const run = ++loading
  await update($, note, () => 'loading…')
  try {
    const cwd = await $.session.cwd()
    const deny = await denyRules($)
    const tools = (await $.tool.list()).map(t => t.name)
    const { plugins, skillDirs } = await loadPlugins($)
    const offs = ((await $.settings.read({ key: 'skillOverrides' })) ?? {}) as Record<string, unknown>
    const skills = await loadSkills($, cwd, offs, skillDirs)
    await update($, lists, () => ({ plugins, skills, mcp: loadMcp(tools, deny, new Map()) }))
    await update($, note, () => 'checking MCP servers…')
    // Slow: it dials every server. Fills in names and health when done.
    const health = await mcpHealth($)
    if (run !== loading) return
    await update($, lists, l => ({ ...l, mcp: loadMcp(tools, deny, health) }))
    await update($, note, n => (n === 'checking MCP servers…' ? '' : n))
  } catch (err) {
    await update($, note, () => `load failed: ${String(err)}`)
  }
}

// ---- marking and applying ----

const markKey = (t: Tab, i: Item) => `${t}:${i.key}`

async function mark($: $, t: Tab, i: Item) {
  await update($, pending, p => {
    const k = markKey(t, i)
    const next = { ...p }
    if (k in next) delete next[k]
    else next[k] = !i.isOn
    return next
  })
}

/** Marks every item to `to`; an item already there loses its mark. */
async function markAll($: $, t: Tab, items: Item[], to: boolean) {
  await update($, pending, p => {
    const next = { ...p }
    for (const i of items) {
      if (i.isOn === to) delete next[markKey(t, i)]
      else next[markKey(t, i)] = to
    }
    return next
  })
}

async function apply($: $) {
  const marks = await read($, pending)
  const all = await read($, lists)
  const rules: [string, boolean][] = []
  const offs: [string, boolean][] = []
  const flags: [string, boolean][] = [] // [plugin id, enabled] for enabledPlugins
  const only = new Map<string, string[]>() // off plugin's key -> the skills picked in it
  const failed: string[] = []
  let pluginsChanged = false

  const switchPlugin = async (i: Item, to: boolean) => {
    for (const st of pluginSteps(i, to)) {
      if ('flag' in st) {
        flags.push([i.id, st.flag])
        pluginsChanged = true
        continue
      }
      const r = await $.process.run(st.argv, { cwd: st.cwd, timeoutMs: 120_000 }).catch(e => ({
        exitCode: 1,
        stderr: String(e),
        stdout: '',
      }))
      if (r.exitCode !== 0) {
        failed.push(`${i.name}: ${(r.stderr || r.stdout).trim().split('\n').at(-1)}`)
        return false
      }
      pluginsChanged = true
    }
    return true
  }

  for (const t of TABS) {
    for (const i of all[t]) {
      const to = marks[markKey(t, i)]
      if (to === undefined) continue
      if (t === 'skills' && i.via) {
        if (to) only.set(i.via, [...(only.get(i.via) ?? []), i.id])
        continue
      }
      if (to === i.isOn) continue
      if (t === 'mcp') rules.push([`mcp__${i.id}`, !to])
      else if (t === 'skills') offs.push([i.id, !to])
      else await switchPlugin(i, to)
    }
  }

  // A skill picked inside an off plugin: turn the plugin on with only the picked skills on.
  for (const [via, picked] of only) {
    const plugin = all.plugins.find(p => p.key === via)
    if (!plugin) continue
    if (marks[`plugins:${via}`] !== true && !(await switchPlugin(plugin, true))) continue
    for (const sk of all.skills.filter(x => x.via === via)) offs.push([sk.id, !picked.includes(sk.id)])
  }

  try {
    if (rules.length > 0 || offs.length > 0 || flags.length > 0) await writeSettings($, rules, offs, flags)
  } catch (err) {
    failed.push(`settings not saved: ${String(err)}`)
  }
  await update($, pending, () => ({}))
  if (pluginsChanged) await update($, reload, () => true)
  if (failed.length > 0) $.ui.toast(`toggles: ${failed.join('; ')}`)
  await refresh($)
}

// ---- the list ----

type Row =
  | { gap: true }
  | { head: string; items: Item[] }
  | Item

/** The rows of a tab: groups in a fixed order, each open group followed by its items. */
async function rowsOf($: $): Promise<{ cur: Tab; rows: Row[]; items: Item[] }> {
  const cur = await read($, tab)
  const q = (await read($, filter)).toLowerCase()
  const all = await read($, lists)
  const marks = await read($, pending)
  const open = await read($, opened)
  const items = all[cur].filter(i => q === '' || i.name.toLowerCase().includes(q))
  const order = ['On', 'Off', 'Your skills', 'This project']
  const offPlugin = (g: string) => items.some(i => i.group === g && i.via)
  // Groups with something on first, then groups with everything off, then off plugins.
  const noneOn = (g: string) => !items.some(i => i.group === g && (marks[markKey(cur, i)] ?? i.isOn))
  const rank = (g: string) => (order.indexOf(g) + 1 || 99) + (offPlugin(g) ? 200 : noneOn(g) ? 100 : 0)
  const groups = [...new Set(items.map(i => i.group))].sort((a, b) => rank(a) - rank(b) || a.localeCompare(b))
  // One group open at a time; at first, the first group with something on.
  const openGroup = open[cur] ?? groups.find(g => !noneOn(g)) ?? ''
  const rows: Row[] = []
  for (const g of groups) {
    const inG = items.filter(i => i.group === g)
    rows.push({ head: g, items: inG })
    if (q !== '' || g === openGroup) rows.push(...inG)
  }
  return { cur, rows, items }
}

const lineKey = (cur: Tab, r: Row) =>
  'gap' in r ? '' : 'head' in r ? `head:${cur}:${r.head}` : `row:${cur}:${r.key}`

/** r: reload plugins in Claude Code, then re-read the lists. */
async function reloadAll($: $) {
  await $.command.run({ command: 'reload-plugins' })
  await update($, reload, () => false)
  await refresh($)
}

async function onKeyFromList($: $, key: string) {
  const goTo = async (t: Tab) => {
    await update($, tab, () => t)
  }
  if (key === 'p') return goTo('plugins')
  if (key === 'm') return goTo('mcp')
  if (key === 's') return goTo('skills')
  if (key === 'r') return reloadAll($)
  if (key === 'a') return Object.keys(await read($, pending)).length > 0 ? apply($) : undefined
  if (key === 'u') return update($, pending, () => ({}))
  if (key === 'f') return update($, typing, () => true)
}

/** The keys shown as buttons under the list: [key, what it does]. */
const KEYS: [string, string][] = [
  ['↑↓', 'move'],
  ['←→', 'open/close'],
  ['space', 'switch'],
  ['a', 'apply'],
  ['u', 'undo'],
  ['r', 'reload'],
  ['f', 'filter'],
]

/** What a key button does when clicked: the same as its key in the list. */
const keyAction = ($: $, k: string) =>
  k === 'a' || k === 'u' || k === 'r' || k === 'f' ? onKeyFromList($, k) : undefined

// ---- hooks ----

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: 'toggles',
      description: 'Switch plugins, MCP servers and skills on or off',
    })
    return next(e)
  })

  on('command.run', { command: 'toggles' }, async $ => {
    // Each open starts on the Plugins tab with no filter.
    await update($, tab, () => 'plugins')
    await update($, filter, () => '')
    await update($, typing, () => false)
    // rows: as tall as the layout allows when seated inline above the prompt.
    await $.ui.open({ id: PANE, title: 'Toggles', focus: true, rows: 500 })
    void refresh($)
    return { text: 'Toggles pane opened.' }
  })

  // The list scrolls inside its own widget, so the tabs, filter and footer stay put.
  on('ui.scroll', { component: 'Pane', requestId: PANE }, async ($, e) => {
    await update($, wheel, w => w + e.by)
    return {}
  })

  // The keyboard stays in the list: Tab and arrows never move it to the tabs or
  // key buttons. The engine's own close mark is left alone.
  on('ui.focus', { component: 'Pane', requestId: PANE }, async ($, e, next) =>
    e.element === undefined || e.origin.kind !== 'person' ? next(e) : { deny: 'focus stays in the list' },
  ).catch(($, e, next) => next(e))

  on('ui.message', { requestId: PANE, element: 'list' }, async ($, e) => {
    const m = e.data as ListMessage
    const { cur, rows } = await rowsOf($)
    const row = rows.find(r => lineKey(cur, r) === ('key' in m ? m.key : ''))
    if (m.t === 'key') await onKeyFromList($, m.key)
    else if (m.t === 'filter') await update($, filter, () => m.value)
    else if (m.t === 'typing') await update($, typing, () => m.on)
    else if (!row || 'gap' in row) return {}
    else if ('head' in row) {
      if (m.t === 'fold') await update($, opened, o => ({ ...o, [cur]: m.open ? row.head : '' }))
      if (m.t === 'mark') {
        const marks = await read($, pending)
        const onNow = row.items.filter(i => marks[markKey(cur, i)] ?? i.isOn).length
        await markAll($, cur, row.items, onNow !== row.items.length)
      }
    } else if (m.t === 'mark') {
      await mark($, cur, row)
    }
    return {}
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const els = $.ui.resolve(e)
    const { Box, Text, Button } = els
    const Client = 'Client' in els ? els.Client : undefined
    const raw = await read($, filter)
    const all = await read($, lists)
    const msg = await read($, note)
    const marks = await read($, pending)
    const needsReload = await read($, reload)
    const { cur, rows } = await rowsOf($)
    const width = Math.max(24, (e.props.bodyColumns ?? 42) - 1)
    const rule = '─'.repeat(Math.max(24, e.props.bodyColumns ?? 42))
    const cut = (s: string, n: number) => (s.length > n ? s.slice(0, Math.max(1, n - 1)) + '…' : s)
    const changes = Object.keys(marks).length
    const markOf = (i: Item) => marks[markKey(cur, i)]

    const lines: Line[] = rows.map((r, n) => {
      if ('gap' in r) return { key: `gap:${n}`, kind: 'gap', glyph: '', name: '', detail: '' }
      const next = rows[n + 1]
      if ('head' in r) {
        const onNow = r.items.filter(i => markOf(i) ?? i.isOn).length
        const isOffPlugin = r.items.some(i => i.via)
        const isOpen = next !== undefined && 'isOn' in next
        return {
          key: lineKey(cur, r),
          kind: 'head',
          open: isOpen,
          glyph: onNow === r.items.length ? '●' : onNow === 0 ? '○' : '◐',
          color: onNow === 0 ? undefined : 'green',
          dim: isOffPlugin && onNow === 0,
          name: r.head,
          detail: `${onNow}/${r.items.length}`,
          isMarked: r.items.some(i => markOf(i) !== undefined),
        }
      }
      const to = markOf(r)
      const willOn = to ?? r.isOn
      return {
        key: lineKey(cur, r),
        kind: 'row',
        glyph: willOn ? '●' : '○',
        color: willOn ? 'green' : undefined,
        dim: !willOn,
        name: r.name.startsWith(`${r.group}:`) ? r.name.slice(r.group.length + 1) : r.name,
        detail: r.via ? '' : cut(r.detail, 18),
        warn: r.warn,
        isMod: r.isMod,
        isMarked: to !== undefined,
      }
    })

    // The key buttons wrap: count the rows they take at this width ("[ k what ]" plus a gap).
    let keyRows = 1
    let used = 0
    for (const [k, what] of KEYS) {
      const w = k.length + what.length + 5
      if (used > 0 && used + 1 + w > width) {
        keyRows++
        used = w
      } else used += (used > 0 ? 1 : 0) + w
    }
    const footerRows =
      1 + keyRows + (changes > 0 ? 1 : 0) + (msg !== '' && rows.length > 0 ? 1 : 0) + (needsReload ? 1 : 0)
    const headerRows = 4
    const bodyRows = e.props.scroll?.bodyRows ?? 30
    // The list fills the room left, so the key buttons sit at the very bottom.
    const height = Math.max(3, bodyRows - headerRows - footerRows)
    const count = (k: Tab) => `${all[k].filter(i => i.isOn).length}/${all[k].length}`
    const tabs: [Tab, string, string][] = [
      ['plugins', 'Plugins', 'p'],
      ['mcp', 'MCP', 'm'],
      ['skills', 'Skills', 's'],
    ]

    return (
      <Box flexDirection="column">
        <Box flexDirection="row" gap={1}>
          {tabs.map(([k, label, key]) => (
            <Button
              key={`tab-${k}`}
              hotkey={key}
              variant={k === cur ? 'primary' : 'secondary'}
              label={`${label} ${count(k)}`}
              onPress={() => update($, tab, () => k)}
            />
          ))}
        </Box>
        <Text dimColor>{rule}</Text>
        {/* The filter, typed from the list after f; ▌ marks typing. */}
        {(await read($, typing)) ? (
          <Text>
            <Text color="cyan">filter </Text>
            {raw}
            <Text color="cyan">▌</Text>
            <Text dimColor>  enter finish · ctrl+u clear</Text>
          </Text>
        ) : raw ? (
          <Text>
            <Text dimColor>filter </Text>
            {raw}
            <Text dimColor>  f edit · backspace clear</Text>
          </Text>
        ) : (
          <Text dimColor>filter… press f</Text>
        )}
        <Text dimColor>{rule}</Text>
        {/* The list stays mounted even when empty: it is what hears the keys. */}
        {Client ? (
          <Client
            key="list"
            module="./list.tsx"
            height={height}
            // JSON round trip drops undefined fields, which a Client's props refuse.
            props={JSON.parse(JSON.stringify({ lines, empty: raw ? 'No matches · backspace to edit the filter' : msg || 'Nothing here.', height, width, view: `${cur}|${raw}`, wheel: await read($, wheel), filter: raw, typing: await read($, typing) }))}
          />
        ) : (
          <Text dimColor>This surface can't draw the list.</Text>
        )}

        {changes > 0 && (
          <Box flexDirection="row" gap={1}>
            <Text color="yellow">
              ✱ {changes} change{changes === 1 ? '' : 's'}
            </Text>
            <Button key="apply" hotkey="a" variant="primary" label="Apply" onPress={() => apply($)} />
            <Button key="undo" hotkey="u" label="Undo" onPress={() => update($, pending, () => ({}))} />
          </Box>
        )}

        {msg !== '' && rows.length > 0 && <Text color="yellow">{cut(msg, width)}</Text>}
        {needsReload && (
          <Button key="reload" variant="primary" label="Plugins changed · r to reload" onPress={() => reloadAll($)} />
        )}
        <Text dimColor>{rule}</Text>
        <Box flexDirection="row" flexWrap="wrap" columnGap={1}>
          {KEYS.map(([k, what]) => (
            <Button key={`keys:${k}`} label={`${k} ${what}`} onPress={() => keyAction($, k)}>
              <Text bold>{k}</Text> <Text dimColor>{what}</Text>
            </Button>
          ))}
        </Box>
      </Box>
    )
  })
}
