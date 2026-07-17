"""POST /generate — NL -> validated dashboard spec. Requires 'steward'."""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from ..catalog import QUERY_CATALOG
from ..generator import generate
from ..security import Principal, audit
from ._auth import json_body, require

router = APIRouter(prefix="/api", tags=["generate"])


@router.post("/generate")
async def generate_dashboard(request: Request,
                             principal: Principal = Depends(require("steward"))):
    body = await json_body(request)
    prompt = body.get("prompt", "").strip()
    if not prompt:
        return JSONResponse({"error": "prompt is required"}, status_code=400)
    catalog = body.get("catalog") or QUERY_CATALOG
    try:
        result = generate(prompt, catalog)
        audit(principal, "generate_dashboard", target=prompt[:80],
              valid=result.get("valid"))
        return result
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"error": str(exc)}, status_code=502)
