"""Conversational dashboard building.

The in-app chat builder and the /api/chat endpoint reuse the LLM generator when a
provider is configured. When no LLM is available (demo/offline), demo_build()
produces a schema-valid spec deterministically from the request and the query
catalog — so the chat works end to end for enablement without a model, and the
same UI lights up with richer results once Ollama is pointed at it.
"""
from __future__ import annotations

import json
import re

from .catalog import QUERY_CATALOG
from .generator import _validate

# Map a dashboard category to the catalog group its queries live in.
GROUP_BY_CAT = {"overview": "Overview", "system": "System", "user": "User",
                "governance": "Governance", "quality": "Quality",
                "sensitivity": "Sensitivity"}

# Column-name heuristics used to pick chart bindings from a query's columns.
VALUE_COLS = ["count", "value", "pct", "score", "days", "edits"]
TIME_COLS = ["week", "date", "month", "day"]
CAT_COLS = ["name", "bucket", "level", "type", "dimension", "source", "term",
            "status", "pii_type", "rating", "owner", "metric", "element",
            "table", "asset", "action", "policy", "worker"]


def conversation_prompt(messages: list[dict], spec: dict | None = None,
                        section: str | None = None) -> str:
    """Fold the chat history (+ the spec so far) into one instruction for the
    generator. If a spec exists, we ask for a full updated spec so refinements
    ('make panel 2 a line chart') edit the current dashboard rather than start
    over. When a section is given, the dashboard is pinned to that category so
    the builder stays consistent with the Analytics section you're in."""
    instruction = next((m.get("content", "") for m in reversed(messages)
                        if m.get("role") == "user"), "").strip()
    pre = (f"Put this dashboard in the '{section}' section (set category={section}). "
           if section in GROUP_BY_CAT else "")
    if spec:
        return (f"{pre}Here is the current dashboard spec as JSON:\n{json.dumps(spec)}\n\n"
                f"Apply this change and return the FULL updated spec: {instruction}")
    # Include brief earlier context so multi-turn intent isn't lost.
    earlier = " ".join(m["content"] for m in messages[:-1]
                       if m.get("role") == "user")[:400]
    lead = f"Context: {earlier}. " if earlier else ""
    return f"{pre}{lead}Build a dashboard: {instruction}"


# ── offline deterministic builder ────────────────────────────
def _kw_category(text: str) -> str:
    t = text.lower()
    if any(k in t for k in ["pii", "sensit", "exposure", "mask", "encrypt"]):
        return "sensitivity"
    if any(k in t for k in ["quality", "dq", "dimension"]):
        return "quality"
    if any(k in t for k in ["glossary", "term", "policy", "lineage", "trust", "coverage"]):
        return "governance"
    if any(k in t for k in ["profil", "scan", "source", "inventory", "system", "worker"]):
        return "system"
    if any(k in t for k in ["owner", "steward", "rating", "activity", "user"]):
        return "user"
    return "overview"


def _first(cols: list[str], pool: list[str], exclude: str | None = None) -> str | None:
    for c in pool:
        if c in cols and c != exclude:
            return c
    return None


def _panel_for(q: dict, idx: int, prefer_kpi: bool = False) -> dict:
    """Build a schema-valid panel for a query, choosing a sensible chart type."""
    cols = q["columns"]
    val = _first(cols, VALUE_COLS)
    tcol = _first(cols, TIME_COLS)
    pid, title = f"p{idx}", q["name"].replace("_", " ").title()

    if prefer_kpi and val:
        return {"id": pid, "kind": "kpi", "title": title,
                "query": q["name"], "bindings": {"value": val}}
    if tcol and val:  # time series
        return {"id": pid, "kind": "chart", "title": title, "query": q["name"],
                "chartType": "line", "bindings": {"x": tcol, "y": val}, "span": 2}
    cat = _first(cols, CAT_COLS, exclude=val) or _first(cols, cols, exclude=val)
    if cat and val:  # categorical breakdown
        ctype = "donut" if q["group"] in ("Sensitivity", "Governance") else "bar"
        return {"id": pid, "kind": "chart", "title": title, "query": q["name"],
                "chartType": ctype, "bindings": {"category": cat, "value": val}, "span": 2}
    return {"id": pid, "kind": "table", "title": title, "query": q["name"]}  # fallback


def _title(instruction: str, cat: str) -> str:
    s = re.sub(r"\s+", " ", instruction).strip().rstrip(".")
    s = s[:60] if s else f"{cat.title()} dashboard"
    return (s[0].upper() + s[1:]) if s else "Dashboard"


def demo_build(instruction: str, spec: dict | None = None,
               section: str | None = None) -> dict:
    """Construct a valid spec from the request without an LLM.

    Picks the category from the active section if given, else from keywords,
    then takes that section's queries and lays out a KPI + a couple of charts
    with bindings drawn from real columns. Always returns a schema-valid spec
    (falls back to a single table panel if the richer layout somehow fails
    validation)."""
    cat = section if section in GROUP_BY_CAT else _kw_category(instruction)
    qs = [q for q in QUERY_CATALOG if q.get("group") == GROUP_BY_CAT[cat]][:4] \
        or QUERY_CATALOG[:3]
    panels = [_panel_for(qs[0], 1, prefer_kpi=True)]
    for i, q in enumerate(qs[1:4], start=2):
        panels.append(_panel_for(q, i))
    spec = {"version": 1, "title": _title(instruction, cat), "category": cat, "panels": panels}

    errors = _validate(spec, QUERY_CATALOG)
    if errors:  # guaranteed-valid minimal fallback
        q = qs[0]
        spec = {"version": 1, "title": _title(instruction, cat), "category": cat,
                "panels": [{"id": "p1", "kind": "table",
                            "title": q["name"].replace("_", " ").title(), "query": q["name"]}]}
        errors = _validate(spec, QUERY_CATALOG)
    return {"spec": spec, "valid": not errors, "errors": errors, "engine": "demo"}


def summarize(result: dict) -> str:
    """A short assistant reply describing what was built (no extra LLM call)."""
    spec = result.get("spec") or {}
    if not result.get("valid"):
        return ("I drafted a dashboard but it needs fixing: "
                + "; ".join(result.get("errors", [])[:3]))
    panels = spec.get("panels", [])
    note = " (offline draft — connect a local LLM for richer layouts)" \
        if result.get("engine") == "demo" else ""
    return (f"Built \u201c{spec.get('title')}\u201d for the {spec.get('category')} "
            f"section with {len(panels)} panel(s): "
            + ", ".join(p["title"] for p in panels) + f".{note} "
            "Tell me what to change, or add it to the dashboards.")
