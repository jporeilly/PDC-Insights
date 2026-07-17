import { useCallback, useEffect, useRef, useState } from 'react'
import { authHeaders, getApiKey, setApiKey, getJSON, postJSON } from '../api.js'
import DocModal from '../components/DocModal.jsx'
import { SECTION_META } from '../data/dashboards.jsx'

/* The in-app AI dashboard builder, ported from ui/mock/chat.html.
   Talks to the same-origin API:
     POST /api/chat               → build/refine a dashboard spec from the conversation
     GET  /api/recommend          → section-aware suggestions shown as starter chips
     POST /api/dashboards         → save the built spec into the catalog (steward)
     POST /api/dashboards/resolve → overlay real numbers on the preview
     GET  /api/snapshot, /health/llm → header status badges
   State per section is persisted in localStorage so context survives
   refreshes and navigation, exactly like the mock. */

const STORE_KEY = (section) => 'pdc-chat:' + (section || 'any')

/* A governance-aware palette: brand family + the trust spectrum, so
   categorical charts read as distinct, meaningful colours. */
const PALETTE = ['var(--c1)', 'var(--high)', 'var(--mid)', 'var(--low)', 'var(--c2)', 'var(--c4)', 'var(--c6)', 'var(--c3)']
const fmtNum = (n) => (typeof n === 'number' ? n.toLocaleString() : (n ?? '—'))

/* ---- placeholder mini-charts (shown until the resolver fills real data) --- */
function MiniPlaceholder({ type }) {
  if (type === 'donut' || type === 'pie') {
    const segs = [38, 24, 18, 12, 8]; const R = 24; const Cc = 2 * Math.PI * R; let off = 0
    return (
      <svg width="100%" height="72" viewBox="0 0 64 64">
        <circle cx="32" cy="32" r={R} fill="none" stroke="var(--surface-1)" strokeWidth="12" />
        {segs.map((v, i) => {
          const len = (Cc * v) / 100
          const el = <circle key={i} cx="32" cy="32" r={R} fill="none" stroke={PALETTE[i % PALETTE.length]}
                             strokeWidth="12" strokeDasharray={`${len} ${Cc - len}`} strokeDashoffset={-off}
                             transform="rotate(-90 32 32)" />
          off += len
          return el
        })}
      </svg>
    )
  }
  if (type === 'line' || type === 'area') {
    return (
      <svg width="100%" height="72" viewBox="0 0 160 64" preserveAspectRatio="none">
        <polyline points="0,50 30,38 60,42 90,22 120,28 160,10" fill="none" stroke="var(--c1)" strokeWidth="3" />
        <polyline points="0,58 30,52 60,48 90,40 120,36 160,30" fill="none" stroke="var(--mid)" strokeWidth="2.5" strokeDasharray="4 3" />
      </svg>
    )
  }
  if (type === 'gauge' || type === 'bullet') {
    return (
      <svg width="100%" height="72" viewBox="0 0 160 24">
        <rect width="160" height="10" rx="5" fill="var(--surface-1)" />
        <rect width="52" height="10" rx="5" fill="var(--low)" />
        <rect x="52" width="40" height="10" fill="var(--mid)" />
        <rect x="92" width="44" height="10" rx="5" fill="var(--high)" />
        <rect x="100" y="-3" width="3" height="16" fill="var(--text-primary)" />
      </svg>
    )
  }
  const bars = [34, 52, 28, 46, 60, 38]; const w = 18; const g = 8
  return (
    <svg width="100%" height="72" viewBox={`0 0 ${bars.length * (w + g)} 64`}>
      {bars.map((h, i) => (
        <rect key={i} x={i * (w + g)} y={64 - h} width={w} height={h} rx="3" fill={PALETTE[i % PALETTE.length]} />
      ))}
    </svg>
  )
}

/* ---- live data renderers (real series from the resolver) ------------------ */
function BarsReal({ series }) {
  const vals = series.map((s) => s.value || 0); const max = Math.max(1, ...vals); const w = 18; const g = 8
  return (
    <svg width="100%" height="72" viewBox={`0 0 ${series.length * (w + g)} 64`}>
      {series.map((s, i) => {
        const h = Math.max(2, Math.round((56 * (s.value || 0)) / max))
        return (
          <rect key={i} x={i * (w + g)} y={64 - h} width={w} height={h} rx="3" fill={PALETTE[i % PALETTE.length]}>
            <title>{`${s.label}: ${fmtNum(s.value)}`}</title>
          </rect>
        )
      })}
    </svg>
  )
}
function DonutReal({ series }) {
  const total = series.reduce((a, s) => a + (s.value || 0), 0) || 1
  const R = 24; const Cc = 2 * Math.PI * R; let off = 0
  return (
    <svg width="100%" height="72" viewBox="0 0 64 64">
      <circle cx="32" cy="32" r={R} fill="none" stroke="var(--surface-1)" strokeWidth="12" />
      {series.map((s, i) => {
        const len = (Cc * (s.value || 0)) / total
        const el = (
          <circle key={i} cx="32" cy="32" r={R} fill="none" stroke={PALETTE[i % PALETTE.length]}
                  strokeWidth="12" strokeDasharray={`${len} ${Cc - len}`} strokeDashoffset={-off}
                  transform="rotate(-90 32 32)">
            <title>{`${s.label}: ${fmtNum(s.value)}`}</title>
          </circle>
        )
        off += len
        return el
      })}
    </svg>
  )
}
function LineReal({ series }) {
  const vals = series.map((s) => s.value || 0)
  const max = Math.max(1, ...vals); const min = Math.min(...vals, 0)
  const pts = series.map((s, i) => {
    const x = series.length > 1 ? (i / (series.length - 1)) * 160 : 0
    const y = 58 - 52 * (((s.value || 0) - min) / ((max - min) || 1))
    return `${x.toFixed(0)},${y.toFixed(0)}`
  }).join(' ')
  return (
    <svg width="100%" height="72" viewBox="0 0 160 64" preserveAspectRatio="none">
      <polyline points={pts} fill="none" stroke="var(--c1)" strokeWidth="3" />
    </svg>
  )
}
function StackedReal({ data }) {
  const cats = data.categories || []; const groups = data.groups || []; const w = 22; const g = 14
  const totals = cats.map((_, i) => groups.reduce((a, gr) => a + (gr.values[i] || 0), 0))
  const max = Math.max(1, ...totals)
  return (
    <svg width="100%" height="80" viewBox={`0 0 ${cats.length * (w + g)} 70`}>
      {cats.map((c, i) => {
        let y = 64
        return groups.map((gr, gi) => {
          const h = Math.round((58 * (gr.values[i] || 0)) / max); y -= h
          return (
            <rect key={`${i}-${gi}`} x={i * (w + g)} y={y} width={w} height={h} fill={PALETTE[gi % PALETTE.length]}>
              <title>{`${c} · ${gr.name}: ${fmtNum(gr.values[i])}`}</title>
            </rect>
          )
        })
      })}
    </svg>
  )
}
function TableReal({ cols, rows }) {
  if (!rows || !rows.length) return <div className="meta muted">No rows.</div>
  return (
    <table className="ptbl">
      <thead><tr>{cols.map((c) => <th key={c}>{c}</th>)}</tr></thead>
      <tbody>
        {rows.slice(0, 6).map((r, i) => (
          <tr key={i}>{r.map((c, j) => <td key={j}>{fmtNum(c)}</td>)}</tr>
        ))}
      </tbody>
    </table>
  )
}

function PanelBody({ p, live }) {
  if (live) {
    if (live.kind === 'kpi') return <div className="kpi-num">{fmtNum(live.value)}{live.unit || ''}</div>
    if (live.kind === 'table') return <TableReal cols={live.columns} rows={live.rows} />
    if (live.kind === 'chart') {
      const t = live.chartType
      if (live.groups) {
        if (t === 'stackedBar' || t === 'stacked') return <StackedReal data={live} />
        const cats = live.categories || []; const g0 = (live.groups[0] || {}).values || []
        const s = cats.map((c, i) => ({ label: c, value: g0[i] || 0 }))
        return (t === 'donut' || t === 'pie') ? <DonutReal series={s} />
          : (t === 'line' || t === 'area') ? <LineReal series={s} /> : <BarsReal series={s} />
      }
      const s = live.series || []
      return (t === 'donut' || t === 'pie') ? <DonutReal series={s} />
        : (t === 'line' || t === 'area') ? <LineReal series={s} /> : <BarsReal series={s} />
    }
  }
  if (p.kind === 'kpi') return <div className="kpi-num">—</div>
  if (p.kind === 'table') {
    return (
      <svg width="100%" height="64" viewBox="0 0 160 64">
        <rect width="160" height="12" fill="var(--surface-1)" />
        <rect y="18" width="160" height="10" fill="var(--surface-1)" opacity=".6" />
        <rect y="32" width="160" height="10" fill="var(--surface-1)" opacity=".6" />
        <rect y="46" width="160" height="10" fill="var(--surface-1)" opacity=".6" />
      </svg>
    )
  }
  if (p.kind === 'text') return <div className="meta">{(p.markdown || '').slice(0, 80)}</div>
  return <MiniPlaceholder type={p.chartType} />
}

/* A plain-language summary of the built dashboard, derived from the spec — no
   extra model call. Rendered as markdown in a DocModal. */
function summaryText(spec) {
  const panels = spec.panels || []
  const kpis = panels.filter((p) => p.kind === 'kpi')
  const charts = panels.filter((p) => p.kind === 'chart')
  const tables = panels.filter((p) => p.kind === 'table')
  const lines = [`This **${spec.category}** dashboard, “${spec.title}”, has ${panels.length} panel(s).`]
  if (kpis.length) lines.push(`${kpis.length} headline metric(s): ${kpis.map((p) => p.title).join(', ')}.`)
  if (charts.length) lines.push(`${charts.length} chart(s): ${charts.map((p) => `${p.title} (${p.chartType})`).join(', ')}.`)
  if (tables.length) lines.push(`${tables.length} detail table(s): ${tables.map((p) => p.title).join(', ')}.`)
  lines.push('')
  panels.forEach((p) => {
    const b = p.bindings || {}
    const dims = b.category || b.x || ''; const val = b.value || b.y || ''
    const how = p.kind === 'kpi' ? `headline value from \`${p.query}\``
      : p.kind === 'table' ? `row-level detail from \`${p.query}\``
        : `${p.chartType} of \`${p.query}\`${dims ? ` by ${dims}` : ''}${val ? `, measuring ${val}` : ''}`
    lines.push(`- **${p.title}** — ${how}`)
  })
  return lines.join('\n')
}

export default function ChatPage({ section: initialSection }) {
  const [section, setSection] = useState(initialSection || '')
  const [messages, setMessages] = useState([])
  const [spec, setSpec] = useState(null)
  const [valid, setValid] = useState(false)
  const [busy, setBusy] = useState(false)
  const [input, setInput] = useState('')
  const [thinking, setThinking] = useState(null)      // transient status line
  const [chips, setChips] = useState([])
  const [live, setLive] = useState(null)              // resolver output for the preview
  const [pdcBadge, setPdcBadge] = useState({ text: 'PDC…', cls: '' })
  const [llmBadge, setLlmBadge] = useState({ text: 'LLM…', cls: '' })
  const [apiKey, setKey] = useState(getApiKey())
  const [saved, setSaved] = useState(null)             // {text, err}
  const [showSummary, setShowSummary] = useState(false)
  const transcriptRef = useRef(null)

  const persist = useCallback((sec, msgs, sp) => {
    try {
      localStorage.setItem(STORE_KEY(sec), JSON.stringify({ messages: msgs, spec: sp, ts: Date.now() }))
    } catch { /* ignore */ }
  }, [])

  const restore = useCallback((sec) => {
    try {
      const raw = localStorage.getItem(STORE_KEY(sec))
      if (!raw) return false
      const d = JSON.parse(raw)
      if (!d || !Array.isArray(d.messages) || !d.messages.length) return false
      setMessages(d.messages); setSpec(d.spec || null); setValid(!!d.spec)
      return true
    } catch { return false }
  }, [])

  /* status badges */
  useEffect(() => {
    getJSON('/api/snapshot')
      .then((h) => setPdcBadge({ text: h.demo ? 'PDC: demo data' : 'PDC: live', cls: h.demo ? 'warn' : 'ok' }))
      .catch(() => setPdcBadge({ text: 'PDC: ?', cls: '' }))
    getJSON('/health/llm')
      .then((l) => setLlmBadge({ text: 'LLM: ' + (l.ok ? (l.model || 'ready') : 'offline'), cls: l.ok ? 'ok' : 'warn' }))
      .catch(() => setLlmBadge({ text: 'LLM: offline', cls: 'warn' }))
  }, [apiKey])

  /* section-aware starter chips */
  useEffect(() => {
    const url = '/api/recommend' + (section ? `?section=${encodeURIComponent(section)}` : '')
    getJSON(url)
      .then((recs) => {
        if (Array.isArray(recs) && recs.length) {
          setChips(recs.slice(0, 6).map((r) => ({
            label: (r.priority === 'high' ? '★ ' : '') + r.title,
            title: r.why + (r.priority ? `  ·  ${r.priority} priority` : ''),
            prompt: r.generate_prompt || r.title,
          })))
        } else throw new Error('empty')
      })
      .catch(() => setChips([
        { label: 'Build a dashboard for this section', prompt: 'Build a dashboard for this section' },
        { label: 'Suggest dashboards from my scans', prompt: 'Suggest dashboards from my scans' },
      ]))
  }, [section, apiKey])

  /* restore this section's saved thread on mount + section change */
  useEffect(() => {
    if (!restore(section)) { setMessages([]); setSpec(null); setValid(false) }
    setSaved(null); setShowSummary(false); setLive(null)
  }, [section, restore])

  /* overlay real numbers on the preview whenever the spec changes */
  useEffect(() => {
    let gone = false
    setLive(null)
    if (!spec) return undefined
    postJSON('/api/dashboards/resolve', spec)
      .then((d) => { if (!gone) setLive(d) })
      .catch(() => {})
    return () => { gone = true }
  }, [spec])

  useEffect(() => {
    const t = transcriptRef.current
    if (t) t.scrollTop = t.scrollHeight
  }, [messages, thinking])

  async function send(text) {
    if (busy || !text.trim()) return
    setBusy(true)
    const msgs = [...messages, { role: 'user', content: text }]
    setMessages(msgs); setInput(''); setThinking('…thinking')
    try {
      const r = await fetch('/api/chat', {
        method: 'POST', headers: authHeaders(),
        body: JSON.stringify({ messages: msgs, spec, section: section || null }),
      })
      if (r.status === 401) { setThinking('Unauthorized — enter an API key above.'); return }
      if (r.status === 403) { setThinking('Forbidden — your role can’t do that.'); return }
      const d = await r.json()
      setThinking(null)
      const next = [...msgs, { role: 'assistant', content: d.reply || 'Done.' }]
      setMessages(next)
      let sp = spec
      if (d.spec) { sp = d.spec; setSpec(d.spec); setValid(!!d.valid); setSaved(null) }
      persist(section, next, sp)
    } catch (e) {
      setThinking('Error: ' + e.message)
    } finally {
      setBusy(false)
    }
  }

  async function addToDashboards() {
    if (!spec) return
    try {
      const d = await postJSON('/api/dashboards', spec)
      if (d.saved) {
        setSaved({ text: `Added ✓  ${d.path} — open the ${spec.category} section in the app to see it.` })
      }
    } catch (e) {
      if (e.status === 403) setSaved({ text: 'Saving needs the steward role. Enter a steward API key above.', err: true })
      else setSaved({ text: 'Could not save: ' + (e.data?.errors ? e.data.errors.join('; ') : e.message), err: true })
    }
  }

  function downloadSpec() {
    if (!spec) return
    const slug = (spec.title || 'dashboard').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
    const blob = new Blob([JSON.stringify(spec, null, 2)], { type: 'application/json' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = slug + '.studio.json'
    a.click(); URL.revokeObjectURL(a.href)
  }

  function clearChat() {
    try { localStorage.removeItem(STORE_KEY(section)) } catch { /* ignore */ }
    setMessages([]); setSpec(null); setValid(false); setLive(null); setSaved(null)
  }

  function changeSection(next) {
    persist(section, messages, spec)     // keep the current section's thread
    setSection(next)
  }

  const label = section ? section[0].toUpperCase() + section.slice(1) : 'any'

  return (
    <div>
      <div className="page-head">
        <div>
          <h1>AI Dashboard Builder</h1>
          <p>Describe the dashboard you want — it’s built from your real catalog queries, and you can add it to the catalog when it’s right.</p>
        </div>
      </div>

      <div className="chat-shell">
        <section className="chat-col">
          <div className="chat-head">
            <select className="b" value={section} onChange={(e) => changeSection(e.target.value)}
                    title="Suggestions and new dashboards target this Analytics section">
              <option value="">Any section</option>
              {Object.entries(SECTION_META).map(([id, m]) => (
                <option key={id} value={id}>{m.name}</option>
              ))}
            </select>
            <span className={`b ${pdcBadge.cls}`}>{pdcBadge.text}</span>
            <span className={`b ${llmBadge.cls}`}>{llmBadge.text}</span>
            <input className="b" placeholder="API key (if auth on)" autoComplete="off"
                   value={apiKey}
                   onChange={(e) => { setKey(e.target.value); setApiKey(e.target.value.trim()) }} />
            <button className="b" style={{ cursor: 'pointer' }} onClick={clearChat}
                    title="Clear this section's saved conversation and start fresh">Clear chat</button>
          </div>
          <div className="transcript" ref={transcriptRef}>
            <div className="msg sys">
              Describe the dashboard you want — I’ll build it for the {label} section and you can add it to the catalog. Or pick a suggestion below.
            </div>
            {messages.map((m, i) => (
              <div key={i} className={`msg ${m.role === 'user' ? 'user' : 'bot'}`}>{m.content}</div>
            ))}
            {thinking && <div className="msg sys">{thinking}</div>}
          </div>
          <div className="chips">
            {chips.map((c, i) => (
              <span key={i} className="chip" title={c.title} onClick={() => send(c.prompt)}>{c.label}</span>
            ))}
          </div>
          <div className="composer">
            <textarea value={input} placeholder="e.g. Show sensitive, unowned assets by source…"
                      onChange={(e) => setInput(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(input) }
                      }} />
            <button className="primary" disabled={busy} onClick={() => send(input)}>Send</button>
          </div>
        </section>

        <section className="chat-col">
          <div className="pv-head">
            <h2>{spec ? (spec.title || 'Dashboard') : 'No dashboard yet'}</h2>
            {spec && <span className="cat">{spec.category}</span>}
            {live && (
              <span className={`data-badge ${live.demo ? 'demo' : 'live'}`}>
                {live.demo ? 'demo data' : 'live data'}
              </span>
            )}
            <button className="ghost sm" disabled={!spec} onClick={() => setShowSummary(true)}
                    title="Show a plain-language summary of this dashboard">Summary</button>
            <button className="ghost sm" disabled={!spec} onClick={downloadSpec}
                    title="Download this dashboard as a .studio.json spec file">Download</button>
            <button className="ghost sm" disabled={!spec} onClick={() => window.print()}
                    title="Print the dashboard or save it as a PDF">Print</button>
            <button className="primary sm" disabled={!spec || !valid || !!saved?.text && !saved.err}
                    onClick={addToDashboards}
                    title="Save this dashboard into the catalog (needs the steward role when auth is on)">
              Add to dashboards
            </button>
          </div>
          <div className="print-head">
            <span className="pt">{spec?.title || ''}</span>
            <span className="pm">AI Builder · generated {new Date().toISOString().slice(0, 10)}</span>
          </div>
          <div className="pv-grid">
            {spec && (spec.panels || []).length
              ? spec.panels.map((p) => {
                const b = Object.entries(p.bindings || {}).map(([k, v]) => `${k}: ${v}`).join(' · ')
                const tag = p.kind === 'chart' ? p.chartType : p.kind
                return (
                  <div key={p.id} className={`pv-panel${p.span >= 2 ? ' span2' : ''}`}>
                    <div className="pt">{p.title}</div>
                    <div className="pbody">
                      <PanelBody p={p} live={live?.panels?.[p.id]} />
                    </div>
                    <div className="meta">{tag} · {p.query}{b ? ' · ' + b : ''}</div>
                  </div>
                )
              })
              : <div className="pv-empty">The dashboard you build will preview here.</div>}
          </div>
          {saved && <div className={`saved-note${saved.err ? ' err' : ''}`}>{saved.text}</div>}
        </section>
      </div>

      {showSummary && spec && (
        <DocModal title="What this dashboard shows" text={summaryText(spec)}
                  onClose={() => setShowSummary(false)} />
      )}
    </div>
  )
}
