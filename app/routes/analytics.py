"""Read endpoints that feed the dashboards. All require at least 'viewer'."""
from flask import Blueprint, jsonify, request

from ..catalog import catalog_snapshot
from ..pdc_client import client
from ..recommend import recommend
from ._auth import require

bp = Blueprint("analytics", __name__, url_prefix="/api")


@bp.post("/facets")
@require("viewer")
def facets():
    body = request.get_json(force=True) or {}
    return jsonify(client.facets(body.get("term", "*"), body.get("facets")))


@bp.post("/search")
@require("viewer")
def search():
    body = request.get_json(force=True) or {}
    return jsonify(client.search(body.get("term", "*"), body.get("facets"),
                                 body.get("page", 1), body.get("perPage", 30)))


@bp.get("/trust-distribution")
@require("viewer")
def trust():
    return jsonify(client.trust_distribution(request.args.get("term", "*")))


@bp.get("/snapshot")
@require("viewer")
def snapshot():
    """Catalog state — works offline in demo mode."""
    return jsonify(catalog_snapshot())


@bp.get("/recommend")
@require("viewer")
def recommend_route():
    scope = request.args.get("scope") or None
    # section (a.k.a. category) makes the suggestions Analytics-section-aware
    section = request.args.get("section") or request.args.get("category") or None
    return jsonify(recommend(catalog_snapshot(), scope, section))
