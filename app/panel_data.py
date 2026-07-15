"""Resolve dashboard panels to actual data from the catalog snapshot.

A dashboard panel carries a ``query`` (one of catalog.QUERY_CATALOG) and a
``kind`` (kpi / chart / table / text). This module turns that into concrete
numbers so the UI renders the real catalog state instead of placeholder shapes.

Two tiers:
  * **Grounded** — queries backed directly by the snapshot's aggregates (trust,
    sensitivity, profiling, PII, and the per-source metrics) compute real values.
    In live mode these reflect the connected PDC; in demo mode, the bundled
    sample.
  * **Derived** — queries with no direct aggregate (trends, some row tables) are
    produced deterministically from the same snapshot, so they're stable and
    clearly demo-shaped rather than random.

Everything degrades safely: a missing snapshot key yields an empty series/zero,
never an exception, so a sparse live snapshot still renders.

Output shapes (consumed by the UI):
  kpi   -> {"kind":"kpi", "value": <number|str>, "unit": ""|"%"}
  chart -> {"kind":"chart", "chartType": <str>, "series":[{"label","value"}]}
           or stacked: {"kind":"chart","chartType","categories":[...],
                        "groups":[{"name","values":[...]}]}
  table -> {"kind":"table", "columns":[...], "rows":[[...], ...]}
  text  -> {"kind":"text", "markdown": <str>}
"""
from __future__ import annotations

from .catalog import QUERY_CATALOG, catalog_snapshot

_COLUMNS = {q["name"]: q["columns"] for q in QUERY_CATALOG}


# ── helpers ──────────────────────────────────────────────────
def _sources(snap: dict) -> list[dict]:
    return snap.get("sources") or []


def _series(d: dict) -> list[dict]:
    """A {name: count} dict -> ordered [{label, value}] series."""
    return [{"label": k, "value": v} for k, v in (d or {}).items()]


def _seed(name: str) -> int:
    """Small stable integer from a string, for deterministic derived values."""
    return sum(ord(c) for c in name)


def _pct(n: float, d: float) -> int:
    return round(100 * n / d) if d else 0


# ── grounded resolvers (real aggregates) ─────────────────────
def _trust_distribution(s):
    t = s.get("trust", {})
    total = sum(t.values()) or 1
    return {"value": _pct(t.get("Highly Trusted", 0), total), "unit": "%",
            "series": _series(t)}


def _sensitivity_mix(s):
    return {"value": s.get("sensitivity", {}).get("High", 0),
            "series": _series(s.get("sensitivity", {}))}


def _pii_discoveries(s):
    p = s.get("pii_types", {})
    return {"value": sum(p.values()), "series": _series(p)}


def _profile_status(s):
    prof = s.get("profiling", {})
    val = s.get("totals", {}).get("profiled_pct")
    if val is None and prof:
        done = prof.get("Completed", 0)
        val = _pct(done, sum(prof.values()))
    return {"value": val if val is not None else 0, "unit": "%", "series": _series(prof)}


def _assets_by_source(s):
    return {"series": [{"label": x["name"], "value": x.get("assets") or 0} for x in _sources(s)]}


def _assets_by_type(s):
    agg: dict[str, int] = {}
    for x in _sources(s):
        agg[x.get("type") or "other"] = agg.get(x.get("type") or "other", 0) + (x.get("assets") or 0)
    return {"series": _series(agg)}


def _quality_by_source(s):
    return {"value": s.get("totals", {}).get("mean_quality", 0),
            "series": [{"label": x["name"], "value": x.get("mean_quality") or 0} for x in _sources(s)]}


def _term_coverage(s):
    return {"value": s.get("totals", {}).get("term_coverage_pct", 0), "unit": "%",
            "series": [{"label": x["name"], "value": x.get("term_coverage_pct") or 0} for x in _sources(s)]}


def _asset_counts(s):
    return {"value": s.get("totals", {}).get("assets") or sum(x.get("assets") or 0 for x in _sources(s))}


def _source_counts(s):
    return {"value": s.get("totals", {}).get("sources") or len(_sources(s))}


def _source_inventory(s):
    rows = [[x.get("name"), x.get("type"), x.get("assets"), x.get("last_scan", "—")] for x in _sources(s)]
    return {"columns": _COLUMNS["source_inventory"], "rows": rows}


def _stale_failed(s):
    rows = [[f"{x['name']}/batch", x["name"], f"{x.get('failed_scans',0)} failed", x.get("last_scan", "—")]
            for x in _sources(s) if x.get("failed_scans")]
    return {"value": sum(x.get("failed_scans", 0) for x in _sources(s)),
            "columns": _COLUMNS["stale_failed"], "rows": rows}


# ── per-source stacked resolvers ─────────────────────────────
def _sensitive_by_source(s):
    cats = [x["name"] for x in _sources(s)]
    high = [x.get("high_sensitivity") or 0 for x in _sources(s)]
    other = [max((x.get("assets") or 0) - (x.get("high_sensitivity") or 0), 0) for x in _sources(s)]
    return {"value": sum(high), "categories": cats,
            "groups": [{"name": "High", "values": high}, {"name": "Other", "values": other}]}


def _owners_coverage(s):
    cats = [x["name"] for x in _sources(s)]
    unowned = [round((x.get("assets") or 0) * (x.get("unowned_pct") or 0) / 100) for x in _sources(s)]
    owned = [max((x.get("assets") or 0) - u, 0) for x, u in zip(_sources(s), unowned)]
    tot = sum(o + u for o, u in zip(owned, unowned)) or 1
    return {"value": _pct(sum(owned), tot), "unit": "%", "categories": cats,
            "groups": [{"name": "Owned", "values": owned}, {"name": "Unowned", "values": unowned}]}


def _trust_by_source(s):
    # No per-source trust banding in the snapshot; derive a stable split from the
    # source's mean quality so the stacked bars are representative (demo-shaped).
    cats, hi, mid, lo = [], [], [], []
    for x in _sources(s):
        a = x.get("assets") or 0
        q = (x.get("mean_quality") or 70) / 100
        cats.append(x["name"]); h = round(a * q * 0.5); m = round(a * 0.3); l = max(a - h - m, 0)
        hi.append(h); mid.append(m); lo.append(l)
    return {"categories": cats, "groups": [
        {"name": "Highly Trusted", "values": hi}, {"name": "Trusted", "values": mid},
        {"name": "Untrusted", "values": lo}]}


# ── derived resolvers (deterministic from the snapshot) ──────
def _dq_dimensions(s):
    base = s.get("totals", {}).get("mean_quality", 76)
    dims = {"Completeness": base + 6, "Validity": base, "Consistency": base - 4,
            "Uniqueness": base + 2, "Timeliness": base - 8}
    dims = {k: max(0, min(100, v)) for k, v in dims.items()}
    return {"value": base, "unit": "", "series": _series(dims)}


def _quality_distribution(s):
    qs = [x.get("mean_quality") or 0 for x in _sources(s)]
    bins = {"0-50": 0, "51-60": 0, "61-70": 0, "71-80": 0, "81-90": 0, "91-100": 0}
    for q in qs:
        for lo, hi, key in [(0, 50, "0-50"), (51, 60, "51-60"), (61, 70, "61-70"),
                            (71, 80, "71-80"), (81, 90, "81-90"), (91, 100, "91-100")]:
            if lo <= q <= hi:
                bins[key] += 1
    return {"series": _series(bins)}


def _worst_tables(s):
    ranked = sorted(_sources(s), key=lambda x: x.get("mean_quality") or 100)[:6]
    rows = [[f"{x['name']}.main", x["name"], x.get("mean_quality") or 0] for x in ranked]
    return {"value": ranked[0].get("mean_quality") if ranked else 0,
            "series": [{"label": r[0], "value": r[2]} for r in rows],
            "columns": _COLUMNS["worst_tables"], "rows": rows}


def _trend(end: float, weeks: int = 8):
    return [{"label": f"W{i+1}", "value": round(end - (weeks - 1 - i) * 1.5, 1)} for i in range(weeks)]


def _coverage_trend(s):
    return {"series": _trend(s.get("totals", {}).get("term_coverage_pct", 61))}


def _recently_modified(s):
    base = max(1, (s.get("totals", {}).get("assets") or 12480) // 400)
    return {"value": base * 7, "series": [{"label": f"D{i+1}", "value": base + (i % 4) * 3} for i in range(7)]}


def _scan_activity(s):
    base = max(1, len(_sources(s)))
    return {"value": base * 30, "series": [{"label": f"D{i+1}", "value": base + (_seed(str(i)) % 5)} for i in range(14)]}


def _pii_typed_rows(s, masked_flag):
    rows = []
    for x in _sources(s):
        if x.get("high_sensitivity"):
            rows.append([f"{x['name']}.pii", x["name"], "EMAIL, SSN", masked_flag(x)])
    return rows


# ── remaining panels (governance / user / quality detail) ────
def _lineage_status(s):
    lin = s.get("lineage", {})
    total = sum(lin.values()) or 1
    return {"value": _pct(lin.get("Verified", 0), total), "unit": "%", "series": _series(lin)}


def _ratings_distribution(s):
    r = s.get("ratings", {})
    n = sum(r.values()) or 1
    avg = sum(int(k) * v for k, v in r.items()) / n if r else 0
    return {"value": round(avg, 1), "series": [{"label": f"{k}★", "value": v} for k, v in r.items()]}


def _policy_counts(s):
    p = s.get("policies", {})
    return {"value": len(p), "series": _series(p)}


def _top_terms(s):
    t = s.get("terms", {})
    return {"value": len(t), "series": _series(t)}


def _edit_activity(s):
    e = s.get("edits", {})
    return {"value": sum(e.values()), "series": _series(e)}


def _owner_workload(s):
    owners = s.get("owners", [])
    return {"value": len(owners),
            "series": [{"label": o["owner"], "value": o.get("count", 0)} for o in owners],
            "columns": ["owner", "count", "edits"],
            "rows": [[o["owner"], o.get("count", 0), o.get("edits", 0)] for o in owners]}


def _cov(s, key, label_pct):
    return {"value": s.get("coverage", {}).get(key, 0), "unit": "%"}


def _stacked_by_source(s, split_pct_key, names):
    """Generic stacked: split each source's assets by a coverage percentage."""
    cats = [x["name"] for x in _sources(s)]
    pct = [(x.get(split_pct_key) or 0) / 100 for x in _sources(s)]
    a = [x.get("assets") or 0 for x in _sources(s)]
    yes = [round(av * p) for av, p in zip(a, pct)]
    no = [max(av - y, 0) for av, y in zip(a, yes)]
    return {"categories": cats, "groups": [{"name": names[0], "values": yes},
                                           {"name": names[1], "values": no}]}


def _generic(query, kind, s):
    """Fallback: render *something* real from the sources for any unmapped query."""
    if kind == "kpi":
        return {"value": s.get("totals", {}).get("assets") or len(_sources(s))}
    if kind == "table":
        cols = _COLUMNS.get(query, ["source", "value"])
        rows = [[x.get("name")] + [x.get("assets") or 0] * (len(cols) - 1) for x in _sources(s)]
        return {"columns": cols, "rows": rows}
    return {"series": [{"label": x["name"], "value": x.get("assets") or 0} for x in _sources(s)]}


RESOLVERS = {
    "trust_distribution": _trust_distribution, "sensitivity_mix": _sensitivity_mix,
    "pii_discoveries": _pii_discoveries, "profile_status": _profile_status,
    "assets_by_source": _assets_by_source, "assets_by_type": _assets_by_type,
    "quality_by_source": _quality_by_source, "term_coverage": _term_coverage,
    "asset_counts": _asset_counts, "source_counts": _source_counts,
    "source_inventory": _source_inventory, "stale_failed": _stale_failed,
    "sensitive_by_source": _sensitive_by_source, "owners_coverage": _owners_coverage,
    "trust_by_source": _trust_by_source, "dq_dimensions": _dq_dimensions,
    "quality_distribution": _quality_distribution, "worst_tables": _worst_tables,
    "coverage_trend": _coverage_trend, "recently_modified": _recently_modified,
    "scan_activity": _scan_activity,
    "pii_assets": lambda s: {"columns": _COLUMNS["pii_assets"],
                             "rows": _pii_typed_rows(s, lambda x: "no")},
    "sensitive_unowned": lambda s: {"columns": _COLUMNS["sensitive_unowned"],
                                    "rows": [[f"{x['name']}.tbl", x["name"], "EMAIL", x.get("mean_quality") or 0]
                                             for x in _sources(s) if x.get("unowned_pct", 0) > 30 and x.get("high_sensitivity")]},
    "lineage_status": _lineage_status,
    "lineage_by_source": lambda s: _stacked_by_source(s, "term_coverage_pct", ["Verified", "Unverified"]),
    "ratings_distribution": _ratings_distribution,
    "policy_counts": _policy_counts,
    "policy_coverage": lambda s: _cov(s, "policy_pct", "policy"),
    "encryption_status": lambda s: _cov(s, "encryption_pct", "encryption"),
    "masking_status": lambda s: _cov(s, "masking_pct", "masking"),
    "top_terms": _top_terms,
    "term_status": lambda s: {"value": s.get("totals", {}).get("term_coverage_pct", 0), "unit": "%"},
    "edit_activity": _edit_activity,
    "owner_workload": _owner_workload,
    "ownership_time": lambda s: {"value": 4, "unit": "d"},
    "worker_status": lambda s: {"value": len([x for x in _sources(s) if not x.get("failed_scans")])},
    "owners_coverage_table": _owner_workload,
    "dq_by_source": lambda s: _stacked_by_source(s, "mean_quality", ["At/Above", "Below"]),
    "untermed_critical": lambda s: {"value": sum(1 for x in _sources(s) if (x.get("term_coverage_pct") or 100) < 50),
                                    "columns": _COLUMNS["untermed_critical"],
                                    "rows": [[f"{x['name']}.critical", x["name"], "High"]
                                             for x in _sources(s) if (x.get("term_coverage_pct") or 100) < 50]},
    "unowned_high_value": lambda s: {"columns": _COLUMNS["unowned_high_value"],
                                     "rows": [[f"{x['name']}.asset", x["name"], "High", x.get("mean_quality") or 0]
                                              for x in _sources(s) if x.get("unowned_pct", 0) > 30]},
    "risk_assets": lambda s: {"columns": _COLUMNS["risk_assets"],
                              "rows": [[f"{x['name']}.risk", x["name"], "Untrusted + High"]
                                       for x in sorted(_sources(s), key=lambda x: x.get("mean_quality") or 100)[:5]]},
}


def resolve_panel(panel: dict, snap: dict | None = None) -> dict:
    """Resolve one panel to concrete data, shaped for its kind."""
    snap = snap if snap is not None else catalog_snapshot()
    kind = panel.get("kind", "chart")
    if kind == "text":
        return {"kind": "text", "markdown": panel.get("markdown", "")}
    query = panel.get("query", "")
    data = RESOLVERS[query](snap) if query in RESOLVERS else _generic(query, kind, snap)

    if kind == "kpi":
        return {"kind": "kpi", "value": data.get("value", 0), "unit": data.get("unit", "")}
    if kind == "table":
        return {"kind": "table",
                "columns": data.get("columns") or _COLUMNS.get(query, []),
                "rows": data.get("rows", [])}
    # chart
    out = {"kind": "chart", "chartType": panel.get("chartType", "bar")}
    if "groups" in data:                       # stacked / multi-series
        out["categories"] = data.get("categories", [])
        out["groups"] = data["groups"]
    else:
        out["series"] = data.get("series", [])
    return out


def scope_snapshot(snap: dict, source: str | None) -> dict:
    """Return a snapshot narrowed to a single data source.

    Per-source fields (assets, quality, coverage, high-sensitivity) are taken
    directly; global distributions (trust, sensitivity, profiling, …) are scaled
    by the source's share of assets — a demo approximation. In live mode the same
    scoping would be a data-source-filtered facet query.
    """
    if not source or source in ("all", "All sources"):
        return snap
    matches = [x for x in snap.get("sources", []) if x.get("name") == source]
    if not matches:
        return snap
    s = matches[0]
    assets = s.get("assets") or 0
    total = sum((x.get("assets") or 0) for x in snap.get("sources", [])) or 1
    share = assets / total
    out = dict(snap)
    out["sources"] = matches
    out["totals"] = {**snap.get("totals", {}), "assets": assets, "sources": 1,
                     "mean_quality": s.get("mean_quality"),
                     "term_coverage_pct": s.get("term_coverage_pct"),
                     "profiled_pct": s.get("profiled_pct")}
    for key in ("trust", "sensitivity", "profiling", "pii_types", "lineage",
                "ratings", "policies", "terms", "edits"):
        if isinstance(snap.get(key), dict):
            out[key] = {k: round(v * share) for k, v in snap[key].items()}
    if s.get("high_sensitivity") is not None and isinstance(out.get("sensitivity"), dict):
        out["sensitivity"] = {**out["sensitivity"], "High": s["high_sensitivity"]}
    return out


def resolve_dashboard(spec: dict, snap: dict | None = None, source: str | None = None) -> dict:
    """Resolve every panel in a dashboard spec -> {panel_id: data}.

    Optionally scope to a single data source so a board can be narrowed to one
    connection.
    """
    snap = snap if snap is not None else catalog_snapshot()
    snap = scope_snapshot(snap, source)
    out = {"demo": bool(snap.get("demo")), "scope": source or "all", "panels": {}}
    for p in spec.get("panels", []):
        pid = p.get("id")
        if pid:
            try:
                out["panels"][pid] = resolve_panel(p, snap)
            except Exception as exc:  # noqa: BLE001 — one bad panel shouldn't blank the board
                out["panels"][pid] = {"kind": p.get("kind", "chart"), "error": str(exc)}
    return out


def source_names(snap: dict | None = None) -> list:
    """The connected data-source names, for the scope selector."""
    snap = snap if snap is not None else catalog_snapshot()
    return [x.get("name") for x in snap.get("sources", []) if x.get("name")]


def _detail(query: str, src: dict, label):
    """A representative per-asset detail value for the drill list."""
    if label:
        return label
    if "quality" in query:
        return src.get("mean_quality")
    if "trust" in query:
        return "Trusted"
    if "sensitiv" in query or "pii" in query:
        return "High" if src.get("high_sensitivity") else "Low"
    if "term" in query or "coverage" in query:
        return f"{src.get('term_coverage_pct', 0)}% termed"
    if "profil" in query or "scan" in query:
        return f"{src.get('profiled_pct', 0)}% profiled"
    if "owner" in query:
        return f"{src.get('unowned_pct', 0)}% unowned"
    return src.get("type", "asset")


def drill_assets(snap: dict | None, query: str, label=None, source=None, limit: int = 30) -> dict:
    """Return the representative underlying assets for a panel (drill-through).

    Demo mode synthesises asset rows from the scoped sources so a click on a
    chart/table opens the assets behind it; live mode would issue a /search
    against PDC filtered by the same facet. Read-only.
    """
    snap = scope_snapshot(snap if snap is not None else catalog_snapshot(), source)
    rows = []
    for x in _sources(snap):
        n = min(6, max(1, (x.get("assets") or 0) // 1000))
        for i in range(n):
            rows.append([f"{x['name']}.{query.split('_')[0]}_{i+1}", x["name"], _detail(query, x, label)])
            if len(rows) >= limit:
                break
        if len(rows) >= limit:
            break
    title = "Assets"
    if label:
        title += f" · {label}"
    if source and source not in ("all", "All sources"):
        title += f" · {source}"
    return {"title": title, "query": query, "columns": ["asset", "source", "detail"], "rows": rows}
