import { useCallback, useEffect, useMemo, useState } from 'react'
import { getJSON, postJSON } from '../api.js'
import {
  DASHBOARDS, SECTION_META, KPI_QUERY, TRUST_BANDS, resolverKind,
} from '../data/dashboards.jsx'
import {
  Donut, Bars, Stacked, Line, Spark, Gauge, Radar, Histo, Bullet, Calendar,
  Spectrum, MiniTable,
} from '../components/charts.jsx'

const fmtNum = (n) => (typeof n === 'number' ? n.toLocaleString() : (n ?? '—'))

/* Convert resolver output -> the props each chart renderer expects, so the
   live overlay and the baked render share the same components. */
function LiveChart({ chart, data, onRow }) {
  const series = data.series || []
  const asKV = () => series.map((s) => ({ k: s.label, v: s.value }))
  switch (chart) {
    case 'spectrum':
      return <Spectrum seg={series.map((s) => ({ k: s.label, v: s.value, r: TRUST_BANDS[s.label] || '' }))} />
    case 'donut': return <Donut data={asKV()} />
    case 'bars': return <Bars data={asKV()} h={170} max={100} />
    case 'line': return <Line series={series.map((s) => s.value)} />
    case 'stacked': {
      const cats = data.categories || []; const groups = data.groups || []
      const rows = cats.map((c, i) => {
        const o = { k: c }; groups.forEach((g) => { o[g.name] = g.values[i] || 0 }); return o
      })
      return <Stacked data={rows} keys={groups.map((g) => g.name)}
                      colors={['var(--high)', 'var(--mid)', 'var(--low)', 'var(--c2)']} />
    }
    case 'gauge': return <Gauge val={Math.round(data.value || 0)} />
    case 'radar': return <Radar axes={asKV()} />
    case 'histo': return <Histo bins={series.map((s) => ({ lo: parseInt(s.label, 10) || 0, v: s.value }))} />
    case 'bullet': return <Bullet rows={series.map((s) => ({ k: s.label, v: s.value, t: 80 }))} />
    case 'table': return <MiniTable cols={data.columns || []} rows={data.rows || []} onRow={onRow} />
    default: return null
  }
}

function BakedChart({ p, onRow }) {
  switch (p.chart) {
    case 'spectrum': return <Spectrum seg={p.data} />
    case 'donut': return <Donut data={p.data} />
    case 'bars': return <Bars data={p.data} {...(p.opts || { h: 170 })} />
    case 'line': return <Line series={p.data} {...(p.opts || {})} />
    case 'stacked': return <Stacked data={p.data} keys={p.keys} colors={p.colors} {...(p.opts || {})} />
    case 'gauge': return <Gauge val={p.val} />
    case 'radar': return <Radar axes={p.data} />
    case 'histo': return <Histo bins={p.data} />
    case 'bullet': return <Bullet rows={p.data} />
    case 'calendar': return <Calendar weeks={p.weeks || 24} />
    case 'table': return <MiniTable cols={p.cols} rows={p.rows} onRow={onRow} />
    default: return null
  }
}

function KpiTile({ p, liveVal }) {
  const arrow = p.dir === 'up' ? '▲' : p.dir === 'down' ? '▼' : ''
  return (
    <div className="panel-card">
      <div className="kpi-top">
        <div>
          <div className="kpi-label">{p.label}</div>
          <div className="kpi-val">{liveVal ?? p.val}</div>
          <div className={`kpi-delta ${p.dir}`}>{arrow} {p.delta}</div>
        </div>
        <div className="kpi-ico" style={{ background: p.tint, color: p.col }}>{p.ico}</div>
      </div>
      <div className="spark"><Spark series={p.spark} color={p.col} /></div>
    </div>
  )
}

/* Drill-through side panel: the underlying assets behind a chart or row. */
function Drill({ drill, onClose }) {
  if (!drill) return null
  return (
    <>
      <div className="drill-scrim" onClick={onClose} />
      <aside className="drill">
        <div className="drill-head">
          <h3>{drill.loading ? 'Loading…' : drill.title || 'Assets'}</h3>
          <button className="drill-x" onClick={onClose} title="Close" aria-label="Close">×</button>
        </div>
        <div className="drill-sub">
          {!drill.loading && `${(drill.rows || []).length} assets · ${drill.query}` +
            (drill.source && drill.source !== 'all' ? ` · ${drill.source}` : '')}
        </div>
        <div className="drill-body">
          {drill.error && <div className="drill-sub">Couldn’t load assets.</div>}
          {!drill.loading && !drill.error && (
            (drill.rows || []).length ? (
              <table>
                <thead><tr>{(drill.columns || []).map((c) => <th key={c}>{c}</th>)}</tr></thead>
                <tbody>
                  {drill.rows.map((r, i) => (
                    <tr key={i}>{r.map((c, j) => <td key={j}>{c == null ? '—' : c}</td>)}</tr>
                  ))}
                </tbody>
              </table>
            ) : <div className="drill-sub">No assets to show.</div>
          )}
        </div>
      </aside>
    </>
  )
}

export default function DashboardsPage({ section, brand, onOpenSettings }) {
  const meta = SECTION_META[section]
  const list = DASHBOARDS[section]
  const [idx, setIdx] = useState(0)
  const [sources, setSources] = useState([])
  const [scope, setScope] = useState('all')
  const [live, setLive] = useState(null)      // {demo, panels:{id:data}}
  const [dashIndex, setDashIndex] = useState(null)
  const [drill, setDrill] = useState(null)
  const [pdcOk, setPdcOk] = useState(null)

  useEffect(() => { setIdx(0); setScope('all'); setLive(null) }, [section])

  useEffect(() => {
    getJSON('/api/dashboards/sources')
      .then((d) => setSources(d.sources || []))
      .catch(() => setSources([]))
    getJSON('/api/dashboards').then(setDashIndex).catch(() => {})
    getJSON('/health/pdc').then((h) => setPdcOk(!!h.ok)).catch(() => setPdcOk(null))
  }, [])

  const dash = list[Math.min(idx, list.length - 1)]

  /* Build a resolve spec mirroring the mock's overlayLive(): wired KPI tiles
     (by label) + every chart/table with a data-q query. */
  const wired = useMemo(() => {
    const panels = []
    dash.panels.forEach((p, i) => {
      if (p.kind === 'kpi') {
        const q = KPI_QUERY[p.label]
        if (q) panels.push({ id: `p${i}`, kind: 'kpi', title: q, query: q, _i: i })
      } else if (p.q) {
        panels.push({ id: `p${i}`, ...resolverKind(p.chart), title: p.q, query: p.q, _i: i })
      }
    })
    return panels
  }, [dash])

  useEffect(() => {
    let gone = false
    setLive(null)
    if (!wired.length) return undefined
    const spec = {
      version: 1, title: 'live', category: dash.id || section, source: scope,
      panels: wired.map(({ _i, ...p }) => p),
    }
    postJSON('/api/dashboards/resolve', spec)
      .then((d) => { if (!gone) setLive(d) })
      .catch(() => {})   // offline — leave the baked render
    return () => { gone = true }
  }, [dash, scope, wired, section])

  const liveFor = (i) => live && live.panels && live.panels[`p${i}`]

  const openDrill = useCallback((query, label) => {
    setDrill({ loading: true, query, source: scope })
    postJSON('/api/dashboards/drill', { query, label, source: scope })
      .then((d) => setDrill({ ...d, query, source: scope }))
      .catch(() => setDrill({ error: true, query, source: scope }))
  }, [scope])

  const downloadSpec = () => {
    // Preferred: stream the real saved spec from the server (exact + validated).
    if (dashIndex && dashIndex[section] && dashIndex[section][idx]) {
      window.location.href = `/api/dashboards/${section}/${dashIndex[section][idx].id}/download`
      return
    }
    // Fallback (offline): export what's on screen as a spec-shaped JSON.
    const spec = {
      version: 1, title: dash.name, category: section,
      panels: dash.panels.map((p, i) => ({
        id: `p${i + 1}`, kind: p.kind === 'kpi' ? 'kpi' : 'chart',
        title: p.title || p.label, query: p.q || KPI_QUERY[p.label] || '', chartType: p.chart || 'bar',
      })),
    }
    const blob = new Blob([JSON.stringify(spec, null, 2)], { type: 'application/json' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `${dash.name.toLowerCase().replace(/[^a-z0-9]+/g, '-')}.studio.json`
    a.click(); URL.revokeObjectURL(a.href)
  }

  return (
    <div>
      {pdcOk === false && (
        <div className="demo-banner">
          <span>You’re viewing <b>demo data</b>. Connect your {brand.product || 'PDC'} and switch to live to run against real data.</span>
          <button className="ghost sm" onClick={onOpenSettings}>Open Settings</button>
        </div>
      )}

      <div className="page-head">
        <div>
          <h1>{meta.name}</h1>
          <p>{meta.desc}</p>
        </div>
        <div className="dash-tools">
          <span className="std-flag">{list.length} standard dashboard{list.length > 1 ? 's' : ''}</span>
          {live && (
            <span className={`data-badge ${live.demo ? 'demo' : 'live'}`}>
              {live.demo ? 'demo data' : 'live data'}
            </span>
          )}
          <select className="scope-sel" value={scope} onChange={(e) => setScope(e.target.value)}
                  title="Narrow this dashboard to one connected data source">
            <option value="all">All sources</option>
            {sources.map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
          <button className="ghost sm" onClick={downloadSpec}
                  title="Download this dashboard as a .studio.json spec">⤓ Download</button>
          <button className="ghost sm" onClick={() => window.print()}
                  title="Print or save the current dashboard as a PDF">⎙ Print / PDF</button>
        </div>
      </div>

      <div className="print-head">
        <span className="pt">{dash.name}</span>
        <span className="pm">{meta.name} · {brand.name || 'Catalog Insights'} · generated {new Date().toISOString().slice(0, 10)}</span>
      </div>

      <div className="dash-tabs">
        {list.map((d, i) => (
          <button key={d.id} className={`dash-tab${i === idx ? ' on' : ''}`} onClick={() => setIdx(i)}>
            <div className="dt-name">{d.name}<span className="dt-badge">Standard</span></div>
            <div className="dt-desc">{d.desc}</div>
          </button>
        ))}
      </div>

      <div className="dash-grid">
        {dash.panels.map((p, i) => {
          if (p.kind === 'kpi') {
            const data = liveFor(i)
            const liveVal = data && data.value != null ? fmtNum(data.value) + (data.unit || '') : null
            return <KpiTile key={i} p={p} liveVal={liveVal} />
          }
          const data = liveFor(i)
          const clickable = !!p.q
          const onRow = p.chart === 'table' && p.q ? (r) => openDrill(p.q, r[0]?.toString?.() ?? null) : undefined
          return (
            <div key={i}
                 className={`panel-card s${p.span || 2}${clickable ? ' clickable' : ''}`}
                 onClick={clickable && p.chart !== 'table' ? () => openDrill(p.q, null) : undefined}>
              <div className="card-h">
                <h3>{p.title}</h3>
                {p.sub ? <span className="sub">{p.sub}</span> : p.chip ? <span className="chip-tag">{p.chip}</span> : null}
              </div>
              <div className="pbody">
                {data
                  ? <LiveChart chart={p.chart} data={data} onRow={onRow} />
                  : <BakedChart p={p} onRow={onRow} />}
              </div>
            </div>
          )
        })}
      </div>

      <Drill drill={drill} onClose={() => setDrill(null)} />
    </div>
  )
}
