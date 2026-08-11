# Desktop shell

Wraps Catalog Insights into a Windows `.exe` installer, the same way the
Glossary and Policy Generators are packaged (Tauri + a vendored Python).

The app itself is unchanged. This is a Tauri window that starts the existing
FastAPI server on a free port and points a webview at it, so the desktop and
browser builds cannot drift apart — there is one UI, served the same way in
both.

## Layout

```
desktop/
  dist/index.html          splash: polls the backend, then navigates to it
  boot.py                  launcher: sys.path + state .env, web or --mcp
  scripts/fetch-python.ps1 vendors a self-contained Python + both requirement sets
  scripts/stage-app.ps1    copies asgi.py + app/ + mcp_server/ + built SPA into vendor/app
  scripts/check-environment.ps1  post-install check: what is missing, and the fix
  scripts/install-ollama.ps1     optional: install Ollama + pull one sized model
  scripts/lib/common.ps1   shared state-dir / interpreter resolution
  src-tauri/src/main.rs    window, paths, the invoke commands
  src-tauri/src/server.rs  free port, spawn uvicorn, job object
```

## Build

```powershell
cd frontend; npm ci; npm run build     # the SPA must exist first
cd ..\desktop; npm install
npm run dist                           # stage + tauri:build + collect
```

The installer is copied to **`dist\` at the repo root** (one short path;
`npm run collect` prints it with a sha256). Tauri's own output stays in
`src-tauri/target/release/bundle/nsis/` — `npm run tauri:build` alone stops
there.

`npm run tauri:dev` runs against the checkout instead — no staging, no vendored
runtime, `python` from PATH. Edit Python, reload the window, done.

## Decisions worth knowing

**A vendored Python, not PyInstaller.** The suite standard, set by the
Glossary Generator (whose driver set PyInstaller genuinely mishandles). This
app's dependency set is lighter, but a vendored tree is still just files —
what was tested is what ships — and one packaging recipe across the PDC-Demo
apps beats a second one that can drift.

**A free port, chosen at launch.** 5002 is the app's usual port and a second
instance must not turn into "the app won't start".

**A kill-on-close job object.** Closing the window stops the server directly,
but a crash or a Task Manager kill would otherwise leak `uvicorn` — still
holding the port, so the *next* launch fails for a reason the user cannot see.
The job object covers that; see `server.rs`.

**The MCP server ships too.** `requirements-mcp.txt` is installed into the
vendored runtime and `mcp_server/` is staged, so the installed app can be
wired into Claude Desktop with no pip on the machine:

```json
{
  "mcpServers": {
    "catalog-insights": {
      "command": "C:\\Program Files\\PDC Catalog Insights\\python\\python.exe",
      "args": ["C:\\Program Files\\PDC Catalog Insights\\app\\boot.py", "--mcp"]
    }
  }
}
```

## Where state goes

`INSIGHTS_STATE_DIR` is set explicitly to the per-user data directory
(`%APPDATA%\com.pentaho.pdc-insights`), so the packaged build never depends on
probing whether Program Files is writable. `app/paths.py` has the full
resolution order. What lands there:

| File | What it is |
| --- | --- |
| `.env` | the Settings page's persisted configuration (PDC connection, LLM) |
| `dashboards/<section>/*.studio.json` | dashboards saved from the chat builder or Designer — they overlay the 18 shipped built-ins, and a save with a built-in's id wins over the shipped copy |
| `audit.log` | one JSON line per privileged action (the shell sets `INSIGHTS_AUDIT_LOG`) |
| `startup-report.txt` | written by the splash's Save report button |

Nothing local ships: `stage-app.ps1` excludes `.env` and stages the built-in
dashboards **from `index.json`**, not by globbing the directory — in a
checkout, `app/dashboards/` is also where saves land, so the directory can
hold a developer's experiments. The index is the authority on what ships, and
the build fails if a listed file is missing.

## The installer

`nsis/installer.nsi` adds a components page over Tauri's default template.

| Install type | What runs |
| --- | --- |
| **Full** | app, Ollama + one sized model, environment check |
| **Minimal (app only)** | app only |
| **Custom** | tick individually |

The bundled Python runtime shows as a ticked, greyed-out entry. It has no
payload of its own — it's laid down by the core section regardless — but the
page is where someone decides what this thing needs, and "you don't have to
install Python" is the most useful thing it can say there.

Each optional step delegates to a script in `$INSTDIR\provisioning\`, all of
which are re-runnable afterwards and are safe no-ops when their work is done.
Nothing there can fail the installation: a skipped step leaves a working app —
the chat builder has a deterministic fallback, and every dashboard runs on the
bundled sample until Settings points at a PDC.

Silent installs:

```powershell
setup.exe /S /NoOllama /NoCheck
```

## Testing on a clean laptop

Expect these, none of which are bugs:

- **SmartScreen will block it.** The installer is unsigned, so Windows shows
  "Windows protected your PC" → *More info* → *Run anyway* — until the binary
  is code-signed.
- **Admin rights, always.** `installMode` is `perMachine`, so it installs to
  `C:\Program Files\PDC Catalog Insights` and always prompts for elevation.
- **Network is needed for two things only** — the WebView2 bootstrapper (if
  the machine lacks the runtime) and the Ollama model pull. The app and its
  Python are entirely inside the installer.
- **The Ollama step is the long one.** It pulls a single model sized to that
  machine — several GB. Untick it for a quick test, or run
  `provisioning\install-ollama.ps1` later.

Then verify:

```powershell
& "$env:ProgramFiles\PDC Catalog Insights\provisioning\check-environment.ps1"
```

On a clean machine expect `WebView2 OK`, `Python (bundled) OK`, `Python
dependencies OK`, a state directory under `%APPDATA%\com.pentaho.pdc-insights`,
and `PDC` skipped until you give it a server — the app runs on the bundled
sample until then, which is the demo-mode behaviour the README describes.

## Code signing

Wired, and off until you configure a certificate:

```powershell
$env:PDCG_SIGN_THUMBPRINT = "<sha1 thumbprint of a cert in the Windows store>"
npm run tauri:build
```

`scripts/sign.ps1` runs for every bundled binary and **no-ops with a note when
no thumbprint is set**, so an unsigned developer build still succeeds. It
accepts `INSIGHTS_SIGN_THUMBPRINT` or the suite-wide `PDCG_SIGN_THUMBPRINT`,
so one variable signs every PDC-Demo build on this machine. The repo holds no
certificate and no `.pfx` — a thumbprint names a certificate in the Windows
store and carries no key material. `*_SIGN_TIMESTAMP` overrides the RFC-3161
timestamp URL; both digests are SHA-256.

## Not done yet

- **Icons are placeholders** (`src-tauri/icons/`) — the suite's generated
  Pentaho mark, not a per-app design.
