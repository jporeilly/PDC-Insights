# PDC connector & the CDA bridge

Two ways to get PDC metadata into a chart. Catalog Insights uses the first;
the second exists for teams whose deliverable standard is CTools artifacts.

## Path A — direct API (this app)

FastAPI calls the PDC public API and the browser renders. No Pentaho Server,
no CDA. This is the default and the simplest to deploy.

Workhorse call — pre-aggregated counts in one request:

```http
POST /api/public/v3/search/facets
{ "searchTerm": "*", "searchFacets": { "type": ["TABLE"] } }
```

```jsonc
// response: data[].options[].count is your chart series
{ "data": [
  { "key": "sensitivity",
    "options": [ { "name": "High", "count": 84 },
                 { "name": "Medium", "count": 311 },
                 { "name": "Low", "count": 1290 } ] } ] }
```

Row-level detail uses `POST /search` (paginated) or `POST /entities/filter`
(cursor, up to 500/page, full attributes incl. `qualityScore`,
`trustScore.value`, `sensitivity`, `businessTerms`, `contentScanDiscoveries`,
`isLineageVerified`, `owners`).

## Path B — CDA Scripting/Kettle DA (the CTools bridge)

When the output must be a CDF/CDE dashboard on a Pentaho Server, the catalog
data still has to come from the API — PDC is not a JDBC source. Wrap the same
calls in **one reusable data access** and every governance dashboard binds to
it.

### Option B1 — Scripting DA (JS/Groovy/Python)

A scripting DA authenticates to PDC, calls `search/facets`, and flattens
`options[]` into rows. Pseudocode:

```python
# PDC delegates auth to Keycloak: POST the realm token endpoint, FORM-ENCODED,
# and read the top-level access_token. (The legacy /api/public/<v>/auth wrapper
# also exists but returns 200-with-no-token on some instances.)
token = http_post_form(PDC + "/keycloak/realms/pdc/protocol/openid-connect/token",
                       {"username": user, "password": pw,
                        "client_id": "pdc-client", "grant_type": "password",
                        "scope": "openid"}).access_token
facets = http_post(PDC + "/api/public/v3/search/facets",
                   {"searchTerm": "*", "searchFacets": {"trustScore": []}},
                   bearer=token).data
rows = [[o["name"], o["count"]]
        for f in facets if f["key"] == "trustScore"
        for o in f["options"]]
# columns: bucket (String), count (Numeric)
return rows
```

The result columns (`bucket`, `count`) are what the chart binds to — exactly
the shape the visual builder expects from any DA.

### Option B2 — Kettle (PDI) DA

A `.ktr` transform: **REST Client** step → **JSON Input** to parse
`data[].options[]` → **Select values** to emit `name`/`count`. Reference the
transform from a Kettle DA. Better when you want lineage on the fetch itself
or to schedule a refresh.

### Parameterising

Expose the facet key and any filter as CDA parameters
(`${facetKey}`, `${sourceId}`) so one DA powers many panels — trust by
source, sensitivity by source, quality by source — by parameter alone.

## Recommendation

Build the **single PDC-connector DA** (B1 first — fewer moving parts) and
every dashboard in `DASHBOARDS.md` lights up from the same source. That DA is
the piece the Dashboard Studio's CDA builder still needs.

## Caveat to verify

Reading trust scores via `search`/`facets` works on tested builds.
*Triggering* Calculate Trust Score through the public API is
version-dependent — confirm against the target instance (PDC 11.0 in the
lab) before any DA or panel depends on it. On 11.0 the authenticated
OpenAPI spec at `/api/public/v3/openapi.json` is the fastest way to check
what the build actually exposes.
