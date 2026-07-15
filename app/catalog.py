"""Catalog snapshot — the state the recommender and host LLM reason over.

A snapshot is a compact, structured read of the catalog assembled from the
PDC facet/search/data-source endpoints: what's connected, how much is
scanned/profiled, and where trust, sensitivity, quality, and coverage sit —
overall and per source.

In demo mode (INSIGHTS_DEMO=true, or PDC unreachable) a bundled sample is
returned and flagged demo=True, so the MCP server is usable for enablement
before a live PDC 10.2.11 instance is wired up.
"""
from __future__ import annotations

import os

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
    "sources": [
        {"name": "Snowflake-PROD", "type": "warehouse", "assets": 4210,
         "profiled_pct": 99, "failed_scans": 0, "high_sensitivity": 280,
         "unowned_pct": 26, "term_coverage_pct": 74, "mean_quality": 86, "last_scan": "12m ago"},
        {"name": "S3-raw", "type": "object_store", "assets": 3120,
         "profiled_pct": 81, "failed_scans": 6, "high_sensitivity": 310,
         "unowned_pct": 52, "term_coverage_pct": 34, "mean_quality": 64, "last_scan": "1h ago"},
        {"name": "Postgres-billing", "type": "database", "assets": 2480,
         "profiled_pct": 97, "failed_scans": 1, "high_sensitivity": 92,
         "unowned_pct": 23, "term_coverage_pct": 68, "mean_quality": 78, "last_scan": "40m ago"},
        {"name": "Oracle-legacy", "type": "database", "assets": 1690,
         "profiled_pct": 88, "failed_scans": 4, "high_sensitivity": 160,
         "unowned_pct": 41, "term_coverage_pct": 41, "mean_quality": 81, "last_scan": "3h ago"},
        {"name": "BigQuery-mart", "type": "warehouse", "assets": 980,
         "profiled_pct": 72, "failed_scans": 2, "high_sensitivity": 0,
         "unowned_pct": 34, "term_coverage_pct": 34, "mean_quality": 73, "last_scan": "1d ago"},
    ],
}


def _facet_map(rows: list[dict], key: str) -> dict:
    """Flatten one facet's options into a {name: count} dict for a given key."""
    for f in rows:
        if f.get("key") == key:
            return {o["name"]: o["count"] for o in f.get("options", [])}
    return {}


def catalog_snapshot() -> dict:
    """Assemble the catalog state the recommender and host LLM reason over.

    Three modes, in priority order:
      1. Demo on  -> return the bundled sample (flagged demo=True) so the app and
         MCP server work with no live PDC. Great for enablement and tests.
      2. Live      -> read facets (sensitivity/type/source), the trust banding,
         and the data-source inventory, and shape them into the snapshot dict.
      3. Live but PDC unreachable -> fall back to the sample with a note, so the
         feature degrades gracefully rather than erroring out.
    """
    if _demo():
        return dict(SAMPLE_SNAPSHOT)
    try:
        # One facet call covers the headline distributions; trust needs its own
        # banded counts; data_sources() supplies the per-source inventory.
        facets = client.facets("*", {"sensitivity": [], "type": [], "rootIds": []})
        trust = {b["name"]: b["count"] for b in client.trust_distribution()}
        sources = []
        for ds in client.data_sources():
            name = ds.get("name")
            sources.append({"name": name, "type": ds.get("type"),
                            "assets": ds.get("assetCount"),
                            "last_scan": ds.get("lastScanAt")})
        return {"demo": False,
                "trust": trust,
                "sensitivity": _facet_map(facets, "sensitivity"),
                "sources": sources,
                "totals": {"sources": len(sources)}}
    except (PDCError, Exception) as exc:  # noqa: BLE001 — degrade, never crash
        snap = dict(SAMPLE_SNAPSHOT)
        snap["note"] = f"PDC unreachable ({exc}); returning demo snapshot"
        return snap
