# Changelog

## 1.10.0 — re-target to PDC 11.0; adopted as its own GitHub project

- The project now lives at github.com/jporeilly/PDC-Insights (public), a
  sibling of the Glossary Generator, Policy Generator and PDC-Scenarios
  repos. Seeded from the 1.9.11 zip; run.sh exec bit + eol rules added.
- Docs and comments re-pointed from PDC 10.2.11 to **PDC 11.0.0** (the
  shared demo lab). Folded in what the sibling apps have already
  live-confirmed on 11.0: Keycloak-first auth (`pdc-client`), POST /search
  and POST /entities/filter on the same bearer token, and the authenticated
  OpenAPI spec at /api/public/v3/openapi.json (/v3/api-docs 401s).
  INSTALL §13 now leads with 11.0 (FerretDB/PostgreSQL under the same REST
  API); 10.2.x kept as the historical baseline.
- Still to verify live on 11.0 (unchanged code paths): POST /search/facets,
  the trust-score read paths, and the MCP HTTP OAuth handshake.

## 1.9.11 — live reads: fix data-source inventory (clears demo fallback)

- run.bat: friendlier launcher — banner with version + a "what it is / what it
  connects to" summary (PDC target, api version, auth, TLS, LLM model, all read
  from .env), and a richer ready screen listing the app, AI builder, Settings,
  and the new diagnostics URLs. VERSION bumped to 1.9.11.

- data_sources() no longer calls GET /api/public/<v>/data-sources, which does
  not exist in the public API (only POST /data-sources/by-ids) and 404'd —
  forcing the whole snapshot to demo. It now enumerates catalog roots via POST
  /entities/filter (the method the Glossary Generator uses), with a data-source
  facet fallback, and never raises. This is what clears the demo banner once
  connected.
- New admin GET /health/pdc/probe runs each live read (facets, trust,
  data_sources) and reports counts / facet keys / a sample / per-call errors,
  so you can see exactly what the catalog returns without curl.

## 1.9.10 — load .env on startup

- wsgi.py now loads `.env` from the project root before the app reads config,
  anchored by file path so it works regardless of the launch directory. Real
  shell environment variables still override `.env`. Fixes the recurring "No
  PDC credentials configured" / reverted-TLS-verify after a restart, where a
  fresh process had `.env` values that were never read (only shell `set`s took
  effect). Plain `waitress-serve --port=8660 wsgi:app` now picks up the full
  configuration.

## 1.9.9 — token debug endpoint

- New admin-only `GET /health/pdc/token` fetches a bearer token through the
  app's own client and returns it (truncated; `?reveal=1` for the full token)
  with the decoded JWT claims (user, roles, expiry) and the exact Keycloak/
  legacy URLs, auth method, TLS-verify, and whether Cloudflare headers are in
  play. Lets you confirm the app is authenticating as expected without curl.

## 1.9.8 — sharper Cloudflare diagnosis

- The connection test now positively identifies a Cloudflare **Access** page
  (by following the redirect chain to `*.cloudflareaccess.com` / `/cdn-cgi/
  access`) versus a **Bot-Fight/managed challenge** (via `cf-mitigated`, the
  `cf-ray`/`server: cloudflare` edge headers), and reports the exact fix for
  each — including the missing "Service Auth" Access policy that lets a service
  token through. Shows where the request actually landed.
- The Test-connection probe now passes the configured Cloudflare Access service
  token explicitly, removing any env-timing ambiguity.

## 1.9.7 — Cloudflare Access / tunnel support

- When PDC sits behind a Cloudflare tunnel with Access or Bot Fight enabled, an
  API client receives an HTML challenge/login page instead of JSON (a browser
  passes it; `requests` can't). The client now sends Cloudflare Access
  service-token headers — `PDC_CF_ACCESS_CLIENT_ID` / `PDC_CF_ACCESS_CLIENT_SECRET`
  — on every PDC and Keycloak call, so it authenticates through the tunnel
  without a browser.
- The non-JSON auth error now recognises a Cloudflare interstitial (via
  `cf-mitigated`, the `CF_Authorization` cookie, or the challenge markup) and
  says so explicitly, pointing at the service-token fix or an internal address
  that bypasses Cloudflare — instead of the generic "hit the web UI" message.

## 1.9.6 — auth diagnostics + model picker

- PDC auth no longer fails with a bare "Expecting value: line 1 column 1" when
  an endpoint returns a non-JSON 2xx body (e.g. a reverse proxy / SPA catch-all
  instead of the API). The client now raises a clear error naming the endpoint,
  status, content-type, and a body snippet, with a hint to check the Base URL /
  that `/keycloak` is exposed (or set `PDC_KC_BASE`/`PDC_KC_REALM`). In `auto`
  mode a non-JSON Keycloak reply cleanly falls back to the legacy `/auth` path.
- Settings model picker is now a real combobox: clicking the field lists **all**
  installed Ollama models and typing filters them. (The old native `<datalist>`
  hid every other model once the field held a full name — the "only one model
  shows" problem.) You can still type any name to pull it; ↑/↓/Enter/Esc work.

## 1.9.5 — Keycloak-first PDC authentication

- PDC auth now goes to the Keycloak realm token endpoint
  (`{base}/keycloak/realms/{realm}/protocol/openid-connect/token`) and reads the
  top-level `access_token`, matching how PDC delegates auth to Keycloak. New
  `PDC_AUTH_METHOD` (`auto`|`keycloak`|`pdc`) defaults to `auto`: Keycloak first,
  falling back to the legacy `/api/public/<v>/auth` wrapper. This fixes the
  "Auth returned 200 but no accessToken" case, where the wrapper responds 200
  without issuing a token.
- New config: `PDC_AUTH_METHOD`, `PDC_KC_REALM` (default `pdc`),
  `PDC_KC_CLIENT_ID` (default `pdc-client`), `PDC_KC_BASE` (optional). Base URL
  is now paste-robust — a pasted realm/API path is normalised to the server root.
- Settings → Test connection now exercises the real client auth path, decodes
  the issued JWT to show the user/roles, and confirms a read-only facet call
  accepts the token.
- Verified end to end against a mock Keycloak+PDC: token issue + decode, bearer
  accepted on a real `facets()` read, 401 re-auth, auto fallback on a Keycloak
  404, keycloak-only failure surfacing, and the paste-guard.

## 1.9.4 — drill-through to underlying assets

- Clicking a chart panel (or a row in a panel table) opens a slide-in drawer
  listing the underlying assets behind it, honouring the active data-source
  scope and the clicked segment/row label. Esc or the scrim closes it.
- New read-only POST /api/dashboards/drill {query, label?, source?} returns the
  asset rows (demo synthesises from the snapshot; live would issue a
  facet-filtered /search).
- Verified: drawer opens with assets and closes on Escape with zero page errors;
  suite covers the endpoint (rows/columns, label detail, 400, source scoping).

## 1.9.3 — per-dashboard data-source scope filter

- Each standard dashboard now has a data-source selector (All sources + each
  connected source). Choosing one narrows every panel to that source: per-source
  fields (assets, quality, coverage, high-sensitivity) are used directly and
  global distributions are scaled by the source's share (a demo approximation;
  live would be a data-source-filtered facet query).
- Resolver gained scope_snapshot() and source_names(); /data and /resolve accept
  a source (query param / body field) and echo the active scope; new
  GET /api/dashboards/sources lists the connected sources.
- Verified: selecting a source re-renders the board (e.g. catalog assets
  12,480 → 4,210 for one source) with zero page errors; suite covers scoping.

## 1.9.2 — remaining dashboard panels wired to live data

- Extended the demo snapshot with aggregates modelled on real PDC entity
  attributes (isLineageVerified, features.rating, policies[], owners[],
  businessTerms[], edit activity, coverage %s).
- Added resolvers and tagged the previously-unwired panels: lineage status &
  by-source, ratings distribution, policy counts & coverage, top business terms,
  edit activity, owner workload, ownership time, encryption/masking status,
  untermed-critical, unowned-high-value, highest-risk assets, DQ-by-source. 41
  chart/table panels across 31 queries now render from the resolver.
- Verified every wired query resolves with no errors across kpi/chart/stacked/
  table shapes; headless sweep of all sections and tabs shows zero page errors.

## 1.9.1 — standard dashboard charts & tables wired to live data

- Extended live-data wiring from the KPI row to the charts and tables on the
  standard dashboards. 27 prominent panels backed by real snapshot aggregates
  (trust spectrum, sensitivity mix, quality by source, profiling status, assets
  by source/type, term coverage gauge, coverage trend, sensitive-by-source,
  owners coverage, quality distribution, DQ dimensions, worst tables, source
  inventory, stale/failed, PII discoveries, …) now re-render from the resolver.
- Added a shared chart adapter that maps resolver output to each renderer's shape
  (spectrum/donut/bars/line/stacked/gauge/radar/histogram/bullet/table) and a
  unified overlay that refreshes KPIs, charts and tables together; panels fall
  back to their baked render when the backend isn't reachable (offline/file://).
- Panels with no grounded aggregate keep their baked sample data, so nothing is
  mislabelled as live. The per-dashboard live/demo badge reflects the source.
- Tests: per-shape resolver checks for every wired renderer type. Verified live:
  the trust spectrum and KPI tiles read the demo sample in demo mode and the PDC
  values when connected. Full regression green; zero page errors across a sweep
  of all sections and dashboard tabs.

## 1.9.0 — dashboards wired to live data

- New read-only panel-data resolver (app/panel_data.py) turns each dashboard
  panel's query into real values from the catalog snapshot. Queries backed by
  aggregates (trust, sensitivity, profiling, PII, per-source metrics) compute
  real numbers; the rest are derived deterministically from the same snapshot so
  every panel renders and nothing errors on a sparse live snapshot.
- New endpoints: GET /api/dashboards/<section>/<id>/data and
  POST /api/dashboards/resolve (both viewer, read-only).
- Chat preview now renders real numbers/series/tables for the built dashboard
  (KPIs, bars, donuts, stacked, lines, tables) with a live/demo badge, instead of
  fixed placeholder shapes. Grouped data honours the panel's declared chart type.
- Standard dashboards overlay live headline KPI values (catalog assets, sources,
  glossary coverage, high sensitivity, profiled %) by matching tile labels to
  resolver queries, with a live/demo badge per dashboard. Verified end-to-end:
  the same tile shows the demo value in demo mode and the live PDC value when
  connected.
- Tests: resolver unit checks, both new endpoints (+404), full-dashboard resolve
  for all 12 with no panel errors. Full regression green; zero page errors.

## 1.8.0 — full regression + fixes found by it

Ran a complete regression (compile, JS syntax, security + functional suites, MCP
boot, launch scripts, every live endpoint, and a headless-browser pass over both
UIs). It surfaced three issues, now fixed:

- Added an inline SVG favicon to both pages — the browser's automatic
  /favicon.ico request was logging a 404 in the console.
- The chat builder now re-renders the section greeting when restoring a saved
  conversation, so the transcript is consistent after a reload (the saved
  user+assistant context was already preserved correctly).
- Confirmed end-to-end through the UI that the PDC "Test connection" button
  reports the real reason (exercised the 401 path live) and the Model picker
  populates from installed Ollama models.

No functional regressions: both suites green, 12 dashboards intact, MCP boots
9 tools / 3 resources, zero page errors.

## 1.7.1 — model picker + real PDC connection test

- Settings Model field is now a picker populated from the models installed in
  your local Ollama (GET /api/llm/models), while still allowing a typed name.
- Settings "Test connection" for PDC now genuinely authenticates and reports the
  specific failure (unreachable host, 401/403 bad creds, 404 wrong API version,
  TLS error) instead of only showing "demo". New POST /api/settings/test-pdc
  tests the form values before you save.
- Docs: added a "PDC won't connect" troubleshooting section and model-picker note.

## 1.7.0 — more suggestions, chat memory, summaries, colour, tooltips

- More dashboard suggestions driven by your PDC connections, each mapped to a
  real search facet: Compare sources (2+ sources), Scan freshness, Key coverage,
  File format mix, Tag coverage, Domain coverage.
- Chat builder now remembers state per section (localStorage) so context
  survives a refresh or navigating away; added a Clear chat control.
- Added a Summary toggle on the chat preview: a plain-language description of
  what the built dashboard shows, derived from the spec (no extra model call).
- Chat preview charts are now colourful (multi-hue governance palette: brand
  teal + the red→amber→green trust spectrum) instead of flat teal.
- Added helpful tooltips across the app (sidebar sections, Settings actions) and
  the chat preview toolbar.
- Fix: the functional test's cleanup used Path().stem (which left ".studio") and
  was deleting all built-in dashboards after each run; it now strips the full
  extension and rebuilds canonical dashboards up front, so the suite is hermetic.
- Docs: documented that data sources are configured in PDC (read-only here) and
  the new connection-grounded suggestions.

## 1.6.0 — save & run against real data, prettier launch scripts

- Settings → Save & apply now switches the app to a live PDC without a restart:
  applies in place, persists to .env, re-authenticates, and the next
  snapshot/recommend/chat reads real data. (Most of this path existed; this
  verifies it end-to-end and makes it discoverable.)
- Added a demo-data banner with an "Open Settings" shortcut, shown whenever the
  app is on demo data, so switching to real data is obvious.
- Rewrote run.sh / run.bat: sectioned, colourised output, preflight checks
  (Python, deps, .env, free port, GPU/CPU, Ollama reachability) and a post-start
  health check that reports app + PDC + LLM status before printing the URLs.
  New shared helper tools/preflight.py.
- model_advice.recommend(force_mode) + /api/llm/suggest?mode= honour the CPU/GPU
  toggle from the scripts.
- Fix: the archive no longer bundles a stray .env (it could overwrite your own
  config on unzip); .env is excluded from packaging.
- Tests: test_app.py covers /api/settings (no password leak, 400 on junk) and
  apply_settings flipping demo→live in place.

## 1.5.1 — live connection status in the footer

- The sidebar footer LLM/PDC dots now reflect REAL reachability instead of static
  placeholders: the LLM dot pings Ollama (/health/llm) and shows the model when
  reachable (green) or "offline" (amber); the PDC dot shows live vs demo via the
  new /health/pdc. Re-checks every 30s. Fixes the footer always showing the LLM
  as amber even when connected.
- Added GET /health/pdc (demo/live + base_url); tests cover both health dots.

## 1.5.0 — one-command launch scripts (run.sh / run.bat)

- Added run.sh (macOS/Linux) and run.bat (Windows): create the venv, install
  deps, write .env on first run, auto-detect GPU vs CPU, print/optionally --pull
  the recommended model, start the web app (waitress on Windows, gunicorn on
  Linux/macOS, Flask fallback), and optionally start the MCP server with --mcp.
- CPU/GPU toggle: --gpu/--cpu flags (default auto-detects via nvidia-smi) flow
  through to model_advice.recommend(force_mode) and GET /api/llm/suggest?mode=.
- Docs: README + INSTALL now lead with the launch scripts; clarified in README,
  INSTALL, MCP-SERVER, and DEPLOYMENT that the local LLM does NOT need the MCP
  server (it's only for external chat/agents like Claude Desktop).

## 1.4.0 — in-app model download + Settings docs

- Settings page can now detect this machine (GPU/CPU) and **download the
  recommended Ollama model** with live progress — no separate `ollama pull`.
- New routes: GET /api/llm/suggest (hardware-aware recommendation, shared with
  tools/suggest_model.py via app/model_advice.py), GET /api/llm/models, and
  POST /api/llm/pull (streams Ollama pull progress as NDJSON; steward-gated).
- waitress is now a real dependency, so the documented Windows run command
  (`waitress-serve --port=8660 wsgi:app`) works after a plain pip install.
- Docs: documented the Settings page (with screenshot) and in-app model
  download; clarified that the MCP server is a separate process from the web
  app; added Windows env-var syntax (`set MCP_HTTP=1`) for the MCP HTTP run.
- Settings defaults aligned: endpoint localhost, read-only pdc_user.
- Tests: test_app.py covers /api/llm/suggest, /models, and /pull.

## 1.3.0 — download & print dashboards

- Every dashboard can be downloaded as a .studio.json spec and printed / saved
  as PDF, from both the app dashboard view and the chat preview.
- Download (app): new GET /api/dashboards/<section>/<id>/download streams the
  spec as an attachment; the toolbar Download button uses it (with a client-side
  fallback). Download (chat): exports the in-memory spec.
- Print / PDF: a @media print stylesheet hides the app chrome and lays out only
  the active dashboard with a branded header, so the browser's Save-as-PDF
  produces a clean report — no server-side renderer or extra dependency.
- Tests: test_app.py now covers the download endpoint (attachment headers + 404).
- Docs: download & print documented in README, INSTALL, and DASHBOARDS.

## 1.2.1 — tests, code comments, docs

- Added tools/test_app.py: a functional suite (34 checks) covering section-aware
  recommend, the deterministic chat builder, the /api/chat + /api/recommend +
  /chat routes, refine, save, and generator validation. Runs on demo data.
- Detailed comments added to the chat route, the chat page's JavaScript (header
  + per-function), and surrounding code grown since the last comment pass.
- Docs: documented the in-app chat builder and section-aware suggestions in
  README, INSTALL (verify step now runs both suites), and DASHBOARDS.

## 1.2.0 — section-aware suggestions

- The in-app chat builder is now section-aware. Open /chat?section=<section>
  (or the "Build with AI" button inside any Analytics section) and the starter
  chips are that section's recommended dashboards, ranked by real catalog
  signals; new dashboards are pinned to the section.
- recommend() / GET /api/recommend / the MCP recommend_dashboards tool all take
  an optional category|section filter.
- Added evergreen per-section suggestions so every Analytics section (incl. User
  and Quality) always has real starters, with signal-driven ones ranked higher.
- Wired the main app's "Build with AI" button to the section-aware chat, and a
  "← Dashboards" link back from the builder.

## 1.1.0 — in-app AI dashboard builder (chat)

- New chat window in the web app at /chat: describe a dashboard, preview it, and
  click "Add to dashboards" to save it into the right section. Grounded on the
  real Query Library and validated before save.
- New POST /api/chat endpoint (conversational, role-gated) backed by the LLM
  generator, with a deterministic offline builder (app/chat_build.py) so the
  chat works end to end without a model.
- Shares the same generator + save path as the standard dashboards and the MCP
  server; the in-app chat and the MCP server are the built-in vs external chats.

## 1.0.7 — docs: connect the MCP server to a chat

- INSTALL §8 now walks through hooking the MCP server up to a chat end to end:
  Claude Desktop config file locations (macOS/Windows), pointing `command` at the
  venv Python that has the deps, restart, verifying the tools appear, and an
  example suggest-then-build conversation.
- Added notes for other MCP chat clients over HTTP and a quick tool test with the
  MCP Inspector (`mcp dev`).

## 1.0.6 — CPU option + hardware-aware model suggestion

- Added `tools/suggest_model.py`: detects OS, RAM, CPU cores, and any NVIDIA GPU,
  then recommends an Ollama model (GPU or CPU tier) and the right native run
  command for the platform.
- Documented a CPU-only path with a model-sizing table (3B/1.5B/0.5B) and tips
  (smaller model, OLLAMA_NUM_PARALLEL=1, keep JSON mode on).
- Added per-platform native run commands; Windows uses `waitress-serve`
  (gunicorn is POSIX-only). Noted in README, INSTALL, and requirements.

## 1.0.5 — read-only account default + native-first LLM config

- Examples now use a READ-ONLY PDC account (`pdc_user`) everywhere, reflecting
  best practice (the app only reads; least-privilege belongs in PDC).
- `LLM_BASE_URL` now defaults to the native `http://localhost:11434`. When the
  app runs via docker compose, the compose file auto-overrides it with
  `host.docker.internal` — so native runs work out of the box and Docker runs
  still reach a host Ollama, with no manual switching.
- Documented a first-class "run natively (no Docker)" path for the web app and
  the MCP server (venv + gunicorn / `python -m mcp_server.server`).
- Deployment guide now recommends native app + native Ollama on the Windows/GPU
  box as the lower-friction setup, Docker as the self-contained alternative.

## 1.0.4 — docs update

- Documented the corrected PDC auth flow (form-encoded /auth → data.accessToken)
  across INSTALL, ARCHITECTURE, and PDC-CONNECTOR, with a manual token curl and
  a read/connect test.
- Added Ollama connection guidance: which LLM_BASE_URL to use where, the
  OLLAMA_HOST=0.0.0.0 bind gotcha, and how to verify the connection.
- Expanded troubleshooting (Ollama bind, model-not-installed, PDC auth/version).
- Clarified the PDC_BEARER_TOKEN caveat (disables auto re-auth) in .env.example.

## 1.0.3 — PDC auth fix

- Corrected the PDC /auth call to match the documented contract: it now sends
  FORM-ENCODED credentials (client_id=pdc-client, grant_type=password,
  scope="openid profile email") instead of JSON, and reads the JWT from
  data.accessToken (was data.token). Required for authenticating to a real PDC
  instance.

## 1.0.2 — port change (final)

- Web app default host port is **8660** (was briefly 8090, which also clashes
  with Pentaho's AWS/K8s config port-forward; original default 8080 is Tomcat).
  8660 clears the Pentaho/Tomcat and PDC port ranges. Fully overridable via
  `INSIGHTS_PORT`; the container always listens on 8660 internally. MCP server
  stays on 8765. See the Ports table in INSTALL.md for the reserved list.

## 1.0.1 — port change

- Initial move off 8080 (superseded by 1.0.2).

## 1.0.0 — first complete release

Initial end-to-end build of Catalog Insights: AI-assisted reporting and
dashboards for Pentaho Data Catalog, plus an MCP server, delivered as a single
containerised project. Runs today in demo mode; ready to point at a live PDC
10.2.11 instance.

### Web app
- Flask backend, read-only PDC client (auth, search, facets, entities,
  data-sources) with automatic re-auth on 401.
- Dashboard spec schema (`.studio.json`) as the single contract.
- LLM dashboard generator: ground → generate → validate → repair loop.
- 12 built-in standard dashboards across 6 sections (also enablement examples).
- Self-contained design mock UI (`ui/mock/index.html`).
- API: `/health`, `/config`, `/api/{facets,search,snapshot,recommend,generate}`,
  `/api/dashboards` — each role-gated.

### MCP server
- 9 tools + 3 resources over the same engine: list_data_sources,
  catalog_snapshot, search_assets, recommend_dashboards, list_standard_dashboards,
  get_query_catalog, generate_dashboard, validate_dashboard, save_dashboard.
- Recommends dashboards from live scan/connection state, then builds them.
- stdio (Claude Desktop) and HTTP transports.

### Security
- Shared auth/roles/audit (`app/security.py`) enforced by both front doors.
- Roles viewer < steward < admin (mirroring PDC tiers); only write is gated.
- Auth modes: none | apikey | jwt (shared secret or JWKS, role-claim mapping).
- Structured JSON audit log of every privileged action.
- Test suite: `python tools/test_security.py`.

### LLM
- Pluggable providers: local (Ollama), commercial (Anthropic/OpenAI), disabled.
- Local default for governance data privacy; constrained JSON output.

### Ops & docs
- Docker + docker-compose (web + optional `--profile mcp`).
- Demo mode (`INSIGHTS_DEMO=true`) for running without a live PDC.
- README, INSTALL guide, 8 docs, 5 rendered architecture/flow diagrams.
- Detailed inline code comments throughout.

### Known limitations
- Dashboard panels are demo-backed until wired to live PDC reads.
- Trust-score *recalculation* via the public API is version-dependent — verify
  on the target instance.
- MCP HTTP OAuth metadata is wired but should be validated against your IdP.
