import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { FileChange, Prompt, Undo } from '../types'

const PANE = 'changes'
const TITLE = 'Changes per prompt'
const KEEP_DAYS = '7'

const prompts = atom({ plugin: 'prompt-changes', key: 'prompts' } as const, [] as Prompt[])
const busy = atom({ plugin: 'prompt-changes', key: 'busy' } as const, false)
const open = atom({ plugin: 'prompt-changes', key: 'open' } as const, null as number | null)
const confirm = atom({ plugin: 'prompt-changes', key: 'confirm' } as const, null as number | null)
const undo = atom({ plugin: 'prompt-changes', key: 'undo' } as const, null as Undo | null)

type $ = EngineInterface

const run = async ($: $, argv: string[]) => {
  const ran = await $.process.run(argv)
  if (ran.exitCode !== 0) throw new Error(ran.stderr.trim() || `${argv[0]} exited ${ran.exitCode}`)
  return ran.stdout
}
const snap = async ($: $, ...args: string[]) =>
  (await run($, ['sh', `${$.plugin.root}/bin/snap.sh`, ...args])).trim()
const isRepo = ($: $) =>
  $.process.run(['git', 'rev-parse', '--is-inside-work-tree']).then(r => r.exitCode === 0, () => false)
const ref = async ($: $, name: string) => `refs/prompt-changes/${await $.session.id()}/${name}`

const plural = (k: number, word: string) => `${k} ${word}${k === 1 ? '' : 's'}`
const summary = (files: FileChange[]) => {
  if (files.length === 0) return 'no changes'
  const add = files.reduce((sum, f) => sum + (f.added ?? 0), 0)
  const del = files.reduce((sum, f) => sum + (f.removed ?? 0), 0)
  return `${plural(files.length, 'file')}  +${add} −${del}`
}
const short = (text: string) => {
  const line = (text.trim().split('\n')[0] ?? '').trim()
  return line === '' ? '(no prompt)' : line.length > 32 ? `${line.slice(0, 31)}…` : line
}

// What changed between two snapshots, from git's -z output.
const changes = async ($: $, from: string, to: string): Promise<FileChange[]> => {
  const range = ['-z', '--no-renames', from, to]
  const [numstat, names] = await Promise.all([
    run($, ['git', 'diff', '--numstat', ...range]),
    run($, ['git', 'diff', '--name-status', ...range]),
  ])
  const status = new Map<string, string>()
  const parts = names.split('\0')
  for (let i = 0; i + 1 < parts.length; i += 2) status.set(parts[i + 1] ?? '', parts[i] ?? '')
  return numstat
    .split('\0')
    .filter(Boolean)
    .map(record => {
      const [added = '-', removed = '-', ...rest] = record.split('\t')
      const path = rest.join('\t')
      const count = (n: string) => (n === '-' ? null : Number(n))
      return { path, added: count(added), removed: count(removed), status: status.get(path) ?? 'M' }
    })
}

// Puts the files back to before prompt n (undoing n and every later prompt),
// then opens Claude's own rewind menu for the chat. Returns what to tell the person.
const discard = async ($: $, n: number): Promise<string> => {
  if (await read($, busy)) return 'Claude is still working: discard once it finishes.'
  const target = (await read($, prompts)).find(p => p.n === n)
  if (!target || target.isDiscarded) return `Prompt #${n} is not in this session's list (or already discarded).`
  try {
    const commit = await snap($, 'restore', target.before, await ref($, 'undo'))
    await update($, prompts, list => list.map(p => (p.n >= n ? { ...p, isDiscarded: true } : p)))
    await update($, undo, () => ({ commit, n }))
    await update($, confirm, () => null)
  } catch (error) {
    return `Discard failed, nothing was changed: ${error instanceof Error ? error.message : String(error)}`
  }
  // Not awaited: the command is queued until the session is idle, which may be after this hook.
  $.command.run({ command: 'rewind', args: '' }).catch(() => $.ui.toast('Press Esc twice to rewind the chat.'))
  return `Code is back to before #${n}. In the rewind menu pick "${short(target.text)}", then "Restore conversation only".`
}

const undoDiscard = async ($: $): Promise<string> => {
  const last = await read($, undo)
  if (!last) return 'Nothing to undo.'
  if (await read($, busy)) return 'Claude is still working: undo once it finishes.'
  try {
    await snap($, 'restore', last.commit, await ref($, 'undo'))
  } catch (error) {
    return `Undo failed, nothing was changed: ${error instanceof Error ? error.message : String(error)}`
  }
  await update($, prompts, list => list.map(p => (p.n >= last.n ? { ...p, isDiscarded: false } : p)))
  await update($, undo, () => null)
  return `Files are back as they were before the discard of #${last.n}. The chat stays rewound.`
}

export const register: Register = on => {
  let inRepo = false

  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'changes', description: 'Show what each prompt changed, and discard it', immediate: true })
    await $.command.register({
      name: 'rewind-discard',
      description: 'Discard the file changes of prompt N and later, then open /rewind for the chat',
      argumentHint: '<prompt number>',
    })
    inRepo = await isRepo($)
    if (inRepo) snap($, 'prune', KEEP_DAYS).catch(error => $.ui.log(`prune failed: ${error}`, { to: 'debug' }))

    return next(e)
  })

  on('command.run', { command: 'changes' }, async $ => {
    await $.ui.open({ id: PANE, title: TITLE })

    return { text: 'Changes pane opened.' }
  })

  on('command.run', { command: 'rewind-discard' }, async ($, e) => {
    const n = Number(e.args.trim().replace(/^#/, ''))
    if (e.args.trim() === '' || !Number.isInteger(n) || n < 1) {
      await $.ui.open({ id: PANE, title: TITLE })
      return { text: 'Usage: /rewind-discard <prompt number>. The changes pane shows the numbers.' }
    }

    return { text: await discard($, n) }
  })

  // Snapshot before each typed prompt; a continuation turn ("") belongs to the prompt before it.
  // The folder is re-checked each turn: it can stop being a repo (e.g. a removed worktree).
  on('turn.start', async ($, e, next) => {
    if (e.agentId !== undefined) return next(e)
    inRepo = await isRepo($)
    if (!inRepo) return next(e)
    await update($, busy, () => true)
    await update($, undo, () => null) // undoing a discard after new work would wipe that work
    await update($, confirm, () => null)
    const list = await read($, prompts)
    if (e.text !== '' || list.length === 0) {
      const n = (list.at(-1)?.n ?? 0) + 1
      try {
        const before = await snap($, 'snap', await ref($, String(n)))
        await update($, prompts, all => [...all, { n, text: e.text, before, files: [] }])
      } catch (error) {
        $.ui.toast(`prompt-changes: snapshot failed, #${n} can't be discarded: ${error}`)
      }
    }

    return next(e)
  })

  on('turn.complete', async ($, e, next) => {
    const done = await next(e)
    if (e.agentId !== undefined || !inRepo) return done
    await update($, busy, () => false)
    const last = (await read($, prompts)).at(-1)
    if (!last || last.isDiscarded) return done
    try {
      const files = await changes($, last.before, await snap($, 'snap'))
      await update($, prompts, list => list.map(p => (p.n === last.n ? { ...p, files } : p)))
    } catch (error) {
      $.ui.log(`diff failed: ${error}`, { to: 'debug' })
    }

    return done
  })

  // The latest prompt whose changes are still in place, above the prompt box; never sent to
  // the model. Passes when there is none; ponytail: while it shows, a band from a mod beneath does not.
  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const live = (await read($, prompts)).findLast(p => p.files.length > 0 && !p.isDiscarded)
    if (e.props.hasSurvey || live === undefined) return next(e)
    const { Box, Button, Text } = $.ui.resolve(e)

    return (
      <Box gap={1}>
        <Text dimColor wrap="truncate-end">
          ✎ #{live.n} "{short(live.text)}": {summary(live.files)}
        </Text>
        <Button key="open-changes" plain label="/changes" onPress={() => $.ui.open({ id: PANE, title: TITLE })} />
      </Box>
    )
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Button, Text } = $.ui.resolve(e)
    if (!inRepo) return <Text dimColor>Not a git repository: nothing to track.</Text>
    const list = await read($, prompts)
    const isBusy = await read($, busy)
    const opened = await read($, open)
    const asking = await read($, confirm)
    const last = await read($, undo)
    const say = (text: string) => $.ui.toast(text)
    const room = Math.max(3, (e.viewport?.rows ?? 24) - 4)

    return (
      <Box flexDirection="column">
        {list.length === 0 && <Text dimColor>No prompts yet.</Text>}
        {[...list]
          .reverse()
          .slice(0, room)
          .map(p => {
            const later = list.filter(q => q.n > p.n && !q.isDiscarded).length
            const paths = new Set(list.filter(q => q.n >= p.n && !q.isDiscarded).flatMap(q => q.files.map(f => f.path)))
            // the arrow only where there are files to open; a space keeps the rows aligned
            const arrow = p.files.length === 0 ? ' ' : opened === p.n ? '▾' : '▸'
            const row = `${arrow} #${p.n} "${short(p.text)}"`
            return (
              <Box key={`p${p.n}`} flexDirection="column">
                <Box gap={1}>
                  {/* the label gives way (cut with …) so the summary and Discard always fit */}
                  <Box flexShrink={1}>
                    <Button
                      key={`toggle-${p.n}`}
                      plain
                      dimColor={p.isDiscarded === true || p.files.length === 0}
                      label={row}
                      onPress={() => update($, open, o => (o === p.n ? null : p.n))}
                    >
                      <Text wrap="truncate-end">{row}</Text>
                    </Button>
                  </Box>
                  <Box flexShrink={0}>
                    <Text dimColor>{p.isDiscarded ? 'discarded' : summary(p.files)}</Text>
                  </Box>
                  {!p.isDiscarded && p.files.length > 0 && !isBusy && asking !== p.n && (
                    <Box flexShrink={0}>
                      <Button key={`discard-${p.n}`} label="Discard" onPress={() => update($, confirm, () => p.n)} />
                    </Box>
                  )}
                </Box>
                {asking === p.n && (
                  <Box gap={1} marginLeft={2}>
                    <Text>
                      Discard {plural(paths.size, 'file')} from #{p.n}
                      {later > 0 ? ` and ${plural(later, 'later prompt')}` : ''}, then rewind the chat?
                    </Text>
                    <Button key="confirm" variant="primary" label="Discard" onPress={async () => say(await discard($, p.n))} />
                    <Button key="cancel" label="Cancel" onPress={() => update($, confirm, () => null)} />
                  </Box>
                )}
                {opened === p.n &&
                  p.files.map(f => (
                    <Text key={`f${p.n}-${f.path}`} dimColor wrap="truncate-start">
                      {'    '}
                      {f.path} {f.added === null ? 'binary' : `+${f.added} −${f.removed}`}
                      {f.status === 'A' ? ' new' : f.status === 'D' ? ' deleted' : ''}
                    </Text>
                  ))}
              </Box>
            )
          })}
        {isBusy && <Text dimColor>Claude is working: discard waits until it finishes.</Text>}
        {last && !isBusy && (
          <Button key="undo" plain label={`↶ Undo discard of #${last.n}`} onPress={async () => say(await undoDiscard($))} />
        )}
      </Box>
    )
  })
}
