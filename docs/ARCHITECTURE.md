# Architecture

## One picture

![System architecture](diagrams/01-architecture.png)

_See [`DIAGRAMS.md`](DIAGRAMS.md) for all diagrams (with editable Mermaid source)._

```
  Browser (UI)                Flask app                    External
 ┌────────────┐         ┌────────────────────┐        ┌──────────────┐
 │ Analytics  │  HTTP   │ /api/facets         │  REST  │ PDC public   │
 │ pages      │────────▶│ /api/search         │───────▶│ API (v3)     │
 │            │         │ /api/trust-dist     │        │ search/facets│
 │ Designer   │         │                     │        │ entities     │
 │            │  HTTP   │ /api/generate ──────┼───┐    └──────────────┘
 │ Settings   │────────▶│                     │   │
 └────────────┘         │ generator.py        │   │    ┌──────────────┐
                        │   ground+validate   │   └───▶│ LLM provider │
                        └────────────────────┘   loop  │ local /      │
                                                        │ commercial   │
                                                        └──────────────┘
```

Three responsibilities, deliberately separate:

1. **Read** — `pdc_client.py` wraps the PDC public API. Reporting only
   needs reads: `search/facets` (counts), `search` (rows), `entities/filter`
   (full attributes). Auth is OAuth-style — a form-encoded `POST /auth` returns
   a short-lived JWT as `data.accessToken`, which the client caches and refreshes
   automatically on a 401. Responses are cached for `PDC_CACHE_TTL` seconds.
2. **Generate** — `generator.py` turns a prompt into a dashboard spec,
   grounded on the real query catalog and validated against the schema.
3. **Render** — the UI consumes specs and `/api/*` data. The same spec the
   Designer edits is what the generator emits and what the exporters read.

## The spec is the contract

![Dashboard spec lifecycle](diagrams/02-spec-lifecycle.png)

`app/schema/dashboard.schema.json` defines a `.studio.json` dashboard:
title, category, filters, and panels (kpi / chart / table / text). Every
producer and consumer speaks this one format:

```
 NL prompt ─▶ generator ─┐
                         ├─▶  dashboard spec (.studio.json) ─▶ editor ─▶ CDF/CDE/CDA export
 hand-built in editor ───┘
```

This is why AI generation is low-risk: the model targets one well-defined
JSON object, not the live UI and not CDF/CDE XML. The existing export
pipeline does the rest.

## Why no Pentaho Server dependency

CTools dashboards (CDF/CDE) run on the Pentaho Server and bind to CDA data
accesses. PDC metadata is not a JDBC source, so a plain SQL DA can't reach
it. Catalog Insights calls the PDC API directly from Flask and renders in
the browser. When a customer's deliverable standard *is* CTools, the bridge
is a CDA Scripting (or Kettle) DA that wraps the same API calls — documented
in `PDC-CONNECTOR.md` — so both paths share one data layer.

## What's behind the PDC API (and why we don't touch it)

PDC stores its data in several engines, all behind the REST API:

- **OpenSearch** — search indexes and discovery metadata. Serves `/search` and
  `/search/facets` (which is why faceted counts come back in one fast call).
- **MongoDB** — operational and user metadata: data sources, ownership,
  policies, glossary, job state, users/roles. (Replaced by FerretDB on
  PostgreSQL in PDC 11.0.)
- **BIDB** — an aggregate store exposed over JDBC/ODBC for BI tools
  (PostgreSQL-based in 10.2.5+). The one PDC component a traditional CTools/CDA
  dashboard could bind to directly.

Catalog Insights connects to **none of these directly** — only the REST API.
That's deliberate: the API applies PDC's own auth and role checks and shields
the app from engine swaps (Mongo→FerretDB) and store changes across versions,
so `pdc_client.py` keeps working without modification.

## Data flow for a single panel

1. Panel spec names a `query` (a DA) and `bindings` (columns → chart roles).
2. For catalog facets, the query resolves to a `search/facets` call with a
   fixed facet key; the `options[].count` rows become the series.
3. For row-level panels, it resolves to `search` or `entities/filter`.
4. The UI binds the named columns to the chart and renders.

## Deployment

Single container, gunicorn with threaded workers (calls are I/O-bound on
PDC and the LLM). `host.docker.internal` is mapped so a containerised app
can reach an Ollama instance on the host. `/health`, `/config`, and
`/health/llm` support orchestration and the Settings test buttons.
