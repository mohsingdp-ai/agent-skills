import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { Item, Lists, Pending, Preset, Tab } from '../types'

const PANE = 'toggles'
const tab = atom({ plugin: 'toggles', key: 'tab' } as const, 'plugins' as Tab)
const filter = atom({ plugin: 'toggles', key: 'filter' } as const, '')
const note = atom({ plugin: 'toggles', key: 'note' } as const, '')
const pending = atom({ plugin: 'toggles', key: 'pending' } as const, {} as Pending)
const folded = atom({ plugin: 'toggles', key: 'folded' } as const, [] as string[])
const naming = atom({ plugin: 'toggles', key: 'naming' } as const, false)
const reload = atom({ plugin: 'toggles', key: 'reload' } as const, false)
const presets = atom({ plugin: 'toggles', key: 'presets' } as const, [] as Preset[], { shape: 'presets-1' })
const lists = atom({ plugin: 'toggles', key: 'lists' } as const, { plugins: [], mcp: [], skills: [] } as Lists, {
  shape: 'lists-3',
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
async function writeSettings($: $, rules: [string, boolean][], offs: [string, boolean][]) {
  const s = await readSettings($)
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

/** On: enable the global install, or install it globally. Off: disable each enabled copy. */
function pluginSteps(i: Item, to: boolean): [string[], string | undefined][] {
  const copies = i.copies ?? []
  if (!to) {
    return copies
      .filter(c => c.isOn)
      .map(c => [['claude', 'plugin', 'disable', i.id, '--scope', c.scope], c.cwd])
  }
  const global = copies.find(c => c.cwd === undefined)
  return global
    ? [[['claude', 'plugin', 'enable', i.id, '--scope', global.scope], undefined]]
    : [[['claude', 'plugin', 'install', i.id, '--scope', 'user'], undefined]]
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
      else items.push({ key: id, id, name: id, isOn: false, group: plugin, detail: 'plugin off', via })
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
  const only = new Map<string, string[]>() // off plugin's key -> the skills picked in it
  const failed: string[] = []
  let pluginsChanged = false

  const switchPlugin = async (i: Item, to: boolean) => {
    for (const [argv, cwd] of pluginSteps(i, to)) {
      const r = await $.process.run(argv, { cwd, timeoutMs: 120_000 }).catch(e => ({
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
    if (rules.length > 0 || offs.length > 0) await writeSettings($, rules, offs)
  } catch (err) {
    failed.push(`settings not saved: ${String(err)}`)
  }
  await update($, pending, () => ({}))
  if (pluginsChanged) await update($, reload, () => true)
  if (failed.length > 0) $.ui.toast(`toggles: ${failed.join('; ')}`)
  await refresh($)
}

// ---- presets ----

async function savePreset($: $, name: string) {
  const all = await read($, lists)
  const state = Object.fromEntries(
    TABS.map(t => [
      t,
      Object.fromEntries(all[t].map(i => [i.key, i.isOn])),
    ]),
  ) as Preset['state']
  const list = [...(await read($, presets)).filter(p => p.name !== name), { name, state }]
  await update($, presets, () => list)
  await $.store.set('presets', list)
  await update($, naming, () => false)
}

/** Marks the changes that turn the current set into the preset; Apply makes them. */
async function usePreset($: $, p: Preset) {
  const all = await read($, lists)
  const marks: Pending = {}
  for (const t of TABS) {
    for (const i of all[t]) {
      const want = p.state[t]?.[i.key]
      if (want !== undefined && want !== i.isOn) marks[markKey(t, i)] = want
    }
  }
  await update($, pending, () => marks)
  await update($, note, () => `preset ${p.name}: ${Object.keys(marks).length} changes marked`)
}

async function deletePreset($: $, name: string) {
  const list = (await read($, presets)).filter(p => p.name !== name)
  await update($, presets, () => list)
  await $.store.set('presets', list)
}

// ---- hooks ----

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: 'toggles',
      description: 'Switch plugins, MCP servers and skills on or off',
    })
    const saved = await $.store.get('presets')
    if (Array.isArray(saved)) await update($, presets, () => saved as Preset[])
    return next(e)
  })

  on('command.run', { command: 'toggles' }, async $ => {
    await $.ui.open({ id: PANE, title: 'Toggles', focus: true })
    void refresh($)
    return { text: 'Toggles pane opened.' }
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const els = $.ui.resolve(e)
    const { Box, Text, Button } = els
    const Input = 'Input' in els ? els.Input : undefined
    const cur = await read($, tab)
    const raw = await read($, filter)
    const q = raw.toLowerCase()
    const all = await read($, lists)
    const msg = await read($, note)
    const marks = await read($, pending)
    const shut = await read($, folded)
    const sets = await read($, presets)
    const isNaming = await read($, naming)
    const needsReload = await read($, reload)
    const width = Math.max(24, (e.props.bodyColumns ?? 42) - 1)
    const cut = (s: string, n: number) => (s.length > n ? s.slice(0, Math.max(1, n - 1)) + '…' : s)
    const changes = Object.keys(marks).length

    // Sections in a fixed order, then rows; a folded section shows its header alone.
    const items = all[cur].filter(i => q === '' || i.name.toLowerCase().includes(q))
    const order = ['On', 'Off', 'Your skills', 'This project']
    const groups = [...new Set(items.map(i => i.group))].sort((a, b) => {
      const offPlugin = (g: string) => items.some(i => i.group === g && i.via)
      const ia = (order.indexOf(a) + 1 || 99) + (offPlugin(a) ? 100 : 0)
      const ib = (order.indexOf(b) + 1 || 99) + (offPlugin(b) ? 100 : 0)
      return ia - ib || a.localeCompare(b)
    })
    const rows: ({ head: string; on: number; total: number } | Item)[] = []
    for (const g of groups) {
      const inG = items.filter(i => i.group === g)
      rows.push({ head: g, on: inG.filter(i => i.isOn).length, total: inG.length })
      if (cur === 'skills' || q !== '' || !shut.includes(`${cur}:${g}`)) rows.push(...inG)
    }

    const count = (k: Tab) => `${all[k].filter(i => i.isOn).length}/${all[k].length}`
    const markOf = (t: Tab, i: Item) => marks[markKey(t, i)]
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
          <Button key="refresh" hotkey="r" label="↻" onPress={() => refresh($)} />
        </Box>
        {Input && (
          <Input
            key="filter"
            placeholder="filter…"
            value={raw}
            onInput={(v: string) => update($, filter, () => v)}
            onSubmit={(v: string) => update($, filter, () => v)}
          />
        )}
        {rows.length === 0 && <Text dimColor>{msg || 'Nothing here.'}</Text>}
        {rows.map((r, n) => {
          if ('head' in r) {
            const id = `${cur}:${r.head}`
            const isShut = q === '' && shut.includes(id)
            const inG = items.filter(i => i.group === r.head)
            const onNow = inG.filter(i => markOf(cur, i) ?? i.isOn).length
            const isOffPlugin = inG.some(i => i.via)
            const isSwitch = cur === 'skills'
            const count = isSwitch ? `${onNow}/${r.total}` : `${r.total}`
            const glyph = isSwitch
              ? onNow === inG.length ? '●' : onNow === 0 ? '○' : '◐'
              : isShut ? '▶' : '▼'
            const glyphColor = isSwitch ? (onNow === 0 ? undefined : 'green') : 'cyan'
            return (
              <Box key={`headbox:${id}`} marginTop={n === 0 ? 0 : 1}>
                <Button
                  key={`head:${id}`}
                  plain
                  onPress={() =>
                    isSwitch
                      ? markAll($, cur, inG, onNow !== inG.length)
                      : update($, folded, f => (f.includes(id) ? f.filter(x => x !== id) : [...f, id]))
                  }
                >
                  <Text color={glyphColor} dimColor={glyphColor === undefined} bold>
                    {glyph}
                  </Text>{' '}
                  <Text bold dimColor={isOffPlugin && onNow === 0}>{r.head}</Text> <Text dimColor>{count}</Text>
                  {isOffPlugin && <Text dimColor>{onNow === 0 ? ' · plugin off' : ' · plugin on ✱'}</Text>}
                </Button>
              </Box>
            )
          }
          const to = markOf(cur, r)
          const willOn = to ?? r.isOn
          const side = to !== undefined ? '✱' : ' '
          return (
            <Button key={`row:${cur}:${r.key}`} plain onPress={() => mark($, cur, r)}>
              {'  '}
              <Text color={willOn ? 'green' : undefined} dimColor={!willOn}>
                {willOn ? '●' : '○'}
              </Text>{' '}
              <Text dimColor={!willOn}>{cut(r.name.startsWith(`${r.group}:`) ? r.name.slice(r.group.length + 1) : r.name, width - 22)}</Text>{' '}
              {r.isMod && <Text color="cyan">mod </Text>}
              {r.warn ? <Text color="yellow">{r.warn}</Text> : <Text dimColor>{cut(r.detail, 16)}</Text>}
              {to !== undefined && <Text color="yellow"> {side}</Text>}
            </Button>
          )
        })}

        {changes > 0 && (
          <Box flexDirection="row" gap={1}>
            <Text color="yellow">
              ✱ {changes} change{changes === 1 ? '' : 's'}
            </Text>
            <Button key="apply" hotkey="a" variant="primary" label="Apply" onPress={() => apply($)} />
            <Button key="undo" hotkey="u" label="Undo" onPress={() => update($, pending, () => ({}))} />
          </Box>
        )}

        {isNaming && Input ? (
          <Input
            key="preset-name"
            autoFocus
            placeholder="preset name, enter to save"
            onSubmit={(v: string) => (v.trim() ? savePreset($, v.trim()) : update($, naming, () => false))}
          />
        ) : (
          <Box flexDirection="row" gap={1}>
            <Text dimColor>Presets</Text>
            {sets.slice(0, 9).map((p, n) => (
              <Button
                key={`preset:${p.name}`}
                hotkey={String(n + 1)}
                label={p.name}
                onPress={() => usePreset($, p)}
              />
            ))}
            <Button key="preset-new" hotkey="n" plain label="+ save" onPress={() => update($, naming, () => true)} />
            {sets.length > 0 && (
              <Button
                key="preset-del"
                plain
                label="− last"
                onPress={() => deletePreset($, sets.at(-1)!.name)}
              />
            )}
          </Box>
        )}

        {msg !== '' && rows.length > 0 && <Text color="yellow">{cut(msg, width * 2)}</Text>}
        {needsReload && (
          <Button
            key="reload"
            hotkey="l"
            variant="primary"
            label="Plugins changed · reload now"
            onPress={async () => {
              await $.command.run({ command: 'reload-plugins' })
              await update($, reload, () => false)
            }}
          />
        )}
        <Text dimColor>⏎ mark · a apply · u undo · 1-9 preset · n save</Text>
      </Box>
    )
  })
}
