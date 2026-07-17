import { useEffect, useRef, useState } from 'react'
import { authHeaders, getJSON, postJSON } from '../api.js'
import ThemeSelect from '../components/ThemeSelect.jsx'

/* Settings — ported from the mock's Settings view. Reads and applies the live
   configuration through the real endpoints:
     GET/POST /api/settings, POST /api/settings/test-pdc,
     GET /api/llm/suggest|models, POST /api/llm/pull (NDJSON stream),
     GET /health/llm, GET /config (branding). */

const PROVIDERS = [
  ['local', 'Local'], ['anthropic', 'Anthropic'], ['openai', 'OpenAI'], ['disabled', 'Off'],
]

function Seg({ options, value, onChange }) {
  return (
    <div className="seg">
      {options.map(([v, label]) => (
        <button key={v} className={value === v ? 'on' : ''} onClick={() => onChange(v)} type="button">
          {label}
        </button>
      ))}
    </div>
  )
}

/* Model picker: clicking the field shows ALL installed models, typing filters
   the list — and you can still type any name to pull it. */
function ModelCombo({ value, onChange, models }) {
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(-1)
  const boxRef = useRef(null)

  useEffect(() => {
    const close = (e) => { if (boxRef.current && !boxRef.current.contains(e.target)) setOpen(false) }
    document.addEventListener('click', close)
    return () => document.removeEventListener('click', close)
  }, [])

  const q = value.trim().toLowerCase()
  const exact = models.some((m) => m.toLowerCase() === q)
  const list = (!q || exact) ? models : models.filter((m) => m.toLowerCase().includes(q))

  const pick = (v) => { onChange(v); setOpen(false); setActive(-1) }

  return (
    <div className="combo" ref={boxRef}>
      <input className="text" value={value} autoComplete="off" placeholder="pick or type a model"
             onFocus={() => { setActive(-1); setOpen(true) }}
             onClick={() => { setActive(-1); setOpen(true) }}
             onChange={(e) => { onChange(e.target.value); setActive(-1); setOpen(true) }}
             onKeyDown={(e) => {
               if (e.key === 'ArrowDown') { e.preventDefault(); setActive((a) => Math.min(a + 1, list.length - 1)) }
               else if (e.key === 'ArrowUp') { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)) }
               else if (e.key === 'Enter') { if (active >= 0 && list[active]) { e.preventDefault(); pick(list[active]) } else setOpen(false) }
               else if (e.key === 'Escape') setOpen(false)
             }} />
      {open && (
        <div className="combo-menu">
          {list.length
            ? list.map((m, i) => (
              <div key={m} className={`combo-item${i === active ? ' active' : ''}`}
                   onMouseDown={(e) => { e.preventDefault(); pick(m) }}>{m}</div>
            ))
            : (
              <div className="combo-empty">
                {models.length
                  ? 'No match — press Enter to use what you typed.'
                  : 'No models installed. Type a name to pull it.'}
              </div>
            )}
        </div>
      )}
    </div>
  )
}

export default function SettingsPage({ version, brand: brandProp }) {
  // LLM
  const [provider, setProvider] = useState('local')
  const [llmUrl, setLlmUrl] = useState('')
  const [model, setModel] = useState('')
  const [jsonMode, setJsonMode] = useState('true')
  const [models, setModels] = useState([])
  const [modelsHint, setModelsHint] = useState('Loading installed models…')
  const [rec, setRec] = useState(null)
  const [pullState, setPullState] = useState({ busy: false, res: null, prog: null, installed: false })
  const [llmTest, setLlmTest] = useState(null)
  const touched = useRef(false)
  // PDC
  const [pdcUrl, setPdcUrl] = useState('')
  const [pdcVer, setPdcVer] = useState('v3')
  const [pdcUser, setPdcUser] = useState('')
  const [pdcPass, setPdcPass] = useState('')
  const [pdcPassPh, setPdcPassPh] = useState('set a password')
  const [cacheTtl, setCacheTtl] = useState('300')
  const [demo, setDemo] = useState('true')
  const [pdcTest, setPdcTest] = useState(null)
  // branding / save
  const [brand, setBrand] = useState(brandProp || null)
  const [saveRes, setSaveRes] = useState(null)
  const [saving, setSaving] = useState(false)

  async function loadSettings() {
    try {
      const s = await getJSON('/api/settings')
      setPdcUrl(s.pdc.base_url || ''); setPdcUser(s.pdc.username || '')
      setPdcVer(s.pdc.version || 'v3'); setCacheTtl(String(s.pdc.cache_ttl ?? 300))
      setPdcPassPh(s.pdc.has_password ? '•••••••••• (unchanged)' : 'set a password')
      setLlmUrl(s.llm.base_url || '')
      if (!touched.current) setModel(s.llm.model || '')
      setJsonMode(String(s.llm.json_mode)); setProvider(s.llm.provider || 'local')
      setDemo(String(s.demo))
    } catch { /* backend unreachable — leave defaults */ }
  }

  useEffect(() => {
    loadSettings()
    getJSON('/config').then((c) => setBrand(c.brand)).catch(() => {})
    getJSON('/api/llm/suggest').then((d) => {
      setRec(d)
      if (!touched.current && d.model) setModel((m) => m || d.model)
      if (d.installed) setPullState((p) => ({ ...p, installed: true }))
    }).catch(() => {})
    refreshModels()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function refreshModels() {
    try {
      const d = await getJSON('/api/llm/models')
      const list = (d.models || []).filter(Boolean)
      setModels(list)
      setModelsHint(list.length
        ? `${list.length} model(s) installed — click the field to see them all, or type a name.`
        : 'No models installed yet — use Download model below, or type a name.')
    } catch {
      setModels([]); setModelsHint('Ollama not reachable — type a model name.')
    }
  }

  async function testLLM() {
    setLlmTest({ cls: '', text: 'testing…' })
    try {
      const d = await getJSON('/health/llm')
      setLlmTest(d.ok ? { cls: 'ok', text: d.detail || 'Reachable' } : { cls: 'err', text: d.detail || 'offline' })
    } catch { setLlmTest({ cls: 'err', text: 'unreachable' }) }
  }

  async function testPDC() {
    setPdcTest({ cls: '', text: 'testing…' })
    const payload = { base_url: pdcUrl.trim(), version: pdcVer, username: pdcUser.trim() }
    if (pdcPass) payload.password = pdcPass    // blank ⇒ use the saved one
    try {
      const d = await postJSON('/api/settings/test-pdc', payload)
      setPdcTest(d.ok ? { cls: 'ok', text: d.detail || 'Connected' } : { cls: 'err', text: d.error || 'failed' })
    } catch (e) { setPdcTest({ cls: 'err', text: e.message }) }
  }

  /* Download the model named in the Model field via Ollama, streaming progress. */
  async function pullModel() {
    const m = model.trim(); if (!m || pullState.busy) return
    setPullState({ busy: true, res: 'Starting…', prog: `pulling ${m} …`, installed: false })
    try {
      const r = await fetch('/api/llm/pull', {
        method: 'POST', headers: authHeaders(), body: JSON.stringify({ model: m }),
      })
      if (r.status === 403) { setPullState({ busy: false, res: 'Needs the steward role.', resCls: 'err' }); return }
      const reader = r.body.getReader(); const dec = new TextDecoder(); let buf = ''
      for (;;) {
        const { value, done } = await reader.read()
        if (done) break
        buf += dec.decode(value, { stream: true })
        const lines = buf.split('\n'); buf = lines.pop()
        for (const ln of lines) {
          if (!ln.trim()) continue
          let o; try { o = JSON.parse(ln) } catch { continue }
          if (o.error) {
            setPullState({ busy: false, res: 'Failed', resCls: 'err', prog: 'Error: ' + o.error + (o.hint ? `  (${o.hint})` : '') })
            return
          }
          const pct = o.total && o.completed ? ` ${Math.round((100 * o.completed) / o.total)}%` : ''
          setPullState((p) => ({ ...p, prog: (o.status || 'working') + pct }))
        }
      }
      setPullState({ busy: false, res: 'Done ✓', resCls: 'ok', prog: `${m} downloaded.`, installed: true })
      refreshModels()
    } catch (e) {
      setPullState({ busy: false, res: 'Failed', resCls: 'err', prog: String(e) })
    }
  }

  async function save() {
    setSaving(true); setSaveRes({ cls: '', text: 'Saving…' })
    const payload = {
      demo: demo === 'true',
      pdc: { base_url: pdcUrl.trim(), version: pdcVer, username: pdcUser.trim(), cache_ttl: parseInt(cacheTtl, 10) },
      llm: { provider, base_url: llmUrl.trim(), model: model.trim(), json_mode: jsonMode === 'true' },
    }
    if (pdcPass) payload.pdc.password = pdcPass   // blank ⇒ keep existing
    try {
      const d = await postJSON('/api/settings', payload)
      if (d.saved) { setSaveRes({ cls: 'ok', text: 'Saved & applied ✓' }); setPdcPass(''); loadSettings() }
      else setSaveRes({ cls: 'err', text: 'Could not save: ' + (d.error || 'unknown') })
    } catch (e) {
      if (e.status === 403) setSaveRes({ cls: 'err', text: 'Saving needs the admin role.' })
      else setSaveRes({ cls: 'err', text: 'Error: ' + e.message })
    } finally { setSaving(false) }
  }

  const recLine = rec
    ? <>Recommended for this machine ({rec.vram_gb ? `GPU · ${rec.vram_gb} GB VRAM` : `CPU · ${rec.ram_gb} GB RAM`}): <b>{rec.model}</b> — {rec.why}. {rec.installed ? <span className="ok">already installed ✓</span> : <span className="warn">not installed</span>}</>
    : 'Checking this machine…'

  return (
    <div className="settings">
      <div className="page-head">
        <div>
          <h1>Settings</h1>
          <p>Connect Catalog Insights to your {brand?.product || 'PDC'} instance and choose where dashboard generation runs.</p>
        </div>
      </div>

      <div className="set-grid">
        <section className="card">
          <h2>LLM connection</h2>
          <p className="desc">Where natural-language dashboard generation runs. Local keeps catalog and PII metadata inside your environment.</p>
          <div className="field" style={{ marginBottom: '.9rem' }}>
            <label>Provider</label>
            <div><Seg options={PROVIDERS} value={provider} onChange={setProvider} /></div>
            <span className="hint">Recommended: <b>Local</b> for governance data — nothing leaves the box.</span>
          </div>
          <div className="field" style={{ marginBottom: '.9rem' }}>
            <label>Endpoint</label>
            <input className="text" value={llmUrl} onChange={(e) => setLlmUrl(e.target.value)} />
          </div>
          <div className="field" style={{ marginBottom: '.9rem' }}>
            <label>Model</label>
            <ModelCombo value={model} models={models}
                        onChange={(v) => { touched.current = true; setModel(v) }} />
            <span className="hint">{modelsHint}</span>
          </div>
          <div className="field" style={{ marginBottom: '.9rem' }}>
            <label>JSON mode</label>
            <select className="text" value={jsonMode} onChange={(e) => setJsonMode(e.target.value)}>
              <option value="true">Constrained (format=json)</option>
              <option value="false">Off</option>
            </select>
            <span className="hint">Forces valid spec output from smaller local models.</span>
          </div>
          <div className="field">
            <label>Model download</label>
            <span className="hint">{recLine}</span>
            <div className="test">
              <button className="ghost sm" onClick={pullModel} disabled={pullState.busy || pullState.installed}>
                {pullState.installed ? 'Installed' : 'Download model'}
              </button>
              {pullState.res && <span className={`test-result ${pullState.resCls || ''}`}>{pullState.res}</span>}
            </div>
            {pullState.prog && <span className="hint mono">{pullState.prog}</span>}
          </div>
          <div className="test">
            <button className="ghost sm" onClick={testLLM} title="Check that the LLM endpoint is reachable">Test connection</button>
            {llmTest && (
              <span className={`test-result ${llmTest.cls}`}>
                <span className={`dot ${llmTest.cls === 'ok' ? 'ok' : 'warn'}`} />{llmTest.text}
              </span>
            )}
          </div>
        </section>

        <section className="card">
          <h2>PDC connection</h2>
          <p className="desc">The {brand?.product || 'Pentaho Data Catalog'} instance to report on. Reads only — no writes are made to the catalog.</p>
          <div className="field" style={{ marginBottom: '.9rem' }}>
            <label>Base URL</label>
            <input className="text" value={pdcUrl} placeholder="https://your-pdc-host"
                   onChange={(e) => setPdcUrl(e.target.value)} />
          </div>
          <div className="field" style={{ marginBottom: '.9rem' }}>
            <label>API version</label>
            <select className="text" value={pdcVer} onChange={(e) => setPdcVer(e.target.value)}>
              <option>v3</option><option>v2</option><option>v1</option>
            </select>
          </div>
          <div className="field" style={{ marginBottom: '.9rem' }}>
            <label>Username</label>
            <input className="text" value={pdcUser} onChange={(e) => setPdcUser(e.target.value)} />
          </div>
          <div className="field" style={{ marginBottom: '.9rem' }}>
            <label>Password</label>
            <input className="text" type="password" value={pdcPass} placeholder={pdcPassPh}
                   onChange={(e) => setPdcPass(e.target.value)} />
          </div>
          <div className="field" style={{ marginBottom: '.9rem' }}>
            <label>Cache responses</label>
            <select className="text" value={cacheTtl} onChange={(e) => setCacheTtl(e.target.value)}>
              <option value="300">5 minutes</option>
              <option value="60">1 minute</option>
              <option value="0">Off</option>
            </select>
          </div>
          <div className="field" style={{ marginBottom: '.9rem' }}>
            <label>Data source</label>
            <div><Seg options={[['false', 'Live PDC'], ['true', 'Demo data']]} value={demo} onChange={setDemo} /></div>
            <span className="hint">Live reads from the PDC above; Demo serves the bundled sample.</span>
          </div>
          <div className="test">
            <button className="ghost sm" onClick={testPDC}
                    title="Authenticate against the PDC and confirm the connection">Test connection</button>
            {pdcTest && (
              <span className={`test-result ${pdcTest.cls}`}>
                <span className={`dot ${pdcTest.cls === 'ok' ? 'ok' : 'warn'}`} />{pdcTest.text}
              </span>
            )}
          </div>
        </section>

        <section className="card span2">
          <h2>Branding</h2>
          <p className="desc">Genericise the product for delivery — set via the <code>INSIGHTS_BRAND_*</code> environment variables (same pattern as the sibling apps). Shown here as currently applied.</p>
          <div className="form-grid">
            <label>Product name<input className="text" value={brand?.name || ''} readOnly /></label>
            <label>Catalog label<input className="text" value={brand?.product || ''} readOnly /></label>
            <label>Accent colour<input className="text" value={brand?.accent || ''} readOnly /></label>
          </div>
        </section>

        <section className="card">
          <h2>Appearance</h2>
          <div className="form-grid">
            <label>
              Color theme
              <ThemeSelect />
            </label>
          </div>
        </section>

        <section className="card">
          <h2>About</h2>
          <dl>
            <dt>Version</dt><dd>{version}</dd>
            <dt>Service</dt><dd>{brand?.name || 'Catalog Insights'} — dashboards over the catalog’s REST API</dd>
            <dt>Backend</dt><dd>Flask API · /api + /health</dd>
            <dt>PDC</dt><dd>validated against Pentaho Data Catalog 11.0.0 (public API v3)</dd>
          </dl>
        </section>
      </div>

      <div className="save-bar">
        <button className="primary" onClick={save} disabled={saving}
                title="Persist these settings to .env and apply them immediately (no restart)">
          Save &amp; apply
        </button>
        {saveRes && <span className={`test-result ${saveRes.cls}`}>{saveRes.text}</span>}
        <span className="save-hint">Saves to .env and applies immediately — the next snapshot, recommendation, and chat run against the live PDC.</span>
      </div>
    </div>
  )
}
