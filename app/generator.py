"""Natural language -> a validated dashboard spec.

This is the brain behind "describe a dashboard and get one." The reliability
trick is NOT a clever prompt — it's grounding plus validation around whatever
model is configured:

    1. GROUND    Hand the model the *real* Query Library (data-access names,
                 their columns) and the allowed chart vocabulary, so it can only
                 bind to things that actually exist.
    2. GENERATE  Ask for a single JSON object conforming to dashboard.schema.json.
    3. VALIDATE  Check it against the schema AND cross-check every query/column
                 against the catalog. On failure, feed the errors back ONCE for a
                 repair pass.
    4. RETURN    {spec, valid, errors}. The editor loads the spec; a human
                 refines it; nothing deploys automatically.

This is the same "generate, validate, repair" loop used for document generation
elsewhere — the model targets one well-defined JSON schema, never live UI or
CDF/CDE XML, which is what keeps it low-risk.
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema

from .llm import get_provider

# Load the spec schema once at import. This is the single source of truth for
# what a valid dashboard looks like; the web routes and MCP tools import _SCHEMA
# and _validate from here so every path validates identically.
_SCHEMA = json.loads((Path(__file__).parent / "schema" / "dashboard.schema.json").read_text())

# The system prompt is intentionally strict and short. The heavy lifting is done
# by the grounding payload (built per-request below) and by validation — not by
# trying to coax the model with prose.
SYSTEM_PROMPT = """You design dashboards for a data catalog governance console.
You output ONE JSON object conforming to the provided JSON Schema — no prose, no markdown fences.

Rules:
- Use ONLY data accesses (queries) listed in CATALOG. Never invent a query name.
- Bind ONLY to column names that appear under that query in CATALOG.
- Pick chartType from the allowed enum and match it to the data shape:
  category+value -> bar/donut; time+value -> line/area; matrix -> heatmap;
  single number -> kpi; score vs target -> bullet/gauge.
- Prefer 3-6 panels. Lead with KPI tiles, then charts, widest panels first.
- Choose the category that best fits the request.
Return only the JSON object."""


def _grounding(catalog: list[dict]) -> str:
    """Render the grounding block the model sees alongside the request.

    `catalog` is the Query Library: a list of {name, group, columns, ...}. We
    flatten each entry to "name [group]: columns = a, b, c" so the model has the
    exact, current vocabulary of queries and columns to bind to — this is what
    stops it inventing tables/columns. We also append the allowed chartType enum
    and category enum, both read straight from the schema so they never drift.
    """
    lines = ["CATALOG (available queries):"]
    for da in catalog:
        cols = ", ".join(da.get("columns", []))
        lines.append(f"- {da['name']} [{da.get('group','')}]: columns = {cols}")
    enums = _SCHEMA["$defs"]["panel"]["properties"]["chartType"]["enum"]
    lines.append("\nALLOWED chartType: " + ", ".join(enums))
    lines.append("CATEGORIES: " + ", ".join(_SCHEMA["properties"]["category"]["enum"]))
    return "\n".join(lines)


def _validate(spec: dict, catalog: list[dict]) -> list[str]:
    """Return a list of human-readable problems with `spec` (empty == valid).

    Two layers, because the schema alone isn't enough:
      1. Structural — jsonschema checks types, required fields, enums, etc.
      2. Referential — every panel.query must be a real catalog query, and every
         bound column must exist under that query. The schema can't express this
         (it doesn't know your catalog), so we check it here. This is what turns
         "a plausible-looking spec" into "a spec that will actually render."

    Shared by the generator's repair loop, the web /api/dashboards save route,
    and the MCP validate_dashboard/save_dashboard tools, so the definition of
    "valid" is identical everywhere.
    """
    # 1) structural validation against the JSON schema
    errors = [e.message for e in jsonschema.Draft7Validator(_SCHEMA).iter_errors(spec)]
    # 2) referential validation against the real catalog
    known = {da["name"]: set(da.get("columns", [])) for da in catalog}
    for p in spec.get("panels", []):
        q = p.get("query")
        if q not in known:
            errors.append(f"panel '{p.get('id')}' references unknown query '{q}'")
            continue  # can't check columns for a query we don't know
        for role, col in (p.get("bindings") or {}).items():
            if col not in known[q]:
                errors.append(f"panel '{p.get('id')}' binds {role} to '{col}' not in '{q}'")
    return errors


def generate(prompt: str, catalog: list[dict], schema_str: str | None = None) -> dict:
    """Run the full ground -> generate -> validate -> (repair once) loop.

    Args:
        prompt:     the user's natural-language request.
        catalog:    the Query Library to ground on (names + columns + samples).
        schema_str: optional pre-serialised schema (the MCP server passes the
                    same one it exposes as a resource); defaults to _SCHEMA.

    Returns {"spec": <dict>, "valid": <bool>, "errors": [<str>, ...]}. We return
    the spec even when invalid so the caller can show the model's attempt and the
    reasons it failed, rather than a bare error.
    """
    provider = get_provider()
    # The user message = grounding + schema + the request. Order matters less than
    # presence: the model needs all three to produce a bindable, valid spec.
    user = (
        f"{_grounding(catalog)}\n\n"
        f"JSON SCHEMA:\n{schema_str or json.dumps(_SCHEMA)}\n\n"
        f"REQUEST: {prompt}"
    )
    raw = provider.complete(SYSTEM_PROMPT, user, json_mode=True)
    spec = _loads(raw)
    errors = _validate(spec, catalog)

    if errors:
        # ONE repair pass: show the model exactly what was wrong and ask again.
        # One pass catches the vast majority of slips (a wrong column name, a
        # missing binding) without risking an infinite correction loop.
        repair = (
            "The previous spec had these problems:\n- " + "\n- ".join(errors)
            + "\n\nReturn a corrected JSON object only."
        )
        spec = _loads(provider.complete(SYSTEM_PROMPT, user + "\n\n" + repair, json_mode=True))
        errors = _validate(spec, catalog)

    return {"spec": spec, "valid": not errors, "errors": errors}


def _loads(raw: str) -> dict:
    """Parse model output into a dict, tolerating common formatting noise.

    Even in JSON mode, weaker/local models sometimes wrap output in ```fences```
    or add a stray word. We strip a leading code fence if present, then slice
    from the first '{' to the last '}' so trailing/leading prose can't break the
    parse. If it's still not valid JSON, json.loads raises and the caller treats
    it as a generation failure.
    """
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")          # drop the fence characters
        raw = raw[raw.find("{"):]      # skip any language hint like ```json
    return json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
