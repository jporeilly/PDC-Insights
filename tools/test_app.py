"""Functional tests — run: python tools/test_app.py

Exercises the catalog/recommend engine, the conversational builder, and the web
routes that back the in-app chat. Runs entirely on the bundled demo snapshot
with the LLM disabled, so it needs no live PDC and no model — the deterministic
builder path is what's under test here. Security (auth/roles/audit) has its own
suite in tools/test_security.py.
"""
import os
import sys

# Demo data + open auth + no model: forces the offline/deterministic paths.
os.environ.update({"INSIGHTS_DEMO": "true", "INSIGHTS_AUTH": "none",
                   "LLM_PROVIDER": "disabled"})
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json  # noqa: E402

from app import create_app  # noqa: E402
from app.catalog import QUERY_CATALOG, catalog_snapshot  # noqa: E402
from app.chat_build import conversation_prompt, demo_build  # noqa: E402
from app.generator import _validate  # noqa: E402
from app.recommend import recommend  # noqa: E402

SECTIONS = ["overview", "system", "user", "governance", "quality", "sensitivity"]
PASS, FAIL = "✓", "✗"
fails = 0

# Ensure the canonical dashboards exist so the download test doesn't depend on
# whatever state a previous run left the dashboards directory in.
try:
    import subprocess
    subprocess.run([sys.executable, "tools/build_dashboards.py"],
                   cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   capture_output=True, timeout=60)
except Exception:
    pass


def check(label, cond):
    global fails
    print(f"  {PASS if cond else FAIL} {label}")
    if not cond:
        fails += 1


print("\n[1] recommend — section awareness")
snap = catalog_snapshot()
for sec in SECTIONS:
    recs = recommend(snap, category=sec)
    # every section must offer at least one suggestion …
    check(f"{sec}: has suggestions ({len(recs)})", len(recs) >= 1)
    # … and every suggestion must belong to that section
    check(f"{sec}: all suggestions match section",
          all(r["category"] == sec for r in recs))
# unfiltered returns more than any single section; scope narrows to one source
check("unfiltered returns the full set", len(recommend(snap)) > len(recommend(snap, category="user")))
scoped = recommend(snap, scope="S3-raw")
check("scope=S3-raw yields only S3-raw suggestions",
      scoped and all("S3-raw" in (r.get("scope") or "") or "S3" in r["title"] for r in scoped))
# suggestions carry the fields the chat relies on
first = recommend(snap, category="sensitivity")[0]
titles = {x["title"] for x in recommend(snap)}
check("connection-based suggestions present (compare/freshness/keys/formats/tags/domain)",
      {"Compare sources","Scan freshness","Key coverage","File format mix","Tag coverage","Domain coverage"} <= titles)
check("suggestion has why + generate_prompt + template + priority",
      all(k in first for k in ("why", "generate_prompt", "standard_template", "priority")))

print("\n[2] chat_build — deterministic builder")
for sec in SECTIONS:
    r = demo_build("something useful", section=sec)
    check(f"{sec}: builds a valid spec pinned to the section",
          r["valid"] and r["spec"]["category"] == sec and not _validate(r["spec"], QUERY_CATALOG))
# keyword routing when no section is pinned
check("keywords route 'PII exposure' → sensitivity",
      demo_build("show me PII exposure")["spec"]["category"] == "sensitivity")
check("keywords route 'quality scores' → quality",
      demo_build("quality scores and worst tables")["spec"]["category"] == "quality")
# prompt assembly carries the section and the current spec
p = conversation_prompt([{"role": "user", "content": "add a trend"}],
                        spec={"title": "x"}, section="governance")
check("conversation_prompt pins section + includes current spec",
      "governance" in p and "current dashboard spec" in p)

print("\n[3] web routes")
from fastapi.testclient import TestClient  # noqa: E402
app = create_app()
c = TestClient(app)
check("GET /chat serves the builder", c.get("/chat").status_code == 200)
check("GET /api/recommend?section=quality is quality-only",
      all(r["category"] == "quality"
          for r in c.get("/api/recommend?section=quality").json()))

# build via the chat endpoint, pinned to a section
r = c.post("/api/chat", json={"messages": [{"role": "user", "content": "anything"}],
                              "section": "user"})
body = r.json()
check("POST /api/chat builds (200, valid)", r.status_code == 200 and body["valid"])
check("chat respects the pinned section", body["spec"]["category"] == "user")
check("chat reports the offline engine", body.get("engine") == "demo")
check("chat returns an assistant reply", bool(body.get("reply")))
check("POST /api/chat with no messages → 400",
      c.post("/api/chat", json={"messages": []}).status_code == 400)

# refine: send the spec back with a follow-up, expect a still-valid spec
r2 = c.post("/api/chat", json={"messages": [
    {"role": "user", "content": "build a user dashboard"},
    {"role": "user", "content": "add owner workload"}], "spec": body["spec"]})
check("refine turn returns a valid spec", r2.json()["valid"])

# the built spec saves through the normal (validated) dashboards route
save = c.post("/api/dashboards", json=body["spec"])
check("built spec saves via /api/dashboards", save.status_code == 200 and save.json().get("saved"))

# download a standard spec as an attachment (the app's Download button)
dl = c.get("/api/dashboards/sensitivity/pii-discoveries/download")
check("GET …/download returns the spec", dl.status_code == 200 and dl.json().get("title"))
check("download sets attachment filename",
      "attachment" in dl.headers.get("Content-Disposition", "") and
      "pii-discoveries.studio.json" in dl.headers.get("Content-Disposition", ""))
check("download of a missing spec → 404",
      c.get("/api/dashboards/sensitivity/nope/download").status_code == 404)

print("\n[3b] LLM management routes")
sug = c.get("/api/llm/suggest").json()
check("GET /api/llm/suggest recommends a model",
      sug.get("model", "").startswith("qwen") and sug.get("mode") in ("gpu", "cpu"))
check("GET /api/llm/models returns a list",
      isinstance(c.get("/api/llm/models").json().get("models"), list))
check("POST /api/llm/pull with no model → 400",
      c.post("/api/llm/pull", json={}).status_code == 400)
# stream (don't buffer) so the test never waits on a real model download
with c.stream("POST", "/api/llm/pull", json={"model": "qwen2.5:0.5b-instruct"}) as pull:
    check("POST /api/llm/pull streams ndjson",
          pull.status_code == 200 and
          pull.headers.get("content-type", "").startswith("application/x-ndjson"))

print("\n[3c] footer status endpoints")
hp = c.get("/health/pdc").json()
check("GET /health/pdc reports demo/live + base_url",
      "ok" in hp and "demo" in hp and "base_url" in hp)
check("demo snapshot → PDC not 'ok' (amber dot)", hp["demo"] is True and hp["ok"] is False)
hl = c.get("/health/llm").json()
check("GET /health/llm reports provider + ok", "ok" in hl and "provider" in hl)

print("\n[3d] settings save + run against real data")
from app.config import apply_settings, public_settings, settings as _settings  # noqa: E402
ps = c.get("/api/settings").json()
check("GET /api/settings exposes pdc/llm/demo", all(k in ps for k in ("pdc", "llm", "demo")))
check("GET /api/settings never returns the password",
      "password" not in ps["pdc"] and "has_password" in ps["pdc"])
check("POST /api/settings with nothing recognised → 400",
      c.post("/api/settings", json={"unknown": 1}).status_code == 400)
# apply live without persisting to .env (persist=False keeps the test hermetic)
apply_settings({"demo": False, "pdc": {"base_url": "https://pentaho.io"}}, persist=False)
check("apply_settings flips to live + updates config in place",
      _settings.pdc.base_url == "https://pentaho.io"
      and public_settings()["demo"] is False)
apply_settings({"demo": True}, persist=False)  # restore demo for the rest of the run

# real PDC connection test surfaces a specific reason (no live PDC needed here)
tp = c.post("/api/settings/test-pdc",
            json={"base_url": "http://127.0.0.1:1", "version": "v2",
                  "username": "u", "password": "p"}).json()
check("test-pdc reports unreachable host clearly", tp["ok"] is False and "reach" in tp["error"].lower())
tp2 = c.post("/api/settings/test-pdc", json={"base_url": "", "username": "u", "password": "p"}).json()
check("test-pdc requires a base URL", tp2["ok"] is False)

print("\n[3e] live panel data (wiring dashboards to real values)")
from app.panel_data import resolve_panel, resolve_dashboard  # noqa: E402
_snap = __import__("app.catalog", fromlist=["catalog_snapshot"]).catalog_snapshot()
_td = resolve_panel({"kind": "chart", "chartType": "bar", "query": "trust_distribution"}, _snap)
check("resolver returns a real series", len(_td.get("series", [])) == 3 and _td["series"][0]["value"] > 0)
_kpi = resolve_panel({"kind": "kpi", "query": "sensitivity_mix"}, _snap)
check("resolver returns a kpi value", isinstance(_kpi.get("value"), (int, float)) and _kpi["value"] > 0)
_stk = resolve_panel({"kind": "chart", "chartType": "stackedBar", "query": "sensitive_by_source"}, _snap)
check("resolver returns stacked groups", "groups" in _stk and len(_stk["groups"]) >= 2)
_dd = c.get("/api/dashboards/sensitivity/pii-discoveries/data").json()
check("/data resolves every panel", "panels" in _dd and len(_dd["panels"]) >= 1
      and all("error" not in v for v in _dd["panels"].values()))
_ri = c.post("/api/dashboards/resolve",
             json={"version": 1, "title": "t", "category": "overview",
                   "panels": [{"id": "k0", "kind": "kpi", "query": "asset_counts"}]}).json()
check("/resolve resolves an inline spec", _ri["panels"]["k0"]["value"] > 0)
check("/data of a missing dashboard -> 404",
      c.get("/api/dashboards/overview/nope/data").status_code == 404)

print("\n[3f] wired chart shapes (standard dashboards -> live)")
_q = lambda kind, ct, query: resolve_panel({"kind": kind, "chartType": ct, "query": query}, _snap)
check("spectrum/bar series for trust_distribution", len(_q("chart","bar","trust_distribution")["series"]) == 3)
check("donut series for sensitivity_mix", len(_q("chart","donut","sensitivity_mix")["series"]) == 3)
check("stacked groups for owners_coverage", len(_q("chart","stackedBar","owners_coverage").get("groups", [])) == 2)
check("gauge value for term_coverage", isinstance(_q("kpi","","term_coverage")["value"], (int, float)))
check("histogram series for quality_distribution", len(_q("chart","bar","quality_distribution")["series"]) >= 1)
check("table rows for source_inventory", len(resolve_panel({"kind":"table","query":"source_inventory"}, _snap)["rows"]) >= 1)

print("\n[3g] per-dashboard source scope")
from app.panel_data import resolve_dashboard, source_names  # noqa: E402
names = source_names(_snap)
check("source_names lists connected sources", len(names) >= 2)
_all = resolve_dashboard({"version":1,"title":"t","category":"overview","panels":[{"id":"k","kind":"kpi","query":"asset_counts"}]}, _snap)["panels"]["k"]["value"]
_one = resolve_dashboard({"version":1,"title":"t","category":"overview","panels":[{"id":"k","kind":"kpi","query":"asset_counts"}]}, _snap, source=names[0])["panels"]["k"]["value"]
check("scoping to one source reduces the total", _one < _all and _one > 0)
check("scope echoed in response", resolve_dashboard({"version":1,"title":"t","category":"o","panels":[]}, _snap, source=names[0])["scope"] == names[0])
_se = c.get("/api/dashboards/sources").json()
check("/sources endpoint returns names", len(_se.get("sources", [])) >= 2)

print("\n[3h] drill-through assets")
_dr = c.post("/api/dashboards/drill", json={"query": "sensitivity_mix", "label": "High"}).json()
check("drill returns asset rows + columns", len(_dr.get("rows", [])) >= 1 and _dr["columns"][0] == "asset")
check("drill honours label in detail", _dr["rows"][0][2] == "High")
check("drill missing query -> 400", c.post("/api/dashboards/drill", json={}).status_code == 400)
_drs = c.post("/api/dashboards/drill", json={"query": "quality_by_source", "source": names[0]}).json()
check("drill scoped to one source returns fewer rows", 0 < len(_drs["rows"]) <= len(_dr["rows"]))

print("\n[4] generator validation still guards")
bad = {"version": 1, "title": "bad", "category": "overview",
       "panels": [{"id": "p", "kind": "chart", "title": "t",
                   "query": "not_a_real_query", "chartType": "bar", "bindings": {}}]}
check("invalid spec is rejected by _validate", len(_validate(bad, QUERY_CATALOG)) > 0)

print(f"\n{'ALL PASS' if not fails else str(fails)+' FAILED'}")
# tidy any dashboard the save test wrote
try:
    import glob
    import re
    from pathlib import Path
    keep = {"catalog-health", "risk-hotspots", "profiling-health", "source-inventory",
            "stewardship", "activity-ratings", "glossary-coverage", "policy-lineage",
            "quality-scores", "dq-dimensions", "exposure-overview", "pii-discoveries"}
    for f in glob.glob("app/dashboards/**/*.studio.json", recursive=True):
        # NB: strip the full ".studio.json" — Path().stem only drops ".json",
        # which would leave "name.studio" and match nothing (deleting everything).
        if Path(f).name[:-len(".studio.json")] not in keep:
            os.remove(f)
except Exception:
    pass

sys.exit(1 if fails else 0)
