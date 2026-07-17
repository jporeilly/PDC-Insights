// Same-origin API helpers. When INSIGHTS_AUTH is on (apikey|jwt) every /api
// and /health route (except /health) wants a bearer token — the key entered in
// the AI Builder header is kept in localStorage and attached everywhere.

const KEY = 'insights-apikey'

export const getApiKey = () => localStorage.getItem(KEY) || ''
export const setApiKey = (k) => {
  if (k) localStorage.setItem(KEY, k)
  else localStorage.removeItem(KEY)
}

export function authHeaders(extra = {}) {
  const h = { 'Content-Type': 'application/json', ...extra }
  const k = getApiKey()
  if (k) h['Authorization'] = 'Bearer ' + k
  return h
}

export async function getJSON(url) {
  const r = await fetch(url, { headers: authHeaders() })
  if (!r.ok) throw Object.assign(new Error(`HTTP ${r.status}`), { status: r.status })
  return r.json()
}

export async function postJSON(url, body) {
  const r = await fetch(url, {
    method: 'POST', headers: authHeaders(), body: JSON.stringify(body),
  })
  const data = await r.json().catch(() => ({}))
  if (!r.ok) throw Object.assign(new Error(data.error || `HTTP ${r.status}`),
    { status: r.status, data })
  return data
}

/* fire-and-forget variant that swallows failures (status dots, backdrops) */
export const tryJSON = (url) => getJSON(url).catch(() => null)
