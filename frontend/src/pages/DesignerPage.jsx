import { useEffect, useRef, useState } from 'react'
import { postJSON } from '../api.js'
import { LIB, CHART_ICONS, SCORE } from '../data/dashboards.jsx'
import { Donut, Bars, Stacked } from '../components/charts.jsx'

/* Dashboard Designer, ported from the mock: a query library, a canvas of
   panels, an inspector, and the "Generate a dashboard" AI drawer. The drawer
   runs a real single-turn build through POST /api/chat and hands the result
   to the AI Builder for refinement. */

const SAMPLE_PANELS = [
  { title: 'Trust by source', chart: 'stacked' },
  { title: 'Sensitivity mix', chart: 'donut' },
  { title: 'Quality vs target', chart: 'bar' },
  { title: 'PII discoveries', chart: 'bar' },
]

const EXAMPLES = [
  { b: 'Stewardship', t: 'owned vs unowned assets per source, plus top owners' },
  { b: 'Privacy review', t: 'sensitivity mix and every PII type discovered' },
  { b: 'Quality deep-dive', t: 'score distribution and the five DQ dimensions' },
]

const GEN_STEPS = ['Reading prompt', 'Grounding on the catalog queries', 'Drafting spec', 'Validating against schema']

function SamplePanel({ idx }) {
  switch (idx) {
    case 0:
      return <Stacked h={160}
        data={[{ k: 'Snow', Untrusted: 300, Trusted: 600, Highly: 900 }, { k: 'S3', Untrusted: 700, Trusted: 400, Highly: 200 }, { k: 'PG', Untrusted: 200, Trusted: 700, Highly: 500 }]}
        keys={['Untrusted', 'Trusted', 'Highly']} colors={SCORE} />
    case 1:
      return <Donut data={[{ k: 'Low', v: 9180, c: 'var(--high)' }, { k: 'Med', v: 2458, c: 'var(--mid)' }, { k: 'High', v: 842, c: 'var(--low)' }]} />
    case 2:
      return <Bars data={[{ k: 'Snowflake', v: 86 }, { k: 'Postgres', v: 78 }, { k: 'S3-raw', v: 64 }, { k: 'Oracle', v: 81 }]} h={160} max={100} />
    default:
      return <Bars data={[{ k: 'EMAIL', v: 1203 }, { k: 'PHONE', v: 980 }, { k: 'SSN', v: 412 }, { k: 'DOB', v: 540 }]} h={160} color="var(--c5)" />
  }
}

export default function DesignerPage({ onOpenChat, llm }) {
  const [selected, setSelected] = useState(0)
  const [chartType, setChartType] = useState('stacked')
  const [drawer, setDrawer] = useState(false)
  const [prompt, setPrompt] = useState('Trust score and PII coverage by data source, with the worst tables called out')
  const [doneSteps, setDoneSteps] = useState(0)
  const [genBusy, setGenBusy] = useState(false)
  const [genResult, setGenResult] = useState(null)   // {spec, valid, reply} | {error}
  const timers = useRef([])

  useEffect(() => () => timers.current.forEach(clearTimeout), [])

  function openDrawer() { setDrawer(true) }
  function closeDrawer() {
    setDrawer(false); setGenResult(null); setDoneSteps(0); setGenBusy(false)
    timers.current.forEach(clearTimeout); timers.current = []
  }

  async function runGen() {
    if (genBusy) return
    setGenBusy(true); setGenResult(null); setDoneSteps(0)
    timers.current.forEach(clearTimeout)
    // pace the step ticks while the real build runs
    timers.current = GEN_STEPS.map((_, i) =>
      setTimeout(() => setDoneSteps((d) => Math.max(d, i + 1)), (i + 1) * 480))
    try {
      const d = await postJSON('/api/chat', {
        messages: [{ role: 'user', content: prompt }], spec: null, section: null,
      })
      setDoneSteps(GEN_STEPS.length)
      setGenResult(d.spec ? { spec: d.spec, valid: d.valid, reply: d.reply } : { error: d.reply || 'No spec returned.' })
    } catch (e) {
      setGenResult({ error: e.status === 401 ? 'Unauthorized — set your API key in the AI Builder.' : e.message })
    } finally {
      setGenBusy(false)
    }
  }

  function openInBuilder() {
    const { spec, reply } = genResult
    // Seed the AI Builder's saved thread so refinement continues seamlessly.
    try {
      localStorage.setItem('pdc-chat:' + (spec.category || 'any'), JSON.stringify({
        messages: [{ role: 'user', content: prompt }, { role: 'assistant', content: reply || 'Built.' }],
        spec, ts: Date.now(),
      }))
    } catch { /* ignore */ }
    closeDrawer()
    onOpenChat(spec.category || '')
  }

  return (
    <div>
      <div className="page-head">
        <div>
          <h1>Dashboard Designer</h1>
          <p>Build and edit dashboards from the query library, or generate a starting point with AI.</p>
        </div>
      </div>

      <div className="ai-bar">
        <svg width="17" height="17" viewBox="0 0 24 24" fill="none">
          <path d="M12 3l1.6 4.4L18 9l-4.4 1.6L12 15l-1.6-4.4L6 9l4.4-1.6L12 3Z" fill="currentColor" />
        </svg>
        <input placeholder="Describe a dashboard, or drag a query onto the canvas…" readOnly onClick={openDrawer} />
        <button className="primary sm" onClick={openDrawer}>Generate</button>
      </div>

      <div className="designer">
        <div className="dz-pane">
          <div className="dz-h"><h3>Query Library</h3><button className="mini">+ New source</button></div>
          <div className="dz-body">
            {LIB.map((grp) => (
              <div key={grp.g}>
                <div className="da-grp">{grp.g}</div>
                {grp.items.map(([n, c]) => (
                  <div className="da" key={n} title={`columns: ${c}`}>
                    <div className="da-name">
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none">
                        <rect x="4" y="4" width="16" height="16" rx="2" stroke="var(--accent)" strokeWidth="2" />
                        <path d="M4 9h16M9 9v11" stroke="var(--accent)" strokeWidth="1.5" />
                      </svg>
                      {n}
                    </div>
                    <div className="da-cols">{c}</div>
                  </div>
                ))}
              </div>
            ))}
          </div>
        </div>

        <div>
          <div className="canvas-grid">
            {SAMPLE_PANELS.map((p, i) => (
              <div key={p.title} className={`panel-card s2${i === selected ? ' sel' : ''}`}
                   onClick={() => setSelected(i)} style={{ cursor: 'pointer' }}>
                <div className="card-h"><h3>{p.title}</h3></div>
                <SamplePanel idx={i} />
              </div>
            ))}
          </div>
        </div>

        <div className="dz-pane">
          <div className="dz-h"><h3>Inspector</h3><span className="chip-tag">Panel</span></div>
          <div className="dz-body">
            <div className="insp-field">
              <label>Panel title</label>
              <input defaultValue={SAMPLE_PANELS[selected].title} key={selected} />
            </div>
            <div className="insp-field">
              <label>Data access</label>
              <select defaultValue="trust_by_source">
                <option>trust_by_source</option>
                <option>sensitivity_mix</option>
                <option>quality_by_source</option>
              </select>
            </div>
            <div className="insp-field">
              <label>Chart type</label>
              <div className="chart-pick">
                {['stacked', 'bar', 'donut', 'line', 'table', 'gauge', 'radar', 'heatmap'].map((t) => (
                  <button key={t} className={`cp${chartType === t ? ' on' : ''}`} title={t}
                          onClick={() => setChartType(t)}>
                    {CHART_ICONS[t] || '▭'}
                  </button>
                ))}
              </div>
            </div>
            <div className="insp-field">
              <label>Category (x)</label>
              <select defaultValue="source"><option>source</option><option>bucket</option></select>
            </div>
            <div className="insp-field">
              <label>Value (y)</label>
              <select defaultValue="count"><option>count</option></select>
            </div>
            <div className="insp-field">
              <label>Series</label>
              <select defaultValue="bucket"><option>bucket</option><option>— none —</option></select>
            </div>
          </div>
        </div>
      </div>

      {drawer && (
        <>
          <div className="scrim" onClick={closeDrawer} />
          <aside className="drawer">
            <div className="drawer-h">
              <h2>
                <svg width="19" height="19" viewBox="0 0 24 24" fill="none">
                  <path d="M12 3l1.6 4.4L18 9l-4.4 1.6L12 15l-1.6-4.4L6 9l4.4-1.6L12 3Z" fill="var(--accent)" />
                  <path d="M19 14l.8 2.2L22 17l-2.2.8L19 20l-.8-2.2L16 17l2.2-.8L19 14Z" fill="var(--accent)" />
                </svg>
                Generate a dashboard
              </h2>
              <p>Describe what you want to see. The model builds it from your real catalog queries — you refine before anything saves.</p>
            </div>
            <div className="drawer-body">
              <div className="prompt-box">
                <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)}
                          placeholder="e.g. Trust score and PII coverage by data source, with the worst tables called out" />
              </div>
              <div style={{ fontSize: '.68rem', textTransform: 'uppercase', letterSpacing: '.06em', color: 'var(--text-muted)', fontWeight: 650, margin: '4px 2px 8px' }}>
                Try one of these
              </div>
              <div className="examples">
                {EXAMPLES.map((ex) => (
                  <button key={ex.b} className="ex" onClick={() => setPrompt(ex.t)}>
                    <b>{ex.b}</b> — {ex.t}
                  </button>
                ))}
              </div>
              <div style={{ marginTop: 12 }}>
                {(genBusy || genResult) && GEN_STEPS.map((s, i) => (
                  <div key={s} className={`gen-step${i < doneSteps ? ' done' : ''}`}>
                    <span className="gs-dot" />{s}
                  </div>
                ))}
                {genResult?.error && <div className="error">{genResult.error}</div>}
                {genResult?.spec && (
                  <div className="gen-preview">
                    <div className="gp-h">{genResult.spec.title} · {genResult.spec.category}</div>
                    <div className="gp-b">
                      {(genResult.spec.panels || []).map((p) => (
                        <div key={p.id} className="gp-panel">
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                            <rect x="3" y="10" width="4" height="11" fill="currentColor" />
                            <rect x="10" y="5" width="4" height="16" fill="currentColor" />
                            <rect x="17" y="13" width="4" height="8" fill="currentColor" />
                          </svg>
                          {p.kind === 'chart' ? p.chartType : p.kind} — {p.title} · <span className="mono">{p.query}</span>
                        </div>
                      ))}
                      <div style={{ marginTop: 10, fontWeight: 650, fontSize: '.78rem' }}
                           className={genResult.valid ? 'ok' : 'warn'}>
                        {genResult.valid ? '✓ Valid' : '△ Needs fixes'} · {(genResult.spec.panels || []).length} panels
                      </div>
                    </div>
                  </div>
                )}
              </div>
              <div className="prov-tag">
                <span className={`dot ${llm?.ok ? 'ok' : 'warn'}`} style={{ width: 6, height: 6 }} />
                {llm?.ok
                  ? `${llm.provider === 'local' ? 'Running locally · ' : ''}${llm.model || 'model ready'} · metadata stays in your environment`
                  : 'LLM offline — the deterministic builder will draft instead'}
              </div>
            </div>
            <div className="drawer-foot">
              <button className="ghost" onClick={closeDrawer}>Cancel</button>
              {genResult?.spec
                ? <button className="primary" onClick={openInBuilder}>Open in AI Builder</button>
                : <button className="primary" disabled={genBusy} onClick={runGen}>{genBusy ? 'Generating…' : 'Generate'}</button>}
            </div>
          </aside>
        </>
      )}
    </div>
  )
}
