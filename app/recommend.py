"""Turn a catalog snapshot into ranked dashboard suggestions.

This is the engine behind "based on what's connected and scanned, what should I
build?" It is a deterministic, rules-based function over a snapshot dict — no LLM
required — which gives three benefits:

  * It runs identically on live or demo data (it only reads the snapshot).
  * It's trivially testable (pure input -> output).
  * It gives the host LLM a solid baseline plus ready-made prompts to build on,
    rather than asking the model to both analyse and design from scratch.

Each suggestion ties a detected SIGNAL (e.g. "S3 is 52% unowned with 310 high-
sensitivity assets") to a built-in standard template and a ready-to-run
generate_prompt for a scoped variant. The host can offer the standard dashboard,
or feed the prompt to generate_dashboard for a tailored one.
"""
from __future__ import annotations

# Thresholds that define "a signal worth surfacing as a dashboard." These are
# first-pass defaults — once pointed at real catalog data they should be tuned to
# the organisation's norms (what counts as "low coverage" varies by maturity).
T = {
    "profiled_low": 90,    # % profiled below this is worth a profiling dashboard
    "failed_scans": 2,     # this many failed scans on a source is notable
    "unowned_high": 40,    # % unowned at/above this is a stewardship gap
    "coverage_low": 50,    # % term coverage below this is a glossary gap
    "quality_low": 75,     # mean quality below this misses the usual 80 target
    "high_sens": 100,      # this many high-sensitivity assets warrants attention
}


def _sev(score: float) -> str:
    """Map a 0–1 ranking score to a coarse priority label for display."""
    return "high" if score >= 0.66 else "medium" if score >= 0.33 else "low"


def recommend(snapshot: dict, scope: str | None = None,
              category: str | None = None) -> list[dict]:
    """Return ranked dashboard suggestions for a snapshot.

    Args:
        snapshot: the catalog state (totals + per-source signals) from
                  app.catalog.catalog_snapshot().
        scope:    optional data-source name. When given, only that source's
                  signals are considered (global signals are skipped), so the
                  caller gets focused, source-specific suggestions.
        category: optional Analytics section (overview|system|user|governance|
                  quality|sensitivity). When given, only suggestions for that
                  section are returned — this is what makes the in-app chat
                  surface section-aware starters.

    Returns a list of suggestion dicts sorted high-priority first, each carrying
    the triggering signal ("why"), a matching standard template, and a prompt.
    """
    sugg: list[dict] = []
    sources = snapshot.get("sources", [])
    if scope:
        # Focused mode: ignore catalog-wide signals, look only at this source.
        sources = [s for s in sources if s["name"] == scope]

    # ── global signals (skipped when a single source is in scope) ──
    if not scope:
        # Profiling health: any failed/skipped assets are operationally relevant.
        prof = snapshot.get("profiling", {})
        failed = prof.get("Failed", 0) + prof.get("Skipped", 0)
        if failed:
            sugg.append(_s("Profiling health", "system", "profiling-health",
                f"{failed} assets failed or were skipped in the last scan",
                "Profiling status, scan freshness, and a list of failed/stale assets across all sources",
                # Scale score with the failure count, but cap so one big number
                # can't dominate the whole ranking.
                score=min(1.0, failed / 800 + 0.4)))

        # Trust: a high share of Untrusted assets is a governance red flag.
        trust = snapshot.get("trust", {})
        untrusted = trust.get("Untrusted", 0)
        total_scored = sum(trust.values()) or 1  # avoid divide-by-zero
        if untrusted / total_scored > 0.2:
            sugg.append(_s("Risk hotspots", "overview", "risk-hotspots",
                f"{round(100*untrusted/total_scored)}% of scored assets are Untrusted",
                "Untrusted assets, unowned high-sensitivity data, and untermed critical elements, with the riskiest assets called out",
                score=0.85))

        # Sensitivity: lots of high-sensitivity assets -> a PII-focused view.
        sens = snapshot.get("sensitivity", {})
        if sens.get("High", 0) > T["high_sens"]:
            sugg.append(_s("PII discoveries", "sensitivity", "pii-discoveries",
                f"{sens['High']} high-sensitivity assets and PII detected by content scans",
                "Every PII type discovered, PII by source, and which sensitive assets are unmasked",
                score=0.8))

        # Glossary: low overall term coverage -> a coverage dashboard. The +15
        # nudges the threshold so we surface it slightly before it's truly dire.
        cov = snapshot.get("totals", {}).get("term_coverage_pct", 100)
        if cov < T["coverage_low"] + 15:
            sugg.append(_s("Glossary coverage", "governance", "glossary-coverage",
                f"term coverage is {cov}% — below where governance wants it",
                "Term coverage by source, top business terms, coverage trend, and untermed critical elements",
                score=0.7))

        # Scale: many connected sources -> an inventory view is simply useful.
        if len(sources) >= 5:
            sugg.append(_s("Source inventory", "system", "source-inventory",
                f"{len(sources)} sources connected — useful to see scale and freshness at a glance",
                "Assets per source, asset type mix, and a source table with last-scan times",
                score=0.5))

        # Evergreen, section-anchored starters. These always apply (low score, so
        # signal-driven ones above outrank them) and guarantee every Analytics
        # section has at least one real suggestion to offer in the chat.
        for title, cat, tmpl, why, prompt, sc in [
            ("Catalog health", "overview", "catalog-health",
             "a single overview of assets, profiling, trust, and coverage",
             "An overview of total assets, profiled %, trust distribution, and term coverage", 0.45),
            ("Stewardship coverage", "user", "stewardship",
             "who owns what, and where ownership is missing",
             "Ownership coverage by source, owner workload, and unowned high-value assets", 0.5),
            ("Activity & ratings", "user", "activity-ratings",
             "recent curation activity and how assets are rated",
             "Recent edit activity, time-to-ownership, and the ratings distribution", 0.42),
            ("Quality scores", "quality", "quality-scores",
             "where quality stands and which tables lag",
             "Quality score distribution and the lowest-scoring tables across sources", 0.5),
            ("DQ dimensions", "quality", "dq-dimensions",
             "quality broken down by dimension",
             "Data-quality dimensions (completeness, validity, …) overall and by source", 0.42),
            ("Policy & lineage", "governance", "policy-lineage",
             "policy counts and lineage completeness",
             "Policy counts, policy coverage, and lineage status by source", 0.45),
            # Connection-grounded starters — each maps to a real PDC search facet,
            # so they get more useful as more sources are connected and scanned.
            ("Scan freshness", "system", "scan-freshness",
             "which assets are going stale since their last profile/scan",
             "Assets by last-profiled age, stale assets per source, and scan recency over time", 0.44),
            ("Key coverage", "quality", "key-coverage",
             "primary/foreign key coverage across scanned tables",
             "Share of tables with primary keys, foreign-key relationships, and tables missing keys by source", 0.4),
            ("File format mix", "system", "file-format-mix",
             "the mix of file formats discovered across object stores",
             "Asset counts by file format (CSV, JSON, Parquet, …) overall and per source", 0.38),
            ("Tag coverage", "governance", "tag-coverage",
             "how consistently assets are tagged",
             "Tag usage, most-used tags, and untagged high-value assets by source", 0.38),
            ("Domain coverage", "overview", "domain-coverage",
             "how assets distribute across business domains",
             "Asset counts by domain, domains per source, and assets with no domain assigned", 0.36),
        ]:
            sugg.append(_s(title, cat, tmpl, why, prompt, score=sc))

        # Cross-source comparison only makes sense with more than one connection.
        if len(sources) >= 2:
            sugg.append(_s("Compare sources", "overview", "source-comparison",
                f"{len(sources)} sources connected — compare them side by side",
                "Trust, quality, term coverage, and sensitivity compared across every connected data source",
                score=0.58))

    # ── per-source signals ──
    for s in sources:
        name = s["name"]
        # Profiling problems on this specific source.
        if s.get("failed_scans", 0) >= T["failed_scans"] or s.get("profiled_pct", 100) < T["profiled_low"]:
            sugg.append(_s(f"Profiling health · {name}", "system", "profiling-health",
                f"{name} is {s.get('profiled_pct','?')}% profiled with {s.get('failed_scans',0)} failed scans",
                f"Profiling status and failed/stale assets for the {name} data source only",
                score=0.75, scope=name))
        # Exposure: sensitive AND poorly owned is the highest-value combination.
        if s.get("high_sensitivity", 0) > 50 and s.get("unowned_pct", 0) >= T["unowned_high"]:
            sugg.append(_s(f"Exposure · {name}", "sensitivity", "exposure-overview",
                f"{name} holds {s['high_sensitivity']} high-sensitivity assets and is {s['unowned_pct']}% unowned",
                f"Sensitivity breakdown and unowned high-sensitivity assets scoped to {name}",
                score=0.82, scope=name))
        # Glossary gaps on this source.
        if s.get("term_coverage_pct", 100) < T["coverage_low"]:
            sugg.append(_s(f"Glossary gaps · {name}", "governance", "glossary-coverage",
                f"{name} term coverage is only {s['term_coverage_pct']}%",
                f"Untermed assets and coverage gaps for the {name} source, prioritised by sensitivity",
                score=0.6, scope=name))
        # Quality laggards on this source.
        if s.get("mean_quality", 100) < T["quality_low"]:
            sugg.append(_s(f"Quality · {name}", "quality", "quality-scores",
                f"{name} mean quality is {s['mean_quality']}, under the 80 target",
                f"Quality score distribution and lowest-scoring tables for {name}",
                score=0.65, scope=name))

    # Section-aware: keep only suggestions for the requested Analytics section.
    if category:
        sugg = [x for x in sugg if x["category"] == category]

    # Rank by score, then convert the numeric score into a display priority so
    # callers don't depend on the raw weighting.
    sugg.sort(key=lambda x: x["score"], reverse=True)
    for x in sugg:
        x["priority"] = _sev(x.pop("score"))
    return sugg


def _s(title, category, template, why, prompt, score, scope=None):
    """Build one suggestion record (kept terse so the rules above stay readable).

    Fields:
        title              human label for the suggestion
        category/template  which Analytics section + which built-in to start from
        why                the signal that triggered it (shown to the user)
        generate_prompt    a ready-to-run prompt for a scoped, generated variant
        scope              the source this is scoped to, if any
        score              0–1 ranking weight (replaced by `priority` before return)
    """
    return {"title": title, "category": category, "standard_template": template,
            "why": why, "generate_prompt": prompt, "scope": scope,
            "score": round(score, 2)}
