"""Standard + saved dashboards. List/read need 'viewer'; save needs 'steward'."""
import json
import re
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response

from ..generator import _validate
from ..catalog import QUERY_CATALOG
from ..security import Principal, audit
from ._auth import json_body, require

router = APIRouter(prefix="/api/dashboards", tags=["dashboards"])
DASH_DIR = Path(__file__).resolve().parent.parent / "dashboards"


@router.get("")
def index(principal: Principal = Depends(require("viewer"))):
    idx = DASH_DIR / "index.json"
    return json.loads(idx.read_text()) if idx.exists() else {}


# NB: the fixed-path routes (/resolve, /sources, /drill) are declared before
# the /{section}/{dash_id} wildcards so they always match first.

@router.post("/resolve")
async def resolve_inline(request: Request,
                         principal: Principal = Depends(require("viewer"))):
    """Resolve an in-memory spec (e.g. the chat preview) to live values.

    Honour an optional top-level "source" to scope to one data source, and an
    optional top-level "demo": true to resolve this one request against the
    bundled sample snapshot regardless of the app-wide live/demo setting
    (read-only; the setting itself is never touched). Payloads without the
    field behave exactly as before.
    """
    spec = await json_body(request)
    from ..catalog import catalog_snapshot
    from ..panel_data import resolve_dashboard
    snap = catalog_snapshot(force_demo=True) if spec.get("demo") else None
    return resolve_dashboard(spec, snap=snap, source=spec.get("source"))


@router.get("/sources")
def list_sources(principal: Principal = Depends(require("viewer"))):
    """Connected data-source names, for the per-dashboard scope selector."""
    from ..panel_data import source_names
    return {"sources": source_names()}


@router.post("/drill")
async def drill(request: Request, principal: Principal = Depends(require("viewer"))):
    """Return the underlying assets behind a panel (or a clicked segment/row).

    Body: {query, label?, source?, demo?}. Read-only; demo synthesises from the
    snapshot, live would issue a facet-filtered /search. "demo": true forces
    the bundled sample snapshot for this request only (per-view override; the
    app-wide setting is never touched).
    """
    body = await json_body(request)
    if not body.get("query"):
        return JSONResponse({"error": "query required"}, status_code=400)
    from ..catalog import catalog_snapshot
    from ..panel_data import drill_assets
    snap = catalog_snapshot(force_demo=True) if body.get("demo") else None
    return drill_assets(snap, body["query"], body.get("label"), body.get("source"))


@router.get("/{section}/{dash_id}")
def get_one(section: str, dash_id: str,
            principal: Principal = Depends(require("viewer"))):
    safe = re.sub(r"[^a-z0-9-]", "", dash_id.lower())
    path = DASH_DIR / section / f"{safe}.studio.json"
    if not path.exists():
        return JSONResponse({"error": "not found"}, status_code=404)
    return json.loads(path.read_text())


@router.get("/{section}/{dash_id}/download")
def download_one(section: str, dash_id: str,
                 principal: Principal = Depends(require("viewer"))):
    """Stream a dashboard spec as a .studio.json file download (Content-
    Disposition: attachment), so the app's Download button saves the exact,
    portable spec — the same artifact the Designer and MCP server consume."""
    safe = re.sub(r"[^a-z0-9-]", "", dash_id.lower())
    path = DASH_DIR / section / f"{safe}.studio.json"
    if not path.exists():
        return JSONResponse({"error": "not found"}, status_code=404)
    return Response(path.read_text(), media_type="application/json",
                    headers={"Content-Disposition":
                             f'attachment; filename="{safe}.studio.json"'})


@router.get("/{section}/{dash_id}/data")
def get_data(section: str, dash_id: str, request: Request,
             principal: Principal = Depends(require("viewer"))):
    """Resolve a dashboard's panels to actual values from the catalog snapshot.

    Returns {demo, scope, panels:{panel_id: {...}}}. Optional ?source= narrows
    the board to a single connected data source. Read-only.
    """
    safe = re.sub(r"[^a-z0-9-]", "", dash_id.lower())
    path = DASH_DIR / section / f"{safe}.studio.json"
    if not path.exists():
        return JSONResponse({"error": "not found"}, status_code=404)
    from ..panel_data import resolve_dashboard
    spec = json.loads(path.read_text())
    return resolve_dashboard(spec, source=request.query_params.get("source"))


@router.post("")
async def save(request: Request, principal: Principal = Depends(require("steward"))):
    spec = await json_body(request)
    errors = _validate(spec, QUERY_CATALOG)
    if errors:
        audit(principal, "save_dashboard", status="rejected")
        return JSONResponse({"saved": False, "errors": errors}, status_code=400)
    category = spec.get("category", "overview")
    slug = re.sub(r"[^a-z0-9]+", "-", spec.get("title", "untitled").lower()).strip("-")
    dest = DASH_DIR / category
    dest.mkdir(parents=True, exist_ok=True)
    (dest / f"{slug}.studio.json").write_text(json.dumps(spec, indent=2))
    audit(principal, "save_dashboard", target=f"{category}/{slug}")
    return {"saved": True, "path": f"{category}/{slug}.studio.json"}
