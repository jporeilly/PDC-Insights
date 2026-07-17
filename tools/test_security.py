"""Security model tests — run: python tools/test_security.py

Covers the shared core (auth, roles, audit), the web API (401/403/200 by
role), and the MCP tools (gated allow/deny). Uses apikey mode + demo data so
it runs with no live PDC.
"""
import io
import json
import logging
import os
import sys

# apikey auth + demo catalog, before importing the app
os.environ.update({
    "INSIGHTS_AUTH": "apikey",
    "INSIGHTS_API_KEYS": "viewkey:carol:viewer,stewkey:bob:steward,adminkey:alice:admin",
    "INSIGHTS_DEMO": "true",
})

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402
from app.security import authenticate, authorize, AuthError, ForbiddenError, Principal  # noqa: E402

PASS, FAIL = "✓", "✗"
fails = 0


def _raises(fn, exc):
    try:
        fn()
        return False
    except exc:
        return True
    except Exception:
        return False


def check(label, cond):
    global fails
    print(f"  {PASS if cond else FAIL} {label}")
    if not cond:
        fails += 1


def H(key):
    return {"Authorization": f"Bearer {key}"}


print("\n[1] core auth + roles")
check("valid key resolves principal", authenticate("Bearer stewkey").role == "steward")
check("unknown key raises AuthError", _raises(lambda: authenticate("Bearer nope"), AuthError))
check("missing header raises AuthError", _raises(lambda: authenticate(None), AuthError))
check("steward >= viewer", Principal("x", "x", "steward").at_least("viewer"))
check("viewer < steward", not Principal("x", "x", "viewer").at_least("steward"))
check("authorize denies under-privileged",
      _raises(lambda: authorize(Principal("x", "x", "viewer"), "steward"), ForbiddenError))

print("\n[2] web API by role")
from fastapi.testclient import TestClient  # noqa: E402
app = create_app()
c = TestClient(app)
check("health is public (200, no auth)", c.get("/health").status_code == 200)
check("snapshot without auth → 401", c.get("/api/snapshot").status_code == 401)
check("snapshot as viewer → 200", c.get("/api/snapshot", headers=H("viewkey")).status_code == 200)
check("recommend as viewer → 200", c.get("/api/recommend", headers=H("viewkey")).status_code == 200)
check("dashboards list as viewer → 200", c.get("/api/dashboards", headers=H("viewkey")).status_code == 200)
check("save as viewer → 403 (needs steward)",
      c.post("/api/dashboards", headers=H("viewkey"), json={"title": "x"}).status_code == 403)
check("generate as viewer → 403",
      c.post("/api/generate", headers=H("viewkey"), json={"prompt": "x"}).status_code == 403)
# steward can save a valid spec
valid = json.load(open("app/dashboards/governance/glossary-coverage.studio.json"))
r = c.post("/api/dashboards", headers=H("stewkey"), json=valid)
check("save valid spec as steward → 200", r.status_code == 200 and r.json().get("saved"))
check("save invalid spec as steward → 400",
      c.post("/api/dashboards", headers=H("stewkey"), json={"title": "bad", "category": "overview", "version": 1, "panels": [{"id": "p", "kind": "chart", "title": "t", "query": "nope", "chartType": "bar", "bindings": {}}]}).status_code == 400)

print("\n[3] MCP tools gated")
from mcp_server import server as srv  # noqa: E402


def as_role(role):
    # simulate the in-tool principal resolution
    srv.gated  # ensure imported
    import mcp_server.security_mcp as sm
    sm.current_principal = lambda: Principal("t", "t", role)


import mcp_server.security_mcp as sm  # noqa: E402
as_role("viewer")
out = srv.save_dashboard(json.dumps(valid))
check("viewer save_dashboard → forbidden", json.loads(out).get("error") == "forbidden")
out = srv.recommend_dashboards("")
check("viewer recommend_dashboards → allowed", isinstance(json.loads(out), list))
as_role("steward")
out = srv.save_dashboard(json.dumps(valid))
check("steward save_dashboard → saved", json.loads(out).get("saved") is True)

print("\n[4] audit log emits records")
buf = io.StringIO()
h = logging.StreamHandler(buf)
h.setFormatter(logging.Formatter("%(message)s"))
alog = logging.getLogger("insights.audit")
alog.addHandler(h)
alog.setLevel(logging.INFO)
c.get("/api/snapshot", headers=H("viewkey"))
c.post("/api/dashboards", headers=H("viewkey"), json={"title": "x"})  # denied
lines = [l for l in buf.getvalue().splitlines() if l.strip()]
recs = [json.loads(l) for l in lines]
check("audit recorded an ok action", any(r["status"] == "ok" for r in recs))
check("audit recorded a denial", any(r["status"] == "denied" for r in recs))
check("audit captures principal + role", all("principal" in r and "role" in r for r in recs))

print(f"\n{'ALL PASS' if not fails else str(fails)+' FAILED'}")
sys.exit(1 if fails else 0)
