import { expect, test } from 'claude-code/testing'

// git and snap.sh are faked here; bin/snap.test.sh checks the real git work.
const OUT: [RegExp, string][] = [
  [/rev-parse --is-inside-work-tree/, 'true\n'],
  [/snap\.sh snap refs\//, 'before1\n'],
  [/snap\.sh snap$/, 'after1\n'],
  [/diff --numstat/, '15\t6\tsrc/sidebar.rs\x003\t0\tsrc/new.rs\0'],
  [/diff --name-status/, 'M\0src/sidebar.rs\0A\0src/new.rs\0'],
  [/snap\.sh restore before1 refs\/prompt-changes\/s1\/undo/, 'undo1\n'],
  [/snap\.sh prune/, ''],
]

const PANE_PROPS = {
  title: 'Changes per prompt',
  isFocused: false,
  bodyColumns: 80,
  placement: 'dock' as const,
  scroll: { offset: 0, bodyRows: 20 },
  view: {},
}

const BAND_PROPS = {
  hasSurvey: false,
  isWorking: false,
  maxRows: 5,
  bodyColumns: 80,
  scroll: { offset: 0, bodyRows: 5 },
  view: {},
}

test('a prompt is listed with its changes, and Discard restores files then opens /rewind', async ($, on) => {
  const ran: string[] = []
  const commands: string[] = []
  on('process.run', ($, e) => {
    const line = e.argv.join(' ')
    ran.push(line)
    const out = OUT.find(([pattern]) => pattern.test(line))
    const result = { exitCode: out ? 0 : 1, stdout: out?.[1] ?? '', stderr: out ? '' : `unexpected: ${line}` }
    return { value: { ...result, isStdoutTruncated: false, isStderrTruncated: false } }
  })
  on('session.id', () => ({ value: 's1' }))
  on('command.register', (_, e) => ({ value: { command: e.name } }))
  on('command.run', ($, e) => {
    commands.push(e.command)
    return { text: '' }
  })
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('ui.toast', () => ({ value: undefined }))
  on('ui.log', () => ({ value: undefined }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('turn.start', (_, e) => ({ turnId: e.turnId }))
  on('turn.complete', (_, e) => ({ text: e.answer }))

  await $.session.start({ cwd: '/repo', surface: 'terminal', isInteractive: true })
  await $.turn.start({ text: 'fold only project rows', turnId: 't1' })
  await $.turn.complete({ reason: 'answer', answer: 'done', durationMs: 1, isAborted: false, turnId: 't1' })

  expect(ran.some(line => /snap\.sh snap refs\/prompt-changes\/s1\/1$/.test(line))).toBe(true)
  const band = await $.ui.mount({ plugin: 'prompt-changes', surface: 'terminal', component: 'AbovePrompt', props: BAND_PROPS })
  expect((await band.find({ type: 'Text', text: /✎ #1 "fold only project rows": 2 files {2}\+18 −6/ }))).toBeDefined()

  const ui = await $.ui.mount({ plugin: 'prompt-changes', surface: 'terminal', component: 'Pane', props: PANE_PROPS, requestId: 'changes' })
  expect((await ui.find({ key: 'toggle-1' }))?.text).toContain('#1 "fold only project rows"')
  await ui.press({ key: 'discard-1' })
  expect((await ui.find({ type: 'Text', text: /Discard 2 files from #1/ }))).toBeDefined()
  await ui.press({ key: 'confirm' })

  expect(ran.some(line => /snap\.sh restore before1 /.test(line))).toBe(true)
  expect(commands).toContain('rewind')
  expect(await ui.find({ type: 'Text', text: 'discarded' })).toBeDefined()
  expect(await ui.find({ key: 'undo' })).toBeDefined()
})

test('a folder that stops being a repo mid-session is skipped quietly', async ($, on) => {
  let isRepo = true
  const ran: string[] = []
  const toasts: string[] = []
  on('process.run', ($, e) => {
    const line = e.argv.join(' ')
    ran.push(line)
    const ok = isRepo || !/rev-parse/.test(line)
    return { value: { exitCode: ok ? 0 : 128, stdout: ok ? 'true\n' : '', stderr: '', isStdoutTruncated: false, isStderrTruncated: false } }
  })
  on('session.id', () => ({ value: 's1' }))
  on('command.register', (_, e) => ({ value: { command: e.name } }))
  on('ui.toast', (_, e) => (toasts.push(e.text), { value: undefined }))
  on('ui.log', () => ({ value: undefined }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('turn.start', (_, e) => ({ turnId: e.turnId }))

  await $.session.start({ cwd: '/repo', surface: 'terminal', isInteractive: true })
  isRepo = false // e.g. the worktree was removed
  await $.turn.start({ text: 'hi', turnId: 't1' })

  expect(ran.some(line => /snap\.sh snap/.test(line))).toBe(false)
  expect(toasts).toEqual([])
})
