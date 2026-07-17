import { useEffect, useState } from 'react'
import ThemeSelect from './components/ThemeSelect.jsx'
import DashboardsPage from './pages/DashboardsPage.jsx'
import DesignerPage from './pages/DesignerPage.jsx'
import ChatPage from './pages/ChatPage.jsx'
import SettingsPage from './pages/SettingsPage.jsx'
import { tryJSON } from './api.js'
import { DASHBOARDS, SECTION_META, SECTIONS } from './data/dashboards.jsx'
import pkg from '../package.json'

/* Nav icons, carried over from the mock. */
const ICONS = {
  overview: <path d="M4 13h6V4H4v9Zm0 7h6v-5H4v5Zm10 0h6V11h-6v9Zm0-16v5h6V4h-6Z" stroke="currentColor" strokeWidth="1.7" fill="none" />,
  system: <><path d="M5 7h14M5 12h14M5 17h14" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" fill="none" /><circle cx="8" cy="7" r="1.6" fill="currentColor" /><circle cx="14" cy="12" r="1.6" fill="currentColor" /><circle cx="10" cy="17" r="1.6" fill="currentColor" /></>,
  user: <><circle cx="12" cy="8" r="3.3" stroke="currentColor" strokeWidth="1.7" fill="none" /><path d="M5.5 19a6.5 6.5 0 0 1 13 0" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" fill="none" /></>,
  governance: <><path d="M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6l7-3Z" stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round" fill="none" /><path d="m9 12 2 2 4-4" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" fill="none" /></>,
  quality: <><path d="M12 3v18M3 12h18" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" fill="none" /><circle cx="12" cy="12" r="8" stroke="currentColor" strokeWidth="1.7" fill="none" /></>,
  sensitivity: <><rect x="5" y="10" width="14" height="10" rx="2" stroke="currentColor" strokeWidth="1.7" fill="none" /><path d="M8 10V7a4 4 0 0 1 8 0v3" stroke="currentColor" strokeWidth="1.7" fill="none" /></>,
  designer: <><path d="m4 20 4-1 10-10-3-3L5 16l-1 4Z" stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round" fill="none" /><path d="m14 6 4 4" stroke="currentColor" strokeWidth="1.7" fill="none" /></>,
  chat: <path d="M21 12a8 8 0 0 1-8 8H4l2.5-2.7A8 8 0 1 1 21 12Z" stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round" fill="none" />,
  settings: <><circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="1.7" fill="none" /><path d="M12 2v3m0 14v3M2 12h3m14 0h3M4.9 4.9l2.1 2.1m10 10 2.1 2.1M19.1 4.9 17 7m-10 10-2.1 2.1" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" fill="none" /></>,
}

function Ico({ id }) {
  return <svg className="nav-ico" viewBox="0 0 24 24">{ICONS[id]}</svg>
}

/* The initial view comes from the URL so the mock's /chat?section=… deep link
   still works when Flask serves the SPA for /chat. */
function initialView() {
  const path = window.location.pathname
  const params = new URLSearchParams(window.location.search)
  if (path === '/chat') return { view: 'chat', section: params.get('section') || '' }
  return { view: 'overview', section: '' }
}

export default function App() {
  const [{ view, section }, setNav] = useState(initialView)
  const [brand, setBrand] = useState({ name: 'Catalog Insights', product: 'Pentaho Data Catalog' })
  const [pdc, setPdc] = useState(null)   // /health/pdc
  const [llm, setLlm] = useState(null)   // /health/llm

  const go = (v, sec = '') => {
    setNav({ view: v, section: sec })
    const url = v === 'chat' ? `/chat${sec ? `?section=${sec}` : ''}` : '/'
    window.history.replaceState(null, '', url)
    window.scrollTo(0, 0)
  }

  /* brand from the API (INSIGHTS_BRAND_*): /health is public, /config adds
     the catalog label when the caller has the viewer role. */
  useEffect(() => {
    tryJSON('/health').then((h) => {
      if (h?.brand) setBrand((b) => ({ ...b, name: h.brand }))
    })
    tryJSON('/config').then((c) => { if (c?.brand) setBrand((b) => ({ ...b, ...c.brand })) })
  }, [])

  /* footer status dots — real reachability, re-checked every 30s. */
  useEffect(() => {
    let alive = true
    const refresh = async () => {
      const p = await tryJSON('/health/pdc'); if (alive) setPdc(p)
      const l = await tryJSON('/health/llm'); if (alive) setLlm(l)
    }
    refresh()
    const t = setInterval(refresh, 30000)
    return () => { alive = false; clearInterval(t) }
  }, [])

  const pdcHost = (pdc?.base_url || '').replace(/^https?:\/\//, '').replace(/\/.*$/, '') || 'PDC'
  const crumbGroup = view === 'designer' ? 'Build' : view === 'settings' ? 'Configure' : view === 'chat' ? 'Build' : 'Analytics'
  const crumbLabel = view === 'designer' ? 'Dashboard Designer'
    : view === 'settings' ? 'Settings'
      : view === 'chat' ? 'AI Builder'
        : SECTION_META[view]?.name || ''

  return (
    <div className="shell">
      <aside className="side">
        <div className="brand">
          <div className="brand-mark">
            <svg width="17" height="17" viewBox="0 0 24 24" fill="none">
              <path d="M4 18V8m5 10V5m5 13v-7m5 7V9" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" />
            </svg>
          </div>
          <div>
            <div className="brand-name">{brand.name === 'Catalog Insights'
              ? <>Catalog <em>Insights</em></> : brand.name}</div>
            <div className="brand-sub">{brand.product}</div>
          </div>
          <span className="version-pill" title="PDC-Insights release">v{pkg.version}</span>
        </div>

        <nav className="nav">
          <div className="nav-label">Analytics</div>
          {SECTIONS.map((id) => (
            <button key={id} className={`nav-item${view === id ? ' active' : ''}`}
                    title={SECTION_META[id].desc} onClick={() => go(id)}>
              <Ico id={id} />
              {SECTION_META[id].name}
              <span className="nav-badge">{DASHBOARDS[id].length}</span>
            </button>
          ))}
          <div className="nav-label">Build</div>
          <button className={`nav-item${view === 'designer' ? ' active' : ''}`}
                  title="Build and edit dashboards, or generate new ones with AI"
                  onClick={() => go('designer')}>
            <Ico id="designer" />Dashboard Designer
          </button>
          <button className={`nav-item${view === 'chat' ? ' active' : ''}`}
                  title="The conversational dashboard builder"
                  onClick={() => go('chat', section)}>
            <Ico id="chat" />AI Builder
          </button>
          <div className="nav-label">Configure</div>
          <button className={`nav-item${view === 'settings' ? ' active' : ''}`}
                  title="Connect your PDC, choose where generation runs, and switch to live data"
                  onClick={() => go('settings')}>
            <Ico id="settings" />Settings
          </button>
        </nav>

        <div className="side-foot">
          <div className="conn">
            <span className={`dot ${pdc?.ok ? 'ok' : 'warn'}`} />
            PDC&nbsp;·&nbsp;<span className="mono">{pdc ? (pdc.ok ? pdcHost : `${pdcHost} · demo`) : 'checking…'}</span>
          </div>
          <div className="conn">
            <span className={`dot ${llm?.ok ? 'ok' : 'warn'}`} />
            LLM&nbsp;·&nbsp;<span className="mono">
              {llm ? (llm.ok ? `${llm.provider === 'local' ? 'local · ' : ''}${llm.model || 'ready'}` : `${llm.provider || 'llm'} · offline`) : 'checking…'}
            </span>
          </div>
          <ThemeSelect />
        </div>
      </aside>

      <div className="main">
        <header className="topbar">
          <div className="crumb">{crumbGroup}&nbsp;/&nbsp;<b>{crumbLabel}</b></div>
          <div className="topbar-spacer" />
          {view !== 'chat' && (
            <button className="primary sm"
                    title="Open the AI dashboard builder for the current section"
                    onClick={() => go('chat', SECTIONS.includes(view) ? view : '')}>
              ✦ Build with AI
            </button>
          )}
        </header>

        <div className="content">
          {SECTIONS.includes(view) && (
            <DashboardsPage section={view} brand={brand} onOpenSettings={() => go('settings')} />
          )}
          {view === 'designer' && (
            <DesignerPage llm={llm} onOpenChat={(sec) => go('chat', sec)} />
          )}
          {view === 'chat' && <ChatPage key={section} section={section} />}
          {view === 'settings' && <SettingsPage version={pkg.version} brand={brand} />}
        </div>
      </div>
    </div>
  )
}
