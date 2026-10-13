/**
 * Yaku Canvas — desktop UI, unified-package door.
 * A full page at /yaku: mounts in the workspace (main) pane as a tab like the
 * built-in views, with a sidebar-nav row and a ⌘K command ("Open Yaku Canvas").
 *
 * Sources become cards; drag a card onto "✨ Yaku Chat" (or press Connect on a
 * card) to wire it in; the composer answers ONLY from connected sources,
 * citing [S1], [S2]… via this plugin's Python backend (ctx.rest).
 * Yaku look (REA from the shipped app): ink canvas, brand #5b4ddb / #a49cff —
 * accents only; every surface/border rides Hermes theme vars so it reskins.
 */
import { host, haptic, PANES_AREA, ROUTES_AREA, SIDEBAR_NAV_AREA, PALETTE_AREA } from '@hermes/plugin-sdk'
import { useCallback, useEffect, useRef, useState } from 'react'
import { jsx, jsxs, Fragment } from 'react/jsx-runtime'

const ID = 'yaku-canvas'
const BRAND = '#5b4ddb'
const BRAND_TINT = '#a49cff'
const BRAND_LINE = 'rgba(140,129,255,0.45)'
const BRAND_SOFT = 'rgba(90,68,221,0.16)'
const CARD_W = 240
const CARD_H = 120
const CHAT_W = 300
const BOARD_W = 1600
const BOARD_H = 1000

const KIND_ICON = {
  youtube: '\u25B6', tiktok: '\u266A', reddit: '\u{1F4AC}',
  social: '\u{1F517}', web: '\u{1F310}', note: '\u270D',
}

/* ---------------- backend door ---------------- */
let CTX = null // captured in register(); ctx.rest -> /api/plugins/yaku-canvas/*
async function api(path, opts) {
  if (CTX?.rest) return CTX.rest(path, { method: opts?.method || 'GET', body: opts?.body })
  // fallback for a bare renderer without the bridge (plain dashboard window)
  const r = await fetch(`/api/plugins/yaku-canvas${path}`, {
    method: opts?.method || 'GET',
    headers: { 'content-type': 'application/json' },
    body: opts?.body ? JSON.stringify(opts.body) : undefined,
  })
  return r.json()
}

async function fetchBoard(id) {
  const b = await api(`/boards/${encodeURIComponent(id)}`)
  return b && b.nodes ? b : { id, name: id, nodes: [], edges: [] }
}

/* ---------------- pieces ---------------- */

function SourceCard({ node, onFocus, selected, onConnect, onDelete, onEdit }) {
  const chars = (node.text || '').length
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(node.text || '')
  const save = () => {
    setEditing(false)
    if (draft !== (node.text || '')) onEdit(node, { text: draft })
  }
  return jsxs('div', {
    onMouseDown: (e) => { if (!editing) { e.preventDefault(); onFocus(node, e) } },
    style: {
      position: 'absolute', left: node.x, top: node.y, width: CARD_W, minHeight: CARD_H, zIndex: 2,
      borderRadius: 12,
      border: `1px solid ${selected ? BRAND_TINT : 'var(--ui-stroke-secondary, rgba(140,140,170,0.35))'}`,
      background: 'var(--ui-card, var(--card, rgba(255,255,255,0.04)))',
      boxShadow: selected
        ? `0 0 0 1.5px ${BRAND_LINE}, 0 8px 24px rgba(0,0,0,0.35)`
        : '0 6px 18px rgba(0,0,0,0.25)',
      padding: '10px 12px', cursor: editing ? 'text' : 'grab',
      userSelect: editing ? 'text' : 'none',
    },
    children: jsxs(Fragment, {
      children: [
        jsxs('div', { style: { display: 'flex', gap: 6, alignItems: 'center' }, children: [
          jsx('span', { style: { fontSize: 12 }, children: KIND_ICON[node.kind] || '\u{1F4C4}' }),
          jsx('span', {
            style: { fontSize: 12.5, fontWeight: 600, color: 'var(--ui-text-primary, #fafafa)',
              whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' },
            title: node.title, children: (node.title || 'Untitled').slice(0, 40),
          }),
          jsx('span', { style: { marginLeft: 'auto', display: 'flex', gap: 2 }, children: [
            jsx('button', {
              onMouseDown: (e) => { e.preventDefault(); e.stopPropagation() },
              onClick: () => { setEditing(true); setDraft(node.text || '') },
              title: 'Edit source text',
              style: { border: 'none', background: 'transparent', cursor: 'pointer',
                fontSize: 11, color: 'var(--ui-text-tertiary, #8f8da6)', padding: '0 3px' },
              children: '\u270E',
            }),
            jsx('button', {
              onMouseDown: (e) => { e.preventDefault(); e.stopPropagation() },
              onClick: () => onDelete(node),
              title: 'Remove card',
              style: { border: 'none', background: 'transparent', cursor: 'pointer',
                fontSize: 11, color: 'var(--ui-text-tertiary, #8f8da6)', padding: '0 3px' },
              children: '\u2715',
            }),
          ] }),
        ] }),
        editing
          ? jsx('textarea', {
              value: draft,
              onChange: (e) => setDraft(e.target.value),
              onBlur: save,
              onKeyDown: (e) => { if (e.key === 'Escape') { setDraft(node.text || ''); setEditing(false) } },
              autoFocus: true,
              style: { width: '100%', minHeight: 70, marginTop: 6, fontSize: 11, lineHeight: 1.45,
                borderRadius: 6, padding: '6px 8px', resize: 'vertical', outline: 'none',
                background: 'rgba(127,127,127,0.08)',
                border: `1px solid ${BRAND_LINE}`,
                color: 'var(--ui-text-primary, #fafafa)',
                fontFamily: 'var(--font-mono, monospace)' },
            })
          : jsx('div', {
              style: { fontSize: 11, color: 'var(--ui-text-tertiary, #8f8da6)', marginTop: 6,
                cursor: 'text',
                display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical', overflow: 'hidden' },
              onClick: () => { setEditing(true); setDraft(node.text || '') },
              children: (node.text || '').slice(0, 120) || node.origin || '\u2014',
            }),
        jsxs('div', {
          style: { display: 'flex', alignItems: 'center', gap: 8, marginTop: 6 },
          children: [
            jsx('span', { style: { fontSize: 10.5, color: 'var(--ui-text-quaternary, #77768c)' },
              children: `${node.kind || 'source'} \u00B7 ${node.status === 'ok' ? `${chars} chars` : (node.origin || 'no text')}` }),
            (!node.connected) && jsx('button', {
              onMouseDown: (e) => { e.preventDefault(); e.stopPropagation() },
              onClick: () => onConnect(node),
              style: { marginLeft: 'auto', fontSize: 10, padding: '2px 8px', borderRadius: 999,
                border: `1px solid ${BRAND_LINE}`, background: BRAND_SOFT, color: BRAND_TINT,
                cursor: 'pointer', fontWeight: 600 },
              children: 'Connect',
            }),
            node.connected && jsx('span', { style: { marginLeft: 'auto', fontSize: 10,
              color: BRAND_TINT }, children: '\u2192 chat' }),
          ],
        }),
      ],
    }),
  })
}

function ChatNode({ x, y, selected, connectedCount, busy, onFocus }) {
  return jsxs('div', {
    onMouseDown: (e) => { e.preventDefault(); onFocus({ id: 'chat', kind: 'chat', x, y }, e) },
    style: {
      position: 'absolute', left: x, top: y, width: CHAT_W, zIndex: 2,
      borderRadius: 12, padding: '12px 14px',
      border: `1px solid ${selected ? BRAND_TINT : BRAND_LINE}`,
      background: `linear-gradient(160deg, ${BRAND_SOFT}, rgba(127,127,127,0.03) 70%)`,
      boxShadow: selected
        ? `0 0 0 1.5px ${BRAND_LINE}, 0 8px 24px rgba(0,0,0,0.35)`
        : '0 6px 18px rgba(0,0,0,0.25)',
      cursor: 'grab', userSelect: 'none',
    },
    children: [
      jsx('div', { style: { fontSize: 12.5, fontWeight: 700, color: BRAND_TINT }, children: '\u2728 Yaku Chat' }),
      jsx('div', {
        style: { fontSize: 11, color: 'var(--ui-text-tertiary, #8f8da6)', marginTop: 4 },
        children: busy ? 'Thinking\u2026'
          : `${connectedCount} source${connectedCount === 1 ? '' : 's'} connected`,
      }),
    ],
  })
}

function Wires({ nodes, edges, onCut }) {
  const byId = Object.fromEntries(nodes.map((n) => [n.id, n]))
  const center = (n, right) => [
    right ? n.x + (n.id === 'chat' ? CHAT_W : CARD_W) : n.x, n.y + 56,
  ]
  const pathFor = (a, b) => {
    const [x1, y1] = center(a, true), [x2, y2] = center(b, false)
    const mx = (x1 + x2) / 2
    return `M ${x1} ${y1} C ${mx} ${y1}, ${mx} ${y2}, ${x2} ${y2}`
  }
  return jsx('svg', {
    width: BOARD_W, height: BOARD_H,
    style: { position: 'absolute', left: 0, top: 0, zIndex: 1 },
    children: jsx(Fragment, {
      children: edges.map((e, i) => {
        const a = byId[e.source], b = byId[e.target]
        if (!a || !b) return null
        const d = pathFor(a, b)
        return jsxs('g', { key: i, children: [
          // fat invisible hit line so a click on the thin wire lands
          jsx('path', { d, fill: 'none', stroke: 'transparent', strokeWidth: 12,
            style: { cursor: 'pointer', pointerEvents: 'stroke' },
            onClick: () => onCut(e) }),
          jsx('path', { d, fill: 'none', stroke: BRAND_LINE, strokeWidth: 1.6,
            style: { pointerEvents: 'none' } }),
        ] })
      }),
    }),
  })
}

/* ---------------- main tab page ---------------- */
function CanvasPage() {
  const [board, setBoard] = useState(null)
  const [selected, setSelected] = useState(null)
  const [newUrl, setNewUrl] = useState('')
  const [adding, setAdding] = useState(false)
  const [question, setQuestion] = useState('')
  const [result, setResult] = useState(null)
  const [chatBusy, setChatBusy] = useState(false)
  const [posDrag, setPosDrag] = useState(null) // {id, dx, dy, moved}
  const viewportRef = useRef(null)

  useEffect(() => { fetchBoard('main').then(setBoard).catch(() => setBoard({ id: 'main', name: 'main', nodes: [], edges: [] })) }, [])

  const edges = board?.edges || []
  const connected = edges.filter((e) => e.target === 'chat').map((e) => e.source)
  const connectedSet = new Set(connected)

  const reload = () => fetchBoard('main').then(setBoard).catch(() => {})

  const addSource = useCallback(async () => {
    const url = newUrl.trim()
    if (!url || adding) return
    setAdding(true)
    try {
      const n = (board?.nodes?.length || 0)
      await api('/boards/main/nodes', {
        method: 'POST',
        body: { url, x: 48 + (n % 3) * 300, y: 48 + Math.floor(n / 3) * 180 },
      })
      await reload()
      haptic('tap')
    } catch (e) { host.notifyError(String(e)) }
    setAdding(false); setNewUrl('')
  }, [newUrl, board, adding])

  const connect = useCallback(async (node) => {
    try {
      await api('/boards/main/edges', { method: 'POST', body: { source: node.id, target: 'chat' } })
      setBoard((b) => ({ ...b, edges: [...(b?.edges || []), { source: node.id, target: 'chat' }] }))
      haptic('tap')
    } catch (e) { host.notifyError(String(e)) }
  }, [])

  const cutEdge = useCallback(async (edge) => {
    try {
      await api(`/boards/main/edges?source=${encodeURIComponent(edge.source)}&target=${encodeURIComponent(edge.target)}`, { method: 'DELETE' })
      setBoard((b) => ({ ...b, edges: (b?.edges || []).filter((x) => !(x.source === edge.source && x.target === edge.target)) }))
      haptic('tap')
    } catch (e) { host.notifyError(String(e)) }
  }, [])

  const editNode = useCallback(async (node, patch) => {
    // optimistic: user text shows instantly
    setBoard((b) => ({ ...b, nodes: b.nodes.map((n) => n.id === node.id ? { ...n, ...patch } : n) }))
    try {
      await api(`/boards/main/nodes/${encodeURIComponent(node.id)}`, { method: 'PUT', body: patch })
      haptic('tap')
    } catch (e) { host.notifyError(String(e)); reload() }
  }, [])

  const deleteNode = useCallback(async (node) => {
    setBoard((b) => ({
      ...b,
      nodes: b.nodes.filter((n) => n.id !== node.id),
      edges: b.edges.filter((e) => e.source !== node.id && e.target !== node.id),
    }))
    try {
      await api(`/boards/main/nodes/${encodeURIComponent(node.id)}`, { method: 'DELETE' })
      haptic('tap')
    } catch (e) { host.notifyError(String(e)); reload() }
  }, [])

  const addNote = useCallback(async () => {
    try {
      const n = (board?.nodes?.length || 0)
      await api(`/boards/main/notes?x=${40 + (n % 3) * 300}&y=${40 + Math.floor(n / 3) * 180}`, {
        method: 'POST', body: { title: 'Note', text: '' },
      })
      await reload()
      haptic('tap')
    } catch (e) { host.notifyError(String(e)) }
  }, [board])

  const onFocusNode = useCallback((node, e) => {
    setSelected(node.id)
    const b = viewportRef.current?.getBoundingClientRect()
    if (!b || node.id === 'chat') return
    setPosDrag({ id: node.id, dx: e.clientX - node.x, dy: e.clientY - node.y })
  }, [])

  useEffect(() => {
    if (!posDrag) return
    const move = (e) => {
      if (posDrag && !posDrag.moved) setPosDrag((d) => ({ ...d, moved: true }))
    }
    const up = async (e) => {
      const b = viewportRef.current?.getBoundingClientRect()
      if (posDrag.moved && b) {
        const nx = Math.max(0, e.clientX - b.left + viewportRef.current.scrollLeft - posDrag.dx)
        const ny = Math.max(0, e.clientY - b.top + viewportRef.current.scrollTop - posDrag.dy)
        setBoard((bd) => ({ ...bd, nodes: bd.nodes.map((n) => n.id === posDrag.id ? { ...n, x: nx, y: ny } : n) }))
        try { await api(`/boards/main/nodes/${encodeURIComponent(posDrag.id)}?x=${nx}&y=${ny}`, { method: 'PATCH' }) } catch {}
      }
      setPosDrag(null)
    }
    window.addEventListener('mousemove', move); window.addEventListener('mouseup', up)
    return () => { window.removeEventListener('mousemove', move); window.removeEventListener('mouseup', up) }
  }, [posDrag])

  const sendChat = useCallback(async () => {
    const q = question.trim()
    if (!q || chatBusy) return
    setChatBusy(true); setResult(null)
    const answerNode = { id: 'answer' }
    try {
      const r = await api('/chat', { method: 'POST', body: { board_id: 'main', question: q, node_ids: connected } })
      setResult(r); haptic('tap')
    } catch (e) { setResult({ error: String(e) }) }
    setChatBusy(false)
  }, [question, chatBusy, connected])

  if (!board) {
    return jsx('div', { style: { padding: 16, color: 'var(--ui-text-tertiary, #8f8da6)' }, children: 'Loading canvas\u2026' })
  }

  const nodes = board.nodes || []
  const CHAT_X = 1040, CHAT_Y = 64

  return jsxs('div', {
    style: { position: 'relative', height: '100%', display: 'flex', flexDirection: 'column' },
    children: [
      // toolbar
      jsxs('div', {
        style: { display: 'flex', gap: 8, padding: '10px 14px', alignItems: 'center', flexShrink: 0,
          borderBottom: '1px solid var(--ui-stroke-secondary, rgba(140,140,170,0.3))' },
        children: [
          jsx('span', { style: { fontWeight: 700, fontSize: 13, color: BRAND_TINT }, children: 'Yaku Canvas' }),
          jsx('input', {
            value: newUrl, placeholder: 'Paste a YouTube/TikTok/Reddit/web link or a note\u2026',
            onChange: (e) => setNewUrl(e.target.value),
            onKeyDown: (e) => { if (e.key === 'Enter') addSource() },
            style: { flex: 1, maxWidth: 460, height: 30, fontSize: 12.5, borderRadius: 8,
              padding: '0 10px', background: 'transparent',
              border: '1px solid var(--ui-stroke-secondary, rgba(140,140,170,0.35))',
              color: 'var(--ui-text-primary, #fafafa)', outline: 'none' },
          }),
          jsx('button', { onClick: addSource, disabled: adding || !newUrl.trim(),
            style: { height: 30, padding: '0 12px', fontSize: 12, borderRadius: 8, border: 'none',
              background: BRAND, color: '#fff', fontWeight: 600, cursor: 'pointer',
              opacity: adding || !newUrl.trim() ? 0.5 : 1 },
            children: adding ? 'Fetching\u2026' : '+ Add source' }),
          jsx('button', { onClick: addNote,
            style: { height: 30, padding: '0 12px', fontSize: 12, borderRadius: 8,
              border: `1px solid ${BRAND_LINE}`, background: 'transparent', color: BRAND_TINT,
              fontWeight: 600, cursor: 'pointer' },
            children: '+ Note' }),
          jsx('span', {
            style: { fontSize: 11.5, color: 'var(--ui-text-quaternary, #77768c)', marginLeft: 'auto' },
            children: `${connected.length}/${nodes.length} sources wired \u00B7 board "${board.name}"`,
          }),
        ],
      }),
      // canvas viewport
      jsx('div', {
        ref: viewportRef,
        onMouseDown: (e) => { if (e.target === e.currentTarget) setSelected(null) },
        style: {
          position: 'relative', flex: 1, overflow: 'auto',
          backgroundImage: 'radial-gradient(circle at 1px 1px, var(--ui-stroke-secondary, rgba(140,140,170,0.22)) 1px, transparent 0)',
          backgroundSize: '22px 22px',
        },
        children: jsx('div', {
          style: { position: 'relative', width: BOARD_W, height: BOARD_H },
          children: jsxs(Fragment, {
            children: [
              jsx(Wires, { nodes, edges, onCut: cutEdge }),
              nodes.map((n) => jsx(SourceCard, {
                key: n.id, node: { ...n, connected: connectedSet.has(n.id) },
                selected: selected === n.id, onFocus: onFocusNode, onConnect: connect,
                onDelete: deleteNode, onEdit: editNode,
              })),
              jsx(ChatNode, { x: CHAT_X, y: CHAT_Y, selected: selected === 'chat',
                connectedCount: connected.length, busy: chatBusy, onFocus: onFocusNode }),
              (result || chatBusy) && jsx('div', {
                style: {
                  position: 'absolute', left: 700, top: 190, width: 500, maxHeight: 430,
                  overflow: 'auto', borderRadius: 12, padding: '12px 14px', fontSize: 12, zIndex: 4,
                  border: `1px solid ${BRAND_LINE}`,
                  background: 'var(--ui-card, var(--card, transparent))',
                  color: 'var(--ui-text-primary, #fafafa)',
                  boxShadow: '0 8px 24px rgba(0,0,0,0.3)', whiteSpace: 'pre-wrap',
                },
                children: chatBusy
                  ? '\u2026grounded on the connected sources'
                  : jsxs(Fragment, {
                      children: [
                        jsx('div', { children: result.answer || result.error || 'no answer' }),
                        jsxs('div', {
                          style: { marginTop: 8, fontSize: 10.5, color: 'var(--ui-text-quaternary, #77768c)' },
                          children: [`${result.model || ''} \u00B7 ${(result.sources || []).length} sources cited`],
                        }),
                      ],
                    }),
              }),
            ],
          }),
        }),
      }),
      // composer
      jsxs('div', {
        style: { display: 'flex', gap: 8, padding: '10px 14px', flexShrink: 0,
          borderTop: '1px solid var(--ui-stroke-secondary, rgba(140,140,170,0.3))' },
        children: [
          jsx('input', {
            value: question,
            placeholder: chatBusy ? 'Grounding\u2026'
              : `Write grounded in the ${connected.length} connected sources\u2026`,
            onChange: (e) => setQuestion(e.target.value),
            onKeyDown: (e) => { if (e.key === 'Enter') sendChat() },
            style: { flex: 1, height: 32, fontSize: 12.5, borderRadius: 8, padding: '0 10px',
              background: 'transparent',
              border: '1px solid var(--ui-stroke-secondary, rgba(140,140,170,0.35))',
              color: 'var(--ui-text-primary, #fafafa)', outline: 'none' },
          }),
          jsx('button', {
            onClick: sendChat, disabled: chatBusy || !connected.length || !question.trim(),
            style: { height: 32, padding: '0 14px', fontSize: 12.5, borderRadius: 8, border: 'none',
              background: BRAND, color: '#fff', fontWeight: 600, cursor: 'pointer',
              opacity: chatBusy || !connected.length || !question.trim() ? 0.5 : 1 },
            children: 'Write',
          }),
        ],
      }),
    ],
  })
}

/* ---------------- registration ---------------- */
export default {
  id: ID,
  name: 'Yaku Canvas',
  register(ctx) {
    CTX = ctx
    // Full page = a tab in the workspace (main) pane, like Sessions/Files/Terminal.
    ctx.register({
      id: 'page',
      area: ROUTES_AREA,
      title: 'Yaku Canvas',
      data: { path: '/yaku' },
      render: () => jsx(CanvasPage, {}),
    })
    // Sidebar row that lights up at the route.
    ctx.register({
      id: 'nav',
      area: SIDEBAR_NAV_AREA,
      data: { path: '/yaku', label: 'Yaku Canvas', codicon: 'layout' },
    })
    // ⌘K command.
    ctx.register({
      id: 'open',
      area: PALETTE_AREA,
      data: {
        id: 'yaku-canvas.open', label: 'Open Yaku Canvas',
        keywords: ['yaku', 'canvas', 'script', 'content'],
        run: () => host.navigate('/yaku'),
      },
    })
  },
}