# MCP server

A second front door onto the same engine. Where the web app shows dashboards,
the MCP server exposes the catalog and the generator as **tools an LLM or agent
can call** — so you can ask, in chat, *"what dashboards should I build?"* and
*"build the PII one for S3"*, and have a real `.studio.json` come back that drops
straight into the app.

> Two ways to chat: the **web app's built-in chat** at `/chat` (no setup beyond
> running the app), and **this MCP server** for *external* chats and agents
> (Claude Desktop, IDEs). Both drive the same generator and save into the same
> `app/dashboards/`.

> **Do I need this for a local LLM? No.** Ollama is called *directly* by the web
> app for `/chat` and dashboard generation — no MCP involved. Run the MCP server
> only to let an external chat/agent (Claude Desktop) call these tools. It's a
> separate process: start it with `./run.sh --mcp` (or `run.bat --mcp`), or
> manually as below.

It reuses `app/pdc_client.py` and `app/generator.py` unchanged. The MCP server
and the web app are two interfaces over one data + spec layer.

```
  Claude / IDE / agent
        │  (MCP)
        ▼
  Catalog Insights MCP server ── recommend_dashboards ─┐
        │                        generate_dashboard     │  reuse
        ▼                        validate_dashboard      │
  app/pdc_client.py  ◀───────────────────────────────────┘
  app/generator.py                       │
        │ REST                           ▼ save_dashboard
        ▼                         app/dashboards/*.studio.json ──▶ shows in the web app
  PDC public API
```

## What it can do

**Read the catalog**
- `list_data_sources` — connected sources and their scan state
- `catalog_snapshot` — totals, trust/sensitivity/quality bands, profiling status,
  PII types, and per-source signals — the state to reason over
- `search_assets` — search with sensitivity / source filters

**Suggest dashboards from your scans & connections**
- `recommend_dashboards(scope?)` — the headline. Reads the snapshot and returns
  ranked suggestions, each with the signal that triggered it, a matching built-in
  template, and a ready-to-run `generate_prompt`. Pass a source name to scope it.

**Build dashboards**
- `get_query_catalog` — the data accesses + columns to ground a spec on
- `generate_dashboard(prompt)` — NL → validated spec (uses the configured LLM)
- `validate_dashboard(spec)` — check a spec the host LLM wrote itself
- `save_dashboard(spec)` — persist it into the app under its category
- `list_standard_dashboards` — the built-in library

**Resources**
- `insights://schema/dashboard` — the spec schema
- `insights://catalog/queries` — the query library
- `insights://dashboards/standard` — the standard-dashboard index

## The suggest-then-build loop

![Suggest-then-build over MCP](diagrams/04-mcp-sequence.png)

This is the workflow you described — the model proposes from real catalog state,
then builds on request:

1. **Ask:** "Based on what's connected, what dashboards should we build?"
   → host calls `recommend_dashboards`. It sees, say, S3-raw is 52% unowned with
   310 high-sensitivity assets and 6 failed scans, and surfaces *Exposure · S3-raw*
   and *Profiling health · S3-raw* with the reasons.
2. **Pick one:** "Build the exposure one for S3."
   → host calls `generate_dashboard` with that suggestion's prompt (or writes the
   spec itself using `get_query_catalog` + the schema, then `validate_dashboard`).
3. **Save:** `save_dashboard` writes it to `app/dashboards/sensitivity/…` and it
   appears in the web app's Sensitivity section next to the standard ones.

Two ways to generate, both supported: let the **server's** configured model build
it (`generate_dashboard`, good with local Ollama), or let the **host** model (e.g.
Claude) author the spec and only call `validate_dashboard` — no second model, and
the validation still guarantees it binds to real queries and columns.

## Try it offline

Set `INSIGHTS_DEMO=true` and the read tools return a bundled sample snapshot
(flagged `demo: true`), so you can exercise `recommend_dashboards` and the
generate/validate loop before a live PDC is connected.

## Connect it

**Claude Desktop (stdio)** — add to `claude_desktop_config.json`:

```jsonc
{
  "mcpServers": {
    "catalog-insights": {
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "cwd": "/path/to/PDC-Insights",
      "env": { "INSIGHTS_DEMO": "true", "PDC_BASE_URL": "https://pdc.example.local" }
    }
  }
}
```

**HTTP (agents / remote)** — run the server over streamable HTTP:

```bash
docker compose --profile mcp up insights-mcp     # serves on :8765
# or, locally:
MCP_HTTP=1 python -m mcp_server.server
```

## Placement

Same story as the web app (see `DEPLOYMENT.md`): it's a thin client to the PDC
API. Co-locate with PDC in a lab; give it a small adjacent host in production.
On your Windows + GPU box, run it alongside the app and point it at Ollama for
the `generate_dashboard` path.

## Safety

The server is read-only against PDC. The only writes are `save_dashboard`,
which writes a validated spec file into the app — never to the catalog. It does
not expose any trust-score recalculation or other mutating PDC operation.
