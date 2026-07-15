# Install guide

Step-by-step setup for **Catalog Insights** — the web app and the MCP server.
Both are thin, stateless clients to the PDC public REST API and an LLM endpoint,
so installation is mostly: get the code, fill in `.env`, run a container.

> You can do every step below with **no live PDC** by setting `INSIGHTS_DEMO=true`
> — the app serves a bundled sample catalog. Good for a first run and for
> enablement. Switch it off when you point at a real instance.

---

## Contents

1. [How it connects (what you do and don't install)](#1-how-it-connects)
2. [Prerequisites](#2-prerequisites)
3. [Pick your path](#3-pick-your-path)
4. [Get the code](#4-get-the-code)
5. [Configure `.env`](#5-configure-env)
6. [Run the web app](#6-run-the-web-app)
7. [Run a local model (Ollama + GPU)](#7-run-a-local-model-ollama--gpu)
8. [Run the MCP server](#8-run-the-mcp-server)
9. [Turn on security](#9-turn-on-security)
10. [Connect to PDC](#10-connect-to-pdc)
11. [Verify everything](#11-verify-everything)
12. [Troubleshooting](#12-troubleshooting)
13. [Version & upgrade notes](#13-version--upgrade-notes)

---

## 1. How it connects

Catalog Insights talks to **one thing**: the PDC public REST API. PDC keeps its
data in several stores behind that API — OpenSearch (search/facets), MongoDB
(operational & user metadata; FerretDB/PostgreSQL from PDC 11.0), and a BIDB for
JDBC/ODBC BI access. **You never connect to those directly, and you shouldn't.**
The REST API is the contract that shields the app from those engines and their
version changes.

```
  You install:                    Already exists (you connect to it):
  ┌────────────────────┐          ┌──────────────────────────────┐
  │ Catalog Insights   │  REST    │ PDC  (Linux, Docker)         │
  │  web app  :8660    │─────────▶│  REST API ─▶ OpenSearch      │
  │  MCP svr  :8765    │          │            ─▶ MongoDB        │
  └─────────┬──────────┘          │            ─▶ BIDB           │
            │ HTTP                 └──────────────────────────────┘
            ▼
  ┌────────────────────┐
  │ LLM endpoint       │   Ollama (local GPU) or a commercial API
  └────────────────────┘
```

No Pentaho Server, CTools, or Semantic Model Editor is installed or required.

### Ports

| Port | Used by | Notes |
| ---- | ------- | ----- |
| **8660** | Catalog Insights web app | default; override with `INSIGHTS_PORT` |
| **8765** | Catalog Insights MCP (HTTP) | override with `MCP_PORT` |
| 8080 | Pentaho Server / PUC (Tomcat) | avoid |
| 8090 | Pentaho config (AWS/K8s port-forward) | avoid |
| 8443 / 9443 | Pentaho SSL / redirect | avoid |
| 8009 / 8005 | Tomcat AJP / shutdown | avoid |
| 9200 | PDC OpenSearch | avoid |
| 27017 | PDC MongoDB | avoid |
| 11434 | Ollama (local LLM) | host service |

Both app ports are fully overridable, and the containers listen on their
defaults internally regardless of the host mapping you choose.

## 2. Prerequisites

| Need | For | Notes |
| ---- | --- | ----- |
| Docker + Docker Compose | running the app/MCP | Docker Desktop on Windows/macOS; Docker Engine on Linux |
| A PDC instance + a read-only account (11.0 is the target; 10.2.x also works) | live data | optional — use `INSIGHTS_DEMO=true` to skip at first |
| Ollama (optional) | local LLM generation | recommended for governance data; needs a GPU for speed |
| Python 3.12 (optional) | running tests / stdio MCP without Docker | only if you run outside containers |
| An NVIDIA GPU (optional) | fast local inference | e.g. your 2× RTX 3060 |

## 3. Pick your path

- **A — Windows 11 + GPU (your box).** Ollama native on Windows (uses both
  GPUs), app + MCP in Docker Desktop, PDC reached over the network. Best mix of
  speed and simplicity. Steps: 4 → 5 → 7 → 6 → 8.
- **B — Linux, co-located with PDC.** Add the app/MCP as containers on the PDC
  host (lab) or a small adjacent VM (production). Steps: 4 → 5 → 6 → 8.
- **C — Local dev / demo.** One machine, `INSIGHTS_DEMO=true`, `LLM_PROVIDER`
  off or local. Steps: 4 → 5 (demo) → 6.

See `docs/DEPLOYMENT.md` for the co-location trade-offs and GPU sizing rationale.

### Quickest start — the launch script

If you just want it running, the launch script does steps 4–7 for you: creates
the venv, installs dependencies, writes `.env` on first run, auto-detects GPU vs
CPU, prints (and optionally pulls) the right model, and starts the web app —
plus the MCP server if you ask for it.

```bash
./run.sh                 # macOS/Linux — web app only
./run.sh --mcp --pull    # also start the MCP server and download the model
```
```bat
run.bat                  :: Windows — web app only
run.bat --mcp --pull     :: also start the MCP server and download the model
```

| Flag | Effect |
| ---- | ------ |
| `--mcp` | also start the MCP server (HTTP :8765) — only needed for external chat/agents |
| `--gpu` / `--cpu` | force model sizing; default auto-detects via `nvidia-smi` |
| `--pull` | download the recommended Ollama model (needs `ollama` on PATH) |
| `--port N` | web app port (default 8660) |
| `--no-venv` | use the current Python instead of creating `.venv` |

The web app runs on **waitress** (Windows) or **gunicorn** (Linux/macOS),
falling back to the Flask dev server if neither is present. `run.sh --help` / `run.bat --help` print the same summary. Both run **preflight checks** (Python, deps, `.env`, free port, GPU/CPU, Ollama reachability) and a **post-start health check** that reports whether the app is up and whether PDC/LLM are live before handing you the URLs.

> **Local LLM does not need the MCP server.** Ollama is called directly by the
> web app for the `/chat` builder and dashboard generation. The MCP server is a
> separate process you start (`--mcp`) only to drive Catalog Insights from an
> *external* chat/agent such as Claude Desktop. The rest of this guide covers the
> manual steps the script automates.

## 4. Get the code

```bash
git clone <your-repo-url> PDC-Insights      # or unzip the delivered archive
cd PDC-Insights
cp .env.example .env
```

## 5. Configure `.env`

Open `.env` and set the blocks you need. Minimum to start in demo mode:

```ini
INSIGHTS_DEMO=true
LLM_PROVIDER=disabled        # turn on later (step 7)
INSIGHTS_AUTH=none           # turn on later (step 9)
```

To point at a real PDC and a local model:

```ini
INSIGHTS_DEMO=false
PDC_BASE_URL=https://pdc.yourcompany.local
PDC_API_VERSION=v3
PDC_USERNAME=pdc_user          # a READ-ONLY PDC account (best practice)
PDC_PASSWORD=••••••••
PDC_VERIFY_TLS=true

LLM_PROVIDER=local
LLM_BASE_URL=http://localhost:11434   # Ollama on this host; see §7 for Docker
LLM_MODEL=qwen2.5:7b-instruct
LLM_JSON_MODE=true
```

Every variable is documented inline in `.env.example`.

## 6. Run the web app

**Natively (Ollama is already native on your host — simplest, most flexible):**

```bash
python -m venv .venv && . .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
gunicorn --bind 0.0.0.0:8660 --threads 4 wsgi:app   # or: flask --app wsgi run -p 8660
```

`LLM_BASE_URL=http://localhost:11434` works directly — no container hop. This is
the recommended setup when Ollama runs on the same host. On **Windows**, use
`waitress-serve --port=8660 wsgi:app` instead of gunicorn (see §7 for the
per-platform table, and `python tools/suggest_model.py` to pick a model).

**Or via Docker** (self-contained; the compose file auto-points the LLM at the
host so you don't change anything):

```bash
docker compose up --build
```

Either way: open <http://localhost:8660>; health check <http://localhost:8660/health>.

In demo mode the dashboards, snapshot, and recommendations work immediately. The
mock UI (`ui/mock/index.html`) is also openable directly in a browser for design
review without running anything.

**Build dashboards by chat.** Once the app is running, open **`/chat`**
(e.g. <http://localhost:8660/chat>) for the in-app AI builder: describe a
dashboard, preview it, and click **Add to dashboards** to write it into the right
section. It uses your local LLM when configured (§7) and a deterministic builder
otherwise, so it works even before Ollama is wired up. It’s **section-aware**:
the **Build with AI** button in any Analytics section opens `/chat?section=<that
section>`, where the suggested starters are that section’s recommended
dashboards and new ones are pinned to it. (This is the built-in chat; §8's MCP
server is for *external* chats like Claude Desktop.)

**Download & print.** Any dashboard (standard or chat-built) has *Download* (saves a `.studio.json` spec) and *Print / PDF* (browser print dialog → Save as PDF) buttons.

## 7. Run a local model (Ollama + GPU)

Recommended default for a governance tool: generation runs locally, so catalog
and PII metadata never leave your environment.

**Windows 11 (your 2× RTX 3060):**

1. Install Ollama for Windows — it uses CUDA and both GPUs automatically.
2. Pull a model:
   ```powershell
   ollama pull qwen2.5:7b-instruct
   ```
3. Since Ollama is native on the host, the simplest setup is to run the app
   natively too (§6) and keep the default `LLM_BASE_URL=http://localhost:11434`.
   No Docker networking, no `host.docker.internal` — just localhost.

**Which `LLM_BASE_URL` to use** (Ollama always listens on port 11434; the app
calls `/api/chat`, and the health check hits `/api/tags`):

| Where the app runs | `LLM_BASE_URL` |
| ------------------ | -------------- |
| Natively on the host (recommended here) | `http://localhost:11434` — the default |
| Via docker compose, Ollama on the host | handled for you — compose injects `host.docker.internal` |
| Both app and Ollama in the same compose network | `http://ollama:11434` (service name) |

So the `.env` default is the native `localhost`; only the containerised path
needs `host.docker.internal`, and the compose file sets that itself — you don't
edit anything to switch between the two.

> **Docker-only gotcha:** Ollama binds to `127.0.0.1:11434` by default, so a
> *container* hitting `host.docker.internal` gets *connection refused* even
> though Ollama is running. Fix it by making Ollama listen on all interfaces —
> set `OLLAMA_HOST=0.0.0.0:11434` on the **host** (on Windows: System Environment
> Variables → restart the Ollama tray app/service), then retry. Running the app
> natively avoids this entirely.

**Verify the connection:**
- From the host: `curl http://localhost:11434/api/tags` should list your models.
- From the app: Settings → "Test connection", or `GET /health/llm` — it probes
  `/api/tags` and returns `{ok, model, detail: "N model(s) available"}`.
- Pull the model first (`ollama pull qwen2.5:7b-instruct`): the connection can
  be healthy but generation fails if the named model isn't installed, and the
  health check only lists what's present.

**Not sure which model?** Run the detector — it reads your OS, RAM, cores, and
any NVIDIA GPU and prints a recommended model + the right run command:

```bash
python tools/suggest_model.py
```

**Model sizing — GPU (VRAM is the limit):**

| Model | ~VRAM (Q4) | Fits | When |
| ----- | ---------- | ---- | ---- |
| `qwen2.5:7b-instruct` | ~5 GB | one card | default — fast, strong JSON |
| `qwen2.5:14b-instruct` | ~9 GB | one card | more headroom |
| `qwen2.5:32b-instruct` | ~20 GB | both cards | overkill for spec JSON |

**Model sizing — CPU-only (no GPU; RAM is the limit, and smaller = faster):**

| Model | ~RAM (Q4) | When |
| ----- | --------- | ---- |
| `qwen2.5:7b-instruct` | ~6 GB | 32 GB+ RAM; works, just slower than GPU |
| `qwen2.5:3b-instruct` | ~3 GB | the CPU sweet spot — usable latency |
| `qwen2.5:1.5b-instruct` | ~2 GB | limited RAM; keeps generation tractable |
| `qwen2.5:0.5b-instruct` | ~1 GB | very limited RAM; expect weaker specs |

On CPU, generation is slower than GPU — prefer a smaller model, keep
`LLM_JSON_MODE=true` (constrained JSON matters more than size), and consider
`OLLAMA_NUM_PARALLEL=1`. Everything else (dashboards, reads, recommendations) is
unaffected by model choice. Commercial APIs (`LLM_PROVIDER=anthropic|openai`)
remain an opt-in alternative if local CPU generation is too slow.

### Native run command by platform

| Platform | Command (web app) |
| -------- | ----------------- |
| Linux / macOS | `gunicorn --bind 0.0.0.0:8660 --threads 4 wsgi:app` |
| Windows | `waitress-serve --port=8660 wsgi:app`  (`pip install waitress`) |
| Any (quick/dev) | `flask --app wsgi run -p 8660` |

gunicorn is POSIX-only, so on Windows use **waitress** (a production-grade WSGI
server that runs natively) or the Flask dev server for local use.

### Configure in the app (Settings)

Most of `.env` can also be reviewed from the running app under **Settings**
(`Configure → Settings`). It surfaces the LLM connection (provider, endpoint,
model, JSON mode), the PDC connection (base URL, API version, read-only account,
cache), and branding — with **Test connection** for both.

![Settings page](settings.png)

**Download a model from here.** The Settings LLM card detects this machine
(GPU vs CPU) and recommends a model, then **Download model** pulls it into your
local Ollama with a live progress readout — no separate `ollama pull` needed.
Behind the scenes this is `GET /api/llm/suggest` (the same advice as
`tools/suggest_model.py`) and `POST /api/llm/pull` (streams Ollama's progress).
Downloading a model needs the `steward` role when auth is on.

**Status dots.** The sidebar footer shows live connection state: **green** = the
dependency is reachable (the LLM dot pings Ollama via `/health/llm`; the PDC dot
reflects live data via `/health/pdc`), **amber** = configured but not reachable,
or running on demo data. So if the LLM dot is amber, the app can't reach Ollama
at the configured endpoint — start Ollama (or fix `LLM_BASE_URL`) and it turns
green with the model name. The dots re-check every 30 seconds.

## 8. Run the MCP server

The MCP server exposes the catalog and the generator as tools an LLM/agent can
call (suggest dashboards from scans, then build them). Two transports:

**HTTP (agents / remote):**

```bash
# natively (install MCP deps once):
pip install -r requirements.txt -r requirements-mcp.txt
MCP_HTTP=1 python -m mcp_server.server          # serves on :8765  (Linux/macOS)

# Windows (cmd): set the variable first, on its own line
set MCP_HTTP=1
python -m mcp_server.server
# Windows (PowerShell): $env:MCP_HTTP=1; python -m mcp_server.server

# or via Docker:
docker compose --profile mcp up insights-mcp    # serves on :8765
```

> **The MCP server is a separate process from the web app** — two front doors on
> the same engine. You do **not** need it to use the dashboards or the built-in
> `/chat` builder; start it only to drive Catalog Insights from an *external*
> chat/agent (Claude Desktop, an IDE). Run the web app with `waitress-serve`
> (§6) and, if you want it, the MCP server with the command above in a second
> terminal.

**Claude Desktop (stdio)** — add to `claude_desktop_config.json`:

```jsonc
{
  "mcpServers": {
    "catalog-insights": {
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "cwd": "/absolute/path/to/PDC-Insights",
      "env": {
        "INSIGHTS_DEMO": "true",
        "PDC_BASE_URL": "https://pdc.yourcompany.local",
        "LLM_PROVIDER": "local",
        "LLM_BASE_URL": "http://localhost:11434"
      }
    }
  }
}
```

### Hook it up to a chat (Claude Desktop)

1. **Install the server's dependencies** into the Python that Claude Desktop
   will launch:
   ```bash
   pip install -r requirements.txt -r requirements-mcp.txt
   ```
2. **Open the config file** (create it if it doesn't exist):
   - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - Windows: `%APPDATA%\Claude\claude_desktop_config.json`
3. **Paste the block above** and edit two things:
   - `cwd` → the absolute path to your `PDC-Insights` folder.
   - `command` → point at the **exact Python that has the deps**, so Claude
     Desktop can import `mcp`/`flask`. If you used a venv, give its interpreter:
     `"/abs/path/PDC-Insights/.venv/bin/python"` (Windows:
     `"C:\\path\\PDC-Insights\\.venv\\Scripts\\python.exe"`) and you can then
     drop the `-m` ambiguity by keeping `"args": ["-m", "mcp_server.server"]`.
   - Set `INSIGHTS_DEMO` to `false` and fill in real `PDC_*` creds when you're
     ready to chat against live data (leave `true` to try it offline first).
4. **Fully quit and reopen Claude Desktop** (config is read at startup).
5. **Confirm it connected:** the tools/connector (slider) icon in the chat box
   should list **catalog-insights** with its tools. If it's missing, open the
   MCP log (Claude Desktop → Settings → Developer) — usually a wrong `cwd` or a
   `command` Python without the deps.

**Now chat with your catalog.** Example flow:

> **You:** Based on what's connected and scanned, what dashboards should we build?
> **Claude:** *(calls `recommend_dashboards`)* … surfaces e.g. *Exposure · S3-raw*
> with the reason (52% unowned, 310 high-sensitivity assets).
> **You:** Build the exposure one for S3.
> **Claude:** *(calls `generate_dashboard` → `validate_dashboard` → `save_dashboard`)*
> … the spec is written to `app/dashboards/sensitivity/` and appears in the web app.

Other useful asks: *"List the connected data sources,"* *"Show a catalog
snapshot,"* *"Generate a quality dashboard scoped to Postgres-billing,"*
*"Validate this spec."* Full tool list and the suggest-then-build sequence are
in `docs/MCP-SERVER.md`.

> Writes (`save_dashboard`) require the `steward` role once you turn on auth
> (§9). With `INSIGHTS_AUTH=none` (local), the default role allows it.

### Other MCP chat clients / agents (HTTP)

Any MCP-capable client can connect over the HTTP transport instead of stdio:
point it at `http://<host>:8765` after starting the server with `MCP_HTTP=1`
(or the `--profile mcp` container). If auth is on, the client supplies a bearer
token (§9).

### Quick test without a chat (MCP Inspector)

To verify the tools respond before wiring a chat, use the Inspector that ships
with the MCP CLI:

```bash
mcp dev mcp_server/server.py        # opens a local UI to call each tool
```

The Inspector lets you click each tool (e.g. `recommend_dashboards`,
`generate_dashboard`) and see the JSON it returns — handy for confirming the PDC
connection and demo/live data before you chat.

## 9. Turn on security

Auth/roles/audit are shared by the web app and the MCP server. Set the mode in
`.env`.

**API keys (simple):**

```ini
INSIGHTS_AUTH=apikey
INSIGHTS_API_KEYS=adminkey:alice:admin,stewkey:bob:steward,viewkey:carol:viewer
INSIGHTS_AUDIT_LOG=/var/log/insights-audit.log
```

Call with `Authorization: Bearer stewkey`. Roles: `viewer` (read) < `steward`
(+ save/generate) < `admin`.

**JWT / SSO (Okta, Entra, …):**

```ini
INSIGHTS_AUTH=jwt
INSIGHTS_JWT_JWKS_URL=https://your-idp/.well-known/jwks.json
INSIGHTS_JWT_AUDIENCE=catalog-insights
INSIGHTS_JWT_ISSUER=https://your-idp/
INSIGHTS_JWT_ROLE_CLAIM=role
INSIGHTS_JWT_ROLE_MAP=Data Steward:steward,Administrator:admin,Analyst:viewer
```

(Or `INSIGHTS_JWT_SECRET=…` instead of JWKS for an HS256 shared secret.)

For the MCP HTTP transport, also set `INSIGHTS_AUTH_ISSUER` and `INSIGHTS_MCP_URL`
so the OAuth resource metadata is correct. Validate the full handshake against
your IdP before relying on it remotely. Details and caveats: `docs/SECURITY.md`.

> Leave `INSIGHTS_AUTH=none` only for a local laptop. Any shared deployment must
> use `apikey` or `jwt`.

## 10. Connect to PDC

1. **Use a read-only service account in PDC** (an Analyst-tier user — e.g. `pdc_user`) and,
   ideally, scope it with a community to just the sources/glossaries these
   dashboards should expose. PDC's own access control is the real backstop —
   prefer this over an admin account even though the app is read-only.
2. Put its credentials in `.env`:
   ```ini
   PDC_BASE_URL=https://pdc.yourcompany.local
   PDC_API_VERSION=v3          # use v2/v1 if v3 isn't enabled on your instance
   PDC_USERNAME=pdc_user
   PDC_PASSWORD=••••••••
   PDC_VERIFY_TLS=true
   PDC_BEARER_TOKEN=           # leave blank — the app fetches a token itself
   ```
3. Set `INSIGHTS_DEMO=false` and restart.

**How auth works.** The app calls `POST /api/public/{version}/auth` on first
use. That endpoint is OAuth-style — it takes **form-encoded** fields
(`username`, `password`, `client_id=pdc-client`, `grant_type=password`,
`scope="openid profile email"`) and returns the JWT as **`data.accessToken`**.
The client caches that token and, because PDC tokens are short-lived with no
refresh, re-authenticates automatically on a 401. You normally never touch a
token yourself.

**Getting a token manually** (handy to confirm credentials before starting the
app, or for the `PDC_BEARER_TOKEN` shortcut):

```bash
curl -X POST "https://pdc.yourcompany.local/api/public/v3/auth" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=pdc_user" -d "password=catalog123!"
# -> { "message": "OK", "data": { "accessToken": "eyJ..." } }
```

Then sanity-check a read with it:

```bash
curl -X POST "https://pdc.yourcompany.local/api/public/v3/search/facets" \
  -H "Authorization: Bearer <accessToken>" -H "Content-Type: application/json" \
  -d '{"searchTerm":"*","searchFacets":{"sensitivity":[]}}'
```

> Setting `PDC_BEARER_TOKEN` makes the app use that fixed token and **skips**
> the automatic 401 re-auth — so it will stop working when the token expires.
> Use it only for quick tests; for a running service use `PDC_USERNAME`/
> `PDC_PASSWORD` so the app re-auths on its own.

The app only ever **reads** from PDC (search, facets, entities, data-sources). It
never writes to the catalog; the single write in the whole product is saving a
dashboard spec file inside the app. (Reachability check: `GET
{PDC_BASE_URL}/api/public/health`.)

### Save & run against real data

You can switch from the bundled demo data to your live PDC entirely from the
**Settings** page — no file editing or restart:

1. Open **Settings**, fill in the **PDC connection** (Base URL, API version,
   username, password) and click **Test connection** — it should read
   *Connected*.
2. Under **Data source**, choose **Live PDC** (the toggle next to *Demo data*).
3. Click **Save & apply**.

This writes the values to `.env`, re-authenticates the PDC client, and applies
immediately: the next snapshot, recommendation, and chat read from your live
instance. The footer **PDC** dot turns green and the demo banner disappears.
(Saving needs the `admin` role when auth is on. The PDC password is stored in
`.env` and is never returned to the browser.)

When you're on demo data, a banner at the top of the app links straight here, and
`run.sh` / `run.bat` print the same hint after their health check.

> **Data sources are configured in PDC, not in Catalog Insights.** You add,
> test, and scan sources inside PDC (Management → Add Data Source → Test
> Connection → Scan Files). Catalog Insights is read-only over PDC's public API,
> so once a source is connected and scanned in PDC it appears here automatically —
> dashboards and suggestions build from whatever PDC has already catalogued.

### Troubleshooting: PDC won't connect (stuck on demo)

If the footer/banner stays on **demo data** after choosing Live PDC, the live
read is failing and the app falls back to demo. Click **Test connection** under
PDC connection — it now actually authenticates and tells you the specific reason:

- *Cannot reach …* — wrong Base URL/host or port, or a network/DNS issue. The
  Base URL must be the PDC API host (scheme + host, e.g. `https://pdc.host`),
  not a UI page.
- *Authentication failed (401/403)* — wrong username/password.
- *404 at …/auth* — wrong **API version**; try v3/v2/v1 to match your instance.
- *TLS/SSL error* — certificate not trusted; for a self-signed cert set
  `PDC_VERIFY_TLS=false` in `.env`.

Once Test connection succeeds, set **Data source → Live PDC** and **Save &
apply**; the PDC dot turns green and the demo banner clears.

**Picking a model.** The **Model** field lists the models installed in your local
Ollama — click it to choose one, or type a name. Use **Download model** to pull
the recommended one.

## 11. Verify everything

```bash
# app is up
curl http://localhost:8660/health

# security model (auth, roles, audit) — runs on demo data, no PDC needed
python tools/test_security.py        # expect: ALL PASS

# functional: recommend (section-aware), the chat builder, and the routes
python tools/test_app.py             # expect: ALL PASS

# dashboards are valid against the schema + query catalog
python tools/build_dashboards.py     # expect: 12 schema-valid dashboards

# with a key set, reads need viewer, saves need steward
curl -H "Authorization: Bearer viewkey" http://localhost:8660/api/snapshot     # 200
curl -H "Authorization: Bearer viewkey" -X POST http://localhost:8660/api/dashboards -d '{}'   # 403
```

In Claude Desktop, confirm the MCP tools appear and `recommend_dashboards`
returns suggestions (demo data is fine).

## 12. Troubleshooting

| Symptom | Likely cause / fix |
| ------- | ------------------ |
| `401` from the app on every call | `INSIGHTS_AUTH` is `apikey`/`jwt` but no/invalid `Authorization: Bearer` header |
| `403` on save/generate | the principal's role is below `steward` |
| App can't reach Ollama from the container | only relevant when the app runs in Docker (running it natively avoids this). Make Ollama listen on all interfaces with `OLLAMA_HOST=0.0.0.0:11434` (it binds to 127.0.0.1 by default); the compose file already injects `host.docker.internal` and the `extra_hosts` mapping |
| LLM "Test connection" ok but generation fails | the named model isn't installed — `ollama pull <LLM_MODEL>`; the health check only lists installed models |
| `PDC unreachable` in snapshot | check `PDC_BASE_URL`/creds and TLS (`PDC_VERIFY_TLS`); confirm `PDC_API_VERSION` is enabled on the instance; or set `INSIGHTS_DEMO=true` to keep working offline |
| Auth to PDC fails / "no accessToken" | `/auth` is form-encoded and returns `data.accessToken` (the client handles this); a failure here means wrong username/password or wrong `PDC_API_VERSION`. Test with the manual curl in §10 |
| PDC calls intermittently 401 | expected — tokens are short-lived; the client re-auths automatically. If it persists, the service account password is wrong, or you pinned an expiring `PDC_BEARER_TOKEN` (use user/pass instead) |
| JWT rejected | check `INSIGHTS_JWT_AUDIENCE`/`ISSUER` match the token, and that the role claim/map resolve to a known role |
| MCP server won't start with auth on | confirm `INSIGHTS_AUTH_ISSUER`/`INSIGHTS_MCP_URL` are set; with `INSIGHTS_AUTH=none` it always starts |
| Port already in use on startup | the web app defaults to **8660** to clear Pentaho/Tomcat (8080, and 8090 used by Pentaho's AWS/K8s config) and PDC ports. If 8660 is also taken, set `INSIGHTS_PORT` in `.env` to any free port — the container always listens on 8660 internally |
| Generated dashboard binds to a missing query | the model strayed from the catalog; `validate_dashboard`/the generator's repair pass catches it — re-run, or tune the prompt |

## 13. Version & upgrade notes

- **PDC 11.0 (the target):** MongoDB is replaced by FerretDB on PostgreSQL;
  OpenSearch still backs search/facets. Because the app only uses the REST API,
  the storage change doesn't affect it — and the sibling Glossary/Policy
  Generator apps have live-confirmed on 11.0 that Keycloak-first auth,
  `POST /search`, and `POST /entities/filter` all work with the same bearer
  token. The authenticated OpenAPI spec is at `/api/public/v3/openapi.json`
  (the conventional `/v3/api-docs` returns 401). Still to re-verify here:
  `POST /search/facets`.
- **PDC 10.2.x:** MongoDB backs operational metadata; OpenSearch backs
  search/facets; BIDB is PostgreSQL-based (10.2.5+). The app was originally
  built and demoed against 10.2.11 — no app change needed across 10.2.x patches.
- **Trust-score writes:** reading trust scores via search/facets is confirmed;
  *triggering* recalculation through the public API is version-dependent. Verify
  on your instance before any dashboard offers a "recalculate" action.
- **CTools deliverables:** if a team requires a CDF/CDE artifact, the supported
  JDBC/ODBC path is **BIDB**, not raw OpenSearch — see `docs/PDC-CONNECTOR.md`.
