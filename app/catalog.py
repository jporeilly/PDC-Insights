"""Catalog snapshot — the state the recommender and host LLM reason over.

A snapshot is a compact, structured read of the catalog assembled from the
PDC facet/search/data-source endpoints: what's connected, how much is
scanned/profiled, and where trust, sensitivity, quality, and coverage sit —
overall and per source.

In demo mode (INSIGHTS_DEMO=true, or PDC unreachable) a bundled sample is
returned and flagged demo=True, so the MCP server is usable for enablement
before a live PDC 11.0 instance is wired up.
"""
from __future__ import annotations

import os

from .config import settings
from .pdc_client import client, PDCError

# The Query Library the generator grounds on. Names match the standard
# dashboards in app/dashboards and the bridge DAs in docs/PDC-CONNECTOR.md.
QUERY_CATALOG = [
    {"name": "asset_counts", "group": "Overview", "columns": ["metric", "count"]},
    {"name": "source_counts", "group": "Overview", "columns": ["metric", "count"]},
    {"name": "trust_distribution", "group": "Governance", "columns": ["bucket", "count"]},
    {"name": "trust_by_source", "group": "Governance", "columns": ["source", "bucket", "count"]},
    {"name": "sensitivity_mix", "group": "Sensitivity", "columns": ["level", "count"]},
    {"name": "sensitive_by_source", "group": "Sensitivity", "columns": ["source", "level", "count"]},
    {"name": "pii_discoveries", "group": "Sensitivity", "columns": ["pii_type", "count", "source"]},
    {"name": "quality_by_source", "group": "Quality", "columns": ["source", "score"]},
    {"name": "quality_distribution", "group": "Quality", "columns": ["bucket", "count"]},
    {"name": "worst_tables", "group": "Quality", "columns": ["table", "source", "score"]},
    {"name": "dq_dimensions", "group": "Quality", "columns": ["dimension", "value"]},
    {"name": "term_coverage", "group": "Governance", "columns": ["source", "pct"]},
    {"name": "top_terms", "group": "Governance", "columns": ["term", "count"]},
    {"name": "coverage_trend", "group": "Governance", "columns": ["week", "pct"]},
    {"name": "untermed_critical", "group": "Governance", "columns": ["element", "source", "sensitivity"]},
    {"name": "lineage_status", "group": "Governance", "columns": ["status", "count"]},
    {"name": "profile_status", "group": "System", "columns": ["status", "count"]},
    {"name": "assets_by_source", "group": "System", "columns": ["source", "count"]},
    {"name": "scan_activity", "group": "System", "columns": ["date", "count"]},
    {"name": "owners_coverage", "group": "User", "columns": ["source", "status", "count"]},
    {"name": "owner_workload", "group": "User", "columns": ["owner", "count", "edits"]},
    {"name": "ratings_distribution", "group": "User", "columns": ["rating", "count"]},
    {"name": "recently_modified", "group": "User", "columns": ["date", "count"]},
    {"name": "edit_activity", "group": "User", "columns": ["action", "count"]},
    {"name": "ownership_time", "group": "User", "columns": ["metric", "days"]},
    {"name": "unowned_high_value", "group": "User", "columns": ["asset", "source", "sensitivity", "trust"]},
    {"name": "assets_by_type", "group": "System", "columns": ["type", "count"]},
    {"name": "source_inventory", "group": "System", "columns": ["source", "type", "assets", "last_scan"]},
    {"name": "stale_failed", "group": "System", "columns": ["asset", "source", "status", "last_attempt"]},
    {"name": "worker_status", "group": "System", "columns": ["worker", "state"]},
    {"name": "risk_assets", "group": "Overview", "columns": ["asset", "source", "issue"]},
    {"name": "term_status", "group": "Governance", "columns": ["status", "count"]},
    {"name": "policy_counts", "group": "Governance", "columns": ["policy", "count"]},
    {"name": "policy_coverage", "group": "Governance", "columns": ["metric", "pct"]},
    {"name": "lineage_by_source", "group": "Governance", "columns": ["source", "status", "count"]},
    {"name": "dq_by_source", "group": "Quality", "columns": ["source", "dimension", "value"]},
    # One query per DQ best-practice dimension. Each resolves to every shape a
    # panel can ask for: kpi -> the dimension's overall score, chart -> the
    # per-source scores, table -> the worst offenders with the dimension's
    # characteristic issue. Grounded in demo mode; derived (stable, clearly
    # demo-shaped) when a live snapshot doesn't carry the aggregate yet.
    {"name": "dq_completeness", "group": "Quality", "columns": ["source", "score"]},
    {"name": "dq_accuracy", "group": "Quality", "columns": ["source", "score"]},
    {"name": "dq_validity", "group": "Quality", "columns": ["source", "score"]},
    {"name": "dq_uniqueness", "group": "Quality", "columns": ["source", "score"]},
    {"name": "dq_consistency", "group": "Quality", "columns": ["source", "score"]},
    {"name": "dq_timeliness", "group": "Quality", "columns": ["source", "score"]},
    {"name": "dq_traceability", "group": "Quality", "columns": ["source", "score"]},
    {"name": "dq_clarity", "group": "Quality", "columns": ["source", "score"]},
    {"name": "dq_availability", "group": "Quality", "columns": ["source", "score"]},
    {"name": "sensitive_unowned", "group": "Sensitivity", "columns": ["asset", "source", "pii", "trust"]},
    {"name": "pii_assets", "group": "Sensitivity", "columns": ["asset", "source", "pii_types", "masked"]},
    {"name": "encryption_status", "group": "Sensitivity", "columns": ["metric", "pct"]},
    {"name": "masking_status", "group": "Sensitivity", "columns": ["metric", "pct"]},
]


def _demo() -> bool:
    return os.getenv("INSIGHTS_DEMO", "false").strip().lower() in {"1", "true", "yes", "on"}


SAMPLE_SNAPSHOT = {
    "demo": True,
    "totals": {"assets": 12480, "sources": 18, "profiled_pct": 94.2,
               "term_coverage_pct": 61, "mean_quality": 76},
    "trust": {"Untrusted": 2104, "Trusted": 3890, "Highly Trusted": 2220},
    "sensitivity": {"Low": 9180, "Medium": 2458, "High": 842},
    "profiling": {"Completed": 11760, "Skipped": 708, "Failed": 12},
    "pii_types": {"EMAIL": 1203, "PHONE": 980, "ADDRESS": 760, "DOB": 540, "SSN": 412},
    # Aggregates modelled on real PDC entity attributes (isLineageVerified,
    # features.rating, policies[], owners[], businessTerms[]) so the remaining
    # panels render real-shaped numbers in demo mode.
    "lineage": {"Verified": 7320, "Partial": 3960, "Unverified": 1200},
    "ratings": {"5": 2140, "4": 3680, "3": 2900, "2": 1180, "1": 580},
    "policies": {"PII Handling": 412, "Retention": 980, "Access Control": 1340,
                 "Data Quality": 760, "Classification": 1520},
    "terms": {"Customer": 980, "Account": 760, "Meter": 540, "Invoice": 430,
              "Service Address": 380, "Usage": 320},
    "edits": {"Tagged": 1840, "Termed": 1260, "Owned": 980, "Rated": 720, "Described": 540},
    "owners": [{"owner": "a.rivera", "count": 1820, "edits": 340},
               {"owner": "j.chen", "count": 1240, "edits": 280},
               {"owner": "m.okafor", "count": 980, "edits": 210},
               {"owner": "s.patel", "count": 760, "edits": 190},
               {"owner": "l.nguyen", "count": 540, "edits": 150}],
    "coverage": {"policy_pct": 68, "encryption_pct": 74, "masking_pct": 61,
                 "term_pct": 61, "lineage_pct": 58},
    # The DQ best-practice dimensions, overall. A deliberate story, not noise:
    # availability/uniqueness strong (the platform does its job), timeliness
    # dragged down by the batch sources, traceability weakest (lineage is the
    # programme's known gap — the Governance boards say the same thing).
    "dq": {"Completeness": 88, "Accuracy": 79, "Validity": 84, "Uniqueness": 94,
           "Consistency": 74, "Timeliness": 66, "Traceability": 58,
           "Clarity": 71, "Availability": 96},
    "terms_total": 412,
    "types": {"Table": 9640, "File": 2840},
    # Eight sources, richer spread of types and postures; asset counts sum to
    # totals.assets (12,480) and high_sensitivity sums to sensitivity.High (842)
    # so cross-panel arithmetic holds up under a demo audience's scrutiny.
    "sources": [
        {"name": "Snowflake-PROD", "type": "warehouse", "assets": 3640,
         "profiled_pct": 99, "failed_scans": 0, "high_sensitivity": 240,
         "unowned_pct": 26, "term_coverage_pct": 74, "mean_quality": 86, "last_scan": "12m ago"},
        {"name": "S3-raw", "type": "object_store", "assets": 2610,
         "profiled_pct": 81, "failed_scans": 6, "high_sensitivity": 280,
         "unowned_pct": 52, "term_coverage_pct": 34, "mean_quality": 64, "last_scan": "1h ago"},
        {"name": "Postgres-billing", "type": "database", "assets": 2140,
         "profiled_pct": 97, "failed_scans": 1, "high_sensitivity": 80,
         "unowned_pct": 23, "term_coverage_pct": 68, "mean_quality": 78, "last_scan": "40m ago"},
        {"name": "Oracle-legacy", "type": "database", "assets": 1450,
         "profiled_pct": 88, "failed_scans": 4, "high_sensitivity": 120,
         "unowned_pct": 41, "term_coverage_pct": 41, "mean_quality": 81, "last_scan": "3h ago"},
        {"name": "BigQuery-mart", "type": "warehouse", "assets": 860,
         "profiled_pct": 72, "failed_scans": 2, "high_sensitivity": 0,
         "unowned_pct": 34, "term_coverage_pct": 34, "mean_quality": 73, "last_scan": "1d ago"},
        {"name": "SharePoint-docs", "type": "document_store", "assets": 720,
         "profiled_pct": 64, "failed_scans": 3, "high_sensitivity": 72,
         "unowned_pct": 58, "term_coverage_pct": 22, "mean_quality": 58, "last_scan": "2d ago"},
        {"name": "Kafka-streams", "type": "streaming", "assets": 640,
         "profiled_pct": 55, "failed_scans": 0, "high_sensitivity": 30,
         "unowned_pct": 47, "term_coverage_pct": 28, "mean_quality": 69, "last_scan": "5m ago"},
        {"name": "MySQL-crm", "type": "database", "assets": 420,
         "profiled_pct": 92, "failed_scans": 0, "high_sensitivity": 20,
         "unowned_pct": 19, "term_coverage_pct": 66, "mean_quality": 77, "last_scan": "2h ago"},
    ],
}


def _facet_map(rows: list[dict], key: str) -> dict:
    """Flatten one facet's options into a {name: count} dict for a given key."""
    for f in rows:
        if f.get("key") == key:
            return {o["name"]: o["count"] for o in f.get("options", [])}
    return {}


# ── live snapshot: one entity sweep, aggregated client-side ──
# PDC 11's /search requires a literal searchTerm and treats "*" as a string
# that matches nothing, so the facet endpoint cannot answer "the whole
# catalog" (verified live 2026-08-25: term="*" -> every option list empty,
# term omitted -> 400, term "a" -> 734 substring hits). /entities/filter
# needs no term and pages the entire catalog, and the governed facts all ride
# on each record: attributes.features carries sensitivity, qualityScore, the
# TABLE-level trustScore, rating and isLineageVerified; attributes holds
# businessTerms and tags; system holds scannedAt/profiledAt. One cached sweep
# therefore yields every distribution the dashboards need — real numbers,
# not the derived stand-ins.
_CONTAINER_TYPES = {"RESOURCE", "SCHEMA", "DATABASE"}
# Trust scores exist per DATASET (a table or file), never per column — the
# spectrum's denominator must be datasets or the "no score" share is inflated
# by columns that could never carry one.
_DATASET_TYPES = {"TABLE", "FILE", "VIEW", "DATASET"}
_TRUST_BANDS = [("Untrusted", 0, 50), ("Trusted", 51, 75), ("Highly Trusted", 76, 100)]
_SWEEP_PAGE = 500
_SWEEP_MAX = 20000          # safety cap for very large estates; noted in snap
_LIVE_CACHE: dict = {"ts": 0.0, "snap": None}


def _short_ts(iso: str | None) -> str:
    s = str(iso or "")
    return s[:16].replace("T", " ") if "T" in s else (s or "—")


def _live_snapshot() -> dict:
    """Aggregate the live catalog from one paged /entities/filter sweep."""
    import time as _time
    ttl = settings.pdc.cache_ttl
    if ttl and _LIVE_CACHE["snap"] is not None and _time.time() - _LIVE_CACHE["ts"] < ttl:
        return _LIVE_CACHE["snap"]

    roots = client.data_sources()
    # A connection surfaces as SEVERAL roots: the resource itself plus the
    # schema/database containers under it, with every entity hanging off the
    # innermost one. Presented raw, the same connection appears twice — the
    # named resource ("Arizona_Water_Operations") with zero assets and its
    # inner schema ("awc_operations") holding them all. Collapse by
    # resourceId: the resource-typed row names the source, and every root in
    # the group feeds that one row.
    groups: dict[str, list[dict]] = {}
    for r in roots:
        rid = r.get("resourceId") or r.get("rootId") or r.get("name")
        groups.setdefault(str(rid), []).append(r)

    root_name: dict[str, str] = {}
    per: dict[str, dict] = {}
    for rows in groups.values():
        head = next((r for r in rows if r.get("rootId") == r.get("resourceId")), None)
        if head is None:  # no self-row: prefer a connector-typed row over a container
            head = next((r for r in rows
                         if str(r.get("type") or "").upper() not in _CONTAINER_TYPES),
                        rows[0])
        name = head.get("name")
        for r in rows:
            if r.get("rootId"):
                root_name[r.get("rootId")] = name
        per[name] = {"assets": 0, "hi": 0, "termed": 0, "prof": 0,
                     "q": [], "type": head.get("type"), "scan": ""}

    sens: dict[str, int] = {}
    trust = {b[0]: 0 for b in _TRUST_BANDS}
    lineage = {"Verified": 0, "Unverified": 0}
    ratings: dict[str, int] = {}
    terms: dict[str, int] = {}
    tags_all: dict[str, int] = {}
    tags_hi: dict[str, int] = {}
    prof = {"Completed": 0, "Pending": 0}
    total = termed = 0
    capped = False
    # Real per-asset rows for the governance tables, gathered on the same
    # pass: HIGH-sensitivity elements missing a business term, and assets
    # carrying governed tags (the estate's stand-in for content-scan PII).
    untermed_rows: list[list] = []
    pii_rows: list[list] = []
    untermed_hi = 0
    datasets = 0          # trust-score basis: tables/files, not columns
    types: dict[str, int] = {}
    worst: list[tuple] = []   # (score, name, source) — lowest quality assets

    for e in client.entities({}, size=_SWEEP_PAGE, extended=True):
        if e.get("type") in _CONTAINER_TYPES:
            continue
        total += 1
        if total > _SWEEP_MAX:
            capped = True
            break
        a = e.get("attributes") or {}
        f = a.get("features") or {}
        sysb = e.get("system") or {}
        src = per.get(root_name.get(e.get("rootId")))
        etype = str(e.get("type") or "OTHER").title()
        types[etype] = types.get(etype, 0) + 1

        if src is not None:
            src["assets"] += 1
            src["scan"] = max(src["scan"], str(sysb.get("scannedAt") or ""))

        s = str(f.get("sensitivity") or "").title()
        if s:
            sens[s] = sens.get(s, 0) + 1
            if s == "High" and src is not None:
                src["hi"] += 1

        q = f.get("qualityScore")
        if isinstance(q, (int, float)):
            if src is not None:
                src["q"].append(q)
            worst.append((q, e.get("name") or "—",
                          root_name.get(e.get("rootId")) or "—"))
            if len(worst) > 400:          # keep the running set small
                worst.sort()
                del worst[12:]

        ts = (f.get("trustScore") or {}).get("value") if isinstance(f.get("trustScore"), dict) else None
        if e.get("type") in _DATASET_TYPES or isinstance(ts, (int, float)):
            datasets += 1
        if isinstance(ts, (int, float)):
            for label, lo, hi in _TRUST_BANDS:
                if lo <= ts <= hi:
                    trust[label] += 1
                    break

        if "isLineageVerified" in f:
            lineage["Verified" if f.get("isLineageVerified") else "Unverified"] += 1

        rating = (f.get("rating") or {}).get("value") if isinstance(f.get("rating"), dict) else None
        if isinstance(rating, (int, float)):
            k = str(int(rating))
            ratings[k] = ratings.get(k, 0) + 1

        bts = a.get("businessTerms") or []
        if bts:
            termed += 1
            if src is not None:
                src["termed"] += 1
            for bt in bts:
                name = (bt or {}).get("name")
                if name:
                    terms[name] = terms.get(name, 0) + 1
        elif s == "High":
            untermed_hi += 1
            if len(untermed_rows) < 12:
                untermed_rows.append([e.get("name") or "—",
                                      root_name.get(e.get("rootId")) or "—", "High"])

        tag_names = [str((t or {}).get("name"))
                     for t in a.get("tags") or [] if (t or {}).get("name")]
        for name in tag_names:
            tags_all[name] = tags_all.get(name, 0) + 1
            if s == "High":
                tags_hi[name] = tags_hi.get(name, 0) + 1
        if tag_names and s == "High" and len(pii_rows) < 12:
            pii_rows.append([e.get("name") or "—",
                             root_name.get(e.get("rootId")) or "—",
                             " · ".join(tag_names[:3]), "—"])

        if sysb.get("profiledAt"):
            prof["Completed"] += 1
            if src is not None:
                src["prof"] += 1
        else:
            prof["Pending"] += 1

    def _pct(n, d):
        return round(100 * n / d, 1) if d else 0

    sources = []
    for name, x in per.items():
        n = x["assets"]
        row = {
            "name": name, "type": x["type"], "assets": n,
            "high_sensitivity": x["hi"],
            "term_coverage_pct": _pct(x["termed"], n),
            "profiled_pct": _pct(x["prof"], n),
            "failed_scans": 0,
            "last_scan": _short_ts(x["scan"]),
        }
        # Omitted rather than None when no entity carried a score: consumers
        # treat a MISSING key as "derive/ignore", but a present None reaches
        # comparisons (recommend's `< threshold`) and arithmetic raw.
        if x["q"]:
            row["mean_quality"] = round(sum(x["q"]) / len(x["q"]))
        sources.append(row)

    # A resource root and the schema under it can BOTH surface as "sources"
    # (data_sources enumerates every root type), with all entities hanging off
    # the inner one — the outer container then shows as a zero-asset row that
    # the derived tier would decorate with stand-in numbers. Keep only rows
    # that actually hold assets, unless nothing does (a genuinely unscanned
    # catalog should still list what is connected).
    holding = [s for s in sources if s["assets"] > 0]
    if holding:
        sources = holding

    all_q = [s["mean_quality"] for s in sources if s.get("mean_quality") is not None]
    top_terms = dict(sorted(terms.items(), key=lambda kv: -kv[1])[:8])
    # The governed tags marking HIGH-sensitivity data stand in for content-scan
    # PII types: real names from this catalog, not the sample's EMAIL/SSN.
    pii = dict(sorted((tags_hi or tags_all).items(), key=lambda kv: -kv[1])[:6])

    totals = {"assets": total, "sources": len(sources),
              "profiled_pct": _pct(prof["Completed"], total),
              "term_coverage_pct": _pct(termed, total)}
    if all_q:
        totals["mean_quality"] = round(sum(all_q) / len(all_q))
    snap = {
        "demo": False,
        "totals": totals,
        "trust": trust,
        "sensitivity": sens,
        "profiling": prof,
        "lineage": lineage,
        "ratings": ratings,
        "terms": top_terms,
        "pii_types": pii,
        "coverage": {"term_pct": _pct(termed, total),
                     "lineage_pct": _pct(lineage["Verified"],
                                         lineage["Verified"] + lineage["Unverified"])},
        "sources": sources,
        # Real asset rows from the sweep — the table resolvers prefer these
        # over the source-derived stand-ins when the key is present.
        "untermed_rows": untermed_rows,
        "untermed_hi_total": untermed_hi,
        "pii_rows": pii_rows,
        "trust_datasets": datasets,
        "types": types,
        "terms_total": len(terms),
        "worst_rows": [[n, srcn, round(sc)] for sc, n, srcn in sorted(worst)[:6]],
    }
    if capped:
        snap["note"] = f"aggregates cover the first {_SWEEP_MAX} entities"
    if ttl:
        _LIVE_CACHE.update(ts=_time.time(), snap=snap)
    return snap


def catalog_snapshot(force_demo: bool = False) -> dict:
    """Assemble the catalog state the recommender and host LLM reason over.

    Three modes, in priority order:
      1. Demo on  -> return the bundled sample (flagged demo=True) so the app and
         MCP server work with no live PDC. Great for enablement and tests.
      2. Live      -> read facets (sensitivity/type/source), the trust banding,
         and the data-source inventory, and shape them into the snapshot dict.
      3. Live but PDC unreachable -> fall back to the sample with a note, so the
         feature degrades gracefully rather than erroring out.

    ``force_demo=True`` returns the bundled sample for this call only, without
    reading or touching the app-wide INSIGHTS_DEMO setting — the per-view
    "Demo data" override in the dashboards UI rides on this.
    """
    if force_demo or _demo():
        return dict(SAMPLE_SNAPSHOT)
    try:
        # One cached entity sweep aggregates every distribution the dashboards
        # need — see _live_snapshot() for why the facet endpoint can't do it.
        return _live_snapshot()
    except (PDCError, Exception) as exc:  # noqa: BLE001 — degrade, never crash
        snap = dict(SAMPLE_SNAPSHOT)
        snap["note"] = f"PDC unreachable ({exc}); returning demo snapshot"
        return snap
