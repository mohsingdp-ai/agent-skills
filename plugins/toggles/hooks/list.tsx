import type { ClientModule } from 'claude-code'

import type { Line, ListMessage, ListProps, ListState } from '../types'

// The toggles list, drawn and driven on the terminal itself so it can take
// ↑ ↓ ← → Space and Enter. It posts what the person did to the hooks module.

const isLine = (l: Line | undefined) => l !== undefined && l.kind !== 'gap'

function step(lines: Line[], at: number, dir: 1 | -1) {
  for (let j = at + dir; j >= 0 && j < lines.length; j += dir) if (isLine(lines[j])) return j
  return -1
}

function headOf(lines: Line[], at: number) {
  for (let j = at; j >= 0; j--) if (lines[j]?.kind === 'head') return j
  return -1
}

const cut = (s: string, n: number) => (s.length > n ? s.slice(0, Math.max(1, n - 1)) + '…' : s)

const List: ClientModule<ListProps, ListState> = (p, surface) => {
  const { Box, Text } = surface.elements
  const lines = p.lines
  const n = Math.max(1, p.height)
  const st = surface.state
  const isFresh = st === undefined || st.view !== p.view

  // Where the window and cursor stand now, the wheel's ticks since the last key included.
  const max = Math.max(0, lines.length - n)
  let off = isFresh ? 0 : Math.min(max, Math.max(0, st.off + (p.wheel - st.wheel)))
  let at = isFresh ? -1 : lines.findIndex(l => l.key === st.cursor)
  if (at < 0) at = step(lines, -1, 1)
  if (isFresh && at >= n) off = Math.min(max, at)

  const post = (m: ListMessage) => surface.post(m)
  const save = (to: number, o: number) =>
    surface.setState({ cursor: lines[to]?.key ?? '', off: o, view: p.view, wheel: p.wheel })
  const moveTo = (to: number) => {
    if (to < 0) return
    let o = off
    if (to < o) o = to
    if (to >= o + n) o = to - n + 1
    save(to, o)
  }

  surface.onKey(ev => {
    // Typing into the filter (after f): letters edit it; Enter or ↓ goes back to the list.
    // Terminals name the erase key differently: accept every spelling.
    const isErase =
      ev.key === 'backspace' || ev.key === 'delete' || ev.key === '\x7f' || ev.key === '\b' || (ev.ctrl && ev.key === 'h')
    if (p.typing) {
      if (ev.key === 'return' || ev.key === 'down' || ev.key === 'tab') return post({ t: 'typing', on: false })
      if (ev.ctrl && ev.key === 'u') return post({ t: 'filter', value: '' })
      if (isErase) return post({ t: 'filter', value: p.filter.slice(0, -1) })
      if (ev.key === 'space') return post({ t: 'filter', value: p.filter + ' ' })
      if (!ev.ctrl && !ev.meta && ev.key.length === 1) post({ t: 'filter', value: p.filter + ev.key })
      return
    }
    // Outside typing, Backspace clears the whole filter.
    if (isErase && p.filter !== '') return post({ t: 'filter', value: '' })
    const line = lines[at]
    switch (ev.key) {
      case 'up':
        return moveTo(step(lines, at, -1))
      case 'down':
        return moveTo(step(lines, at, 1))
      case 'pageup':
        return moveTo(Math.max(step(lines, -1, 1), step(lines, Math.max(0, at - n), 1)))
      case 'pagedown':
        return moveTo(step(lines, Math.min(lines.length, at + n), -1))
      case 'home':
        return moveTo(step(lines, -1, 1))
      case 'end':
        return moveTo(step(lines, lines.length, -1))
      case 'left':
        if (line?.kind === 'head' && line.open) return post({ t: 'fold', key: line.key, open: false })
        return moveTo(headOf(lines, at))
      case 'right':
        if (line?.kind === 'head' && !line.open) post({ t: 'fold', key: line.key, open: true })
        return
      case 'return':
        if (line?.kind === 'head') return post({ t: 'fold', key: line.key, open: !line.open })
        if (line) post({ t: 'mark', key: line.key })
        return
      case ' ':
      case 'space':
        if (line) post({ t: 'mark', key: line.key })
        return
      default:
        if (!ev.ctrl && !ev.meta && ev.key.length === 1) post({ t: 'key', key: ev.key })
    }
  })

  surface.onPointer(ev => {
    if (ev.type !== 'down' || ev.button !== 'left') return
    const to = off + ev.y
    const line = lines[to]
    if (!isLine(line) || !line) return
    // A click moves the cursor; on a group it also opens or closes it. Space switches.
    moveTo(to)
    if (line.kind === 'head') post({ t: 'fold', key: line.key, open: !line.open })
  })

  // A scrollbar on the right edge, only when the list is longer than the window.
  const hasBar = lines.length > n
  const width = Math.max(20, p.width) - (hasBar ? 2 : 0)
  const thumb = hasBar ? Math.max(1, Math.round((n * n) / lines.length)) : 0
  const thumbAt = hasBar && max > 0 ? Math.round((off * (n - thumb)) / max) : 0
  const bar = Array.from({ length: n }, (_, i) => (i >= thumbAt && i < thumbAt + thumb ? '┃' : '│'))

  if (lines.length === 0) {
    return (
      <Box height={n}>
        <Text dimColor> {p.empty}</Text>
      </Box>
    )
  }

  return (
    <Box flexDirection="row" height={n}>
      <Box flexDirection="column" flexGrow={1}>
        {lines.slice(off, off + n).map((l, i) => {
          const isCursor = off + i === at
          if (l.kind === 'gap') return <Text key={l.key}> </Text>
          const lead = l.kind === 'head' ? ' ' : '   '
          const room = width - lead.length - 2 - l.detail.length - (l.isMod ? 4 : 0) - 4
          return (
            <Text key={l.key} inverse={isCursor}>
              {lead}
              <Text color={l.color} dimColor={l.color === undefined} bold={l.kind === 'head'}>
                {l.glyph}
              </Text>{' '}
              <Text bold={l.kind === 'head'} dimColor={l.dim}>
                {cut(l.name, Math.max(6, room))}
              </Text>{' '}
              {l.isMod && <Text color="cyan">mod </Text>}
              {l.warn ? <Text color="yellow">{l.warn}</Text> : <Text dimColor>{l.detail}</Text>}
              {l.isMarked && <Text color="yellow"> ✱</Text>}{' '}
            </Text>
          )
        })}
      </Box>
      {hasBar && (
        <Box flexDirection="column" width={1} marginLeft={1}>
          {bar.map((c, i) => (
            <Text key={`bar:${i}`} color={c === '┃' ? 'cyan' : undefined} dimColor={c !== '┃'}>
              {c}
            </Text>
          ))}
        </Box>
      )}
    </Box>
  )
}

export default List
