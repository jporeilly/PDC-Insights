"""Catalog Insights MCP server.

Exposes the PDC catalog and the dashboard generator as MCP tools so an LLM or
agent (Claude Desktop, an IDE, an automation) can:

  • read what's connected and scanned        list_data_sources, catalog_snapshot
  • get suggestions from that state           recommend_dashboards
  • ground a spec on the real query library   get_query_catalog (+ schema resource)
  • turn a request into a dashboard           generate_dashboard / validate_dashboard
  • drop a dashboard into the app             save_dashboard

It reuses the same app/pdc_client.py and app/generator.py the web app uses —
the MCP server and the web app are two front doors onto one data + spec layer.

Run (stdio, e.g. Claude Desktop):   python -m mcp_server.server
Run (HTTP):                         MCP_HTTP=1 python -m mcp_server.server
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from app.generator import generate as _generate, _SCHEMA, _validate
from app.pdc_client import client
from app.recommend import recommend
from app.catalog import QUERY_CATALOG, catalog_snapshot as _snapshot
from app.security import ForbiddenError
from .security_mcp import build_auth, gated

DASH_DIR = Path(__file__).resolve().parent.parent / "app" / "dashboards"

_verifier, _auth = build_auth()
_kwargs = {"host": os.getenv("MCP_HOST", "0.0.0.0"), "port": int(os.getenv("MCP_PORT", "8765"))}
if _verifier is not None:
    _kwargs["token_verifier"] = _verifier
    if _auth is not None:
        _kwargs["auth"] = _auth

mcp = FastMCP("Catalog Insights", **_kwargs)


# ── resources (stable reference material) ────────────────────
@mcp.resource("insights://schema/dashboard")
def schema_resource() -> str:
    """The dashboard spec JSON Schema — the contract a generated spec must meet."""
    return json.dumps(_SCHEMA, indent=2)


@mcp.resource("insights://catalog/queries")
def queries_resource() -> str:
    """The Query Library: data accesses and their columns, for grounding specs."""
    return json.dumps(QUERY_CATALOG, indent=2)


@mcp.resource("insights://dashboards/standard")
def standard_resource() -> str:
    """Index of built-in standard dashboards, by section."""
    idx = DASH_DIR / "index.json"
    return idx.read_text() if idx.exists() else "{}"


# ── tools: catalog reads ─────────────────────────────────────
@mcp.tool()
@gated("viewer")
def list_data_sources() -> str:
    """List connected data sources (databases, files, cloud stores) and their
    scan state. Use this to see what's connected before suggesting dashboards."""
    snap = _snapshot()
    return json.dumps(snap.get("sources", []), indent=2)


@mcp.tool()
@gated("viewer")
def catalog_snapshot() -> str:
    """A compact read of overall catalog state: totals, trust distribution,
    sensitivity mix, profiling status, PII types, and per-source signals.
    This is the state to reason over when recommending dashboards."""
    return json.dumps(_snapshot(), indent=2)


@mcp.tool()
@gated("viewer")
def search_assets(term: str = "*", sensitivity: str = "", source: str = "") -> str:
    """Search catalog assets. Optional filters: sensitivity (Low/Medium/High)
    and source (data-source name). Returns matching asset rows."""
    facets: dict = {}
    if sensitivity:
        facets["sensitivity"] = [sensitivity]
    if source:
        facets["rootIds"] = [source]
    try:
        return json.dumps(client.search(term, facets, per_page=25), indent=2)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": str(exc),
                           "hint": "PDC may be unreachable; set INSIGHTS_DEMO=true to explore offline"})


# ── tools: recommendations ───────────────────────────────────
@mcp.tool()
@gated("viewer")
def recommend_dashboards(scope: str = "", section: str = "") -> str:
    """Suggest useful dashboards based on the current connections and scans.

    Reads the catalog snapshot and returns ranked suggestions — each with the
    signal that triggered it (why), a matching built-in template, and a
    ready-to-run generate_prompt. Pass a data-source name as scope to focus on
    one source; pass an Analytics section (overview|system|user|governance|
    quality|sensitivity) to focus on one section."""
    return json.dumps(recommend(_snapshot(), scope or None, section or None), indent=2)


@mcp.tool()
@gated("viewer")
def list_standard_dashboards() -> str:
    """List the built-in standard dashboards available per section. These are
    ready to use as-is or to scope/duplicate."""
    idx = DASH_DIR / "index.json"
    return idx.read_text() if idx.exists() else "{}"


@mcp.tool()
@gated("viewer")
def get_query_catalog() -> str:
    """The data accesses a dashboard can bind to, with their columns. Ground any
    generated spec on these names — do not invent queries or columns."""
    return json.dumps(QUERY_CATALOG, indent=2)


# ── tools: generation ────────────────────────────────────────
@mcp.tool()
@gated("steward")
def generate_dashboard(prompt: str) -> str:
    """Turn a natural-language request into a validated dashboard spec
    (.studio.json), grounded on the real query catalog and checked against the
    schema. Returns { spec, valid, errors }. Use save_dashboard to persist it."""
    try:
        return json.dumps(_generate(prompt, QUERY_CATALOG), indent=2)
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": str(exc),
                           "hint": "Set LLM_PROVIDER/LLM_BASE_URL, or write the spec yourself and call validate_dashboard"})


@mcp.tool()
@gated("viewer")
def validate_dashboard(spec_json: str) -> str:
    """Validate a dashboard spec you wrote against the schema AND the query
    catalog (queries/columns must exist). Returns { valid, errors }. Lets the
    host LLM author the spec directly and check it without a second model."""
    try:
        spec = json.loads(spec_json)
    except json.JSONDecodeError as exc:
        return json.dumps({"valid": False, "errors": [f"not valid JSON: {exc}"]})
    errors = _validate(spec, QUERY_CATALOG)
    return json.dumps({"valid": not errors, "errors": errors}, indent=2)


@mcp.tool()
@gated("steward")
def save_dashboard(spec_json: str) -> str:
    """Persist a dashboard spec so it appears in the app under its category.
    Validates first; refuses to save an invalid spec. Returns the saved path."""
    try:
        spec = json.loads(spec_json)
    except json.JSONDecodeError as exc:
        return json.dumps({"saved": False, "errors": [f"not valid JSON: {exc}"]})
    errors = _validate(spec, QUERY_CATALOG)
    if errors:
        return json.dumps({"saved": False, "errors": errors})
    category = spec.get("category", "overview")
    slug = re.sub(r"[^a-z0-9]+", "-", spec.get("title", "untitled").lower()).strip("-")
    dest = DASH_DIR / category
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / f"{slug}.studio.json"
    path.write_text(json.dumps(spec, indent=2))
    return json.dumps({"saved": True, "path": str(path.relative_to(DASH_DIR.parent.parent)),
                       "category": category, "title": spec.get("title")})


def main() -> None:
    transport = "streamable-http" if os.getenv("MCP_HTTP") else "stdio"
    mcp.run(transport=transport)


if __name__ == "__main__":
    main()
