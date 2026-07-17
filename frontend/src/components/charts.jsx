/* Lightweight SVG chart renderers, ported 1:1 from the design mock
   (ui/mock/index.html). Pure components — no chart library needed.
   Colors come through CSS variables so every theme restyles the charts. */

export const C = ['var(--c1)', 'var(--c2)', 'var(--c3)', 'var(--c4)', 'var(--c5)', 'var(--c6)']
export const SCORE = ['var(--low)', 'var(--mid)', 'var(--high)']

const fmt = (n) => (typeof n === 'number' ? n.toLocaleString() : (n ?? '—'))

/* ---- donut + legend ---------------------------------------------------- */
export function Donut({ data, total }) {
  const W = 200; const H = 148; const cx = 78; const cy = H / 2; const r = 58; const thick = 22
  const sum = total || data.reduce((a, d) => a + d.v, 0) || 1
  let ang = -Math.PI / 2
  const arcs = data.map((d, i) => {
    const a2 = ang + (d.v / sum) * 2 * Math.PI
    const x1 = cx + r * Math.cos(ang); const y1 = cy + r * Math.sin(ang)
    const x2 = cx + r * Math.cos(a2); const y2 = cy + r * Math.sin(a2)
    const large = a2 - ang > Math.PI ? 1 : 0
    const el = (
      <path key={i} d={`M${x1} ${y1}A${r} ${r} 0 ${large} 1 ${x2} ${y2}`}
            stroke={d.c || C[i % 6]} strokeWidth={thick} fill="none" strokeLinecap="butt">
        <title>{`${d.k}: ${fmt(d.v)}`}</title>
      </path>
    )
    ang = a2
    return el
  })
  return (
    <div>
      <svg className="chart-svg" viewBox={`0 0 ${W} ${H}`} width="100%" height={H}>
        {arcs}
        <text x={cx} y={cy - 3} textAnchor="middle" fontSize="22" fontWeight="600"
              style={{ fill: 'var(--text-primary)', fontFamily: 'inherit' }}>
          {sum.toLocaleString()}
        </text>
        <text x={cx} y={cy + 14} textAnchor="middle" fontSize="10">total</text>
      </svg>
      <div className="legend-row" style={{ marginTop: 6 }}>
        {data.map((d, i) => (
          <span className="lr" key={d.k}>
            <span className="sw" style={{ background: d.c || C[i % 6] }} />
            {d.k} <b style={{ marginLeft: 4 }}>{fmt(d.v)}</b>
          </span>
        ))}
      </div>
    </div>
  )
}

/* ---- bars (horizontal by default) -------------------------------------- */
export function Bars({ data, horizontal = true, h = 200, max, color }) {
  const W = 360
  const m = max || Math.max(...data.map((d) => d.v)) * 1.1 || 1
  if (horizontal) {
    const bh = Math.min(26, (h - 10) / data.length - 8)
    const gap = (h - 10) / data.length
    return (
      <svg className="chart-svg" viewBox={`0 0 ${W} ${h}`} width="100%" height={h}>
        {data.map((d, i) => {
          const y = 8 + i * gap
          const bw = (d.v / m) * (W - 120)
          return (
            <g key={i}>
              <text x={0} y={y + bh / 2 + 4} className="bar-lbl">{d.k}</text>
              <rect x={96} y={y} width={Math.max(2, bw)} height={bh} rx={4}
                    fill={d.c || color || 'var(--c1)'}>
                <title>{`${d.k}: ${fmt(d.v)}`}</title>
              </rect>
              <text x={96 + bw + 7} y={y + bh / 2 + 4} fontSize="11"
                    style={{ fill: 'var(--text-secondary)' }}>{fmt(d.v)}</text>
            </g>
          )
        })}
      </svg>
    )
  }
  const bw = (W - 20) / data.length - 12
  return (
    <svg className="chart-svg" viewBox={`0 0 ${W} ${h}`} width="100%" height={h}>
      {data.map((d, i) => {
        const x = 20 + i * ((W - 20) / data.length)
        const bh = (d.v / m) * (h - 28)
        return (
          <g key={i}>
            <rect x={x} y={h - 22 - bh} width={bw} height={bh} rx={4}
                  fill={d.c || color || 'var(--c1)'}><title>{`${d.k}: ${fmt(d.v)}`}</title></rect>
            <text x={x + bw / 2} y={h - 6} textAnchor="middle" fontSize="10">{d.k}</text>
          </g>
        )
      })}
    </svg>
  )
}

/* ---- stacked columns + legend ------------------------------------------ */
export function Stacked({ data, keys, colors, h = 200 }) {
  const W = 360
  const max = Math.max(...data.map((d) => keys.reduce((a, k) => a + (d[k] || 0), 0))) * 1.1 || 1
  const slot = (W - 30) / data.length
  const bw = Math.min(46, slot - 14)
  return (
    <div>
      <svg className="chart-svg" viewBox={`0 0 ${W} ${h}`} width="100%" height={h}>
        {data.map((d, i) => {
          let y = h - 24
          const x = 30 + i * slot + (slot - bw) / 2
          return (
            <g key={i}>
              {keys.map((k, j) => {
                const bh = ((d[k] || 0) / max) * (h - 34)
                y -= bh
                return (
                  <rect key={k} x={x} y={y} width={bw} height={bh} fill={colors[j]}
                        rx={j === keys.length - 1 ? 4 : 0}>
                    <title>{`${d.k} · ${k}: ${fmt(d[k])}`}</title>
                  </rect>
                )
              })}
              <text x={x + bw / 2} y={h - 8} textAnchor="middle" fontSize="10">{d.k}</text>
            </g>
          )
        })}
      </svg>
      <div className="legend-row">
        {keys.map((k, j) => (
          <span className="lr" key={k}><span className="sw" style={{ background: colors[j] }} />{k}</span>
        ))}
      </div>
    </div>
  )
}

/* ---- line / area -------------------------------------------------------- */
export function Line({ series, h = 190, area = true, color = 'var(--c1)', fmt: f = (v) => v }) {
  const W = 360; const pad = 28
  const max = Math.max(...series) * 1.15 || 1
  const min = Math.min(...series) * 0.9
  const xs = (i) => pad + i * ((W - pad - 8) / (series.length - 1 || 1))
  const ys = (v) => h - 22 - ((v - min) / ((max - min) || 1)) * (h - 36)
  const d = series.map((v, i) => `${i ? 'L' : 'M'}${xs(i)} ${ys(v)}`).join(' ')
  const last = series[series.length - 1]
  return (
    <svg className="chart-svg" viewBox={`0 0 ${W} ${h}`} width="100%" height={h}>
      {[0, 0.5, 1].map((t) => (
        <line key={t} x1={pad} y1={22 + t * (h - 58)} x2={W - 8} y2={22 + t * (h - 58)} className="gl" />
      ))}
      {area && (
        <path d={`${d} L${xs(series.length - 1)} ${h - 22} L${pad} ${h - 22} Z`} fill={color} opacity=".10" />
      )}
      <path d={d} stroke={color} strokeWidth="2.4" fill="none" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={xs(series.length - 1)} cy={ys(last)} r="3.6" fill={color} />
      <text x={xs(series.length - 1)} y={ys(last) - 9} textAnchor="middle" fontSize="11"
            style={{ fill: 'var(--text-secondary)' }}>{f(last)}</text>
    </svg>
  )
}

/* ---- sparkline (KPI tiles) ---------------------------------------------- */
export function Spark({ series, color }) {
  const W = 120; const h = 34
  const max = Math.max(...series); const min = Math.min(...series)
  const xs = (i) => i * (W / (series.length - 1 || 1))
  const ys = (v) => h - 4 - ((v - min) / ((max - min) || 1)) * (h - 8)
  const d = series.map((v, i) => `${i ? 'L' : 'M'}${xs(i)} ${ys(v)}`).join(' ')
  return (
    <svg className="chart-svg" viewBox={`0 0 ${W} ${h}`} width="100%" height={h}>
      <path d={`${d} L${W} ${h} L0 ${h} Z`} fill={color} opacity=".12" />
      <path d={d} stroke={color} strokeWidth="2" fill="none" />
    </svg>
  )
}

/* ---- gauge (semi-circle %) ---------------------------------------------- */
export function Gauge({ val, label = 'have a term' }) {
  const W = 200; const H = 130; const cx = 100; const cy = 110; const r = 78
  const arc = (a1, a2) => {
    const p1 = [cx + r * Math.cos(a1), cy + r * Math.sin(a1)]
    const p2 = [cx + r * Math.cos(a2), cy + r * Math.sin(a2)]
    return `M${p1[0]} ${p1[1]}A${r} ${r} 0 0 1 ${p2[0]} ${p2[1]}`
  }
  const a = Math.PI + (Math.min(100, Math.max(0, val)) / 100) * Math.PI
  return (
    <svg className="chart-svg" viewBox={`0 0 ${W} ${H}`} width="100%" height={H}>
      <path d={arc(Math.PI, 2 * Math.PI)} stroke="var(--surface-2)" strokeWidth="16" fill="none" strokeLinecap="round" />
      <path d={arc(Math.PI, a)} stroke="var(--brand)" strokeWidth="16" fill="none" strokeLinecap="round" />
      <text x={cx} y={cy - 8} textAnchor="middle" fontSize="30" fontWeight="600"
            style={{ fill: 'var(--text-primary)', fontFamily: 'inherit' }}>{val}%</text>
      <text x={cx} y={cy + 10} textAnchor="middle" fontSize="10">{label}</text>
    </svg>
  )
}

/* ---- radar (DQ dimensions) ---------------------------------------------- */
export function Radar({ axes }) {
  const W = 300; const H = 200; const cx = 150; const cy = 100; const R = 78; const n = axes.length || 1
  const pt = (i, f) => [
    cx + R * f * Math.cos(-Math.PI / 2 + (i * 2 * Math.PI) / n),
    cy + R * f * Math.sin(-Math.PI / 2 + (i * 2 * Math.PI) / n),
  ]
  const ring = (f) => axes.map((_, i) => {
    const p = pt(i, f); return `${i ? 'L' : 'M'}${p[0]} ${p[1]} `
  }).join('') + 'Z'
  const shape = axes.map((ax, i) => {
    const p = pt(i, (ax.v || 0) / 100); return `${i ? 'L' : 'M'}${p[0]} ${p[1]} `
  }).join('') + 'Z'
  return (
    <svg className="chart-svg" viewBox={`0 0 ${W} ${H}`} width="100%" height={H}>
      {[0.25, 0.5, 0.75, 1].map((f) => (
        <path key={f} d={ring(f)} fill="none" stroke="var(--gridline)" strokeWidth="1" />
      ))}
      {axes.map((ax, i) => {
        const lp = pt(i, 1.18)
        return <text key={ax.k} x={lp[0]} y={lp[1] + 3} textAnchor="middle" fontSize="9.5">{ax.k}</text>
      })}
      <path d={shape} fill="var(--brand)" opacity=".16" stroke="var(--brand)" strokeWidth="2" />
    </svg>
  )
}

/* ---- histogram (score distribution, banded colors) ----------------------- */
export function Histo({ bins }) {
  const W = 360; const h = 190
  const max = Math.max(...bins.map((b) => b.v)) * 1.1 || 1
  const bw = (W - 30) / bins.length - 4
  return (
    <svg className="chart-svg" viewBox={`0 0 ${W} ${h}`} width="100%" height={h}>
      {bins.map((b, i) => {
        const x = 24 + i * ((W - 30) / bins.length)
        const bh = (b.v / max) * (h - 30)
        const col = b.lo < 51 ? 'var(--low)' : b.lo < 76 ? 'var(--mid)' : 'var(--high)'
        return (
          <g key={i}>
            <rect x={x} y={h - 22 - bh} width={bw} height={bh} rx={2} fill={col} opacity=".85">
              <title>{`${b.lo}+: ${fmt(b.v)}`}</title>
            </rect>
            {i % 2 === 0 && <text x={x + bw / 2} y={h - 7} textAnchor="middle" fontSize="9">{b.lo}</text>}
          </g>
        )
      })}
    </svg>
  )
}

/* ---- bullet (value vs target) -------------------------------------------- */
export function Bullet({ rows }) {
  const W = 360; const rowH = 34; const track = W - 150
  return (
    <svg className="chart-svg" viewBox={`0 0 ${W} ${rows.length * rowH + 6}`} width="100%" height={rows.length * rowH + 6}>
      {rows.map((r, i) => {
        const y = i * rowH + 6
        return (
          <g key={r.k}>
            <text x={0} y={y + 15} className="bar-lbl">{r.k}</text>
            <rect x={90} y={y + 4} width={track} height={16} rx={3} fill="var(--surface-2)" />
            <rect x={90} y={y + 4} width={(track * r.v) / 100} height={16} rx={3}
                  fill={r.v >= r.t ? 'var(--high)' : 'var(--mid)'}>
              <title>{`${r.k}: ${r.v} (target ${r.t})`}</title>
            </rect>
            <line x1={90 + (track * r.t) / 100} y1={y} x2={90 + (track * r.t) / 100} y2={y + 24}
                  stroke="var(--text-primary)" strokeWidth="2" />
            <text x={90 + track + 8} y={y + 16} fontSize="11" style={{ fill: 'var(--text-secondary)' }}>{r.v}</text>
          </g>
        )
      })}
    </svg>
  )
}

/* ---- activity calendar (github-style) ------------------------------------ */
export function Calendar({ weeks = 24, seed = 7 }) {
  const W = 360; const cell = 12; const gap = 3
  // deterministic pseudo-random so the demo texture doesn't flicker on re-render
  let s = seed
  const rand = () => { s = (s * 9301 + 49297) % 233280; return s / 233280 }
  const cells = []
  for (let w = 0; w < weeks; w++) {
    for (let d = 0; d < 7; d++) {
      const v = rand()
      const col = v > 0.8 ? 'var(--brand)'
        : v > 0.55 ? 'color-mix(in srgb, var(--brand) 65%, transparent)'
          : v > 0.3 ? 'color-mix(in srgb, var(--brand) 32%, transparent)'
            : 'var(--surface-2)'
      cells.push(<rect key={`${w}-${d}`} x={w * (cell + gap)} y={d * (cell + gap) + 4}
                       width={cell} height={cell} rx={2.5} fill={col} />)
    }
  }
  return (
    <div>
      <svg className="chart-svg" viewBox={`0 0 ${W} ${7 * (cell + gap) + 18}`} width="100%" height={7 * (cell + gap) + 18}>
        {cells}
      </svg>
      <div className="legend-row" style={{ justifyContent: 'flex-end' }}>
        <span className="lr">
          Less
          <span className="sw" style={{ background: 'var(--surface-2)', margin: '0 2px' }} />
          <span className="sw" style={{ background: 'color-mix(in srgb, var(--brand) 32%, transparent)', margin: '0 2px' }} />
          <span className="sw" style={{ background: 'color-mix(in srgb, var(--brand) 65%, transparent)', margin: '0 2px' }} />
          <span className="sw" style={{ background: 'var(--brand)', margin: '0 2px' }} />
          More
        </span>
      </div>
    </div>
  )
}

/* ---- trust spectrum ------------------------------------------------------ */
export function Spectrum({ seg }) {
  const sum = seg.reduce((a, s) => a + s.v, 0) || 1
  return (
    <div>
      <div className="spectrum-bar">
        {seg.map((s, i) => (
          <div key={s.k} className="spectrum-seg"
               style={{ width: `${(s.v / sum) * 100}%`, background: SCORE[i] }}>
            {Math.round((s.v / sum) * 100)}%
          </div>
        ))}
      </div>
      <div className="spectrum-legend">
        {seg.map((s, i) => (
          <div key={s.k} className="leg">
            <span className="sw" style={{ background: SCORE[i] }} />
            {s.k} <b>{fmt(s.v)}</b> <span>{s.r}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

/* ---- mini table (rows may be strings, numbers, or JSX pills) -------------- */
export function MiniTable({ cols, rows, onRow }) {
  return (
    <table className="tbl">
      <thead>
        <tr>{cols.map((c) => <th key={c}>{c}</th>)}</tr>
      </thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={i} onClick={onRow ? (e) => { e.stopPropagation(); onRow(r) } : undefined}
              style={onRow ? undefined : { cursor: 'default' }}>
            {r.map((cell, j) => <td key={j}>{cell ?? '—'}</td>)}
          </tr>
        ))}
      </tbody>
    </table>
  )
}
