import { expect, test } from 'claude-code/testing'

const PANE = {
  plugin: 'toggles',
  component: 'Pane',
  requestId: 'toggles',
  surface: 'terminal',
  props: {
    title: 'Toggles',
    isFocused: true,
    bodyColumns: 50,
    placement: 'dock',
    scroll: { offset: 0, bodyRows: 30 },
    view: {},
  },
} as const

const item = (key: string, isOn: boolean) => ({
  key,
  id: key,
  name: key,
  isOn,
  group: isOn ? 'On' : 'Off',
  detail: '1 skill · global',
})

const LISTS = {
  plugins: [item('alpha', true), item('beta', false), item('gamma', false)],
  mcp: [],
  skills: [],
}

test('arrows move, right opens a closed group, space marks', async ($, on) => {
  on('state.get', ($, e, next) =>
    e.key === 'lists' ? { value: { value: { shape: 'lists-4', value: LISTS }, version: 1 } } : next(e),
  )
  const ui = await $.ui.mount(PANE)

  // On is open (something in it is on); Off starts closed.
  expect(await ui.find({ type: 'Text', text: /alpha/, in: 'list' })).toBeTruthy()
  expect(await ui.find({ type: 'Text', text: /beta/, in: 'list' })).toBeFalsy()

  // Cursor starts on the On header: down to alpha, down to the Off header, right opens it.
  await ui.key({ key: 'down', in: 'list' })
  await ui.key({ key: 'down', in: 'list' })
  await ui.key({ key: 'right', in: 'list' })
  expect(await ui.find({ type: 'Text', text: /beta/, in: 'list' })).toBeTruthy()
  // One group open at a time: opening Off closed On.
  expect(await ui.find({ type: 'Text', text: /alpha/, in: 'list' })).toBeFalsy()

  // Down to beta, space marks it: the footer shows one change.
  await ui.key({ key: 'down', in: 'list' })
  await ui.key({ key: ' ', in: 'list' })
  expect((await ui.find({ type: 'Text', text: /change/ }))?.text).toContain('1 change')

  // Left from a row goes to its header; left again closes the group.
  await ui.key({ key: 'left', in: 'list' })
  await ui.key({ key: 'left', in: 'list' })
  expect(await ui.find({ type: 'Text', text: /gamma/, in: 'list' })).toBeFalsy()
  await ui.unmount()
})

test('a long list draws a scrollbar; a short one does not', async ($, on) => {
  const many = { ...LISTS, plugins: Array.from({ length: 40 }, (_, n) => item(`p${n}`, true)) }
  on('state.get', ($, e, next) =>
    e.key === 'lists' ? { value: { value: { shape: 'lists-4', value: many }, version: 1 } } : next(e),
  )
  const ui = await $.ui.mount(PANE)
  expect(await ui.find({ type: 'Text', text: /┃/, in: 'list' })).toBeTruthy()
  await ui.unmount()
})

test('a short list has no scrollbar', async ($, on) => {
  on('state.get', ($, e, next) =>
    e.key === 'lists' ? { value: { value: { shape: 'lists-4', value: LISTS }, version: 1 } } : next(e),
  )
  const ui = await $.ui.mount(PANE)
  expect(await ui.find({ type: 'Text', text: /┃/, in: 'list' })).toBeFalsy()
  await ui.unmount()
})

test('f types into the filter from the list; enter finishes', async ($, on) => {
  on('state.get', ($, e, next) =>
    e.key === 'lists' ? { value: { value: { shape: 'lists-4', value: LISTS }, version: 1 } } : next(e),
  )
  const ui = await $.ui.mount(PANE)
  await ui.key({ key: 'f', in: 'list' })
  await ui.key({ key: 'g', in: 'list' })
  await ui.key({ key: 'a', in: 'list' })
  expect(await ui.find({ type: 'Text', text: /gamma/, in: 'list' })).toBeTruthy()
  expect(await ui.find({ type: 'Text', text: /alpha/, in: 'list' })).toBeFalsy()
  expect((await ui.find({ type: 'Text', text: /filter/ }))?.text).toContain('ga')

  // Backspace edits; Enter stops typing, so letters are keys again.
  await ui.key({ key: 'backspace', in: 'list' })
  await ui.key({ key: 'backspace', in: 'list' })
  await ui.key({ key: 'return', in: 'list' })
  expect(await ui.find({ type: 'Text', text: /alpha/, in: 'list' })).toBeTruthy()
  await ui.unmount()
})

test('backspace outside typing clears the whole filter', async ($, on) => {
  on('state.get', ($, e, next) =>
    e.key === 'lists' ? { value: { value: { shape: 'lists-4', value: LISTS }, version: 1 } } : next(e),
  )
  const ui = await $.ui.mount(PANE)
  for (const k of ['f', 'g', 'a', 'm', 'return']) await ui.key({ key: k, in: 'list' })
  expect(await ui.find({ type: 'Text', text: /alpha/, in: 'list' })).toBeFalsy()
  await ui.key({ key: 'backspace', in: 'list' })
  expect(await ui.find({ type: 'Text', text: /alpha/, in: 'list' })).toBeTruthy()
  await ui.unmount()
})

test('a filter that matches nothing can still be edited and cleared', async ($, on) => {
  on('state.get', ($, e, next) =>
    e.key === 'lists' ? { value: { value: { shape: 'lists-4', value: LISTS }, version: 1 } } : next(e),
  )
  const ui = await $.ui.mount(PANE)
  for (const k of ['f', 'z', 'z']) await ui.key({ key: k, in: 'list' })
  expect(await ui.find({ type: 'Text', text: /No matches/, in: 'list' })).toBeTruthy()
  await ui.key({ key: 'backspace', in: 'list' })
  await ui.key({ key: 'backspace', in: 'list' })
  expect(await ui.find({ type: 'Text', text: /alpha/, in: 'list' })).toBeTruthy()
  await ui.unmount()
})
