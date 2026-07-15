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
 ],
}


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
