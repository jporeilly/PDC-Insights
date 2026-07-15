"""POST /generate — NL -> validated dashboard spec. Requires 'steward'."""
from flask import Blueprint, g, jsonify, request

from ..catalog import QUERY_CATALOG
from ..generator import generate
from ..security import audit
from ._auth import require

bp = Blueprint("generate", __name__, url_prefix="/api")


@bp.post("/generate")
@require("steward")
def generate_dashboard():
    body = request.get_json(force=True) or {}
    prompt = body.get("prompt", "").strip()
    if not prompt:
        return jsonify({"error": "prompt is required"}), 400
    catalog = body.get("catalog") or QUERY_CATALOG
    try:
        result = generate(prompt, catalog)
        audit(g.principal, "generate_dashboard", target=prompt[:80],
              valid=result.get("valid"))
        return jsonify(result)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)}), 502
