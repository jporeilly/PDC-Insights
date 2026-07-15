# Dashboard catalog

The governance dashboard set Catalog Insights ships as built-ins and as the
example library for the Designer. Each maps to a PDC API feed and to chart
types the editor already supports. Categories match the `category` enum in
the spec schema and the Analytics nav.

> Audience key — **BA** Business Analyst · **DS** Data Steward · **OP** platform/technical

---

## Overview  *(landing)*
A single page that answers "is the catalog healthy?" — top KPIs pulled from
each domain below, plus the trust spectrum as the hero.

| Panel | Feed | Chart |
| ----- | ---- | ----- |
| Total assets, sources, terms, % owned | `search/facets` (type, rootIds) | KPI tiles |
| Trust spectrum | `trust-distribution` | segmented bar (hero) |
| Quality by source | `search/facets` qualityScore × rootIds | stacked bar |
| Sensitivity mix | `search/facets` sensitivity | donut |

## System  *(OP)*
Operational health of the catalog itself, "similar to the other product."

| Panel | Feed | Chart |
| ----- | ---- | ----- |
| Profiling status | `entities/filter` profileStatus (COMPLETED/SKIPPED/FAILED) | donut |
| Scan & profile freshness | `search/facets` profiledAt | calendar heatmap |
| Stale / failed assets | `entities/filter` profileStatus=FAILED | table |
| Assets by data source | `search/facets` rootIds | bar |

## User  *(DS, BA)*
Stewardship and human activity over the catalog.

| Panel | Feed | Chart |
| ----- | ---- | ----- |
| Owned vs unowned by source | `entities/filter` owners | stacked bar |
| Owner workload (top owners) | `entities/filter` owners | bar |
| Recently modified assets | `search/facets` modifiedAt | line |
| Ratings distribution | `entities/filter` features.rating | histogram |

## Governance  *(DS)*
Glossary coverage and policy posture.

| Panel | Feed | Chart |
| ----- | ---- | ----- |
| % assets with a business term | `search/facets` businessTerms | KPI + gauge |
| Top business terms | `search/facets` businessTerms | bar |
| Untermed critical elements | `entities/filter` isCriticalDataElement + no term | table |
| Lineage verified vs not | `entities/filter` isLineageVerified | donut |

## Quality  *(DS, BA)*
Data-quality detail.

| Panel | Feed | Chart |
| ----- | ---- | ----- |
| Quality score distribution | `search/facets` qualityScore | histogram |
| DQ dimensions per source | `entities/filter` stats | radar |
| Worst-N tables | `search` sort by qualityScore | bar |
| Quality vs target | computed vs threshold | bullet |

## Sensitivity  *(DS, OP)*
Privacy and exposure.

| Panel | Feed | Chart |
| ----- | ---- | ----- |
| Sensitivity breakdown | `search/facets` sensitivity | donut |
| Content-scan discoveries (PII types) | `entities/filter` contentScanDiscoveries | bar |
| High sensitivity, no owner | `entities/filter` sensitivity=High + owners empty | table |
| Sensitive assets by source | `search/facets` sensitivity × rootIds | stacked bar |

---

## Trust-score buckets

The UI bands trust scores the same way PDC's facets do:

- **Untrusted** 0–50
- **Trusted** 51–75
- **Highly Trusted** 76–100

These three colours (red / amber / green) are the product's recurring motif.

## Live data

Dashboard panels render real values from the catalog snapshot, not placeholders.
A read-only resolver (`app/panel_data.py`) maps each panel's `query` to actual
numbers and serves them at:

- `GET /api/dashboards/<section>/<id>/data` — resolve a saved dashboard's panels.
- `POST /api/dashboards/resolve` — resolve an in-memory spec (used by the chat
  preview).

In **demo** mode these come from the bundled sample; in **live** mode they come
from your connected PDC (trust, sensitivity, profiling, PII, and per-source
metrics). A live/demo badge on each dashboard and the chat preview shows which
you're seeing. Queries with no direct aggregate are derived deterministically
from the same snapshot, so every panel shows a real number and nothing errors on
a sparse live snapshot.

## Suggestions from your connections

Recommendations are driven by what PDC has actually scanned. **You connect data
sources inside PDC** (Management → Add Data Source → Test Connection → Scan
Files); Catalog Insights reads them read-only via the PDC API
(`/data-sources` + `/search/facets`) — you do not add sources here. The more
sources you connect and scan, the more suggestions appear.

### Connection-grounded suggestions

Beyond the signal-driven ones (risk hotspots, exposure, profiling health, …),
these map to real PDC search facets and scale with your connections:

- **Compare sources** — trust/quality/coverage/sensitivity side by side (shown
  once 2+ sources are connected).
- **Scan freshness** — assets by last-profiled age and stale assets per source.
- **Key coverage** — primary/foreign-key coverage across scanned tables.
- **File format mix** — asset counts by file format across object stores.
- **Tag coverage** — tag usage and untagged high-value assets.
- **Domain coverage** — assets by business domain, and assets with no domain.

Each carries a "why", a generate prompt, and a priority; clicking one in the
chat builds it for the active section.

## Building dashboards by chat

Besides the 12 built-ins, dashboards can be built conversationally in the app at
`/chat` (and externally via the MCP server). The chat is **section-aware**: it
takes the active Analytics section, shows that section's recommended dashboards
as one-tap starters (ranked by real catalog signals — see
`app/recommend.py`), and pins anything you build to that section.

Pipeline, same contract as everything else:

```
prompt (+ section + spec-so-far)
   → app/chat_build.py: conversation_prompt() / demo_build()
   → app/generator.py: ground → generate → validate → repair   (LLM path)
                       or a deterministic builder               (offline path)
   → a schema-valid .studio.json   → preview → Add to dashboards (steward)
```

The deterministic builder (`demo_build`) exists so the chat works with no LLM
configured: it picks the category from the section (or keywords), takes that
section's queries from the catalog, and lays out a KPI plus a couple of charts
with bindings drawn from real columns — always schema-valid. Point
`LLM_PROVIDER=local` at Ollama and the same UI produces richer layouts. Both
paths are covered by `tools/test_app.py`.

## Download & print

Any dashboard can be **downloaded** or **printed / saved as PDF**:

- **Download** — the toolbar's *Download* button (and the chat preview's
  *Download*) saves the dashboard as a `.studio.json` spec — the same portable
  artifact the Designer and MCP server consume. In the app this streams the real
  saved spec from `GET /api/dashboards/<section>/<id>/download` (served with a
  `Content-Disposition: attachment`); the chat exports the spec it has in hand.
- **Print / PDF** — the *Print / PDF* button calls the browser's print dialog. A
  `@media print` stylesheet hides the app chrome (sidebar, tabs, toolbar) and
  lays out just the active dashboard with a branded header, so *Save as PDF* in
  the dialog produces a clean one- or two-page report. No server-side renderer
  or extra dependency is involved — the browser does the work, which keeps the
  container lean and works identically for the app view and the chat preview.

For an automated/headless PDF (e.g. a scheduled export), drive the same print
path with any headless-Chrome tool against the dashboard URL.

## Notes / open questions

- Trust-score *reads* via `search`/`facets` are confirmed; *triggering*
  recalculation through the public API is version-dependent — confirm on
  the target build (PDC 11.0 in the lab) before any panel offers a
  "recalculate" action.
- Trend panels (anything "over time") need a stored snapshot; the API gives
  point-in-time state. A small nightly snapshot table is the cheapest fix —
  flagged for a later milestone.
