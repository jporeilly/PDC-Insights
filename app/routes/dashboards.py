"""Standard + saved dashboards. List/read need 'viewer'; save needs 'steward'."""
import json
import re
from pathlib import Path

from flask import Blueprint, Response, g, jsonify, request

from ..generator import _validate
from ..catalog import QUERY_CATALOG
from ..security import audit
from ._auth import require

bp = Blueprint("dashboards", __name__, url_prefix="/api/dashboards")
DASH_DIR = Path(__file__).resolve().parent.parent / "dashboards"


@bp.get("")
@require("viewer")
def index():
    idx = DASH_DIR / "index.json"
    return jsonify(json.loads(idx.read_text()) if idx.exists() else {})


@bp.get("/<section>/<dash_id>")
@require("viewer")
def get_one(section, dash_id):
    safe = re.sub(r"[^a-z0-9-]", "", dash_id.lower())
    path = DASH_DIR / section / f"{safe}.studio.json"
    if not path.exists():
        return jsonify({"error": "not found"}), 404
    return jsonify(json.loads(path.read_text()))


@bp.get("/<section>/<dash_id>/download")
@require("viewer")
def download_one(section, dash_id):
    """Stream a dashboard spec as a .studio.json file download (Content-
    Disposition: attachment), so the app's Download button saves the exact,
    portable spec — the same artifact the Designer and MCP server consume."""
    safe = re.sub(r"[^a-z0-9-]", "", dash_id.lower())
    path = DASH_DIR / section / f"{safe}.studio.json"
    if not path.exists():
        return jsonify({"error": "not found"}), 404
    return Response(path.read_text(), mimetype="application/json",
                    headers={"Content-Disposition":
                             f'attachment; filename="{safe}.studio.json"'})


@bp.get("/<section>/<dash_id>/data")
@require("viewer")
def get_data(section, dash_id):
    """Resolve a dashboard's panels to actual values from the catalog snapshot.

    Returns {demo, scope, panels:{panel_id: {...}}}. Optional ?source= narrows
    the board to a single connected data source. Read-only.
    """
    safe = re.sub(r"[^a-z0-9-]", "", dash_id.lower())
    path = DASH_DIR / section / f"{safe}.studio.json"
    if not path.exists():
        return jsonify({"error": "not found"}), 404
    from ..panel_data import resolve_dashboard
    spec = json.loads(path.read_text())
    return jsonify(resolve_dashboard(spec, source=request.args.get("source")))


@bp.post("/resolve")
@require("viewer")
def resolve_inline():
    """Resolve an in-memory spec (e.g. the chat preview) to live values.

    Honour an optional top-level "source" to scope to one data source.
    """
    spec = request.get_json(force=True) or {}
    from ..panel_data import resolve_dashboard
    return jsonify(resolve_dashboard(spec, source=spec.get("source")))


@bp.get("/sources")
@require("viewer")
def list_sources():
    """Connected data-source names, for the per-dashboard scope selector."""
    from ..panel_data import source_names
    return jsonify({"sources": source_names()})


@bp.post("/drill")
@require("viewer")
def drill():
    """Return the underlying assets behind a panel (or a clicked segment/row).

    Body: {query, label?, source?}. Read-only; demo synthesises from the snapshot,
    live would issue a facet-filtered /search.
    """
    body = request.get_json(force=True) or {}
    if not body.get("query"):
        return jsonify({"error": "query required"}), 400
    from ..panel_data import drill_assets
    return jsonify(drill_assets(None, body["query"], body.get("label"), body.get("source")))


@bp.post("")
@require("steward")
def save():
    spec = request.get_json(force=True) or {}
    errors = _validate(spec, QUERY_CATALOG)
    if errors:
        audit(g.principal, "save_dashboard", status="rejected")
        return jsonify({"saved": False, "errors": errors}), 400
    category = spec.get("category", "overview")
    slug = re.sub(r"[^a-z0-9]+", "-", spec.get("title", "untitled").lower()).strip("-")
    dest = DASH_DIR / category
    dest.mkdir(parents=True, exist_ok=True)
    (dest / f"{slug}.studio.json").write_text(json.dumps(spec, indent=2))
    audit(g.principal, "save_dashboard", target=f"{category}/{slug}")
    return jsonify({"saved": True, "path": f"{category}/{slug}.studio.json"})
