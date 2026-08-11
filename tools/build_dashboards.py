"""Generate the built-in standard dashboards as schema-valid .studio.json files.

These ship with the app (seed library) AND serve as enablement examples —
each one opens in the Designer so users can see how a real spec is shaped.
Run from the project root:  python tools/build_dashboards.py
"""
import json
import pathlib

import jsonschema

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCHEMA = json.loads((ROOT / "app/schema/dashboard.schema.json").read_text())
OUT = ROOT / "app/dashboards"


def kpi(i, title, query):
    return {"id": f"k{i}", "kind": "kpi", "title": title, "query": query, "span": 1}


def chart(i, title, query, ct, bind, span=2, options=None):
    p = {"id": f"c{i}", "kind": "chart", "title": title, "query": query,
         "chartType": ct, "bindings": bind, "span": span}
    if options:
        p["options"] = options
    return p


def table(i, title, query, span=4):
    return {"id": f"t{i}", "kind": "table", "title": title, "query": query, "span": span}


def text(i, title, query, markdown, span=2):
    # The schema requires a query on every panel; a text panel names the feed
    # it annotates so the reference stays valid.
    return {"id": f"x{i}", "kind": "text", "title": title, "query": query,
            "markdown": markdown, "span": span}


# section -> [dashboards]
DASHBOARDS = {
 "overview": [
  {"id": "catalog-health", "title": "Catalog health", "category": "overview",
   "subtitle": "Trust, quality & coverage at a glance",
   "panels": [
     kpi(1, "Catalog assets", "asset_counts"), kpi(2, "Data sources", "source_counts"),
     kpi(3, "Glossary coverage", "term_coverage"), kpi(4, "High sensitivity", "sensitivity_mix"),
     chart(1, "Trust spectrum", "trust_distribution", "bar",
           {"category": "bucket", "value": "count"}, options={"scoreBands": True}),
     chart(2, "Sensitivity mix", "sensitivity_mix", "donut", {"category": "level", "value": "count"}),
     chart(3, "Quality by source", "quality_by_source", "bar", {"category": "source", "value": "score"}),
     chart(4, "Glossary coverage trend", "coverage_trend", "line", {"x": "week", "y": "pct"}),
   ]},
  {"id": "risk-hotspots", "title": "Risk hotspots", "category": "overview",
   "subtitle": "Where governance needs attention",
   "panels": [
     kpi(1, "Untrusted assets", "trust_distribution"), kpi(2, "Unowned high sensitivity", "sensitive_by_source"),
     kpi(3, "Untermed critical", "untermed_critical"), kpi(4, "Failed scans", "profile_status"),
     table(1, "Highest-risk assets", "risk_assets"),
     chart(2, "Trust by source", "trust_by_source", "stackedBar",
           {"category": "source", "value": "count", "series": "bucket"}),
     chart(3, "Sensitivity mix", "sensitivity_mix", "donut", {"category": "level", "value": "count"}),
     chart(4, "Coverage gap by source", "term_coverage", "bar", {"category": "source", "value": "pct"}),
   ]},
  {"id": "executive-scorecard", "title": "Executive scorecard", "category": "overview",
   "subtitle": "Targets & posture on one page",
   "panels": [
     kpi(1, "Catalog assets", "asset_counts"), kpi(2, "Mean quality", "quality_by_source"),
     kpi(3, "Term coverage", "term_coverage"), kpi(4, "Lineage verified", "lineage_status"),
     chart(1, "Quality vs target", "quality_by_source", "bullet",
           {"category": "source", "value": "score"}, options={"target": 80}),
     chart(2, "DQ dimensions", "dq_dimensions", "radar", {"category": "dimension", "value": "value"}),
     chart(3, "Term coverage", "term_coverage", "gauge", {"value": "pct"}),
     table(1, "Watchlist", "risk_assets", span=2),
   ]},
 ],
 "system": [
  {"id": "profiling-health", "title": "Profiling health", "category": "system",
   "subtitle": "Scan & profile status",
   "panels": [
     kpi(1, "Profiled assets", "profile_status"), kpi(2, "Failed scans", "profile_status"),
     kpi(3, "Avg scan time", "scan_activity"), kpi(4, "Workers active", "worker_status"),
     chart(1, "Profiling status", "profile_status", "donut", {"category": "status", "value": "count"}),
     chart(2, "Assets by data source", "assets_by_source", "bar", {"category": "source", "value": "count"}),
     chart(3, "Scan & profile activity", "scan_activity", "calendarHeatmap",
           {"x": "date", "value": "count"}, span=4),
     table(1, "Stale & failed assets", "stale_failed"),
   ]},
  {"id": "source-inventory", "title": "Source inventory", "category": "system",
   "subtitle": "What is connected & how much",
   "panels": [
     kpi(1, "Connected sources", "source_counts"), kpi(2, "Total assets", "asset_counts"),
     kpi(3, "Tables", "asset_counts"), kpi(4, "Files", "asset_counts"),
     chart(1, "Assets by data source", "assets_by_source", "bar", {"category": "source", "value": "count"}),
     chart(2, "Assets by type", "assets_by_type", "donut", {"category": "type", "value": "count"}),
     table(1, "Sources", "source_inventory"),
   ]},
  {"id": "scan-operations", "title": "Scan operations", "category": "system",
   "subtitle": "Throughput, freshness & the fix queue",
   "panels": [
     kpi(1, "Scans 14d", "scan_activity"), kpi(2, "Profiled assets", "profile_status"),
     kpi(3, "Workers active", "worker_status"), kpi(4, "Failed scans", "stale_failed"),
     chart(1, "Daily scan volume", "scan_activity", "line", {"x": "date", "y": "count"}),
     chart(2, "Profiled assets", "profile_status", "gauge", {"value": "count"}),
     table(1, "Fix queue", "stale_failed"),
   ]},
 ],
 "user": [
  {"id": "stewardship", "title": "Stewardship", "category": "user",
   "subtitle": "Ownership coverage & workload",
   "panels": [
     kpi(1, "Assets owned", "owners_coverage"), kpi(2, "Active stewards", "owner_workload"),
     kpi(3, "Unowned assets", "owners_coverage"), kpi(4, "Avg time to own", "ownership_time"),
     chart(1, "Owned vs unowned", "owners_coverage", "stackedBar",
           {"category": "source", "value": "count", "series": "status"}),
     chart(2, "Owner workload", "owner_workload", "bar", {"category": "owner", "value": "count"}),
     table(1, "Unowned high-value assets", "unowned_high_value"),
   ]},
  {"id": "activity-ratings", "title": "Activity & ratings", "category": "user",
   "subtitle": "Edits, ratings & freshness",
   "panels": [
     kpi(1, "Edits this week", "edit_activity"), kpi(2, "Avg rating", "ratings_distribution"),
     kpi(3, "Assets rated", "ratings_distribution"), kpi(4, "Modified 7d", "recently_modified"),
     chart(1, "Ratings distribution", "ratings_distribution", "bar", {"category": "rating", "value": "count"}),
     chart(2, "Recently modified", "recently_modified", "line", {"x": "date", "y": "count"}),
     chart(3, "Edits by action", "edit_activity", "bar", {"category": "action", "value": "count"}),
     chart(4, "Most active stewards", "owner_workload", "bar", {"category": "owner", "value": "edits"}),
   ]},
  {"id": "contribution-pulse", "title": "Contribution pulse", "category": "user",
   "subtitle": "Daily edits & ownership momentum",
   "panels": [
     kpi(1, "Edits total", "edit_activity"), kpi(2, "Avg rating", "ratings_distribution"),
     kpi(3, "Assets owned", "owners_coverage"), kpi(4, "Modified 7d", "recently_modified"),
     chart(1, "Edit activity", "recently_modified", "calendarHeatmap",
           {"x": "date", "value": "count"}, span=4),
     chart(2, "Edits by action", "edit_activity", "donut", {"category": "action", "value": "count"}),
     chart(3, "Assets owned", "owners_coverage", "gauge", {"value": "count"}),
   ]},
 ],
 "governance": [
  {"id": "glossary-coverage", "title": "Glossary coverage", "category": "governance",
   "subtitle": "Term coverage & gaps",
   "panels": [
     kpi(1, "Terms defined", "top_terms"), kpi(2, "Term coverage", "term_coverage"),
     kpi(3, "Critical untermed", "untermed_critical"), kpi(4, "Terms in review", "term_status"),
     chart(1, "Term coverage", "term_coverage", "gauge", {"value": "pct"}),
     chart(2, "Top business terms", "top_terms", "bar", {"category": "term", "value": "count"}),
     chart(3, "Coverage trend", "coverage_trend", "line", {"x": "week", "y": "pct"}),
     table(1, "Untermed critical elements", "untermed_critical", span=2),
   ]},
  {"id": "policy-lineage", "title": "Policy & lineage", "category": "governance",
   "subtitle": "Policy posture & lineage health",
   "panels": [
     kpi(1, "Lineage verified", "lineage_status"), kpi(2, "Policies applied", "policy_counts"),
     kpi(3, "Assets in policy", "policy_coverage"), kpi(4, "Unverified lineage", "lineage_status"),
     chart(1, "Lineage verified", "lineage_status", "donut", {"category": "status", "value": "count"}),
     chart(2, "Assets per policy", "policy_counts", "bar", {"category": "policy", "value": "count"}),
     chart(3, "Lineage coverage by source", "lineage_by_source", "stackedBar",
           {"category": "source", "value": "count", "series": "status"}, span=4),
   ]},
  {"id": "governance-sla", "title": "Governance SLA", "category": "governance",
   "subtitle": "Coverage targets, tracked like SLAs",
   "panels": [
     kpi(1, "Term coverage", "term_coverage"), kpi(2, "Policy coverage", "policy_coverage"),
     kpi(3, "Lineage verified", "lineage_status"), kpi(4, "Terms in review", "term_status"),
     chart(1, "Term coverage", "term_coverage", "gauge", {"value": "pct"}, options={"target": 75}),
     chart(2, "Policy coverage", "policy_coverage", "gauge", {"value": "pct"}),
     chart(3, "Lineage verified", "lineage_status", "gauge", {"value": "count"}),
     chart(4, "Term coverage vs target", "term_coverage", "bullet",
           {"category": "source", "value": "pct"}, options={"target": 75}),
   ]},
 ],
 "quality": [
  {"id": "quality-scores", "title": "Quality scores", "category": "quality",
   "subtitle": "Score distribution & laggards",
   "panels": [
     kpi(1, "Mean quality", "quality_by_source"), kpi(2, "Below target", "worst_tables"),
     kpi(3, "Completeness", "dq_dimensions"), kpi(4, "Uniqueness", "dq_dimensions"),
     chart(1, "Quality score distribution", "quality_distribution", "histogram",
           {"category": "bucket", "value": "count"}),
     chart(2, "Quality vs target", "quality_by_source", "bullet",
           {"category": "source", "value": "score"}, options={"target": 80}),
     chart(3, "Lowest-scoring tables", "worst_tables", "bar", {"category": "table", "value": "score"}),
     table(1, "Below-target tables", "worst_tables", span=2),
   ]},
  {"id": "dq-dimensions", "title": "DQ dimensions", "category": "quality",
   "subtitle": "The dimensions behind the score",
   "panels": [
     kpi(1, "Completeness", "dq_dimensions"), kpi(2, "Accuracy", "dq_dimensions"),
     kpi(3, "Validity", "dq_dimensions"), kpi(4, "Consistency", "dq_dimensions"),
     chart(1, "DQ dimensions", "dq_dimensions", "radar", {"category": "dimension", "value": "value"}),
     chart(2, "Dimension scores", "dq_dimensions", "bar", {"category": "dimension", "value": "value"}),
     chart(3, "Dimensions by source", "dq_by_source", "stackedBar",
           {"category": "source", "value": "value", "series": "dimension"}, span=4),
   ]},
  {"id": "quality-posture", "title": "Quality posture", "category": "quality",
   "subtitle": "The mean, the bands & the fix list",
   "panels": [
     kpi(1, "Mean quality", "quality_by_source"), kpi(2, "Lowest score", "worst_tables"),
     kpi(3, "Completeness", "dq_dimensions"), kpi(4, "Profiled assets", "profile_status"),
     chart(1, "Mean quality score", "quality_by_source", "gauge", {"value": "score"}),
     chart(2, "Score bands", "quality_distribution", "donut", {"category": "bucket", "value": "count"}),
     table(1, "Fix list", "worst_tables"),
   ]},
 ],
 "sensitivity": [
  {"id": "exposure-overview", "title": "Exposure overview", "category": "sensitivity",
   "subtitle": "Sensitivity levels & exposure",
   "panels": [
     kpi(1, "High sensitivity", "sensitivity_mix"), kpi(2, "Unowned sensitive", "sensitive_by_source"),
     kpi(3, "Encrypted", "encryption_status"), kpi(4, "In residency policy", "policy_coverage"),
     chart(1, "Sensitivity breakdown", "sensitivity_mix", "donut", {"category": "level", "value": "count"}),
     chart(2, "Sensitive by source", "sensitive_by_source", "stackedBar",
           {"category": "source", "value": "count", "series": "level"}),
     table(1, "High sensitivity · no owner", "sensitive_unowned"),
   ]},
  {"id": "pii-discoveries", "title": "PII discoveries", "category": "sensitivity",
   "subtitle": "Content-scan findings",
   "panels": [
     kpi(1, "PII columns", "pii_discoveries"), kpi(2, "PII types", "pii_discoveries"),
     kpi(3, "Masked", "masking_status"), kpi(4, "In high-sens assets", "pii_discoveries"),
     chart(1, "Content-scan discoveries", "pii_discoveries", "bar", {"category": "pii_type", "value": "count"}),
     chart(2, "PII by source", "pii_discoveries", "bar", {"category": "source", "value": "count"}),
     table(1, "Assets containing PII", "pii_assets"),
   ]},
  {"id": "protection-controls", "title": "Protection controls", "category": "sensitivity",
   "subtitle": "Encryption & masking posture",
   "panels": [
     kpi(1, "Encrypted", "encryption_status"), kpi(2, "Masked", "masking_status"),
     kpi(3, "High sensitivity", "sensitivity_mix"), kpi(4, "PII columns", "pii_discoveries"),
     chart(1, "Encryption coverage", "encryption_status", "gauge", {"value": "pct"}),
     chart(2, "Masking coverage", "masking_status", "gauge", {"value": "pct"}),
     table(1, "PII protection status", "pii_assets"),
   ]},
 ],
}


# ── the DQ best-practice dimension boards (Quality section) ──────────────────
# One dashboard per dimension. Each follows the same teaching shape — the
# dimension's score (gauge + per-source), the OPERATIONAL companion panel that
# actually moves the dimension, the worst-first fix queue, and a definition —
# so the Quality section reads as a data-quality practice, not just charts.
# (dimension, characteristic issue, companion panel, definition markdown)
DQ_BOARDS = [
    ("Completeness", "null rate above threshold",
     chart(3, "Profiling status", "profile_status", "donut",
           {"category": "status", "value": "count"}),
     "**Are required values present?** The share of expected values actually "
     "populated — null and empty rates measured against profiled expectations. "
     "**How to move it:** widen profile coverage; unprofiled columns hide "
     "missing values."),
    ("Accuracy", "value drift vs reference",
     chart(3, "Quality vs target", "quality_by_source", "bullet",
           {"category": "source", "value": "score"}, options={"target": 80}),
     "**Do values reflect the real world?** Drift against governed reference "
     "data and known-good distributions. **How to move it:** reference-data "
     "checks against the governed source of truth."),
    ("Validity", "format/pattern violations",
     chart(3, "At/above vs below target", "dq_by_source", "stackedBar",
           {"category": "source", "value": "value", "series": "dimension"}),
     "**Do values conform to their rules?** Format, pattern, range and "
     "vocabulary checks. **How to move it:** deploy the governed "
     "data-identification patterns — invalid rows fail the governed regex."),
    ("Uniqueness", "duplicate key values",
     chart(3, "Lowest-scoring tables", "worst_tables", "bar",
           {"category": "table", "value": "score"}),
     "**Is each real-world thing recorded once?** Duplicate detection on "
     "primary and business keys. **How to move it:** key profiling — PK and "
     "unique expectations induced from the scan."),
    ("Consistency", "cross-source value mismatch",
     chart(3, "Quality score distribution", "quality_distribution", "bar",
           {"category": "bucket", "value": "count"}),
     "**Does the same fact agree everywhere?** Cross-source comparison of the "
     "same business fact. **How to move it:** shared business terms — one "
     "governed definition applied everywhere."),
    ("Timeliness", "stale since last load",
     chart(3, "Scan & profile activity", "scan_activity", "line",
           {"x": "date", "y": "count"}),
     "**Is the data fresh enough to use?** Age since the last successful load "
     "or scan against the agreed refresh window. **How to move it:** scan "
     "scheduling — batch sources age between loads."),
    ("Traceability", "lineage unverified",
     chart(3, "Lineage status", "lineage_status", "donut",
           {"category": "status", "value": "count"}),
     "**Can you follow the data to its origin?** Verified lineage upstream and "
     "downstream of each asset. **How to move it:** lineage capture and "
     "verification per asset — the programme's current weakest dimension."),
    ("Clarity", "missing description or term",
     chart(3, "Term coverage by source", "term_coverage", "bar",
           {"category": "source", "value": "pct"}),
     "**Can a consumer understand it?** Descriptions, business terms and "
     "documentation coverage. **How to move it:** glossary coverage — "
     "undocumented assets read as unclear data."),
    ("Availability", "asset unreachable at scan",
     chart(3, "Assets by data source", "assets_by_source", "bar",
           {"category": "source", "value": "count"}),
     "**Can consumers actually reach it?** Successful-scan and connection "
     "health as a proxy for consumability. **How to move it:** connection "
     "health — failed scans mean consumers cannot rely on the asset."),
]

for _dim, _issue, _companion, _definition in DQ_BOARDS:
    _q = f"dq_{_dim.lower()}"
    DASHBOARDS["quality"].append({
        "id": _q.replace("_", "-"), "title": _dim, "category": "quality",
        "subtitle": f"DQ dimension · {_issue}",
        "panels": [
            kpi(1, f"{_dim} score", _q),
            kpi(2, "Mean quality", "quality_by_source"),
            chart(1, f"{_dim} score", _q, "gauge", {"value": "score"}),
            chart(2, f"{_dim} by source", _q, "bar",
                  {"category": "source", "value": "score"}),
            _companion,
            text(1, f"What {_dim} measures", _q, _definition),
            table(1, f"Fix queue — {_issue}", _q),
        ]})

# ── operational additions across the other sections ──────────────────────────
DASHBOARDS["overview"].append(
  {"id": "dq-program", "title": "DQ program", "category": "overview",
   "subtitle": "The nine dimensions, one page",
   "panels": [
     kpi(1, "Mean quality", "quality_by_source"), kpi(2, "Availability", "dq_availability"),
     kpi(3, "Timeliness", "dq_timeliness"), kpi(4, "Traceability", "dq_traceability"),
     chart(1, "DQ dimensions", "dq_dimensions", "radar",
           {"category": "dimension", "value": "value"}),
     chart(2, "Dimension scores", "dq_dimensions", "bar",
           {"category": "dimension", "value": "value"}),
     text(1, "Reading this page", "dq_dimensions",
          "Each Analytics · Quality dashboard drills one of these dimensions "
          "with its fix queue and the operational lever that moves it. Start "
          "with the lowest bar."),
     table(1, "Weakest dimension — Traceability fix queue", "dq_traceability", span=2),
   ]})

DASHBOARDS["system"].append(
  {"id": "source-operations", "title": "Source operations", "category": "system",
   "subtitle": "Connections, throughput & the fix queue",
   "panels": [
     kpi(1, "Data sources", "source_counts"), kpi(2, "Profiled assets", "profile_status"),
     kpi(3, "Catalog assets", "asset_counts"), kpi(4, "Availability", "dq_availability"),
     chart(1, "Profiling status", "profile_status", "donut",
           {"category": "status", "value": "count"}),
     chart(2, "Assets by data source", "assets_by_source", "bar",
           {"category": "source", "value": "count"}),
     chart(3, "Scan & profile activity", "scan_activity", "line",
           {"x": "date", "y": "count"}, span=4),
     table(1, "Stale & failed assets", "stale_failed"),
   ]})

DASHBOARDS["governance"].append(
  {"id": "trust-deep-dive", "title": "Trust deep-dive", "category": "governance",
   "subtitle": "The trust spectrum, source by source",
   "panels": [
     kpi(1, "Highly trusted", "trust_distribution"), kpi(2, "Term coverage", "term_coverage"),
     kpi(3, "Lineage verified", "lineage_status"), kpi(4, "Untermed critical", "untermed_critical"),
     chart(1, "Trust spectrum", "trust_distribution", "bar",
           {"category": "bucket", "value": "count"}, options={"scoreBands": True}),
     chart(2, "Trust by source", "trust_by_source", "stackedBar",
           {"category": "source", "value": "count", "series": "bucket"}),
     chart(3, "Coverage trend", "coverage_trend", "line", {"x": "week", "y": "pct"}),
     table(1, "Untermed critical elements", "untermed_critical", span=2),
   ]})

DASHBOARDS["governance"].append(
  {"id": "glossary-adoption", "title": "Glossary adoption", "category": "governance",
   "subtitle": "Terms in use & where they are missing",
   "panels": [
     kpi(1, "Glossary coverage", "term_coverage"), kpi(2, "Catalog assets", "asset_counts"),
     kpi(3, "Clarity", "dq_clarity"), kpi(4, "Lineage verified", "lineage_status"),
     chart(1, "Top business terms", "top_terms", "donut",
           {"category": "term", "value": "count"}),
     chart(2, "Coverage by source", "term_coverage", "bar",
           {"category": "source", "value": "pct"}),
     chart(3, "Coverage trend", "coverage_trend", "line", {"x": "week", "y": "pct"}),
     table(1, "Untermed critical elements", "untermed_critical", span=2),
   ]})

DASHBOARDS["sensitivity"].append(
  {"id": "pii-deep-dive", "title": "PII deep-dive", "category": "sensitivity",
   "subtitle": "Types, spread & the unprotected list",
   "panels": [
     kpi(1, "High sensitivity", "sensitivity_mix"), kpi(2, "PII columns", "pii_discoveries"),
     kpi(3, "Encrypted", "encryption_status"), kpi(4, "Masked", "masking_status"),
     chart(1, "PII types discovered", "pii_discoveries", "donut",
           {"category": "pii_type", "value": "count"}),
     chart(2, "High sensitivity by source", "sensitive_by_source", "stackedBar",
           {"category": "source", "value": "count", "series": "level"}),
     chart(3, "Sensitivity mix", "sensitivity_mix", "donut",
           {"category": "level", "value": "count"}),
     table(1, "Assets containing PII", "pii_assets", span=2),
   ]})

DASHBOARDS["user"].append(
  {"id": "ownership-program", "title": "Ownership program", "category": "user",
   "subtitle": "Who owns what — and what nobody owns",
   "panels": [
     kpi(1, "Assets owned", "owners_coverage"), kpi(2, "Data sources", "source_counts"),
     kpi(3, "High sensitivity", "sensitivity_mix"), kpi(4, "Catalog assets", "asset_counts"),
     chart(1, "Owned vs unowned by source", "owners_coverage", "stackedBar",
           {"category": "source", "value": "count", "series": "status"}),
     chart(2, "Owner workload", "owner_workload", "bar",
           {"category": "owner", "value": "count"}),
     chart(3, "Edits by action", "edit_activity", "donut",
           {"category": "action", "value": "count"}),
     table(1, "Unowned high-value assets", "unowned_high_value", span=2),
   ]})


def main():
    validator = jsonschema.Draft7Validator(SCHEMA)
    written = 0
    index = {}
    for section, dashboards in DASHBOARDS.items():
        d = OUT / section
        d.mkdir(parents=True, exist_ok=True)
        index[section] = []
        for spec in dashboards:
            out = {"version": 1, "title": spec["title"], "category": spec["category"],
                   "subtitle": spec.get("subtitle", ""), "panels": spec["panels"]}
            errs = sorted(validator.iter_errors(out), key=lambda e: e.path)
            if errs:
                raise SystemExit(f"INVALID {spec['id']}: {errs[0].message}")
            (d / f"{spec['id']}.studio.json").write_text(json.dumps(out, indent=2))
            index[section].append({"id": spec["id"], "title": spec["title"],
                                    "subtitle": spec.get("subtitle", "")})
            written += 1
    (OUT / "index.json").write_text(json.dumps(index, indent=2))
    print(f"✓ wrote {written} schema-valid dashboards + index.json")


if __name__ == "__main__":
    main()
